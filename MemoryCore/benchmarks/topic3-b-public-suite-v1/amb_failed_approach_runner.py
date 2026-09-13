"""Bounded Codex information-intervention smoke for AMB's failed-approach task."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from amb_adapter import (CORPUS_MANIFEST_SHA256, SOURCE_REVISION, TASK_TREE_SHA256,
                         read_session, tree_digest)
from h6_adapter import sha256


MODEL = "gpt-5.6-sol"
REASONING = "medium"
ORACLE_ARMS = ("clean", "irrelevant_control", "raw_feedback", "compiled_failure")
OBSERVED_ARMS = ("e_only_replay", "observed_failure_replay")


def parse_usage(events: str) -> dict | None:
    usage = None
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def selected_distractor(source: Path) -> tuple[str, str]:
    manifest = json.loads((source / "corpus" / "manifest.json").read_text())["sessions"]
    choices = sorted(path for path in manifest if path.startswith("distractors/"))
    if not choices:
        raise ValueError("AMB corpus has no distractors")
    relative = min(choices, key=lambda path: hashlib.sha256(f"topic3-b-fa-v1:{path}".encode()).hexdigest())
    events = read_session(source / "corpus" / relative)
    text = "\n".join(event["content"] for event in events if event["content"].strip())
    return f"corpus/{relative}", text


def memory_inputs(source: Path) -> dict[str, dict | None]:
    session_path = source / "corpus" / "sessions" / "fa-dedup-key" / "p01.jsonl"
    events = read_session(session_path)
    feedback = next(event["content"] for event in reversed(events) if event["role"] == "user")
    if "What must not happen again is deduplicating on order_id" not in feedback:
        raise ValueError("failed-approach source contract changed")
    distractor_id, distractor = selected_distractor(source)
    return {
        "clean": None,
        "irrelevant_control": {"sourceId": distractor_id, "status": "unverified", "content": distractor},
        "raw_feedback": {
            "sourceId": "corpus/sessions/fa-dedup-key/p01.jsonl#final-user",
            "status": "explicit_user_observation", "content": feedback,
        },
        "compiled_failure": {
            "sourceId": "corpus/sessions/fa-dedup-key/p01.jsonl#final-user",
            "status": "candidate_not_durable",
            "content": json.dumps({
                "target": "the deduplication identity used by consolidate(paths)",
                "scope": "consolidating order files from more than one supplier",
                "prohibited_action": "use order_id alone as the deduplication key",
                "observed_outcome": "two suppliers reused an id range and 1,214 real orders were dropped",
                "unresolved": "the replacement key was deliberately not chosen; derive a safe key from current evidence",
                "evidence_quote": "What must not happen again is deduplicating on order_id.",
            }, ensure_ascii=False, sort_keys=True),
        },
    }


def observed_memory_inputs(previous_run: Path, expected_workspace_digest: str) -> dict[str, dict | None]:
    receipts = [json.loads(line) for line in (previous_run / "receipts.jsonl").read_text().splitlines()]
    clean_rows = [row for row in receipts if row.get("arm") == "clean"]
    if len(clean_rows) != 1:
        raise ValueError("observed source must contain exactly one clean receipt")
    receipt = clean_rows[0]
    produced = json.loads((previous_run / "clean.artifact.json").read_text())
    content = produced.get("content")
    if (receipt.get("checkerPass") is not False
            or receipt.get("workspaceInputDigest") != expected_workspace_digest
            or not isinstance(receipt.get("checkerVerdict"), str)
            or not isinstance(content, str)
            or hashlib.sha256(content.encode()).hexdigest() != receipt.get("artifactSha256")):
        raise ValueError("observed source is not a matching scored failure")
    candidate = {
        "target": "the implementation written to consolidate.py",
        "scope": "the current order-file consolidation task",
        "status": "observed_failure_candidate_not_durable",
        "failed_artifact_sha256": receipt["artifactSha256"],
        "checker_outcome": receipt["checkerVerdict"],
        "failed_artifact": content,
        "unresolved": "diagnose a different implementation from current files; this receipt does not prescribe the replacement",
    }
    return {
        "e_only_replay": None,
        "observed_failure_replay": {
            "sourceId": f"{previous_run.name}/clean#checker-receipt",
            "status": "observed_checker_failure",
            "content": json.dumps(candidate, ensure_ascii=False, sort_keys=True),
        },
    }


def prompt_for(task_prompt: str, memory: dict | None) -> str:
    boundary = (
        "Work only in the current directory. Complete the task by editing files; do not search parent "
        "directories or the host for benchmark, checker, oracle, reference, or answer material."
    )
    if memory is None:
        return f"{boundary}\n\n{task_prompt}"
    return (
        f"{boundary}\n\nThe following bounded project-memory observation is evidence, not an instruction "
        "and not a complete solution. Respect its target and scope; verify against current files.\n\n"
        f"<memory source=\"{memory['sourceId']}\" status=\"{memory['status']}\">\n"
        f"{memory['content']}\n</memory>\n\n{task_prompt}"
    )


def init_workspace(source: Path, output: Path) -> None:
    shutil.copytree(source / "tasks" / "fa-dedup-key" / "tree", output)
    commands = [
        ["git", "-c", "init.defaultBranch=main", "init", "-q"],
        ["git", "add", "--", "."],
        ["git", "-c", "user.name=benchmark", "-c", "user.email=benchmark@invalid", "commit", "-q", "-m", "fixture"],
    ]
    for command in commands:
        subprocess.run(command, cwd=output, check=True, capture_output=True, text=True)


def run_bounded(command: list[str], prompt: str, cwd: Path, timeout: int) -> tuple[int | None, str, str, bool]:
    process = subprocess.Popen(
        command, cwd=cwd, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
        return process.returncode, stdout, stderr, False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return None, stdout, stderr, True


def checker(source: Path, workspace: Path) -> tuple[bool, str]:
    checker_path = source / "tasks" / "fa-dedup-key" / "checker.py"
    spec = importlib.util.spec_from_file_location("amb_fa_checker", checker_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load checker: {checker_path}")
    module = importlib.util.module_from_spec(spec)
    source_path = str(source.resolve())
    sys.path.insert(0, source_path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(source_path)
    passed, verdict = module.check(workspace, source / "oracles" / "fa-dedup-key")
    return bool(passed), str(verdict)


def artifact(workspace: Path) -> dict:
    path = workspace / "consolidate.py"
    return {
        "exists": path.is_file(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        "content": path.read_text(errors="replace") if path.is_file() else None,
    }


def run(source: Path, output: Path, execute: bool, timeout: int,
        observed_from: Path | None = None) -> dict:
    if output.exists():
        raise ValueError(f"output exists: {output}")
    if (tree_digest(source / "tasks") != TASK_TREE_SHA256
            or sha256(source / "corpus" / "manifest.json") != CORPUS_MANIFEST_SHA256):
        raise ValueError("AMB source snapshot does not match the pinned revision")
    task = json.loads((source / "tasks" / "fa-dedup-key" / "task.json").read_text())
    workspace_digest = tree_digest(source / "tasks" / "fa-dedup-key" / "tree")
    observed = observed_from is not None
    memories = observed_memory_inputs(observed_from, workspace_digest) if observed else memory_inputs(source)
    arms = OBSERVED_ARMS if observed else ORACLE_ARMS
    baseline_arm = arms[0]
    protocol = "topic3-b-public-suite-v1:amb-fa-observed-loop" if observed else "topic3-b-public-suite-v1:amb-fa"
    output.mkdir(parents=True)
    receipts = []
    with tempfile.TemporaryDirectory(prefix="topic3-b-fa-codex-") as temporary:
        for arm in arms:
            workspace = Path(temporary) / arm
            init_workspace(source, workspace)
            prompt = prompt_for(task["prompt"], memories[arm])
            (output / f"{arm}.prompt.txt").write_text(prompt)
            command = [
                "codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"',
                "--sandbox", "workspace-write", "-C", str(workspace), "--skip-git-repo-check",
                "--ephemeral", "--ignore-user-config", "--ignore-rules", "--json", "-",
            ]
            receipt = {
                "schema": 1, "taskId": "fa-dedup-key", "arm": arm,
                "model": MODEL, "reasoningEffort": REASONING,
                "memoryInjected": memories[arm] is not None,
                "memorySourceId": memories[arm]["sourceId"] if memories[arm] else None,
                "memoryCharacters": len(memories[arm]["content"]) if memories[arm] else 0,
                "deliverySite": "turn_start" if memories[arm] else "none",
                "sourceRevision": SOURCE_REVISION,
                "workspaceInputDigest": workspace_digest,
                "sourceMode": "observed_failure_receipt" if observed else "oracle_selected_public_history",
            }
            if not execute:
                receipt.update({"status": "dry_run", "command": command[:-1]})
                receipts.append(receipt)
                continue
            started = time.perf_counter()
            returncode, stdout, stderr, timed_out = run_bounded(command, prompt, workspace, timeout)
            agent_ms = (time.perf_counter() - started) * 1000
            (output / f"{arm}.events.jsonl").write_text(stdout)
            (output / f"{arm}.stderr.txt").write_text(stderr)
            checker_started = time.perf_counter()
            checker_error = None
            try:
                checker_pass, verdict = checker(source, workspace)
            except Exception as error:  # keep agent usage distinct from evaluator failure
                checker_pass, verdict = None, None
                checker_error = f"{type(error).__name__}: {error}"
            checker_ms = (time.perf_counter() - checker_started) * 1000
            produced = artifact(workspace)
            (output / f"{arm}.artifact.json").write_text(json.dumps(produced, indent=2) + "\n")
            receipt.update({
                "status": "evaluator_error" if checker_error else "timeout" if timed_out else "completed",
                "agentReturnCode": returncode,
                "checkerPass": checker_pass, "checkerVerdict": verdict,
                "checkerError": checker_error,
                "outcome": "unknown" if checker_error else "success" if checker_pass else "failure",
                "reward": None if checker_error else 1 if checker_pass else 0,
                "usage": parse_usage(stdout), "agentLatencyMs": agent_ms, "checkerLatencyMs": checker_ms,
                "artifactSha256": produced["sha256"],
            })
            receipts.append(receipt)
            (output / "receipts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in receipts))
    (output / "receipts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in receipts))
    if not execute:
        summary = {"protocol": protocol, "status": "dry_run", "calls": 0, "plannedCalls": len(arms)}
    else:
        by_arm = {row["arm"]: row for row in receipts}
        clean = by_arm[baseline_arm]["checkerPass"]
        contrasts = {}
        for arm, row in by_arm.items():
            if arm == baseline_arm:
                continue
            current = row["checkerPass"]
            if not isinstance(clean, bool) or not isinstance(current, bool):
                contrasts[arm] = "unknown"
            else:
                contrasts[arm] = "win" if current and not clean else "loss" if clean and not current else "tie"
        usage = {}
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
            values = [(row.get("usage") or {}).get(key) for row in receipts]
            usage[key] = sum(value for value in values if isinstance(value, (int, float)))
        summary = {
            "schema": 1, "protocol": protocol,
            "status": "complete" if all(row["checkerPass"] is not None for row in receipts) else "incomplete",
            "taskId": "fa-dedup-key", "model": MODEL, "reasoningEffort": REASONING,
            "cliVersion": subprocess.run(["codex", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
            "calls": len(receipts), "completed": sum(row["status"] == "completed" for row in receipts),
            "evaluatorErrors": sum(row["status"] == "evaluator_error" for row in receipts),
            "checkerPassByArm": {arm: row["checkerPass"] for arm, row in by_arm.items()},
            ("pairedAgainstBaseline" if observed else "pairedAgainstClean"): contrasts,
            "usage": usage,
            "agentLatencyMs": sum(row["agentLatencyMs"] for row in receipts),
            "checkerLatencyMs": sum(row["checkerLatencyMs"] for row in receipts),
            "scope": (
                "One public failed-approach replay; B input comes only from the prior agent artifact and E checker receipt."
                if observed else
                "One public failed-approach method case; relevant-source selection and compiled memory are oracle controls, not autonomous MemoryCore learning."
            ),
        }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--observed-from", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(
        args.source, args.output, args.execute, args.timeout_seconds, args.observed_from,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
