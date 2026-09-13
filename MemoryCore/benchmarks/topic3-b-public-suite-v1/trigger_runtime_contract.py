"""Verify Trigger Bench adapter enabled, disabled, and forced-failure paths."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from amb_failed_approach_runner import MODEL, REASONING, parse_usage, run_bounded
from h6_adapter import write_json
from trigger_codex_runner import AGENTS_TEXT, toml


PROMPT = "What package manager do I usually use?"
SEED = {"memories": [{"name": "pkg-manager", "content": "User uses pnpm as their package manager."}]}


def bridge_call(tsx: Path, bridge: Path, operation: str, store: Path, payload=None) -> dict:
    run = subprocess.run(
        [str(tsx), str(bridge), operation, str(store)],
        input=json.dumps(payload or {}), text=True, capture_output=True, timeout=30,
    )
    if run.returncode != 0:
        raise RuntimeError(run.stderr)
    return json.loads(run.stdout)


def codex_call(run_dir: Path, bench: Path, tsx: Path, mode: str, timeout: int) -> dict:
    run_dir.mkdir(parents=True)
    workspace, store = run_dir / "workspace", run_dir / "store"
    workspace.mkdir()
    bridge = bench / "trigger_memory_bridge.ts"
    bridge_call(tsx, bridge, "seed", store, SEED)
    trace_path, answer_path = run_dir / "trace.jsonl", run_dir / "answer.txt"
    command = [
        "codex", "exec", "--model", MODEL,
        "-c", f'model_reasoning_effort="{REASONING}"',
        "-c", "suppress_unstable_features_warning=true",
        "--sandbox", "workspace-write", "-C", str(workspace),
        "--skip-git-repo-check", "--ephemeral", "--ignore-rules",
        "--json", "-o", str(answer_path), "-",
    ]
    if mode != "disabled":
        (workspace / "AGENTS.md").write_text(AGENTS_TEXT)
        mcp_args = [
            str(bench / "trigger_memory_mcp.py"),
            "--store", str(store), "--trace", str(trace_path),
            "--bridge", str(bridge), "--tsx", str(tsx),
            "--policy", "trigger_policy_v3",
        ]
        if mode == "forced_failure":
            mcp_args.append("--force-failure")
        command[2:2] = ["--enable", "mcp_2026_07_28"]
        command[6:6] = [
            "-c", f"mcp_servers.memorycore.command={toml(sys.executable)}",
            "-c", f"mcp_servers.memorycore.args={toml(mcp_args)}",
            "-c", "mcp_servers.memorycore.startup_timeout_sec=20",
            "-c", 'mcp_servers.memorycore.default_tools_approval_mode="approve"',
            "-c", 'mcp_servers.memorycore.enabled_tools=["memory_search","memory_write"]',
        ]
    started = time.perf_counter()
    returncode, stdout, stderr, timed_out = run_bounded(command, PROMPT, workspace, timeout)
    latency_ms = (time.perf_counter() - started) * 1000
    (run_dir / "events.jsonl").write_text(stdout)
    (run_dir / "stderr.txt").write_text(stderr)
    answer = answer_path.read_text() if answer_path.exists() else ""
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    records = bridge_call(tsx, bridge, "dump", store)["records"]
    expected = {
        "enabled": returncode == 0 and not timed_out and len(trace) >= 1
                   and all(row["ok"] for row in trace) and "pnpm" in answer.lower()
                   and len(records) == 1,
        "disabled": returncode == 0 and not timed_out and not trace and len(records) == 1,
        "forced_failure": returncode == 0 and not timed_out and len(trace) >= 1
                          and all(not row["ok"] for row in trace) and len(records) == 1,
    }[mode]
    return {
        "mode": mode,
        "pass": expected,
        "returnCode": returncode,
        "timedOut": timed_out,
        "toolCalls": len(trace),
        "successfulToolCalls": sum(row["ok"] for row in trace),
        "finalRecordCount": len(records),
        "storeUnchanged": len(records) == 1 and records[0]["content"].endswith(
            "User uses pnpm as their package manager."),
        "answerSha256": hashlib.sha256(answer.encode()).hexdigest(),
        "usage": parse_usage(stdout),
        "latencyMs": latency_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output exists: {output}")
    output.mkdir(parents=True)
    bench = Path(__file__).resolve().parent
    tsx = bench.parents[1] / "node_modules" / ".bin" / "tsx"
    modes = [codex_call(output / mode, bench, tsx, mode, args.timeout_seconds)
             for mode in ("enabled", "disabled", "forced_failure")]
    summary = {
        "schema": 1,
        "protocol": "trigger-memorycore-runtime-contract-v1",
        "status": "passed" if all(item["pass"] for item in modes) else "failed",
        "model": MODEL,
        "reasoningEffort": REASONING,
        "modes": modes,
        "scope": "Three isolated Codex turns. Disabled omits MCP registration; forced failure returns a tool error. "
                 "All stores are local fixtures and remain unchanged outside the enabled read path.",
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
