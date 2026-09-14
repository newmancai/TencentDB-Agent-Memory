#!/usr/bin/env python3
"""Run Codex on every update row in the frozen MemoryCode generation subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
from pathlib import Path
from typing import Any

from memorycode_codex_update import (
    ARMS,
    EFFORT,
    MODEL,
    canonical_bytes,
    command_for,
    execute,
    parse_events,
    prompt_for,
    read_jsonl,
    write_atomic,
)
from memorycode_score import score_receipt


PROTOCOL = "memorycode-codex-complete-update-diagnostic-v2"
SOURCE_PACKET_SHA256 = "ecabcda9142f5094cfa73b62ce1c41e6c87bad33633b2ccb2c29b1c69f1c76e4"
TASK_IDS = (
    "memorycode-079",
    "memorycode-113",
    "memorycode-150",
    "memorycode-179",
    "memorycode-197",
    "memorycode-219",
    "memorycode-249",
    "memorycode-278",
    "memorycode-321",
    "memorycode-359",
)
BOOTSTRAP_SEED = 20260914
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def exact_sign_p(wins: int, losses: int) -> float:
    trials = wins + losses
    if not trials:
        return 1.0
    tail = sum(math.comb(trials, index) for index in range(min(wins, losses) + 1)) / 2**trials
    return min(1.0, 2 * tail)


def selected_packets(path: Path, expected_hash: str = SOURCE_PACKET_SHA256) -> list[dict[str, Any]]:
    if file_sha256(path) != expected_hash:
        raise ValueError("source packet hash does not match the frozen protocol")
    packets = read_jsonl(path)
    selected = [packet for packet in packets if packet.get("target_status") == "update"]
    if tuple(packet.get("task_id") for packet in selected) != TASK_IDS:
        raise ValueError("complete update selection no longer matches the ten frozen IDs")
    if any(len(packet.get("targets", [])) != 1 for packet in selected):
        raise ValueError("every selected update must have one strict target")
    return selected


def summarize(selection: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {(task_id, arm) for task_id in TASK_IDS for arm in ARMS}
    by_key = {(row["task_id"], row["arm"]): row for row in receipts}
    complete = (
        len(receipts) == len(expected)
        and set(by_key) == expected
        and all(row["status"] == "passed" for row in receipts)
    )
    pairs = []
    if complete:
        for task_id in TASK_IDS:
            clean = by_key[(task_id, "no_history")]["scores"]["target_strict"]
            raw = by_key[(task_id, "raw_full")]["scores"]["target_strict"]
            pairs.append(
                {
                    "task_id": task_id,
                    "history_class": by_key[(task_id, "raw_full")]["history_class"],
                    "session_count": by_key[(task_id, "raw_full")]["session_count"],
                    "no_history": clean,
                    "raw_full": raw,
                    "delta": raw - clean,
                    "comparison": "win" if raw > clean else "loss" if raw < clean else "tie",
                }
            )

    deltas = [row["delta"] for row in pairs]
    wins = sum(delta > 0 for delta in deltas)
    losses = sum(delta < 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    bootstrap = []
    if deltas:
        generator = random.Random(BOOTSTRAP_SEED)
        bootstrap = [statistics.mean(generator.choices(deltas, k=len(deltas))) for _ in range(10_000)]

    usage = {
        arm: {
            key: sum((row.get("usage") or {}).get(key, 0) for row in receipts if row["arm"] == arm)
            for key in USAGE_KEYS
        }
        for arm in ARMS
    }
    for arm in ARMS:
        usage[arm]["noncached_input_tokens"] = (
            usage[arm]["input_tokens"] - usage[arm]["cached_input_tokens"]
        )
        usage[arm]["wall_seconds"] = sum(
            row["wall_seconds"] for row in receipts if row["arm"] == arm
        )

    quality = {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_delta": statistics.mean(deltas) if deltas else None,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_95ci": [quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)]
        if bootstrap
        else None,
        "exact_sign_p_two_sided": exact_sign_p(wins, losses),
        "no_history_accuracy": statistics.mean(row["no_history"] for row in pairs) if pairs else None,
        "raw_full_accuracy": statistics.mean(row["raw_full"] for row in pairs) if pairs else None,
        "by_history_class": {
            name: {
                "tasks": len(part),
                "wins": sum(row["delta"] > 0 for row in part),
                "losses": sum(row["delta"] < 0 for row in part),
                "ties": sum(row["delta"] == 0 for row in part),
                "no_history_accuracy": statistics.mean(row["no_history"] for row in part),
                "raw_full_accuracy": statistics.mean(row["raw_full"] for row in part),
            }
            for name in ("short", "long")
            if (part := [row for row in pairs if row["history_class"] == name])
        },
        "pairs": pairs,
    }
    if not complete:
        decision = "invalid_execution"
    elif wins > losses:
        decision = "directional_raw_history_gain_on_open_complete_update_stratum"
    elif losses > wins:
        decision = "directional_raw_history_regression_on_open_complete_update_stratum"
    else:
        decision = "no_directional_difference_on_open_complete_update_stratum"
    return {
        "schema": 1,
        "protocol": PROTOCOL,
        "status": "complete" if complete else "invalid",
        "selection": selection,
        "completed_calls": sum(row["status"] == "passed" for row in receipts),
        "planned_calls": len(expected),
        "quality": quality,
        "cost": usage,
        "decision": decision,
        "claim_boundary": "complete frozen update stratum, but open development data and not natural use",
    }


def run(arguments: argparse.Namespace) -> int:
    if (arguments.model, arguments.effort, arguments.timeout) != (MODEL, EFFORT, 180):
        raise ValueError("model, effort, and timeout are frozen by the protocol")
    cli_version = subprocess.run(
        ["codex", "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    if cli_version != "codex-cli 0.153.4":
        raise ValueError(f"unexpected Codex CLI version: {cli_version}")
    packets = selected_packets(arguments.packets)
    selection = {
        "rule": "all target_status=update rows in the frozen 24-dialogue generation subset",
        "task_ids": list(TASK_IDS),
        "session_counts": [packet["session_count"] for packet in packets],
        "arms": list(ARMS),
        "model": arguments.model,
        "reasoning_effort": arguments.effort,
        "timeout_seconds": arguments.timeout,
        "planned_calls": len(TASK_IDS) * len(ARMS),
        "source_packets_sha256": file_sha256(arguments.packets),
    }
    if arguments.validate_only:
        print(json.dumps(selection, indent=2))
        return 0

    arguments.out.mkdir(parents=True, exist_ok=False)
    raw_dir = arguments.out / "raw"
    empty_dir = arguments.out / "empty-workdir"
    raw_dir.mkdir()
    empty_dir.mkdir()
    write_atomic(arguments.out / "selection.json", selection)
    schedule = []
    for index, packet in enumerate(packets):
        order = ARMS[index % 2 :] + ARMS[: index % 2]
        schedule.extend((packet, arm) for arm in order)
    inputs = [
        {"task_id": packet["task_id"], "arm": arm, "prompt": prompt_for(packet, arm)}
        for packet, arm in schedule
    ]
    with (arguments.out / "inputs.jsonl").open("xb") as stream:
        for row in inputs:
            stream.write(canonical_bytes(row))

    receipts = []
    receipt_path = arguments.out / "receipts.jsonl"
    for packet, arm in schedule:
        stem = f"{len(receipts):02d}-{packet['task_id']}-{arm}"
        event_path = raw_dir / f"{stem}.events.jsonl"
        stderr_path = raw_dir / f"{stem}.stderr.txt"
        message_path = raw_dir / f"{stem}.message.txt"
        prompt = prompt_for(packet, arm)
        returncode, timed_out, wall = execute(
            command_for(empty_dir.resolve(), message_path.resolve(), arguments.model, arguments.effort),
            prompt,
            event_path,
            stderr_path,
            arguments.timeout,
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
        scored = score_receipt(
            packet, {"arm": arm, "status": "passed" if valid else "failed", "output": output}
        )
        receipt = {
            "schema": 1,
            "task_id": packet["task_id"],
            "dialogue_id": packet["dialogue_id"],
            "session_count": packet["session_count"],
            "history_class": packet["history_class"],
            "target_status": packet["target_status"],
            "arm": arm,
            "status": "passed" if valid else "invalid",
            "returncode": returncode,
            "timed_out": timed_out,
            "violations": violations,
            "event_counts": event_counts,
            "stderr_bytes": stderr_path.stat().st_size,
            "usage": usage,
            "wall_seconds": wall,
            "output": output,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "scores": {
                key: scored[key]
                for key in ("syntax_valid", "official_compatible", "target_coverage", "target_strict")
            },
        }
        receipts.append(receipt)
        with receipt_path.open("ab") as stream:
            stream.write(canonical_bytes(receipt))
        print(
            json.dumps(
                {key: receipt[key] for key in ("task_id", "arm", "status", "wall_seconds", "scores")}
            ),
            flush=True,
        )
        if not valid:
            break

    summary = summarize(selection, receipts)
    summary["execution"] = {
        "cli_version": cli_version,
        "retries": 0,
        "timeouts": sum(row["timed_out"] for row in receipts),
        "tool_event_violations": sum(bool(row["violations"]) for row in receipts),
        "nonempty_stderr_files": sum(row["stderr_bytes"] > 0 for row in receipts),
    }
    summary["evidence"] = {
        "selection_sha256": file_sha256(arguments.out / "selection.json"),
        "inputs_sha256": file_sha256(arguments.out / "inputs.jsonl"),
        "receipts_sha256": file_sha256(receipt_path),
    }
    write_atomic(arguments.out / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["status"] == "complete" else 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", choices=("low", "medium", "high"), default=EFFORT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--validate-only", action="store_true")
    arguments = parser.parse_args()
    if not arguments.validate_only and arguments.out is None:
        parser.error("--out is required unless --validate-only is used")
    raise SystemExit(run(arguments))


if __name__ == "__main__":
    main()

