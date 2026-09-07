#!/usr/bin/env python3
"""Small real-Qwen apply/no-apply run for the phase-1 scope adjustment."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2]
PHASE1 = CORE / "research/memory-battle/zero-feedback-phase1/run_phase1.py"
spec = importlib.util.spec_from_file_location("phase1_runner", PHASE1)
phase1 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(phase1)

ANCHOR = CORE.parent.parent / ".local-evidence/mainline-2026-09-06/zero-feedback-phase1-r1/anchors/candidate/home"
TASK = phase1.FAMILY / "EP02_I03_context_noise/task.yaml"
BAD_RECORD_CONTENT = "BATCH|approved_ids|blocked_ids"
SCHEDULE = ((1, "unadjusted"), (1, "adjusted"), (2, "adjusted"), (2, "unadjusted"))
TARGETS = {
    "format_conflict": {
        "task_id": "FEEDBACK_V1_FORMAT_CONFLICT",
        "prompt": (
            "Run a new read-only compliance audit of suspended APAC integrations. This is a separate audit: "
            "do not reuse any prior exception or prior output format, and do not modify integrations. "
            "Use the current config service, then output exactly CHECK|<comma-separated integration IDs in service order>."
        ),
    },
    "fact_preservation": {
        "task_id": "FEEDBACK_V1_FACT_PRESERVATION",
        "prompt": (
            "From the prior Wave Cedar operation, report the three integrations that received the session-bounded "
            "restart exception. Do not modify integrations. Output exactly IDS|<comma-separated integration IDs "
            "in the original approved order>."
        ),
    },
}


def load_bad_record() -> dict:
    rows = []
    for file in sorted((ANCHOR / ".tdai/records").glob("*.jsonl")):
        rows.extend(json.loads(line) for line in file.read_text().splitlines() if line.strip())
    matches = [row for row in rows if BAD_RECORD_CONTENT in row.get("content", "")]
    if len(matches) != 1 or matches[0].get("version") != 1:
        raise RuntimeError("expected one current phase-1 spurious format instruction")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_relative_to(Path("/tmp")) or root.exists():
        raise ValueError("fresh isolated --root below /tmp required")
    bad = load_bad_record()
    plan = {
        "schemaVersion": "tdai-native-feedback-two-arm-plan.v1",
        "status": "FIXED_BEFORE_MODEL_DISPATCH",
        "sourceAnchor": str(ANCHOR),
        "adjustmentTarget": {"recordId": bad["id"], "expectedVersion": bad["version"]},
        "arms": {"unadjusted": "all source memories", "adjusted": "pre-retrieval exact mask of spurious instruction"},
        "preservedRecordTypes": ["episodic"],
        "targets": TARGETS,
        "schedule": SCHEDULE,
        "model": phase1.MODEL,
        "runtimeFeedbackInputs": ["taskRunId", "tool result contracts", "host objective validators"],
        "productionMemoryActions": 0,
    }
    root.mkdir(parents=True)
    phase1.save(root / "run-plan.json", plan)
    phase1.fast.install_fast_adapter()
    for target_name, target in TARGETS.items():
        for block, arm in SCHEDULE:
            directory = root / "targets" / target_name / f"block-{block}-{arm}"
            treatment = plan["adjustmentTarget"] if arm == "adjusted" else None
            phase1.run_episode(
                directory,
                TASK,
                anchor=ANCHOR,
                capture=False,
                case=target_name,
                task_id=target["task_id"],
                prompt_text=target["prompt"],
                treatment=treatment,
            )
    print(json.dumps({"status": "MODEL_RUNS_COMPLETE", "root": str(root)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
