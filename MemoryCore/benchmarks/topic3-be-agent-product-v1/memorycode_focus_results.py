#!/usr/bin/env python3
"""Recompute MemoryCode focus quality and separate cold from reusable stage cost."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memorycode_focus import (
    RAW_ARM,
    file_sha256,
    read_jsonl,
    receipt_scores,
    summarize,
    write_atomic,
)


def analyze_run(packets_path: Path, run_root: Path) -> dict[str, Any]:
    packets = read_jsonl(packets_path)
    receipts_path = run_root / "receipts.jsonl"
    receipts = read_jsonl(receipts_path)
    original = json.loads((run_root / "summary.json").read_text())
    receipt_task_ids = {row["task_id"] for row in receipts}
    selected_packets = [
        packet for packet in packets if packet["task_id"] in receipt_task_ids
    ]
    focus_arms = sorted({row["arm"] for row in receipts} - {RAW_ARM})
    if len(focus_arms) != 1:
        raise ValueError(f"run must contain one focus arm: {run_root}")
    focus_arm = focus_arms[0]
    packets_by_id = {packet["task_id"]: packet for packet in packets}
    if len(packets_by_id) != len(packets):
        raise ValueError("packets must have unique task IDs")

    rescored = []
    for receipt in receipts:
        packet = packets_by_id.get(receipt["task_id"])
        if packet is None:
            raise ValueError(f"receipt task missing from packets: {receipt['task_id']}")
        row = dict(receipt)
        row["scores"] = receipt_scores(
            packet,
            receipt["output"],
            receipt["status"] == "passed",
        )
        rescored.append(row)

    result = summarize(
        selected_packets,
        rescored,
        focus_arm=focus_arm,
        protocol=original["protocol"],
    )
    result["cli_version"] = original.get("cli_version")
    result["evidence"] = {
        "packets_sha256": file_sha256(packets_path),
        "receipts_sha256": file_sha256(receipts_path),
        **{
            key: value
            for key, value in original.get("evidence", {}).items()
            if key != "receipts_sha256"
        },
    }
    expected_receipts_hash = original.get("evidence", {}).get("receipts_sha256")
    if (
        expected_receipts_hash
        and expected_receipts_hash != result["evidence"]["receipts_sha256"]
    ):
        raise ValueError(f"receipt hash changed: {run_root}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-packets", type=Path, required=True)
    parser.add_argument("--v1-run", type=Path, required=True)
    parser.add_argument("--v2-packets", type=Path, required=True)
    parser.add_argument("--v2-run", type=Path, required=True)
    parser.add_argument("--compact-pilot", type=Path, required=True)
    parser.add_argument("--cached-pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    development = analyze_run(arguments.v1_packets, arguments.v1_run)
    confirmation = analyze_run(arguments.v2_packets, arguments.v2_run)
    compact = analyze_run(arguments.v2_packets, arguments.compact_pilot)
    cached = analyze_run(arguments.v2_packets, arguments.cached_pilot)
    result = {
        "schema": 1,
        "protocol": "memorycode-focus-quality-and-infra-results-v1",
        "quality": {
            "development_v1": development,
            "disjoint_confirmation_v2": confirmation,
        },
        "infra": {
            "quality_anchor": "disjoint_confirmation_v2",
            "persisted_compiler_projection": confirmation["infra"],
            "rejected_compact_pilot": compact,
            "rejected_independent_cli_prefix_cache_pilot": cached,
            "decision": (
                "persist compiled guidelines by exact history revision; do not remove raw "
                "history from the coding call and do not rely on cache reuse across independent "
                "Codex CLI processes"
            ),
        },
        "claim_boundary": (
            "public synthetic development plus one disjoint confirmation set; warm costs are "
            "stage decomposition, not a dollar-price estimate or production SLO"
        ),
    }
    write_atomic(arguments.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
