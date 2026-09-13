"""Run clean and MemoryCore-enhanced coding-agent arms in marked worktrees."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import sys
import subprocess


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/project-agent"))
from backend import command_for, events_from, parse_usage, run_command, terminal_error

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
    # Porcelain v1 uses a leading space as part of the two-column status.  Removing
    # all leading whitespace turns `` M path`` into ``M path`` and corrupts paths
    # consumed by output-scope enforcement.
    return result.stdout.rstrip("\r\n")


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




def read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if (manifest.get("schema") != 1 or not isinstance(manifest.get("tasks"), list)
            or not manifest["tasks"]):
        raise ValueError("manifest must have schema=1 and non-empty tasks")
    timeout = manifest.get("timeout_seconds", 900)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if manifest.get("evaluation_mode", "diagnostic") not in {"diagnostic", "pilot", "heldout"}:
        raise ValueError("invalid evaluation_mode")
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
            # Both controlled arms explicitly disable instruction discovery below;
            # checked-in project instructions are still ordinary readable files.
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
        raw_path = task.get("baseline_context")
        if raw_path:
            raw = Path(raw_path).read_text()
            return f"Prior project observations (respect source and scope):\n{raw}\n\n{task['prompt']}"
        return task["prompt"]
    context_path = Path(task.get("memory_context", ""))
    if not context_path.is_file():
        raise ValueError(f"memory arm lacks context for {task['id']}")
    context = context_path.read_text()
    if len(context.encode()) > task.get("max_context_bytes", 16000):
        raise ValueError(f"memory context exceeds its byte budget: {task['id']}")
    return ("Use the following bounded project memory as evidence, respecting its scope and timestamps. "
            "It may nominate facts for verification but does not override repository evidence.\n\n"
            f"<memorycore_context>\n{context}\n</memorycore_context>\n\n{task['prompt']}")










def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = int(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def summarize(receipts: list[dict], manifest: dict | None = None) -> dict:
    observed = [r for r in receipts if r["status"] != "dry_run"]
    keys = [(r["task_id"], r["arm"]) for r in observed]
    errors = []
    if len(keys) != len(set(keys)):
        errors.append("duplicate_task_arm")
    tasks = {t["id"]: t for t in (manifest or {}).get("tasks", [])}
    expected = {(task, arm) for task in tasks for arm in ARMS}
    if not tasks:
        errors.append("missing_expected_manifest")
    elif set(keys) != expected:
        errors.append("incomplete_or_unexpected_task_arm_matrix")
    for r in observed:
        if r["task_id"] in tasks and (r["kind"] != tasks[r["task_id"]]["kind"]
                or r.get("cluster_id") != tasks[r["task_id"]].get("cluster_id")):
            errors.append("receipt_metadata_mismatch")
    clusters = {t.get("cluster_id") for t in tasks.values() if t.get("cluster_id")}
    if any(not t.get("cluster_id") for t in tasks.values()):
        errors.append("missing_cluster_id")
    if len(tasks) < 12 or len(clusters) < 4:
        errors.append("insufficient_tasks_or_clusters")
    for cluster in clusters:
        kinds = {t["kind"] for t in tasks.values() if t.get("cluster_id") == cluster}
        if kinds != {"necessary_update", "same_topic_control"}:
            errors.append("missing_within_cluster_control")
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
                     "usage_missing_tasks": sum(row.get("usage") is None for row in rows),
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
    passed = complete and not errors
    for backend in ("codex", "claude"):
        counts = paired[backend]
        passed = passed and counts.get("win", 0) > counts.get("loss", 0)
        passed = passed and counts.get("necessary_update_win", 0) >= 1
        passed = passed and counts.get("same_topic_control_win", 0) >= counts.get("same_topic_control_loss", 0)
        passed = passed and arms[f"{backend}_memory"]["severe_regressions"] <= arms[f"{backend}_clean"]["severe_regressions"]
    mode = (manifest or {}).get("evaluation_mode", "diagnostic")
    return {"protocol": "topic3-be-agent-product-v1", "arms": arms, "paired_memory_vs_clean": paired,
            "evaluation_mode": mode, "contract_errors": sorted(set(errors)),
            "observed_protocol_conditions_met": bool(passed),
            "pass": bool(passed and mode == "heldout"),
            "product_readiness": "not_established_by_this_pilot",
            "scope": "Within-backend paired coding tasks; a pass alone is not evidence of product parity."}


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
                       "base_commit": before["base_commit"], "cluster_id": task.get("cluster_id"),
                       "model_requested": manifest.get(f'{arm.split("_", 1)[0]}_model'),
                       "effort": manifest.get(f'{arm.split("_", 1)[0]}_effort', "medium"),
                       "context_mode": "scoped_memory" if memory else "raw_history" if task.get("baseline_context") else "none",
                       "instruction_mode": "controlled_discovery_disabled"}
            if dry_run:
                receipt.update({"status": "dry_run", "command": command[:-1]})
                receipts.append(receipt)
                continue
            environment = os.environ.copy()
            if arm.startswith("claude"):
                environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
                environment["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] = "1"
            agent = run_command(command, workspace, timeout,
                                input=prompt if arm.startswith("codex") else None,
                                env=environment)
            if agent["status"] == "completed" and terminal_error(agent["stdout"]):
                agent["status"] = "agent_error"
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
        atomic_write(output / "summary.json", json.dumps(summarize(receipts, manifest), indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(read_manifest(args.manifest), args.output, args.dry_run)


if __name__ == "__main__":
    main()
