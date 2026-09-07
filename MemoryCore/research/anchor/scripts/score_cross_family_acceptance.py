#!/usr/bin/env python3
"""Deterministic scorer for the source-isolated cross-family acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    plan = load(root / "run-plan.json")
    rows = []
    admission = []
    extraction_costs = {"unadjusted": {"calls": 0, "totalTokens": 0, "wallMs": 0.0},
                        "adjusted": {"calls": 0, "totalTokens": 0, "wallMs": 0.0}}
    for family_name, family in plan["families"].items():
        for arm in ("unadjusted", "adjusted"):
            anchor = load(root / "families" / family_name / "anchors" / arm / "result.json")
            records = anchor["materialized"]["records"]
            instructions = [row for row in records if row["type"] == "instruction"]
            marker_leaks = [row["record_id"] for row in instructions
                            if family["bounded_marker"] in row["content"]]
            any_marker_leaks = [row["record_id"] for row in records
                                if family["bounded_marker"] in row["content"]]
            extraction_rows = [json.loads(line) for line in
                               (root / "families" / family_name / "anchors" / arm /
                                "trace/extraction-model.jsonl").read_text().splitlines() if line.strip()]
            for extraction in extraction_rows:
                usage = extraction.get("response", {}).get("usage", {})
                extraction_costs[arm]["calls"] += 1
                extraction_costs[arm]["totalTokens"] += usage.get("total_tokens", 0)
                extraction_costs[arm]["wallMs"] += extraction.get("wallTimeMs", 0)
            admission.append({"family": family_name, "arm": arm, "records": len(records),
                              "instructions": len(instructions), "boundedInstructionLeaks": marker_leaks,
                              "boundedMarkerInAnyRecord": any_marker_leaks})
        for block, arm in plan["schedule"]:
            result = load(root / "families" / family_name / "targets" / f"block-{block}-{arm}" / "result.json")
            final = (result.get("final") or "").strip()
            semantic = all(token in final for token in family["fact_tokens"])
            exact = final == family["expected"]
            rows.append({"family": family_name, "block": block, "arm": arm, "final": final,
                         "semanticFactsCorrect": semantic, "exactOutput": exact,
                         "noMutations": len(result["audit"].get("updates", [])) == 0,
                         "cost": result["cost"]})
    metrics = {}
    for arm in ("unadjusted", "adjusted"):
        selected = [row for row in rows if row["arm"] == arm]
        calls = sum(row["cost"]["calls"] for row in selected)
        tokens = sum(row["cost"]["input_tokens"] + row["cost"]["output_tokens"] for row in selected)
        metrics[arm] = {"exact": sum(row["exactOutput"] for row in selected), "total": len(selected),
                        "semanticFactsCorrect": sum(row["semanticFactsCorrect"] for row in selected),
                        "severeRegressions": sum(not row["noMutations"] for row in selected),
                        "targetCalls": calls, "targetTokens": tokens,
                        "extractionCalls": extraction_costs[arm]["calls"],
                        "extractionTokens": extraction_costs[arm]["totalTokens"],
                        "lifecycleCalls": calls + extraction_costs[arm]["calls"],
                        "lifecycleTokens": tokens + extraction_costs[arm]["totalTokens"],
                        "extractionWallMs": extraction_costs[arm]["wallMs"]}
    metrics["adjustedAdmission"] = {
        "familiesWithoutBoundedInstruction": sum(not row["boundedInstructionLeaks"] for row in admission
                                                   if row["arm"] == "adjusted"),
        "familiesWithoutMarkerInAnyRecord": sum(not row["boundedMarkerInAnyRecord"] for row in admission
                                                  if row["arm"] == "adjusted"),
        "totalFamilies": len(plan["families"]),
    }
    output = {"schemaVersion": "tdai-cross-family-result.v1", "rows": rows,
              "admission": admission, "metrics": metrics, "productionMemoryActions": 0}
    (root / "result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
