"""Shared installed-CLI adapter for the product host and controlled evaluations."""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time


def run_command(command: list[str], workspace: Path, timeout: int, **kwargs) -> dict:
    started = time.perf_counter()
    log_directory = kwargs.pop('log_directory', None)
    handles = []
    stdout = stderr = ''
    try:
        if log_directory is not None:
            log_directory = Path(log_directory)
            log_directory.mkdir(parents=True, exist_ok=True)
            for name in ('stdout.jsonl', 'stderr.txt'):
                handles.append((log_directory / name).open('w'))
        input_text = kwargs.pop("input", None)
        process = subprocess.Popen(command, cwd=workspace, text=True, stdin=subprocess.PIPE,
                                   stdout=handles[0] if handles else subprocess.PIPE,
                                   stderr=handles[1] if handles else subprocess.PIPE,
                                   start_new_session=True, **kwargs)
        try:
            stdout, stderr = process.communicate(input_text, timeout=timeout)
            status, returncode = "completed", process.returncode
        except subprocess.TimeoutExpired:
            # Stop this run's descendants before its checker reads the workspace.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            status, returncode = "timeout", None
        except KeyboardInterrupt:
            # User cancellation must stop the same descendants as a deadline.
            # They run in a new session and do not receive the host's Ctrl-C.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            status, returncode = 'cancelled', None
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    except OSError as error:
        status, returncode = "launch_error", None
        stdout, stderr = "", str(error)
    finally:
        for handle in handles:
            handle.close()
    if log_directory is not None:
        output_path, error_path = log_directory / 'stdout.jsonl', log_directory / 'stderr.txt'
        if output_path.exists(): stdout = output_path.read_text(errors='replace')
        if error_path.exists():
            stderr = error_path.read_text(errors='replace') or stderr or ''
            error_path.write_text(stderr)
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return {"status": status, "returncode": returncode, "stdout": stdout, "stderr": stderr,
            "wall_seconds": time.perf_counter() - started}


def isolated_filesystem_command(command: list[str], workspace: Path, hidden_root: Path) -> list[str]:
    """Hide benchmark sources and sibling arms while leaving one clone writable."""
    workspace = workspace.resolve()
    hidden_root = hidden_root.resolve()
    try:
        workspace.relative_to(hidden_root)
    except ValueError as exc:
        raise ValueError('isolated workspace must be below the hidden root') from exc
    bubblewrap = shutil.which('bwrap')
    if not bubblewrap:
        raise ValueError('bwrap is required for benchmark filesystem isolation')

    result = [bubblewrap, '--die-with-parent', '--unshare-pid', '--unshare-ipc',
              '--unshare-uts', '--share-net', '--ro-bind', '/', '/', '--dev', '/dev',
              '--proc', '/proc', '--tmpfs', '/tmp', '--dir', '/tmp/codex-runtime',
              '--setenv', 'XDG_RUNTIME_DIR', '/tmp/codex-runtime',
              '--tmpfs', str(hidden_root)]
    ancestors = []
    current = workspace.parent
    while current != hidden_root:
        ancestors.append(current)
        current = current.parent
    for path in reversed(ancestors):
        result += ['--dir', str(path)]
    result += ['--bind', str(workspace), str(workspace)]

    # Codex needs its credentials but not user sessions, skills, logs, or thread
    # databases. The inner Codex sandbox continues to protect these bootstrap
    # files from model-issued shell commands.
    codex_home = Path.home() / '.codex'
    result += ['--tmpfs', str(codex_home)]
    for name in ('auth.json',):
        source = codex_home / name
        if source.is_file():
            result += ['--ro-bind', str(source), str(source)]
    return result + ['--chdir', str(workspace), '--'] + command


def command_for(arm: str, workspace: Path, prompt: str, manifest: dict) -> list[str]:
    backend = arm.split("_", 1)[0]
    if backend == "codex":
        command = ["codex", "exec", "--sandbox", "workspace-write", "-C", str(workspace),
                   "--ephemeral", "--ignore-user-config", "--ignore-rules", "--json",
                   "-c", 'web_search="disabled"',
                   "-c", "project_doc_max_bytes=0", "-c", "memories.use_memories=false",
                   "-c", "memories.generate_memories=false", "-c", "features.memories=false",
                   "-c", f'model_reasoning_effort="{manifest.get("codex_effort", "medium")}"']
        if manifest.get("codex_model"):
            command += ["--model", manifest["codex_model"]]
        command += ["-"]
        return command
    command = ["claude", "--print", "--no-session-persistence",
               "--setting-sources", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--disable-slash-commands",
               "--permission-mode", "acceptEdits", "--tools", "Read,Edit,Write,Bash",
               "--allowedTools", "Read,Edit,Write,Bash",
               "--output-format", "stream-json", "--verbose",
               "--effort", manifest.get("claude_effort", "medium")]
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
    return any(e.get("type") in {"turn.failed", "error"}
               or (e.get("type") == "result" and e.get("is_error", False))
               for e in events_from(stdout))


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
