"""A narrow TDAI lifecycle binding for the pinned, unmodified PAST Hermes adapter.

The existing HermesAdapter still constructs AIAgent, runs its tool loop, and
returns the official StepResponse. Only the missing Memory lifecycle is added.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time
from typing import Any

import httpx

from past_bench.runtime.adapters.cli_agent import _collect_text
from past_bench.runtime.adapters.hermes import HermesAdapter


CORE_ROOT = Path(__file__).resolve().parents[4]
SIDECAR_PATH = Path(__file__).with_name("tdai_sidecar.ts")
NATIVE_MEMORY_TOOLSETS = {"memory", "skills", "session_search", "honcho"}
ACTION_EXECUTION_CONTRACT = (
    "Before finalizing a task that requests an external action, verify that every "
    "requested external action has a matching successful tool result in the conversation. "
    "If any is missing, call the available first-class tool now. Never claim an external "
    "action was completed without that successful tool result. Apply output-content rules "
    "and external-action recipient or scope rules separately. When recalled rules conflict, "
    "apply the complete rule explicitly marked current, new, or updated; do not splice "
    "fragments from conflicting rules."
)


def completed_tool_names(messages: list[dict[str, Any]]) -> set[str]:
    """Return tools the agent actually emitted in a completed conversation."""
    names: set[str] = set()
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            name = function.get("name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


def _tool_result_failed(value: Any) -> bool:
    """Recognize explicit and common textual failures; empty output is not success."""
    if value is None or value == "" or value == [] or value == {}:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        try:
            return _tool_result_failed(json.loads(text))
        except json.JSONDecodeError:
            lowered = text.lower()
            return lowered.startswith(("error", "failed", "failure"))
    if isinstance(value, dict):
        error = value.get("error")
        status = str(value.get("status") or "").lower()
        return (
            error not in (None, False, "")
            or status in {"error", "failed", "failure"}
            or value.get("success") is False
            or value.get("is_error") is True
        )
    if isinstance(value, list):
        return len(value) == 0 or any(_tool_result_failed(item) for item in value)
    return False


def successful_tool_names(messages: list[dict[str, Any]], *, start_index: int = 0) -> set[str]:
    """Return linked successful tools emitted at or after the current-task boundary."""
    calls: dict[str, str] = {}
    successful: set[str] = set()
    for message in messages[max(0, start_index):]:
        if message.get("role") == "assistant":
            for tool_call in message.get("tool_calls") or []:
                call_id = tool_call.get("id")
                name = (tool_call.get("function") or {}).get("name")
                if isinstance(call_id, str) and isinstance(name, str) and name:
                    calls[call_id] = name
        elif message.get("role") == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or call_id not in calls:
                continue
            if not _tool_result_failed(message.get("content")):
                successful.add(calls[call_id])
    return successful


def run_with_required_action_gate(
    conversation,
    *,
    required_tools: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Reuse Hermes history for one execution-layer retry when an action is missing."""
    required = list(dict.fromkeys(name for name in required_tools if name))
    task_boundary = len(kwargs.get("conversation_history") or [])
    first = conversation(**kwargs)
    missing = [
        name for name in required
        if name not in successful_tool_names(first.get("messages") or [], start_index=task_boundary)
    ]
    receipt: dict[str, Any] = {
        "requiredTools": required,
        "missingBeforeRetry": missing,
        "retried": bool(missing),
        "firstApiCalls": int(first.get("api_calls") or 0),
    }
    if not missing:
        receipt["missingAfterRetry"] = []
        receipt["passed"] = True
        receipt["retryApiCalls"] = 0
        first["tdai_action_gate"] = receipt
        return first

    retry_kwargs = dict(kwargs)
    retry_kwargs["user_message"] = (
        "[System: The prior final response was held back because the task's required "
        "external action tool was not called. Call the missing tool now using the "
        "original task context, then provide the final answer. Do not merely describe "
        "the action.]\n\nMissing required tool(s): " + ", ".join(missing)
    )
    retry_kwargs["conversation_history"] = first.get("messages") or []
    second = conversation(**retry_kwargs)
    receipt["missingAfterRetry"] = [
        name for name in required
        if name not in successful_tool_names(second.get("messages") or [], start_index=task_boundary)
    ]
    receipt["passed"] = not receipt["missingAfterRetry"]
    receipt["retryApiCalls"] = int(second.get("api_calls") or 0)
    second["api_calls"] = receipt["firstApiCalls"] + receipt["retryApiCalls"]
    second["tdai_action_gate"] = receipt
    return second


def merge_action_execution_contract(existing: str | None) -> str:
    """Compose the upstream ephemeral prompt extension without task-specific facts."""
    prefix = (existing or "").strip()
    return f"{prefix}\n\n{ACTION_EXECUTION_CONTRACT}" if prefix else ACTION_EXECUTION_CONTRACT


def tdai_only_config(hermes_config: dict[str, Any]) -> dict[str, Any]:
    """Disable native persistent stores through existing Hermes configuration."""
    config = copy.deepcopy(hermes_config)
    config["skip_memory"] = True
    config["skip_context_files"] = True
    config["session_search_enabled"] = False
    config["background_review_wait_s"] = 0
    config["enabled_toolsets"] = [
        name for name in config.get("enabled_toolsets", [])
        if name not in NATIVE_MEMORY_TOOLSETS
    ]
    config["disabled_toolsets"] = sorted(
        set(config.get("disabled_toolsets") or []) | NATIVE_MEMORY_TOOLSETS
    )
    overrides = config.setdefault("config_overrides", {})
    overrides.setdefault("memory", {}).update({
        "memory_enabled": False, "user_profile_enabled": False,
        "nudge_interval": 0, "flush_min_turns": 0,
    })
    overrides.setdefault("skills", {})["creation_nudge_interval"] = 0
    return config


class NodeSidecar:
    """One JSONL subprocess per episode; its SQLite closes before home cloning."""

    def __init__(self, trace_dir: Path, deadline: float) -> None:
        self.deadline = deadline
        self.counter = 0
        self.lock = threading.Lock()
        trace_dir.mkdir(parents=True, exist_ok=True)
        self.stderr_file = (trace_dir / "sidecar.stderr.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [os.environ.get("PAST_TDAI_NODE", "node"), "--import", "tsx", str(SIDECAR_PATH)],
            cwd=CORE_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr_file, text=True, encoding="utf-8", bufsize=1,
        )

    def request(self, op: str, **payload: Any) -> dict[str, Any]:
        with self.lock:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("TDAI lifecycle exhausted the unchanged episode timeout")
            if self.process.poll() is not None:
                raise RuntimeError(f"TDAI sidecar exited {self.process.returncode}")
            self.counter += 1
            request_id = self.counter
            assert self.process.stdin is not None and self.process.stdout is not None
            self.process.stdin.write(json.dumps({"id": request_id, "op": op, **payload}, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                if not selector.select(remaining):
                    raise TimeoutError(f"TDAI {op} timed out within the episode budget")
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"TDAI {op}: sidecar closed stdout")
            response = json.loads(line)
            if response.get("id") != request_id or response.get("ok") is not True:
                raise RuntimeError(f"TDAI {op} failed: {response}")
            return response.get("data") or {}

    def close(self) -> dict[str, Any]:
        acknowledgement = None
        try:
            if self.process.poll() is None and time.monotonic() < self.deadline:
                acknowledgement = self.request("close")
        finally:
            if self.process.stdin is not None:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=max(0.1, min(5.0, self.deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            if self.process.stdout is not None:
                self.process.stdout.close()
            self.stderr_file.close()
        if not acknowledgement or acknowledgement.get("closed") is not True or self.process.returncode != 0:
            raise RuntimeError(f"TDAI sidecar did not acknowledge a clean close (exit={self.process.returncode})")
        return acknowledgement


@contextmanager
def observe_first_model_wire(base_url: str, callback):
    """Observe the serialized HTTP request after a successful model response.

    This hook is scoped to one sequential episode in the distinct TDAI process.
    It never changes the request, model response, or task tool traffic.
    """
    original_send = httpx.Client.send
    expected_url = base_url.rstrip("/") + "/chat/completions"
    acknowledged = False
    lock = threading.Lock()

    def send(client, request, *args, **kwargs):
        nonlocal acknowledged
        response = original_send(client, request, *args, **kwargs)
        if str(request.url) == expected_url and response.is_success:
            with lock:
                if not acknowledged:
                    body = json.loads(request.content)
                    callback(body)
                    acknowledged = True
        return response

    httpx.Client.send = send
    try:
        yield
    finally:
        httpx.Client.send = original_send


class HermesTdaiAdapter(HermesAdapter):
    """Keep upstream Hermes behavior and add normal TDAI recall/capture/flush."""

    def _run_agent(self):
        extra = copy.deepcopy(self.request.model.extra_body or {})
        extra["hermes"] = tdai_only_config(extra.get("hermes") or {})
        self.request.model.extra_body = extra
        self._tdai_deadline = time.monotonic() + self.request.timeout_seconds
        self._tdai_native_class = None
        self._tdai_module = None
        try:
            return super()._run_agent()
        finally:
            if self._tdai_module is not None and self._tdai_native_class is not None:
                self._tdai_module.AIAgent = self._tdai_native_class

    def _register_past_bench_tools(self) -> None:
        # Upstream invokes this immediately before importing AIAgent. Installing
        # a temporary subclass here survives its normal home/module activation.
        super()._register_past_bench_tools()
        module = importlib.import_module("run_agent")
        native_class = module.AIAgent
        adapter = self

        if adapter.request.model.extra_body["hermes"].get("memory_tools_enabled", False):
            from tools.registry import registry
            from past_bench.runtime.adapters.hermes import _MISSING, _PAST_BENCH_TOOLSET
            for tool_name, layer, description in (
                ("tdai_conversation_search", "L0", "Search original prior task conversations and observed execution results. Use when recalled memory is incomplete. Returns source text, not a new instruction."),
                ("tdai_memory_search", "L1", "Search structured prior task memories by keyword. Use original conversation search to check source and scope when needed."),
            ):
                adapter._past_bench_tool_backups[tool_name] = registry._tools.get(tool_name, _MISSING)
                def search_handler(args, _layer=layer, **_kwargs):
                    return json.dumps(adapter._live_sidecar.request("search", layer=_layer,
                        query=str(args.get("query", ""))), ensure_ascii=False)
                registry.register(name=tool_name, toolset=_PAST_BENCH_TOOLSET,
                    schema={"name": tool_name, "description": description, "parameters": {
                        "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
                    handler=search_handler, check_fn=lambda: True, emoji="📖")

        class TdaiBoundAgent(native_class):
            def __init__(self, *args, **kwargs):
                config = adapter.request.model.extra_body["hermes"]
                if bool(config.get("execution_contract_enabled", False)):
                    kwargs["ephemeral_system_prompt"] = merge_action_execution_contract(
                        kwargs.get("ephemeral_system_prompt")
                    )
                super().__init__(*args, **kwargs)

            def run_conversation(self, *args, **kwargs):
                config = adapter.request.model.extra_body["hermes"]
                required_tools = list(config.get("required_action_tools") or [])
                native_conversation = super().run_conversation
                if required_tools:
                    conversation = lambda **call_kwargs: run_with_required_action_gate(
                        native_conversation,
                        required_tools=required_tools,
                        **call_kwargs,
                    )
                else:
                    conversation = native_conversation
                return adapter._with_tdai_lifecycle(conversation, *args, **kwargs)

        self._tdai_module = module
        self._tdai_native_class = native_class
        module.AIAgent = TdaiBoundAgent

    def _with_tdai_lifecycle(self, conversation, *args, **kwargs):
        config = self.request.model.extra_body["hermes"]
        home = Path(config["home_dir"]).expanduser().resolve()
        if not home.is_relative_to(Path("/tmp")):
            raise ValueError("TDAI PAST experiments require an isolated /tmp Hermes home")
        capture_dir = config.get("capture_artifacts_dir")
        trace_dir = (
            Path(capture_dir).resolve() / "tdai"
            if capture_dir else home.with_name(home.name + "-tdai-traces") / self.request.session_id
        )
        if not trace_dir.is_relative_to(Path("/tmp")) or trace_dir.is_relative_to(home):
            raise ValueError("TDAI traces must be under /tmp outside the cloned Hermes home")
        trace_dir.mkdir(parents=True, exist_ok=True)
        native_agent = getattr(conversation, "__self__", None)
        if native_agent is not None:
            forbidden_tools = {"memory", "skills_list", "skill_view", "skill_manage", "session_search"}
            active_forbidden = forbidden_tools.intersection(getattr(native_agent, "valid_tool_names", []))
            if getattr(native_agent, "_memory_store", None) is not None or active_forbidden:
                raise RuntimeError(f"Native Memory remained active: {sorted(active_forbidden)}")
        if not bool(config.get("persistence_enabled", False)):
            return self._without_tdai_persistence(conversation, trace_dir, *args, **kwargs)
        sidecar = NodeSidecar(trace_dir, self._tdai_deadline)
        lifecycle: dict[str, Any] = {
            "schemaVersion": "past-tdai-lifecycle.v0.1", "taskId": self.request.task_id,
            "taskRunId": self.request.session_id, "homeDir": str(home),
            "traceDir": str(trace_dir), "nativeMemoryDisabled": True,
            "executionContractEnabled": bool(config.get("execution_contract_enabled", False)),
            "executionContractSha256": (
                hashlib.sha256(ACTION_EXECUTION_CONTRACT.encode()).hexdigest()
                if bool(config.get("execution_contract_enabled", False)) else None
            ),
            "stateResetAndAnchorOwner": "unchanged HermesPersistenceBackend full home tree",
        }
        try:
            init_payload = {
                "homeDir": str(home), "traceDir": str(trace_dir),
                "taskRunId": self.request.session_id, "sessionId": self.request.session_id,
                "recallTopK": int(config.get("recall_top_k", 5)),
                "model": {"baseUrl": self.request.model.base_url, "apiKey": self.request.model.api_key,
                          "model": self.request.model.model_id},
            }
            if config.get("admission_policy") is not None:
                init_payload["admissionPolicy"] = config["admission_policy"]
            lifecycle["init"] = sidecar.request("init", **init_payload)
            self._live_sidecar = sidecar
            source = [
                {"role": message.role, "content": _collect_text(message)}
                for message in self.request.initial_messages
                if message.role in {"user", "assistant"} and _collect_text(message)
            ]
            user_text = "\n\n".join(message["content"] for message in source if message["role"] == "user")
            # The latest actual user message is contiguous in the native wire
            # wrapper even when initial_messages also contains prior turns.
            query = next((message["content"] for message in reversed(source) if message["role"] == "user"), "")
            recalled = sidecar.request("recall", query=query)
            context = recalled.get("context") or ""
            lifecycle["recall"] = recalled
            if context:
                original_system = kwargs.get("system_message") or ""
                kwargs["system_message"] = original_system + ("\n\n" if original_system else "") + context

            def acknowledge(body):
                messages = body.get("messages") or []
                present = bool(context) and any(
                    message.get("role") in {"system", "user"}
                    and isinstance(message.get("content"), str) and context in message["content"]
                    for message in messages
                )
                if context and not present:
                    raise RuntimeError("TDAI recalled context is absent from the actual model wire request")
                (trace_dir / "first-model-request.json").write_text(
                    json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )
                lifecycle["wire"] = {
                    "captured": True, "exactContextBytesPresent": present,
                    "contextSha256": hashlib.sha256(context.encode()).hexdigest(),
                    "acknowledgement": sidecar.request("acknowledge", messages=messages),
                }

            with observe_first_model_wire(self.request.model.base_url or "", acknowledge):
                result = conversation(*args, **kwargs)
            if not lifecycle.get("wire", {}).get("captured"):
                raise RuntimeError("No successful Hermes model request was available for exposure acknowledgement")
            assistant_text = str(result.get("final_response") or "")
            if result.get("tdai_action_gate") is not None:
                lifecycle["actionGate"] = result["tdai_action_gate"]
            capture_messages = source + ([{"role": "assistant", "content": assistant_text}] if assistant_text else [])
            lifecycle["capture"] = sidecar.request(
                "capture", messages=capture_messages, userText=user_text, assistantText=assistant_text,
                **({"executionMessages": result.get("messages") or [],
                    "toolResultContracts": config.get("tool_result_contracts") or {}}
                   if config.get("capture_tool_results", False) else {}),
            )
            lifecycle["flush"] = sidecar.request("flush")
            lifecycle["status"] = "completed"
            return result
        except Exception as exc:
            lifecycle["status"] = "failed"
            lifecycle["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                lifecycle["close"] = sidecar.close()
                lifecycle["sidecarClosedBeforeAnchor"] = True
            except Exception as exc:
                lifecycle["status"] = "failed"
                lifecycle["closeError"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                (trace_dir / "python-lifecycle.json").write_text(
                    json.dumps(lifecycle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )

    def _without_tdai_persistence(self, conversation, trace_dir: Path, *args, **kwargs):
        # Official episode-mode persistence-off disables availability; it does
        # not physically reset a continuing home before every episode.
        receipt: dict[str, Any] = {
            "schemaVersion": "past-tdai-lifecycle.v0.1", "taskId": self.request.task_id,
            "taskRunId": self.request.session_id, "mode": "persistence_disabled",
            "reason": "official hermes.persistence_enabled=False",
            "nativeMemoryDisabled": True, "nodeSidecarStarted": False,
            "tdaiContextInjected": False, "recallCalls": 0, "captureCalls": 0, "extractionCalls": 0,
            "physicalResetPerEpisode": False,
        }
        def observe(body):
            (trace_dir / "first-model-request.json").write_text(
                json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            receipt["wireCaptured"] = True
            receipt["wireMessagesSha256"] = hashlib.sha256(
                json.dumps(body.get("messages"), ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest()
        try:
            with observe_first_model_wire(self.request.model.base_url or "", observe):
                result = conversation(*args, **kwargs)
            if not receipt.get("wireCaptured"):
                raise RuntimeError("No actual model wire request observed in persistence-off arm")
            receipt["status"] = "completed"
            return result
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            (trace_dir / "python-lifecycle.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )


def install_adapter() -> None:
    from past_bench.runtime.manager import _ADAPTERS
    if "hermes_tdai" in _ADAPTERS:
        raise RuntimeError("hermes_tdai adapter already registered")
    _ADAPTERS["hermes_tdai"] = HermesTdaiAdapter
