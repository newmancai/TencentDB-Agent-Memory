"""No-model tests of lifecycle and isolation; these are not B1 outcome evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, "/tmp/past-bench-b1-prep-20260905/src")
from past_bench.models.content import TextBlock
from past_bench.models.message import Message
from past_bench.runtime.protocol import RuntimeModelConfig, StartSessionRequest
from past_bench.runner.self_evolve import HermesPersistenceBackend
from hermes_tdai_adapter import (
    ACTION_EXECUTION_CONTRACT,
    HermesTdaiAdapter,
    completed_tool_names,
    merge_action_execution_contract,
    observe_first_model_wire,
    run_with_required_action_gate,
    successful_tool_names,
    tdai_only_config,
)


class GlueTests(unittest.TestCase):
    def test_completed_tool_names_reads_actual_assistant_calls(self):
        messages = [
            {"role": "assistant", "tool_calls": [
                {"function": {"name": "notes_list"}},
                {"function": {"name": "notes_share"}},
            ]},
            {"role": "tool", "content": "ok"},
        ]
        self.assertEqual(completed_tool_names(messages), {"notes_list", "notes_share"})

    def test_successful_tool_names_requires_a_linked_non_error_result(self):
        messages = [
            {"role": "assistant", "tool_calls": [
                {"id": "ok", "function": {"name": "notes_share"}},
                {"id": "bad", "function": {"name": "notes_delete"}},
                {"id": "missing", "function": {"name": "notes_update"}},
            ]},
            {"role": "tool", "tool_call_id": "ok", "content": json.dumps({"status": "shared"})},
            {"role": "tool", "tool_call_id": "bad", "content": json.dumps({"error": "forbidden"})},
        ]
        self.assertEqual(successful_tool_names(messages), {"notes_share"})

    def test_required_action_gate_reuses_history_for_one_retry(self):
        calls = []

        def conversation(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {
                    "messages": [{"role": "assistant", "tool_calls": [
                        {"id": "list", "function": {"name": "notes_list"}},
                    ]}],
                    "api_calls": 2,
                }
            return {
                "messages": list(kwargs["conversation_history"]) + [
                    {"role": "assistant", "tool_calls": [
                        {"id": "share", "function": {"name": "notes_share"}},
                    ]},
                    {"role": "tool", "tool_call_id": "share", "content": json.dumps({"status": "shared"})},
                ],
                "api_calls": 2,
                "final_response": "done",
            }

        result = run_with_required_action_gate(
            conversation,
            required_tools=["notes_share"],
            user_message="original task",
            conversation_history=[],
            task_id="same-task",
        )
        self.assertEqual(len(calls), 2)
        self.assertIn("notes_share", calls[1]["user_message"])
        self.assertEqual(result["api_calls"], 4)
        self.assertEqual(result["tdai_action_gate"]["missingAfterRetry"], [])
        self.assertTrue(result["tdai_action_gate"]["passed"])

    def test_required_action_gate_does_not_accept_an_error_result(self):
        def conversation(**kwargs):
            return {
                "messages": [{"role": "assistant", "tool_calls": [
                    {"id": "share", "function": {"name": "notes_share"}},
                ]}, {"role": "tool", "tool_call_id": "share", "content": json.dumps({"error": "forbidden"})}],
                "api_calls": 1,
            }
        result = run_with_required_action_gate(conversation, required_tools=["notes_share"])
        self.assertEqual(result["tdai_action_gate"]["missingAfterRetry"], ["notes_share"])
        self.assertFalse(result["tdai_action_gate"]["passed"])

    def test_successful_tool_names_rejects_empty_text_and_explicit_failure_flags(self):
        messages = []
        values = ["", "Error: forbidden", {"success": False}, {"is_error": True}, {}]
        for index, value in enumerate(values):
            call_id = f"c{index}"
            messages.extend([
                {"role": "assistant", "tool_calls": [{"id": call_id, "function": {"name": f"tool_{index}"}}]},
                {"role": "tool", "tool_call_id": call_id, "content": json.dumps(value) if not isinstance(value, str) else value},
            ])
        self.assertEqual(successful_tool_names(messages), set())

    def test_required_action_gate_ignores_a_previous_task_receipt(self):
        old_history = [
            {"role": "assistant", "tool_calls": [{"id": "old", "function": {"name": "notes_share"}}]},
            {"role": "tool", "tool_call_id": "old", "content": json.dumps({"status": "shared"})},
        ]
        calls = []

        def conversation(**kwargs):
            calls.append(kwargs)
            return {"messages": list(kwargs.get("conversation_history") or []), "api_calls": 1}

        result = run_with_required_action_gate(
            conversation, required_tools=["notes_share"], conversation_history=old_history,
            user_message="share again for this task",
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["tdai_action_gate"]["missingBeforeRetry"], ["notes_share"])
        self.assertFalse(result["tdai_action_gate"]["passed"])

    def test_action_execution_contract_composes_with_upstream_ephemeral_prompt(self):
        self.assertEqual(
            merge_action_execution_contract(None),
            ACTION_EXECUTION_CONTRACT,
        )
        self.assertEqual(
            merge_action_execution_contract("upstream prompt"),
            "upstream prompt\n\n" + ACTION_EXECUTION_CONTRACT,
        )
        self.assertNotIn("SM04", ACTION_EXECUTION_CONTRACT)
        self.assertNotIn("notes_share", ACTION_EXECUTION_CONTRACT)

    def test_native_memory_is_disabled_without_mutating_upstream_config(self):
        upstream = {
            "persistence_enabled": True, "enabled_toolsets": ["memory", "skills", "session_search", "past_bench_runtime"],
            "config_overrides": {"memory": {"memory_enabled": True, "user_profile_enabled": True}},
        }
        effective = tdai_only_config(upstream)
        self.assertTrue(upstream["config_overrides"]["memory"]["memory_enabled"])
        self.assertTrue(effective["persistence_enabled"])
        self.assertEqual(effective["enabled_toolsets"], ["past_bench_runtime"])
        self.assertTrue(effective["skip_memory"])
        self.assertFalse(effective["config_overrides"]["memory"]["memory_enabled"])
        self.assertFalse(effective["config_overrides"]["memory"]["user_profile_enabled"])
        self.assertEqual(effective["config_overrides"]["skills"]["creation_nudge_interval"], 0)

    def test_only_first_successful_actual_model_wire_request_is_acknowledged(self):
        observed = []
        responses = iter([500, 200, 200])
        def transport(request):
            return httpx.Response(next(responses), json={"ok": True})
        original = httpx.Client.send
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            with observe_first_model_wire("http://model.invalid/v1", observed.append):
                for index in range(3):
                    client.post("http://model.invalid/v1/chat/completions", json={"messages": [{"role": "user", "content": str(index)}]})
        self.assertIs(httpx.Client.send, original)
        self.assertEqual(observed, [{"messages": [{"role": "user", "content": "1"}]}])

    def test_clean_source_capture_and_flush_finish_before_sidecar_close(self):
        with tempfile.TemporaryDirectory(prefix="past-tdai-glue-") as directory:
            home = Path(directory) / "home"
            adapter = object.__new__(HermesTdaiAdapter)
            adapter.request = StartSessionRequest(
                session_id="source-episode", agent_name="hermes-tdai", task_id="unchanged-task", task_name="source",
                max_turns=20, timeout_seconds=300,
                initial_messages=[Message(role="user", content=[TextBlock(text="Please use concise tables next time.")])],
                model=RuntimeModelConfig(model_id="same-model", base_url="http://model.invalid/v1", api_key="local",
                    extra_body={"hermes": {"persistence_enabled": True, "home_dir": str(home), "capture_artifacts_dir": str(Path(directory) / "artifacts")}}),
            )
            adapter._tdai_deadline = time.monotonic() + 300
            operations = []
            class Sidecar:
                def __init__(self, *args): pass
                def request(self, op, **data):
                    operations.append((op, data))
                    return {"context": "Previously recalled unrelated fact."} if op == "recall" else {"ok": True}
                def close(self): operations.append(("close", {}))
            def conversation(**kwargs):
                self.assertEqual(kwargs["system_message"], "Previously recalled unrelated fact.")
                with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
                    client.post("http://model.invalid/v1/chat/completions", json={"messages": [
                        {"role": "system", "content": kwargs["system_message"]},
                        {"role": "user", "content": "unchanged native task wrapper"},
                    ]})
                return {"final_response": "Acknowledged the requested format."}
            with patch("hermes_tdai_adapter.NodeSidecar", Sidecar):
                adapter._with_tdai_lifecycle(conversation, user_message="unchanged native task wrapper")
            self.assertEqual([op for op, _ in operations], ["init", "recall", "acknowledge", "capture", "flush", "close"])
            captured = operations[3][1]
            self.assertEqual(captured["messages"], [
                {"role": "user", "content": "Please use concise tables next time."},
                {"role": "assistant", "content": "Acknowledged the requested format."},
            ])
            self.assertNotIn("Previously recalled", json.dumps(captured))
            self.assertNotIn("native task wrapper", json.dumps(captured))

    def test_missing_wire_acknowledgement_aborts_capture_and_closes_sidecar(self):
        with tempfile.TemporaryDirectory(prefix="past-tdai-no-wire-") as directory:
            adapter = object.__new__(HermesTdaiAdapter)
            adapter.request = StartSessionRequest(
                session_id="episode", agent_name="hermes-tdai", task_id="task", task_name="task",
                max_turns=20, timeout_seconds=300,
                model=RuntimeModelConfig(model_id="model", base_url="http://model.invalid/v1",
                    extra_body={"hermes": {"persistence_enabled": True, "home_dir": str(Path(directory) / "home")}}),
            )
            adapter._tdai_deadline = time.monotonic() + 300
            operations = []
            class Sidecar:
                def __init__(self, *args): pass
                def request(self, op, **data): operations.append(op); return {}
                def close(self): operations.append("close")
            with patch("hermes_tdai_adapter.NodeSidecar", Sidecar):
                with self.assertRaisesRegex(RuntimeError, "No successful Hermes model request"):
                    adapter._with_tdai_lifecycle(lambda **kwargs: {"final_response": "unobserved"})
            self.assertEqual(operations, ["init", "recall", "close"])

    def test_persistence_off_never_starts_node_or_recalls_captures_extracts(self):
        with tempfile.TemporaryDirectory(prefix="past-tdai-off-") as directory:
            adapter = object.__new__(HermesTdaiAdapter)
            artifacts = Path(directory) / "artifacts"
            adapter.request = StartSessionRequest(
                session_id="off-episode", agent_name="hermes-tdai", task_id="task", task_name="task",
                max_turns=20, timeout_seconds=300,
                model=RuntimeModelConfig(model_id="model", base_url="http://model.invalid/v1",
                    extra_body={"hermes": {"persistence_enabled": False, "home_dir": str(Path(directory) / "home"),
                                           "capture_artifacts_dir": str(artifacts)}}),
            )
            adapter._tdai_deadline = time.monotonic() + 300
            def conversation(**kwargs):
                self.assertNotIn("system_message", kwargs)
                with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
                    client.post("http://model.invalid/v1/chat/completions", json={"messages": [
                        {"role": "user", "content": "same native task prompt"},
                    ]})
                return {"final_response": "same native response"}
            with patch("hermes_tdai_adapter.NodeSidecar") as node:
                result = adapter._with_tdai_lifecycle(conversation, user_message="same native task prompt")
                node.assert_not_called()
            self.assertEqual(result["final_response"], "same native response")
            receipt = json.loads((artifacts / "tdai/python-lifecycle.json").read_text())
            self.assertEqual(receipt["mode"], "persistence_disabled")
            self.assertTrue(receipt["wireCaptured"])
            self.assertFalse(receipt["tdaiContextInjected"])
            self.assertEqual((receipt["recallCalls"], receipt["captureCalls"], receipt["extractionCalls"]), (0, 0, 0))

    def test_official_home_anchor_and_reset_include_closed_tdai_sqlite(self):
        with tempfile.TemporaryDirectory(prefix="past-tdai-anchor-") as directory:
            root = Path(directory); home = root / "home"; state = home / ".tdai"
            state.mkdir(parents=True)
            with sqlite3.connect(state / "memory.sqlite") as connection:
                connection.execute("CREATE TABLE records (content TEXT)")
                connection.execute("INSERT INTO records VALUES (?)", ("captured source fact",))
            backend = HermesPersistenceBackend()
            backend.clone_state(home, root / "anchor")
            backend.reset_state(home)
            self.assertFalse((home / ".tdai").exists())
            backend.clone_state(root / "anchor", home)
            with sqlite3.connect(home / ".tdai/memory.sqlite") as connection:
                self.assertEqual(connection.execute("SELECT content FROM records").fetchone()[0], "captured source fact")


if __name__ == "__main__":
    unittest.main()
