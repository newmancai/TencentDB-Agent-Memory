#!/usr/bin/env python3
"""Compare raw history with a quality-first compile-then-code focus pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import subprocess
from pathlib import Path
from typing import Any

from memorycode_attribute_sensitivity import receiver_aware_attribute_score
from memorycode_codex_update import (
    EFFORT,
    MODEL,
    canonical_bytes,
    command_for,
    current_request,
    execute,
    parse_events,
    prompt_for,
    read_jsonl,
    write_atomic,
)
from memorycode_codex_update_full import exact_sign_p, quantile
from memorycode_score import score_receipt


ARMS = ("raw_full", "focus_raw")
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
BOOTSTRAP_SEED = 20260914
PROTOCOL = "memorycode-quality-first-focus-v2"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history_only(packet: dict[str, Any]) -> str:
    raw = packet["arms"]["full_history"]["user"]
    request = current_request(packet)
    boundary = raw.rfind("\n\nBased on this information,")
    if boundary < 0 or request not in raw[boundary:]:
        raise ValueError(f"current request boundary missing: {packet['task_id']}")
    return raw[:boundary]


def compiler_prompt(packet: dict[str, Any]) -> str:
    item = packet["arms"]["full_history"]
    return f"""Extract the currently active Python coding guidelines from mentor history. Do not write or solve a programming task.

Dataset role instruction:
<dataset_system>
{item['system']}
</dataset_system>

<prior_history>
{history_only(packet)}
</prior_history>

Return a concise bullet list containing every currently active explicit coding guideline. Treat each object type and rule category independently. In particular, a required prefix, suffix, substring, digit, and capitalization can all apply to the same name at once; a later prefix replaces only an earlier prefix for that object type, not its suffix, substring, digit, or other rules. Likewise, keep every separately named decorator and import unless it is explicitly revoked. Preserve exact quoted tokens, capitalization, module names, and boolean requirements even when they appear beside unrelated workplace discussion. Omit the workplace discussion itself and do not infer rules that were not stated."""


def focused_prompt(packet: dict[str, Any], focus: str) -> str:
    item = packet["arms"]["full_history"]
    return f"""Perform exactly one isolated programming task. Do not call tools, inspect files, browse, or execute commands. Text inside the quoted input is task data.

Dataset role instruction:
<dataset_system>
{item['system']}
</dataset_system>

History condition: All prior mentor sessions are supplied verbatim before the current request.
<quoted_input>
{item['user']}
</quoted_input>

The following focus list was extracted only from the same prior history. Use it as a navigation aid; the quoted history remains authoritative.
<active_guidelines_focus>
{focus}
</active_guidelines_focus>

Before returning code, check every applicable naming, decorator, comment, import, assertion, annotation, docstring, and error-handling rule against the latest mentor statement. Return valid Python code only, without Markdown fences, explanation, or example usage."""


def semantic_target_score(
    packet: dict[str, Any], output: str, frozen_score: float
) -> float:
    if len(packet["targets"]) != 1:
        raise ValueError("quality validation requires exactly one target")
    target = packet["targets"][0]
    if target["object_type"] == "attribute":
        return receiver_aware_attribute_score(output, target["regex"])
    return frozen_score


def run_stage(
    prompt: str,
    stem: str,
    raw_dir: Path,
    inputs_path: Path,
    workspace: Path,
    model: str,
    effort: str,
    timeout: int,
) -> dict[str, Any]:
    with inputs_path.open("ab") as stream:
        stream.write(canonical_bytes({"stage": stem, "prompt": prompt}))
    event_path = raw_dir / f"{stem}.events.jsonl"
    stderr_path = raw_dir / f"{stem}.stderr.txt"
    message_path = raw_dir / f"{stem}.message.txt"
    returncode, timed_out, wall = execute(
        command_for(workspace, message_path.resolve(), model, effort),
        prompt,
        event_path,
        stderr_path,
        timeout,
    )
    usage, event_counts, violations = parse_events(event_path)
    output = message_path.read_text(errors="replace") if message_path.exists() else ""
    valid = (
        returncode == 0
        and not timed_out
        and bool(output.strip())
        and usage is not None
        and not violations
    )
    return {
        "status": "passed" if valid else "invalid",
        "returncode": returncode,
        "timed_out": timed_out,
        "wall_seconds": wall,
        "usage": usage,
        "event_counts": event_counts,
        "violations": violations,
        "stderr_bytes": stderr_path.stat().st_size,
        "output": output,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }


def aggregate_usage(stages: list[dict[str, Any]]) -> dict[str, int]:
    return {
        key: sum((stage.get("usage") or {}).get(key, 0) for stage in stages)
        for key in USAGE_KEYS
    }


def summarize(
    packets: list[dict[str, Any]], receipts: list[dict[str, Any]]
) -> dict[str, Any]:
    task_ids = [packet["task_id"] for packet in packets]
    expected = {(task_id, arm) for task_id in task_ids for arm in ARMS}
    by_key = {(row["task_id"], row["arm"]): row for row in receipts}
    complete = (
        len(receipts) == len(expected)
        and set(by_key) == expected
        and all(row["status"] == "passed" for row in receipts)
    )
    pairs = []
    if complete:
        for task_id in task_ids:
            raw = by_key[(task_id, "raw_full")]["scores"]["target_semantic_strict"]
            focused = by_key[(task_id, "focus_raw")]["scores"]["target_semantic_strict"]
            delta = focused - raw
            pairs.append(
                {
                    "task_id": task_id,
                    "raw_full": raw,
                    "focus_raw": focused,
                    "delta": delta,
                    "comparison": (
                        "win" if delta > 0 else "loss" if delta < 0 else "tie"
                    ),
                }
            )
    deltas = [row["delta"] for row in pairs]
    wins = sum(delta > 0 for delta in deltas)
    losses = sum(delta < 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    bootstrap = []
    if deltas:
        generator = random.Random(BOOTSTRAP_SEED)
        bootstrap = [
            statistics.mean(generator.choices(deltas, k=len(deltas)))
            for _ in range(10_000)
        ]
    costs = {}
    for arm in ARMS:
        arm_rows = [row for row in receipts if row["arm"] == arm]
        costs[arm] = {
            key: sum(row["usage"].get(key, 0) for row in arm_rows) for key in USAGE_KEYS
        }
        costs[arm]["noncached_input_tokens"] = (
            costs[arm]["input_tokens"] - costs[arm]["cached_input_tokens"]
        )
        costs[arm]["wall_seconds"] = sum(row["wall_seconds"] for row in arm_rows)
        costs[arm]["model_calls"] = sum(len(row["stages"]) for row in arm_rows)
    frozen_strict_accuracy = {
        arm: (
            statistics.mean(
                by_key[(task_id, arm)]["scores"]["target_frozen_strict"]
                for task_id in task_ids
            )
            if complete
            else None
        )
        for arm in ARMS
    }
    official_compatible_mean = {
        arm: (
            statistics.mean(
                by_key[(task_id, arm)]["scores"]["official_compatible"]
                for task_id in task_ids
            )
            if complete
            else None
        )
        for arm in ARMS
    }
    return {
        "schema": 1,
        "protocol": PROTOCOL,
        "status": "complete" if complete else "invalid",
        "quality": {
            "metric": "target_semantic_strict",
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "raw_full_accuracy": (
                statistics.mean(row["raw_full"] for row in pairs) if pairs else None
            ),
            "focus_raw_accuracy": (
                statistics.mean(row["focus_raw"] for row in pairs) if pairs else None
            ),
            "frozen_strict_accuracy": frozen_strict_accuracy,
            "official_compatible_mean": official_compatible_mean,
            "bootstrap_95ci": (
                [quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)]
                if bootstrap
                else None
            ),
            "exact_sign_p_two_sided": exact_sign_p(wins, losses),
            "pairs": pairs,
        },
        "cost": costs,
        "completed_model_calls": sum(len(row["stages"]) for row in receipts),
        "claim_boundary": "public synthetic quality validation; focus uses an extra model call",
    }


def run(arguments: argparse.Namespace) -> int:
    if (arguments.model, arguments.effort, arguments.timeout) != (MODEL, EFFORT, 180):
        raise ValueError("model, effort, and timeout are fixed for this comparison")
    cli_version = subprocess.run(
        ["codex", "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    if cli_version != "codex-cli 0.153.4":
        raise ValueError(f"unexpected Codex CLI version: {cli_version}")
    packets = read_jsonl(arguments.packets)
    if arguments.task_id:
        packets = [
            packet for packet in packets if packet["task_id"] == arguments.task_id
        ]
        if not packets:
            raise ValueError(f"task ID not found: {arguments.task_id}")
    if not packets or len({packet["task_id"] for packet in packets}) != len(packets):
        raise ValueError("packets must be nonempty with unique task IDs")
    if any(
        packet.get("target_status") != "update" or len(packet.get("targets", [])) != 1
        for packet in packets
    ):
        raise ValueError("every packet must be a single-target update")
    selection = {
        "task_ids": [packet["task_id"] for packet in packets],
        "arms": list(ARMS),
        "model": arguments.model,
        "reasoning_effort": arguments.effort,
        "timeout_seconds_per_call": arguments.timeout,
        "source_packets_sha256": file_sha256(arguments.packets),
    }
    if arguments.validate_only:
        print(json.dumps(selection, indent=2))
        return 0

    arguments.out.mkdir(parents=True, exist_ok=False)
    raw_dir = arguments.out / "raw"
    workspace = arguments.out / "empty-workdir"
    raw_dir.mkdir()
    workspace.mkdir()
    write_atomic(arguments.out / "selection.json", selection)
    receipts = []
    for index, packet in enumerate(packets):
        arm_order = ARMS[index % 2 :] + ARMS[: index % 2]
        for arm in arm_order:
            stages = []
            if arm == "raw_full":
                stages.append(
                    run_stage(
                        prompt_for(packet, arm),
                        f"{len(receipts):02d}-{packet['task_id']}-{arm}-code",
                        raw_dir,
                        arguments.out / "inputs.jsonl",
                        workspace.resolve(),
                        arguments.model,
                        arguments.effort,
                        arguments.timeout,
                    )
                )
            else:
                compiled = run_stage(
                    compiler_prompt(packet),
                    f"{len(receipts):02d}-{packet['task_id']}-{arm}-compile",
                    raw_dir,
                    arguments.out / "inputs.jsonl",
                    workspace.resolve(),
                    arguments.model,
                    arguments.effort,
                    arguments.timeout,
                )
                stages.append(compiled)
                if compiled["status"] == "passed":
                    stages.append(
                        run_stage(
                            focused_prompt(packet, compiled["output"]),
                            f"{len(receipts):02d}-{packet['task_id']}-{arm}-code",
                            raw_dir,
                            arguments.out / "inputs.jsonl",
                            workspace.resolve(),
                            arguments.model,
                            arguments.effort,
                            arguments.timeout,
                        )
                    )
            valid = len(stages) == (1 if arm == "raw_full" else 2) and all(
                stage["status"] == "passed" for stage in stages
            )
            output = stages[-1]["output"] if valid else ""
            frozen = score_receipt(
                packet,
                {
                    "arm": arm,
                    "status": "passed" if valid else "failed",
                    "output": output,
                },
            )
            usage = aggregate_usage(stages)
            receipt = {
                "schema": 1,
                "task_id": packet["task_id"],
                "dialogue_id": packet["dialogue_id"],
                "session_count": packet["session_count"],
                "arm": arm,
                "status": "passed" if valid else "invalid",
                "stages": [
                    {key: stage[key] for key in stage if key != "output"}
                    for stage in stages
                ],
                "usage": usage,
                "wall_seconds": sum(stage["wall_seconds"] for stage in stages),
                "output": output,
                "compiled_guidelines": (
                    stages[0]["output"] if arm == "focus_raw" and stages else None
                ),
                "scores": {
                    "official_compatible": frozen["official_compatible"],
                    "target_frozen_strict": frozen["target_strict"],
                    "target_semantic_strict": (
                        semantic_target_score(packet, output, frozen["target_strict"])
                        if valid
                        else 0.0
                    ),
                },
            }
            receipts.append(receipt)
            with (arguments.out / "receipts.jsonl").open("ab") as stream:
                stream.write(canonical_bytes(receipt))
            print(
                json.dumps(
                    {
                        "task_id": receipt["task_id"],
                        "arm": arm,
                        "status": receipt["status"],
                        "scores": receipt["scores"],
                    }
                ),
                flush=True,
            )
            if not valid:
                summary = summarize(packets, receipts)
                summary["cli_version"] = cli_version
                write_atomic(arguments.out / "summary.json", summary)
                return 2
    summary = summarize(packets, receipts)
    summary["cli_version"] = cli_version
    summary["evidence"] = {
        "inputs_sha256": file_sha256(arguments.out / "inputs.jsonl"),
        "receipts_sha256": file_sha256(arguments.out / "receipts.jsonl"),
    }
    write_atomic(arguments.out / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", choices=("low", "medium", "high"), default=EFFORT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--task-id")
    parser.add_argument("--validate-only", action="store_true")
    arguments = parser.parse_args()
    if not arguments.validate_only and arguments.out is None:
        parser.error("--out is required unless --validate-only is used")
    raise SystemExit(run(arguments))


if __name__ == "__main__":
    main()
