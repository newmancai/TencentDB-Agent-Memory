"""Shared installed-CLI adapter for the product host and controlled evaluations."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


def _stop_process_group(process: subprocess.Popen) -> None:
    """Stop the command and every descendant created in its isolated session."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _read_log_output(
    log_directory: Path, stdout: str | None, stderr: str | None
) -> tuple[str, str]:
    output_path = log_directory / "stdout.jsonl"
    error_path = log_directory / "stderr.txt"
    if output_path.exists():
        stdout = output_path.read_text(errors="replace")
    if error_path.exists():
        stderr = error_path.read_text(errors="replace") or stderr or ""
        error_path.write_text(stderr)
    return stdout or "", stderr or ""


def run_command(command: list[str], workspace: Path, timeout: int, **kwargs) -> dict:
    started = time.perf_counter()
    log_directory = kwargs.pop("log_directory", None)
    handles = []
    stdout = stderr = ""
    try:
        if log_directory is not None:
            log_directory = Path(log_directory)
            log_directory.mkdir(parents=True, exist_ok=True)
            for name in ("stdout.jsonl", "stderr.txt"):
                handles.append((log_directory / name).open("w"))
        input_text = kwargs.pop("input", None)
        process = subprocess.Popen(
            command,
            cwd=workspace,
            text=True,
            stdin=subprocess.PIPE,
            stdout=handles[0] if handles else subprocess.PIPE,
            stderr=handles[1] if handles else subprocess.PIPE,
            start_new_session=True,
            **kwargs,
        )
        try:
            stdout, stderr = process.communicate(input_text, timeout=timeout)
            status, returncode = "completed", process.returncode
        except subprocess.TimeoutExpired:
            # Stop this run's descendants before its checker reads the workspace.
            _stop_process_group(process)
            stdout, stderr = process.communicate()
            status, returncode = "timeout", None
        except KeyboardInterrupt:
            # User cancellation must stop the same descendants as a deadline.
            # They run in a new session and do not receive the host's Ctrl-C.
            _stop_process_group(process)
            stdout, stderr = process.communicate()
            status, returncode = "cancelled", None
        except BaseException:
            _stop_process_group(process)
            process.communicate()
            raise
    except OSError as error:
        status, returncode = "launch_error", None
        stdout, stderr = "", str(error)
    finally:
        for handle in handles:
            handle.close()
    if log_directory is not None:
        stdout, stderr = _read_log_output(log_directory, stdout, stderr)
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return {
        "status": status,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "wall_seconds": time.perf_counter() - started,
    }


def command_for(arm: str, workspace: Path, prompt: str, manifest: dict) -> list[str]:
    backend = arm.split("_", 1)[0]
    if backend == "codex":
        command = [
            "codex",
            "exec",
            "--sandbox",
            "workspace-write",
            "-C",
            str(workspace),
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "-c",
            "project_doc_max_bytes=0",
            "-c",
            "memories.use_memories=false",
            "-c",
            "memories.generate_memories=false",
            "-c",
            "features.memories=false",
            "-c",
            f'model_reasoning_effort="{manifest.get("codex_effort", "medium")}"',
        ]
        if manifest.get("codex_model"):
            command += ["--model", manifest["codex_model"]]
        command += ["-"]
        return command
    command = [
        "claude",
        "--print",
        "--no-session-persistence",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--permission-mode",
        "acceptEdits",
        "--tools",
        "Read,Edit,Write,Bash",
        "--allowedTools",
        "Read,Edit,Write,Bash",
        "--output-format",
        "stream-json",
        "--verbose",
        "--effort",
        manifest.get("claude_effort", "medium"),
    ]
    if manifest.get("claude_model"):
        command += ["--model", manifest["claude_model"]]
    command += [prompt]
    return command


def events_from(stdout: str) -> list[dict]:
    try:
        value = json.loads(stdout)
        if isinstance(value, dict):
            return [value]
    except json.JSONDecodeError:
        pass
    result = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                result.append(event)
        except json.JSONDecodeError:
            continue
    return result


def terminal_error(stdout: str) -> bool:
    return any(
        e.get("type") in {"turn.failed", "error"}
        or (e.get("type") == "result" and e.get("is_error", False))
        for e in events_from(stdout)
    )


def parse_usage(backend: str, stdout: str) -> dict | None:
    if backend == "codex":
        usage = None
        for event in events_from(stdout):
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
        return usage
    result = None
    for event in events_from(stdout):
        if isinstance(event, dict) and (event.get("type") == "result" or "usage" in event):
            result = event
    if not result:
        return None
    usage = result.get("usage")
    if isinstance(usage, dict) and "total_cost_usd" in result:
        usage = {**usage, "reported_cost_usd": result["total_cost_usd"]}
    return usage if isinstance(usage, dict) else None
