#!/usr/bin/env python3
"""Source-isolated two-family acceptance for evidence-scoped memory admission."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2]
PHASE1 = CORE / "research/memory-battle/zero-feedback-phase1/run_phase1.py"
spec = importlib.util.spec_from_file_location("phase1_runner_cross_family", PHASE1)
phase1 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(phase1)

BASE_ADAPTER = CORE / "research/memory-battle/exp-000-capability-first-reset/past-tdai/hermes_tdai_adapter.py"
TASK = phase1.FAMILY / "EP02_I03_context_noise/task.yaml"
SCHEDULE = ((1, "unadjusted"), (1, "adjusted"), (2, "adjusted"), (2, "unadjusted"))
FAMILIES = {
    "vendor_boreal_en": {
        "source_user": (
            "Vendor Boreal review: production is blocked pending SOC 2. A staging-only pilot is allowed through "
            "2027-03-31. For this ticket only, reply as REVIEW|vendor|decision|expiry."
        ),
        "source_assistant": "REVIEW|Boreal|production-blocked-staging-only|2027-03-31",
        "task_id": "FEEDBACK_V1_VENDOR_BOREAL",
        "target_prompt": (
            "Report the prior Vendor Boreal approval boundary and expiry. Do not modify any integration. "
            "Output exactly ANSWER|production-blocked|staging-only|2027-03-31."
        ),
        "expected": "ANSWER|production-blocked|staging-only|2027-03-31",
        "fact_tokens": ["production-blocked", "staging-only", "2027-03-31"],
        "bounded_marker": "REVIEW|vendor|decision|expiry",
    },
    "aurora_window_zh": {
        "source_user": (
            "极光发布的维护窗口是 2026-10-12 02:00–03:00 UTC。仅限本次工单，"
            "请按 WINDOW|项目|开始时间|结束时间 回复。"
        ),
        "source_assistant": "WINDOW|极光发布|2026-10-12 02:00 UTC|2026-10-12 03:00 UTC",
        "task_id": "FEEDBACK_V1_AURORA_WINDOW",
        "target_prompt": (
            "报告先前极光发布的维护日期及 UTC 起止时间。不要修改任何集成。"
            "仅输出 MAINT|2026-10-12|02:00|03:00。"
        ),
        "expected": "MAINT|2026-10-12|02:00|03:00",
        "fact_tokens": ["2026-10-12", "02:00", "03:00"],
        "bounded_marker": "WINDOW|项目|开始时间|结束时间",
    },
}


def load_adapter():
    adapter_spec = importlib.util.spec_from_file_location("cross_family_base_tdai", BASE_ADAPTER)
    module = importlib.util.module_from_spec(adapter_spec)
    assert adapter_spec.loader is not None
    adapter_spec.loader.exec_module(module)
    return module


def build_anchor(directory: Path, family: dict, adjusted: bool) -> dict:
    home, trace = directory / "home", directory / "trace"
    home.mkdir(parents=True)
    trace.mkdir(parents=True)
    phase1.env(home, trace)
    module = load_adapter()
    sidecar = module.NodeSidecar(trace, time.monotonic() + 300)
    try:
        init = {"homeDir": str(home), "traceDir": str(trace), "taskRunId": "source-extraction",
                "sessionId": f"source-{directory.parent.name}-{directory.name}",
                "model": phase1.MODEL, "recallTopK": 5}
        if adjusted:
            init["admissionPolicy"] = "evidence_scoped_v1"
        sidecar.request("init", **init)
        messages = [
            {"role": "user", "content": family["source_user"]},
            {"role": "assistant", "content": family["source_assistant"]},
        ]
        sidecar.request("capture", messages=messages, userText=family["source_user"],
                        assistantText=family["source_assistant"])
        materialized = sidecar.request("flush")
    finally:
        sidecar.close()
    result = {"arm": "adjusted" if adjusted else "unadjusted", "materialized": materialized}
    phase1.save(directory / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_relative_to(Path("/tmp")) or root.exists():
        raise ValueError("fresh isolated --root below /tmp required")
    root.mkdir(parents=True)
    plan = {
        "schemaVersion": "tdai-cross-family-plan.v1",
        "status": "FIXED_BEFORE_MODEL_DISPATCH",
        "families": FAMILIES,
        "schedule": SCHEDULE,
        "arms": {"unadjusted": "normal extraction", "adjusted": "evidence_scoped_v1 at final draft"},
        "model": phase1.MODEL,
        "productionMemoryActions": 0,
    }
    phase1.save(root / "run-plan.json", plan)
    phase1.fast.install_fast_adapter()
    for family_name, family in FAMILIES.items():
        anchors = {}
        for arm in ("unadjusted", "adjusted"):
            anchor_dir = root / "families" / family_name / "anchors" / arm
            anchors[arm] = build_anchor(anchor_dir, family, arm == "adjusted")
        for block, arm in SCHEDULE:
            phase1.run_episode(
                root / "families" / family_name / "targets" / f"block-{block}-{arm}",
                TASK,
                anchor=root / "families" / family_name / "anchors" / arm / "home",
                capture=False,
                case=family_name,
                task_id=family["task_id"],
                prompt_text=family["target_prompt"],
            )
    print(json.dumps({"status": "MODEL_RUNS_COMPLETE", "root": str(root)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
