#!/usr/bin/env python3
"""Recompute the bounded MemoryCode AI-infra optimization results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memorycode_focus import (
    RAW_ARM,
    authoritative_history,
    history_only,
    read_jsonl,
    write_atomic,
)
from memorycode_focus_results import analyze_run


SELF_ARM = "self_focus_raw"
SOURCE_ARM = "focus_source_raw"
COST_KEYS = ("input_tokens", "noncached_input_tokens", "wall_seconds", "model_calls")


def aggregate_cost(runs: list[dict[str, Any]], arm: str) -> dict[str, float | int]:
    keys = (*COST_KEYS, "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
    return {key: sum(run["cost"][arm][key] for run in runs) for key in keys}


def ratio(
    numerator: dict[str, float | int], denominator: dict[str, float | int]
) -> dict[str, float | None]:
    return {
        key: numerator[key] / denominator[key] if denominator[key] else None
        for key in COST_KEYS
    }


def source_history_audit(packet_paths: list[Path]) -> dict[str, Any]:
    packets = [packet for path in packet_paths for packet in read_jsonl(path)]
    task_ids = [packet["task_id"] for packet in packets]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("history audit packets must have unique task IDs")

    raw_bytes = sum(len(history_only(packet).encode()) for packet in packets)
    source_bytes = sum(len(authoritative_history(packet).encode()) for packet in packets)
    by_sessions: dict[str, dict[str, int | float]] = {}
    for count in sorted({packet["session_count"] for packet in packets}):
        group = [packet for packet in packets if packet["session_count"] == count]
        group_raw = sum(len(history_only(packet).encode()) for packet in group)
        group_source = sum(len(authoritative_history(packet).encode()) for packet in group)
        by_sessions[str(count)] = {
            "tasks": len(group),
            "raw_history_bytes": group_raw,
            "source_history_bytes": group_source,
            "source_raw_ratio": group_source / group_raw,
        }
    return {
        "tasks": len(packets),
        "raw_history_bytes": raw_bytes,
        "source_history_bytes": source_bytes,
        "source_raw_ratio": source_bytes / raw_bytes,
        "byte_reduction_fraction": 1 - source_bytes / raw_bytes,
        "by_session_count": by_sessions,
        "boundary": (
            "deterministic UTF-8 history bytes before model tokenization; every mentor turn "
            "is preserved verbatim and mentee turns are omitted"
        ),
    }


def self_pilot_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    raw = aggregate_cost(runs, RAW_ARM)
    focused = aggregate_cost(runs, SELF_ARM)
    pairs = [pair for run in runs for pair in run["quality"]["pairs"]]
    active_pairs = [
        pair for run in runs for pair in run["quality"]["active_rule_semantic_paired"]["pairs"]
    ]
    absolute_targets = {pair["task_id"]: pair[SELF_ARM] for pair in pairs}
    gates = {
        "all_self_targets_one": all(score == 1 for score in absolute_targets.values()),
        "no_target_regression": all(pair["delta"] >= 0 for pair in pairs),
        "no_active_rule_regression": all(pair["delta"] >= 0 for pair in active_pairs),
        "one_call_per_arm_and_task": raw["model_calls"] == focused["model_calls"] == len(runs),
        "aggregate_noncached_input_at_most_1_05x_raw": (
            focused["noncached_input_tokens"] <= 1.05 * raw["noncached_input_tokens"]
        ),
    }
    return {
        "completed_tasks": [pair["task_id"] for pair in pairs],
        "planned_task_not_run_after_hard_failure": "memorycode-206",
        "target_pairs": pairs,
        "active_rule_pairs": active_pairs,
        "cost": {RAW_ARM: raw, SELF_ARM: focused},
        "ratio_vs_raw": ratio(focused, raw),
        "gates": gates,
        "passed": all(gates.values()),
        "decision": (
            "stop after the second exposed pilot task; do not select or run a new confirmation set"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-packets", type=Path, action="append", required=True)
    parser.add_argument("--source-packets", type=Path, required=True)
    parser.add_argument("--source-pilot", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--self-339-packets", type=Path, required=True)
    parser.add_argument("--self-339-run", type=Path, required=True)
    parser.add_argument("--self-300-packets", type=Path, required=True)
    parser.add_argument("--self-300-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    source_pilot = analyze_run(arguments.self_300_packets, arguments.source_pilot)
    source_confirmation = analyze_run(arguments.source_packets, arguments.source_run)
    self_runs = [
        analyze_run(arguments.self_339_packets, arguments.self_339_run),
        analyze_run(arguments.self_300_packets, arguments.self_300_run),
    ]
    source_gates = {
        "all_calls_valid": source_confirmation["status"] == "complete",
        "zero_target_regressions": source_confirmation["quality"]["losses"] == 0,
        "warm_noncached_input_below_raw": (
            source_confirmation["infra"]["warm_ratio_vs_raw"]["noncached_input_tokens"] < 1
        ),
    }
    result = {
        "schema": 1,
        "protocol": "memorycode-ai-infra-optimization-results-v1",
        "authoritative_source_context": {
            "history_audit": source_history_audit(arguments.audit_packets),
            "exposed_pilot": source_pilot,
            "disjoint_confirmation": source_confirmation,
            "promotion_gates": source_gates,
            "promoted": all(source_gates.values()),
            "decision": (
                "keep off by default: warm non-cached input fell, but the frozen primary "
                "confirmation contained one win and one loss"
            ),
        },
        "single_pass_self_focus": self_pilot_summary(self_runs),
        "accepted_optimization": (
            "persist the two-stage compiler result by exact history revision and reuse it off "
            "the coding hot path; neither new prompt/context shortcut passed its frozen gate"
        ),
        "claim_boundary": (
            "public synthetic MemoryCode method evidence; model wall time is noisy, history-byte "
            "audit precedes tokenization, and no result is a production SLO or dollar-cost claim"
        ),
    }
    write_atomic(arguments.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
