"""Run clean and MemoryCore-enhanced coding-agent arms in marked worktrees."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time


ARMS = ("codex_clean", "codex_memory", "claude_clean", "claude_memory")
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def task_arms(task: dict, index: int) -> tuple[str, ...]:
    if "arms" in task:
        return tuple(task["arms"])
    offset = index % len(ARMS)
    return ARMS[offset:] + ARMS[:offset]


def git_output(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=workspace, text=True, capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed in {workspace}: {result.stderr.strip()}")
    return result.stdout.strip()


def workspace_state(workspace: Path, *, include_untracked: bool = False) -> dict:
    status_args = ["status", "--porcelain=v1"]
    if not include_untracked:
        status_args.append("--untracked-files=no")
    changes = [line for line in git_output(workspace, *status_args).splitlines()
               if line != "?? .agent-benchmark-worktree"]
    return {"base_commit": git_output(workspace, "rev-parse", "HEAD"), "changes": changes}


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def run_command(command: list[str], workspace: Path, timeout: int, **kwargs) -> dict:
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command, cwd=workspace, text=True, capture_output=True, timeout=timeout, **kwargs,
        )
        status, returncode = "completed", result.returncode
        stdout, stderr = result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired as error:
        status, returncode = "timeout", None
        stdout, stderr = error.stdout or "", error.stderr or ""
    except OSError as error:
        status, returncode = "launch_error", None
        stdout, stderr = "", str(error)
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return {"status": status, "returncode": returncode, "stdout": stdout, "stderr": stderr,
            "wall_seconds": time.perf_counter() - started}


def read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if (manifest.get("schema") != 1 or not isinstance(manifest.get("tasks"), list)
            or not manifest["tasks"]):
        raise ValueError("manifest must have schema=1 and non-empty tasks")
    timeout = manifest.get("timeout_seconds", 900)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    task_ids = set()
    workspace_paths = set()
    for index, task in enumerate(manifest["tasks"]):
        required = ("id", "kind", "workspaces", "prompt", "checker")
        if (not isinstance(task, dict) or any(key not in task for key in required)
                or not isinstance(task["id"], str) or not TASK_ID.fullmatch(task["id"])
                or task["id"] in task_ids or not isinstance(task["prompt"], str) or not task["prompt"].strip()
                or not isinstance(task["checker"], list) or not task["checker"]
                or any(not isinstance(arg, str) or not arg for arg in task["checker"])
                or not isinstance(task["workspaces"], dict)
                or not isinstance(task.get("checker_timeout_seconds", 300), int)
                or isinstance(task.get("checker_timeout_seconds", 300), bool)
                or task.get("checker_timeout_seconds", 300) < 1
                or task["kind"] not in {"necessary_update", "same_topic_control"}):
            raise ValueError(f"invalid task: {task!r}")
        task_ids.add(task["id"])
        arms = task_arms(task, index)
        if (not arms or len(set(arms)) != len(arms) or set(arms) - set(ARMS)
                or any(arm not in task["workspaces"]
                       or not isinstance(task["workspaces"][arm], str) for arm in arms)):
            raise ValueError(f"invalid workspaces: {task['id']}")
        resolved = []
        revisions = set()
        for arm in arms:
            workspace = Path(task["workspaces"][arm]).resolve()
            if not (workspace / ".agent-benchmark-worktree").is_file():
                raise ValueError(f"unmarked benchmark workspace: {workspace}")
            if any((workspace / name).exists() for name in ("CLAUDE.md", "CLAUDE.local.md")):
                raise ValueError(f"benchmark workspace contains Claude instructions: {workspace}")
            state = workspace_state(workspace, include_untracked=True)
            if state["changes"]:
                raise ValueError(f"benchmark workspace is not clean: {workspace}")
            resolved.append(workspace)
            revisions.add(state["base_commit"])
        if len(set(resolved)) != len(resolved):
            raise ValueError(f"arms must not share a workspace: {task['id']}")
        if len(revisions) != 1:
            raise ValueError(f"arms must start at one base commit: {task['id']}")
        if workspace_paths.intersection(resolved):
            raise ValueError(f"tasks must not reuse workspaces: {task['id']}")
        workspace_paths.update(resolved)
        if any(arm.endswith("_memory") for arm in arms):
            if not isinstance(task.get("memory_context"), str):
                raise ValueError(f"memory arm lacks context for {task['id']}")
            context_path = Path(task["memory_context"])
            if not context_path.is_file():
                raise ValueError(f"memory arm lacks context for {task['id']}")
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
        failures = sum(row["status"] != "completed" or row.get("agent_returncode") != 0
                       or row.get("checker_status") != "completed" for row in rows)
        arms[arm] = {"tasks": len(rows), "checker_pass": sum(row["checker_pass"] for row in rows),
                     "execution_failures": failures,
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
    complete = all(arms[arm]["tasks"] > 0 and arms[arm]["execution_failures"] == 0 for arm in ARMS)
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
    for index, task in enumerate(manifest["tasks"]):
        for arm in task_arms(task, index):
            if arm not in ARMS:
                raise ValueError(f"unknown arm: {arm}")
            memory = arm.endswith("_memory")
            workspace = Path(task["workspaces"][arm]).resolve()
            before = workspace_state(workspace, include_untracked=True)
            if before["changes"]:
                raise ValueError(f"benchmark workspace is not clean: {workspace}")
            prompt = prompt_for(task, memory)
            command = command_for(arm, workspace, prompt, manifest)
            receipt = {"task_id": task["id"], "kind": task["kind"], "arm": arm, "backend": arm.split("_", 1)[0],
                       "memory_injected": memory, "workspace": str(workspace),
                       "base_commit": before["base_commit"]}
            if dry_run:
                receipt.update({"status": "dry_run", "command": command[:-1]})
                receipts.append(receipt)
                continue
            environment = os.environ.copy()
            if arm.startswith("claude"):
                environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
            agent = run_command(command, workspace, timeout,
                                input=prompt if arm.startswith("codex") else None,
                                env=environment)
            stem = f"{task['id']}-{arm}"
            (output / f"{stem}.stdout").write_text(agent["stdout"])
            (output / f"{stem}.stderr").write_text(agent["stderr"])
            agent_changes = workspace_state(workspace, include_untracked=True)["changes"]
            checker = run_command(task["checker"], workspace,
                                  int(task.get("checker_timeout_seconds", 300)))
            (output / f"{stem}.checker.stdout").write_text(checker["stdout"])
            (output / f"{stem}.checker.stderr").write_text(checker["stderr"])
            completed = agent["status"] == checker["status"] == "completed"
            receipt.update({
                "status": agent["status"],
                "agent_returncode": agent["returncode"],
                "checker_status": checker["status"],
                "checker_returncode": checker["returncode"],
                "checker_pass": completed and agent["returncode"] == checker["returncode"] == 0,
                "severe_regression": checker["status"] != "completed"
                or checker["returncode"] in set(task.get("severe_regression_codes", [])),
                "usage": parse_usage(receipt["backend"], agent["stdout"]),
                "agent_wall_seconds": agent["wall_seconds"],
                "checker_wall_seconds": checker["wall_seconds"],
                "agent_changes": agent_changes,
            })
            receipts.append(receipt)
            atomic_write(output / "receipts.jsonl", "".join(json.dumps(row) + "\n" for row in receipts))
    atomic_write(output / "receipts.jsonl", "".join(json.dumps(row) + "\n" for row in receipts))
    if not dry_run:
        atomic_write(output / "summary.json", json.dumps(summarize(receipts), indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(read_manifest(args.manifest), args.output, args.dry_run)


if __name__ == "__main__":
    main()
