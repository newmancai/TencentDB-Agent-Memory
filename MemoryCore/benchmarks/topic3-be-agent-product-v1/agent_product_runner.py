"""Run clean and MemoryCore-enhanced coding-agent arms in marked worktrees."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import subprocess
import time


ARMS = ("codex_clean", "codex_memory", "claude_clean", "claude_memory")


def read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != 1 or not isinstance(manifest.get("tasks"), list):
        raise ValueError("manifest must have schema=1 and tasks")
    for task in manifest["tasks"]:
        required = ("id", "kind", "workspaces", "prompt", "checker")
        if (any(key not in task for key in required) or not isinstance(task["checker"], list)
                or task["kind"] not in {"necessary_update", "same_topic_control"}):
            raise ValueError(f"invalid task: {task!r}")
        arms = task.get("arms", ARMS)
        if set(arms) - set(ARMS) or any(arm not in task["workspaces"] for arm in arms):
            raise ValueError(f"invalid workspaces: {task['id']}")
        resolved = []
        for arm in arms:
            workspace = Path(task["workspaces"][arm]).resolve()
            if not (workspace / ".agent-benchmark-worktree").is_file():
                raise ValueError(f"unmarked benchmark workspace: {workspace}")
            if any((workspace / name).exists() for name in ("CLAUDE.md", "CLAUDE.local.md")):
                raise ValueError(f"benchmark workspace contains Claude instructions: {workspace}")
            resolved.append(workspace)
        if len(set(resolved)) != len(resolved):
            raise ValueError(f"arms must not share a workspace: {task['id']}")
    return manifest


def prompt_for(task: dict, memory: bool) -> str:
    if not memory:
        return task["prompt"]
    context_path = Path(task.get("memory_context", ""))
    if not context_path.is_file():
        raise ValueError(f"memory arm lacks context for {task['id']}")
    context = context_path.read_text()
    return ("Use the following bounded project memory as evidence, respecting its scope and timestamps. "
            "It may nominate facts for verification but does not override repository evidence.\n\n"
            f"<memorycore_context>\n{context}\n</memorycore_context>\n\n{task['prompt']}")


def command_for(arm: str, workspace: Path, prompt: str, manifest: dict) -> list[str]:
    backend = arm.split("_", 1)[0]
    if backend == "codex":
        command = ["codex", "exec", "--sandbox", "workspace-write", "-C", str(workspace),
                   "--ephemeral", "--ignore-user-config", "--ignore-rules", "--json"]
        if manifest.get("codex_model"):
            command += ["--model", manifest["codex_model"]]
        command += ["-"]
        return command
    command = ["claude", "--print", "--no-session-persistence",
               "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write,Bash",
               "--output-format", "json", "--effort", manifest.get("claude_effort", "medium")]
    if manifest.get("claude_model"):
        command += ["--model", manifest["claude_model"]]
    command += [prompt]
    return command


def parse_usage(backend: str, stdout: str) -> dict | None:
    if backend == "codex":
        usage = None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
        return usage
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    usage = result.get("usage")
    if isinstance(usage, dict) and "total_cost_usd" in result:
        usage = {**usage, "reported_cost_usd": result["total_cost_usd"]}
    return usage if isinstance(usage, dict) else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = int(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def summarize(receipts: list[dict]) -> dict:
    arms = {}
    for arm in ARMS:
        rows = [row for row in receipts if row["arm"] == arm and row["status"] != "dry_run"]
        wall = [row["agent_wall_seconds"] for row in rows]
        numeric_usage = Counter()
        for row in rows:
            for key, value in (row.get("usage") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_usage[key] += value
        arms[arm] = {"tasks": len(rows), "checker_pass": sum(row["checker_pass"] for row in rows),
                     "severe_regressions": sum(row["severe_regression"] for row in rows),
                     "usage": dict(numeric_usage) if numeric_usage else None,
                     "agent_wall_seconds": {"sum": sum(wall), "p50": quantile(wall, .5), "p95": quantile(wall, .95)}}
    paired = {}
    by_key = {(row["task_id"], row["arm"]): row for row in receipts if row["status"] != "dry_run"}
    for backend in ("codex", "claude"):
        counts = Counter()
        for task_id in {row["task_id"] for row in receipts}:
            clean = by_key.get((task_id, f"{backend}_clean"))
            memory = by_key.get((task_id, f"{backend}_memory"))
            if not clean or not memory:
                continue
            outcome = "win" if memory["checker_pass"] and not clean["checker_pass"] else "loss" if clean["checker_pass"] and not memory["checker_pass"] else "tie"
            counts[outcome] += 1
            counts[f"{memory['kind']}_{outcome}"] += 1
        paired[backend] = dict(counts)
    complete = all(arms[arm]["tasks"] > 0 for arm in ARMS)
    passed = complete
    for backend in ("codex", "claude"):
        counts = paired[backend]
        passed = passed and counts.get("win", 0) > counts.get("loss", 0)
        passed = passed and counts.get("necessary_update_win", 0) >= 1
        passed = passed and counts.get("same_topic_control_win", 0) >= counts.get("same_topic_control_loss", 0)
        passed = passed and arms[f"{backend}_memory"]["severe_regressions"] <= arms[f"{backend}_clean"]["severe_regressions"]
    return {"protocol": "topic3-be-agent-product-v1", "arms": arms, "paired_memory_vs_clean": paired,
            "pass": bool(passed), "scope": "Isolated coding-task product comparison; cross-backend totals are secondary."}


def run(manifest: dict, output: Path, dry_run: bool) -> None:
    output.mkdir(parents=True, exist_ok=False)
    receipts = []
    timeout = int(manifest.get("timeout_seconds", 900))
    for task in manifest["tasks"]:
        for arm in task.get("arms", ARMS):
            if arm not in ARMS:
                raise ValueError(f"unknown arm: {arm}")
            memory = arm.endswith("_memory")
            workspace = Path(task["workspaces"][arm]).resolve()
            prompt = prompt_for(task, memory)
            command = command_for(arm, workspace, prompt, manifest)
            receipt = {"task_id": task["id"], "kind": task["kind"], "arm": arm, "backend": arm.split("_", 1)[0],
                       "memory_injected": memory, "workspace": str(workspace)}
            if dry_run:
                receipt.update({"status": "dry_run", "command": command[:-1] if arm.startswith("codex") else command[:-1]})
                receipts.append(receipt)
                continue
            started = time.perf_counter()
            try:
                environment = os.environ.copy()
                if arm.startswith("claude"):
                    environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
                agent = subprocess.run(command, input=prompt if arm.startswith("codex") else None,
                                       text=True, capture_output=True, timeout=timeout, cwd=workspace,
                                       env=environment)
                timed_out = False
            except subprocess.TimeoutExpired as error:
                agent = error
                timed_out = True
            agent_wall = time.perf_counter() - started
            stdout = agent.stdout or ""
            stderr = agent.stderr or ""
            stem = f"{task['id']}-{arm}"
            (output / f"{stem}.stdout").write_text(stdout)
            (output / f"{stem}.stderr").write_text(stderr)
            checker_started = time.perf_counter()
            checker = subprocess.run(task["checker"], text=True, capture_output=True,
                                     timeout=int(task.get("checker_timeout_seconds", 300)), cwd=workspace)
            checker_wall = time.perf_counter() - checker_started
            (output / f"{stem}.checker.stdout").write_text(checker.stdout)
            (output / f"{stem}.checker.stderr").write_text(checker.stderr)
            receipt.update({
                "status": "timeout" if timed_out else "completed",
                "agent_returncode": None if timed_out else agent.returncode,
                "checker_returncode": checker.returncode,
                "checker_pass": checker.returncode == 0,
                "severe_regression": checker.returncode in set(task.get("severe_regression_codes", [])),
                "usage": parse_usage(receipt["backend"], stdout),
                "agent_wall_seconds": agent_wall,
                "checker_wall_seconds": checker_wall,
            })
            receipts.append(receipt)
            (output / "receipts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in receipts))
    (output / "receipts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in receipts))
    if not dry_run:
        (output / "summary.json").write_text(json.dumps(summarize(receipts), indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(read_manifest(args.manifest), args.output, args.dry_run)


if __name__ == "__main__":
    main()
