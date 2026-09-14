import argparse
import fcntl
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from project_agent import (
    Host,
    command_for,
    extraction_prompt,
    final_text,
    raw_user_context,
    retain_project_instructions,
)


class ProjectAgentTest(unittest.TestCase):
    def test_prompt_payloads_use_compact_lossless_json(self):
        source = {"id": "u1", "order": 1, "role": "user", "text": "保留 0 值。"}
        raw = raw_user_context([source])
        self.assertEqual(json.loads(raw), source)
        self.assertNotIn('": "', raw)
        prompt = extraction_prompt({"observations": []}, source)
        self.assertIn('{"prior":', prompt)
        self.assertIn(',"NEW_USER_OBSERVATION":', prompt)

    def test_normal_product_use_retains_project_guidance(self):
        original = command_for("codex_memory", Path("/tmp"), "task", {})
        normal = retain_project_instructions(original)
        self.assertNotIn("project_doc_max_bytes=0", normal)
        self.assertNotIn("--ignore-user-config", normal)
        self.assertIn("--sandbox", normal)
        self.assertIn("workspace-write", normal)
        self.assertIn("project_doc_max_bytes=0", original)

    def host(self, root, mode="scoped"):
        args = argparse.Namespace(
            state=root / "state",
            workspace=root,
            owner="u",
            project="p",
            backend="codex",
            model="example",
            effort="medium",
            timeout=2,
            mode=mode,
            paths=["src/api"],
            action="edit",
            max_bytes=12000,
            check=None,
        )
        return Host(args)

    def test_store_uses_precompiled_bundle_when_wrapper_supplies_it(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            completed = Mock(stdout='{"ok":true,"result":{"revision":0}}', stderr="")
            with (
                patch.dict(
                    "project_agent.os.environ",
                    {
                        "MEMORY_AGENT_NODE": "/runtime/node",
                        "MEMORY_AGENT_STORE_BUNDLE": "/package/dist/project-agent-store.mjs",
                    },
                ),
                patch("project_agent.subprocess.run", return_value=completed) as execute,
            ):
                result = self.host(root).store("snapshot")

            self.assertEqual(result, {"revision": 0})
            self.assertEqual(
                execute.call_args.args[0],
                ["/runtime/node", "/package/dist/project-agent-store.mjs"],
            )

    def test_prepare_run_bridge_retains_context_when_task_ingest_fails(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = self.host(root).store(
                "prepareRun",
                options={"paths": ["src/api"], "action": "edit", "maxBytes": 12_000},
                observation={"id": "invalid-empty-task", "role": "user", "text": ""},
            )

            self.assertEqual(prepared["snapshot"]["revision"], 0)
            self.assertEqual(prepared["selection"]["status"], "selected")
            self.assertIsNone(prepared["task"]["ingest"])
            self.assertIn("invalid observation", prepared["task"]["error"])
            self.assertEqual(list(prepared["task"]["observation"]), ["id", "order", "role", "text"])

    def test_off_and_store_failure_still_run_ordinary_agent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("off", "scoped"):
                host = self.host(root, mode)
                host.store = Mock(side_effect=RuntimeError("unavailable"))
                host.call = Mock(return_value="edited")
                result = host.run("Implement the function.", root)
                self.assertEqual(result["final"], "edited")
                self.assertIsNone(result["error"])
                if mode == "off":
                    host.store.assert_not_called()
                    self.assertEqual(result["context_mode"], "off")
                else:
                    self.assertEqual(result["context_mode"], "off_fallback")
                    self.assertIn("unavailable", result["memory_error"])

    def test_budget_overflow_retains_exact_raw_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            observation = {
                "id": "u1",
                "order": 1,
                "role": "user",
                "text": "Keep the zero override.",
            }
            snapshot = {
                "observations": [observation],
                "constraints": [{"sourceId": "u1", "quote": observation["text"]}],
                "retractions": [],
                "revision": 1,
            }
            host.store = Mock(
                return_value={
                    "snapshot": snapshot,
                    "selection": {"status": "selected", "omittedForBudget": 1},
                }
            )
            result = host.context("scoped", ["src/api"], "edit", 1)
            self.assertEqual(result["mode"], "raw_fallback")
            self.assertEqual(json.loads(result["text"]), observation)

    def test_failed_extraction_persists_raw_observation_only(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            host.store = Mock(
                side_effect=[{"observations": [], "constraints": []}, {"accepted": []}]
            )
            host.call = Mock(side_effect=RuntimeError("backend 502"))
            result = host.remember("Keep existing worker behavior.", root, compile_constraints=True)
            self.assertEqual(result["extraction_error"], "backend 502")
            self.assertEqual(host.store.call_args.kwargs["proposals"], [])
            self.assertEqual(
                host.store.call_args.kwargs["observation"]["text"], "Keep existing worker behavior."
            )

    def test_remember_defaults_to_lossless_raw_storage_without_model_calls(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            host.store = Mock(side_effect=[{"observations": []}, {"revision": 1, "accepted": []}])
            host.call = Mock(side_effect=AssertionError("must not invoke a model"))
            result = host.remember("Keep the exact instruction.", root)
            host.call.assert_not_called()
            self.assertEqual(result["observation"]["text"], "Keep the exact instruction.")
            self.assertEqual(result["calls"], [])
            source = result["observation"]
            host.store = Mock(
                return_value={
                    "snapshot": {
                        "observations": [source],
                        "constraints": [],
                        "revision": 1,
                    },
                    "selection": None,
                }
            )
            context = host.context("scoped", ["."], "edit", 12000)
            self.assertEqual(context["mode"], "raw")
            self.assertEqual(json.loads(context["text"]), source)

    def test_compiled_state_is_reused_without_run_path_compiler_calls(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            quote = "Use a 10 second timeout."
            host.store = Mock(
                side_effect=[
                    {"observations": [], "constraints": []},
                    {"revision": 1, "accepted": [{"id": "c1"}]},
                ]
            )
            host.call = Mock(
                return_value=json.dumps(
                    {
                        "proposals": [
                            {
                                "key": "timeout",
                                "quote": quote,
                                "scope": {"paths": ["src/api"], "actions": ["edit"]},
                            }
                        ]
                    }
                )
            )
            remembered = host.remember(quote, root, compile_constraints=True)
            self.assertEqual(host.call.call_count, 1)

            source = remembered["observation"]
            snapshot = {
                "observations": [source],
                "constraints": [{"sourceId": source["id"], "quote": quote}],
                "retractions": [],
                "revision": 1,
            }
            selected = {
                "status": "selected",
                "omittedForBudget": 0,
                "text": json.dumps(
                    {
                        "id": "c1",
                        "key": "timeout",
                        "scope": {"paths": ["src/api"], "actions": ["edit"]},
                        "sourceId": source["id"],
                        "order": 1,
                        "userQuote": quote,
                    }
                ),
            }
            loaded = {"snapshot": snapshot, "selection": selected}
            host.store = Mock(side_effect=[loaded, loaded])
            host.call.reset_mock()
            first = host.context("scoped", ["src/api"], "edit", 12_000)
            second = host.context("scoped", ["src/api"], "edit", 12_000)
            host.call.assert_not_called()
            self.assertEqual(first["mode"], "scoped")
            self.assertEqual(first["text"], second["text"])
            self.assertEqual(first["revision"], second["revision"])

    def test_partial_compilation_does_not_drop_other_user_requirements(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            source = {
                "id": "u1",
                "order": 1,
                "role": "user",
                "text": "Use zero retries. Keep cancellation support.",
            }
            snapshot = {
                "observations": [source],
                "constraints": [{"sourceId": "u1", "quote": "Use zero retries."}],
                "retractions": [],
                "revision": 1,
            }
            host.store = Mock(
                return_value={
                    "snapshot": snapshot,
                    "selection": {"status": "selected", "omittedForBudget": 0, "text": "{}"},
                }
            )
            result = host.context("scoped", ["src/api"], "edit", 12000)
            self.assertEqual(json.loads(result["text"])["uncompiled_user_observations"], [source])

    def test_extraction_does_not_turn_tool_output_into_user_memory(self):
        stdout = "\n".join(
            json.dumps(e)
            for e in [
                {
                    "type": "item.completed",
                    "item": {"type": "command_execution", "aggregated_output": "bad JSON"},
                },
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": '{"proposals":[]}'},
                },
            ]
        )
        self.assertEqual(json.loads(final_text("codex", stdout)), {"proposals": []})

    def test_full_store_retains_loaded_context_and_marks_unsaved_task(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            snapshot = {
                "observations": [
                    {
                        "id": "policy",
                        "order": 128,
                        "role": "user",
                        "text": "Explicit zero must be preserved.",
                    }
                ],
                "constraints": [],
                "revision": 128,
            }
            host.store = Mock(
                return_value={
                    "snapshot": snapshot,
                    "selection": None,
                    "task": {
                        "observation": {
                            "id": "task",
                            "order": 129,
                            "role": "user",
                            "text": "Fix the retry default.",
                        },
                        "ingest": None,
                        "error": "Error: project observation capacity",
                    },
                }
            )
            host.call = Mock(return_value="edited")
            result = host.run("Fix the retry default.", root)
            self.assertEqual(result["context_mode"], "raw")
            self.assertIn("Explicit zero must be preserved.", host.call.call_args.args[0])
            self.assertFalse(result["task_persisted"])
            self.assertFalse(result["receipt_persisted"])
            self.assertIn("capacity", result["memory_error"])
            self.assertEqual(
                json.loads((root / "task.json").read_text())["text"], "Fix the retry default."
            )

    def test_run_uses_one_pre_model_bridge_call_and_one_receipt_write(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            source = {
                "id": "policy",
                "order": 1,
                "role": "user",
                "text": "Keep explicit zero values.",
            }
            snapshot = {
                "observations": [source],
                "constraints": [{"sourceId": source["id"], "quote": source["text"]}],
                "retractions": [],
                "revision": 1,
            }
            selected = {
                "status": "selected",
                "omittedForBudget": 0,
                "text": json.dumps(
                    {
                        "id": "c1",
                        "key": "zero",
                        "scope": {"paths": ["src/api"], "actions": ["edit"]},
                        "sourceId": source["id"],
                        "order": 1,
                        "userQuote": source["text"],
                    }
                ),
            }
            host.store = Mock(
                side_effect=[
                    {
                        "snapshot": snapshot,
                        "selection": selected,
                        "task": {
                            "observation": {
                                "id": "task",
                                "order": 2,
                                "role": "user",
                                "text": "Fix the retry default.",
                            },
                            "ingest": {"revision": 2, "accepted": []},
                            "error": None,
                        },
                    },
                    {"revision": 3, "accepted": []},
                ]
            )
            host.call = Mock(return_value="edited")

            result = host.run("Fix the retry default.", root)

            self.assertEqual(
                [call.args[0] for call in host.store.call_args_list],
                ["prepareRun", "ingest"],
            )
            self.assertTrue(result["task_persisted"])
            self.assertTrue(result["receipt_persisted"])
            self.assertEqual(result["context_revision"], 1)
            pending = host.store.call_args_list[0].kwargs["observation"]
            self.assertNotIn("order", pending)
            self.assertEqual(pending["text"], "Fix the retry default.")
            self.assertEqual(host.store.call_args_list[1].kwargs["observation"]["order"], 3)

    def test_raw_run_uses_one_shot_without_scoped_options(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root, "raw")
            source = {"id": "u1", "order": 1, "role": "user", "text": "Keep zero values."}
            host.store = Mock(
                side_effect=[
                    {
                        "snapshot": {
                            "observations": [source],
                            "constraints": [],
                            "retractions": [],
                            "revision": 1,
                        },
                        "selection": None,
                        "task": {
                            "observation": {
                                "id": "task",
                                "order": 2,
                                "role": "user",
                                "text": "Edit code.",
                            },
                            "ingest": {"revision": 2, "accepted": []},
                            "error": None,
                        },
                    },
                    {"revision": 3, "accepted": []},
                ]
            )
            host.call = Mock(return_value="edited")

            result = host.run("Edit code.", root)

            self.assertEqual(result["context_mode"], "raw")
            self.assertIn("Keep zero values.", host.call.call_args.args[0])
            self.assertNotIn("options", host.store.call_args_list[0].kwargs)
            self.assertEqual(
                [call.args[0] for call in host.store.call_args_list], ["prepareRun", "ingest"]
            )

    def test_invalid_checker_fails_before_memory_or_model(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            host.store = Mock()
            host.call = Mock()
            for invalid in ("{", "[]", '[""]', '["python", 3]', '["python", "\\u0000"]'):
                host.args.check = invalid
                with self.assertRaises(ValueError):
                    host.run("Edit code.", root)
            host.store.assert_not_called()
            host.call.assert_not_called()

    def test_invalid_context_scope_is_rejected_without_raw_fallback_or_model_call(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root)
            host.store = Mock()
            host.call = Mock()
            invalid = [
                ("scoped", ["../escape"], "edit", 12_000),
                ("scoped", ["/absolute"], "edit", 12_000),
                ("scoped", ["src//api"], "edit", 12_000),
                ("scoped", ["src\\api"], "edit", 12_000),
                ("scoped", [], "edit", 12_000),
                ("scoped", ["src/api"], "deploy", 12_000),
                ("scoped", ["src/api"], "edit", 0),
                ("scoped", ["src/api"], "edit", 64_001),
                ("unknown", ["src/api"], "edit", 12_000),
            ]
            for mode, paths, action, budget in invalid:
                with self.subTest(mode=mode, paths=paths, action=action, budget=budget):
                    host.args.mode = mode
                    host.args.paths = paths
                    host.args.action = action
                    host.args.max_bytes = budget
                    with self.assertRaises(ValueError):
                        host.run("Edit code.", root)
            host.store.assert_not_called()
            host.call.assert_not_called()
            self.assertFalse((root / "task.json").exists())

            command = [
                sys.executable,
                str(Path(__file__).with_name("project_agent.py")),
                "--state",
                str(root / "cli-state"),
                "--workspace",
                str(root),
                "--project",
                "p",
                "context",
                "--paths",
                "../escape",
            ]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("normalized repository-relative", json.loads(completed.stdout)["error"])
            self.assertNotIn("Traceback", completed.stderr)

    def test_concurrent_cli_returns_structured_busy_error(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            command = [
                sys.executable,
                str(Path(__file__).with_name("project_agent.py")),
                "--state",
                str(state),
                "--workspace",
                str(root),
                "--project",
                "p",
                "history",
            ]
            with (state / "writer.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("state is busy", json.loads(completed.stdout)["error"])
            self.assertNotIn("Traceback", completed.stderr)

    def test_checker_recovery_uses_current_files_without_model_or_memory_calls(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root, "off")
            original = host.state / "runs" / "original"
            original.mkdir(parents=True)
            host.args.check = json.dumps(
                [
                    sys.executable,
                    "-c",
                    'from pathlib import Path; assert Path("answer").read_text()=="fixed"',
                ]
            )
            host.call = Mock(return_value="coding done")
            host.store = Mock(side_effect=AssertionError("no memory in off/recheck"))
            # A checker failure must leave a completed coding checkpoint.
            first = host.run("Implement answer.", original)
            self.assertFalse(first["checker_pass"])
            (root / "answer").write_text("fixed")
            host.args.check = None
            evidence = host.state / "runs" / "retry"
            evidence.mkdir()
            result = host.check_run("original", evidence)
            self.assertTrue(result["checker_pass"])
            self.assertEqual(result["calls"], [])
            host.call.assert_called_once()
            host.store.assert_not_called()
            self.assertEqual(json.loads((original / "checker.json").read_text())["returncode"], 1)
            self.assertEqual(json.loads((evidence / "checker.json").read_text())["returncode"], 0)

    def test_recovery_refuses_unknown_completion_and_different_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root, "off")
            original = host.state / "runs" / "original"
            original.mkdir(parents=True)
            host.call = Mock(side_effect=RuntimeError("interrupted model"))
            host.run("Edit code.", original)
            with patch("project_agent.run_command") as execute:
                with self.assertRaisesRegex(ValueError, "completion is unconfirmed"):
                    host.check_run("original", root)
                task = json.loads((original / "task.json").read_text())
                task["workspace"] = "/different"
                (original / "task.json").write_text(json.dumps(task))
                with self.assertRaisesRegex(ValueError, "must match"):
                    host.check_run("original", root)
                with self.assertRaises(ValueError):
                    host.check_run("../original", root)
                execute.assert_not_called()

    def test_explicit_incomplete_recovery_checks_terminal_partial_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root, "off")
            original = host.state / "runs" / "original"
            (original / "agent").mkdir(parents=True)
            host.args.check = json.dumps(
                [
                    sys.executable,
                    "-c",
                    'from pathlib import Path; assert Path("answer").read_text()=="partial"',
                ]
            )
            (original / "task.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "workspace": str(host.workspace),
                        "owner": host.args.owner,
                        "project": host.args.project,
                        "check": json.loads(host.args.check),
                    }
                )
            )
            (original / "agent" / "receipt.json").write_text(json.dumps({"status": "timeout"}))
            (root / "answer").write_text("partial")
            host.args.allow_incomplete = True
            evidence = host.state / "runs" / "retry"
            evidence.mkdir()
            result = host.check_run("original", evidence)
            self.assertTrue(result["checker_pass"])
            self.assertFalse(result["completion_confirmed"])
            self.assertEqual(result["source_agent_status"], "timeout")
            self.assertIn("not automatically accepted", result["acceptance"])

            # A fabricated/nonterminal status cannot use the opt-in path.
            (original / "agent" / "receipt.json").write_text(json.dumps({"status": "completed"}))
            with self.assertRaisesRegex(ValueError, "terminal timeout"):
                host.check_run("original", root)

    def test_coding_checkpoint_survives_host_interruption_before_check(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host = self.host(root, "off")
            original = host.state / "runs" / "original"
            original.mkdir(parents=True)
            host.args.check = json.dumps([sys.executable, "-c", 'print("checked")'])
            host.call = Mock(return_value="complete")
            with patch.object(host, "check", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    host.run("Edit code.", original)
            self.assertTrue((original / "agent-result.json").exists())
            evidence = host.state / "runs" / "retry"
            evidence.mkdir()
            self.assertTrue(host.check_run("original", evidence)["checker_pass"])
            host.call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
