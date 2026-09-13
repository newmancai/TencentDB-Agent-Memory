"""Direct vs two-stage dependency bridge on a new balanced STALE holdout."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time


MODEL = "gpt-5.6-sol"
REASONING = "medium"
SEED = "topic3-b-stale-bridge-v1:"
EXCLUDED = {
    "6e8a7e72-3158-4676-9aa4-a4ce492015fd", "9ce11bb3-9680-4e92-86fc-5f450d36405b",
    "cc9aaa40-77d3-47f7-8551-8e216bb47887", "f5a0a3c8-4300-4b37-a45b-8584af2be8f2",
    "f50107f1-364f-4c07-bdd6-bf144c6da875", "7b568b27-c87a-4a93-9596-e65478544681",
    "f57e6cfd-16a4-47b8-ab87-1b50838580e9", "11e0c473-dbd3-4645-964a-86affc5f998d",
}
NEGATIVE_RATIONALES = {
    "284d2ed9-8551-444a-8b97-d230cd144967": "Location-sharing permission and meditation duration can both remain true.",
    "872d8b8c-24f3-4472-a6e3-a7e42d04ff40": "Meditation duration and house ownership can both remain true.",
    "e1703b4d-f093-43cf-8003-75f8949c69d0": "House-insurance status and a knee-limited exercise routine can both remain true.",
    "0c199bef-29ae-489f-b772-af9a43d6eb0e": "Running routine and location-sharing permission can both remain true.",
    "830a2e06-981f-411c-bef0-99ec4190fbfa": "Residential altitude and a knee-limited exercise routine can both remain true.",
    "36da4cf0-035a-41fc-aae1-5080fe2e2460": "Relationship status and house ownership can both remain true.",
    "26910318-c4ce-431f-8b6f-8eaad3ffd8b8": "Snow persistence and meditation duration can both remain true.",
    "6f69a06e-01a9-442e-927b-70f40d6cc8f3": "Credit score and location-sharing permission can both remain true.",
}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "had", "has", "have", "i", "in", "into", "is", "it", "my", "no", "not", "of",
    "on", "or", "so", "that", "the", "their", "they", "this", "to", "was", "were",
    "with", "you", "your",
}


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_rows(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))


def read_rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prepare(parquet: Path, out: Path) -> None:
    import pyarrow.parquet as pq

    source = pq.read_table(parquet, columns=["uid", "M_old", "M_new", "explanation", "type"]).to_pylist()
    selected = {
        kind: sorted((row for row in source if row["type"] == kind and row["uid"] not in EXCLUDED),
                     key=lambda row: hashlib.sha256((SEED + row["uid"]).encode()).hexdigest())[:4]
        for kind in ("T1", "T2")
    }
    if any(len(values) != 4 for values in selected.values()):
        raise ValueError("expected four new rows per type")
    if set().union(*(set(row["uid"] for row in values) for values in selected.values())) & EXCLUDED:
        raise ValueError("holdout overlaps direct-binder set")

    out.mkdir(parents=True, exist_ok=False)
    tasks, labels, audit = [], [], []
    for kind in ("T1", "T2"):
        for index, row in enumerate(selected[kind]):
            positive = f"{row['uid']}:positive"
            tasks.append({"id": positive, "old_observation": row["M_old"], "later_observation": row["M_new"]})
            labels.append({"id": positive, "action": "supersede", "kind": kind,
                           "source_uid": row["uid"], "explanation": row["explanation"]})
            paired = selected["T1"][(index + 1) % 4] if kind == "T1" else selected["T1"][3 - index]
            negative = f"{row['uid']}:negative"
            tasks.append({"id": negative, "old_observation": row["M_old"],
                          "later_observation": paired["M_new"]})
            labels.append({"id": negative, "action": "retain", "kind": f"{kind}_negative",
                           "source_uid": row["uid"], "paired_later_uid": paired["uid"]})
            audit.append({"id": negative, "source_uid": row["uid"], "paired_later_uid": paired["uid"],
                          "label": "retain", "audit": NEGATIVE_RATIONALES[row["uid"]],
                          "audited_before_inference": True})
    write_rows(out / "tasks.jsonl", tasks)
    write_rows(out / "labels.private.jsonl", labels)
    dump(out / "negative-audit.json", audit)
    dump(out / "selection.json", {
        "protocol": "topic3-b-stale-bridge-v1", "excluded_positive_uids": sorted(EXCLUDED),
        "selected": {kind: [row["uid"] for row in values] for kind, values in selected.items()},
        "positive_pairs": 8, "negative_pairs": 8,
        "selection": "exclude v1; four per type by SHA256(topic3-b-stale-bridge-v1:+uid)",
        "negative_pairing": "T1 next-index T1 later; T2 reverse-index T1 later",
    })


DIRECT_INSTRUCTION = """Decide whether a later user observation makes an older memory unsafe to use as current.
Return supersede only when the later observation directly conflicts with the old memory or necessarily invalidates it through a clear commonsense dependency. Return retain when both can remain true. Return ask when evidence is insufficient.
For supersede, evidence_quote must be a non-empty exact substring of later_observation supporting the update. For retain or ask, evidence_quote must be an empty string. Do not browse or call tools. Return only JSON matching the schema.
"""

PROPOSER_INSTRUCTION = """Analyze how a later user observation changes practical state and which exact basis of an older memory might be affected. This is candidate-scope expansion, not a final invalidation decision.
Return zero or more bounded dependency paths. Mark a path necessary only when the later condition makes the old current-default unsafe; possible when it merely raises a question; none when both can coexist. Shared topic alone is not a dependency. Every path evidence_quote must be an exact substring of later_observation. Do not browse or call tools. Return only JSON matching the schema.
"""

JUDGE_INSTRUCTION = """Make the final high-precision memory decision using the chronological observations and an untrusted dependency proposal. The proposal may be wrong.
Return supersede only when an exact old current-default has lost safety through a direct conflict or a necessary practical dependency. Return retain when both observations can remain true. Return ask only when the old default is genuinely unresolved. Broad implication, topic drift, and merely possible paths are insufficient.
For supersede, evidence_quote must be a non-empty exact substring of later_observation. For retain or ask it must be empty. Do not browse or call tools. Return only JSON matching the schema.
"""


def pair(task: dict) -> dict:
    return {"old_observation": task["old_observation"], "later_observation": task["later_observation"]}


def direct_prompt(task: dict) -> str:
    return DIRECT_INSTRUCTION + "\n" + json.dumps(pair(task), ensure_ascii=False)


def proposer_prompt(task: dict) -> str:
    return PROPOSER_INSTRUCTION + "\n" + json.dumps(pair(task), ensure_ascii=False)


def judge_prompt(task: dict, proposal: dict) -> str:
    return JUDGE_INSTRUCTION + "\n" + json.dumps({**pair(task), "dependency_proposal": proposal}, ensure_ascii=False)


def call(out: Path, empty: Path, schema: Path, stem: str, prompt: str) -> dict:
    message = out / "raw" / f"{stem}.message.json"
    started = time.perf_counter()
    run = subprocess.run([
        "codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"',
        "--sandbox", "read-only", "-C", str(empty.resolve()), "--skip-git-repo-check",
        "--ephemeral", "--ignore-user-config", "--ignore-rules", "--output-schema",
        str(schema.resolve()), "--json", "--output-last-message", str(message.resolve()), "-",
    ], input=prompt, text=True, capture_output=True, timeout=300)
    wall = time.perf_counter() - started
    (out / "raw" / f"{stem}.events.jsonl").write_text(run.stdout)
    (out / "raw" / f"{stem}.stderr.txt").write_text(run.stderr)
    parsed = None
    try:
        parsed = json.loads(message.read_text())
    except Exception:
        pass
    usage = None
    for line in run.stdout.splitlines():
        event = json.loads(line)
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
    return {"returncode": run.returncode, "wall_seconds": wall, "output": parsed, "usage": usage}


def infer(out: Path) -> None:
    tasks = read_rows(out / "tasks.jsonl")
    (out / "raw").mkdir()
    empty = out / "empty-workdir"
    empty.mkdir()
    action_schema = out / "action-schema.json"
    proposal_schema = out / "proposal-schema.json"
    dump(action_schema, {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["supersede", "retain", "ask"]},
        "evidence_quote": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["action", "evidence_quote", "reason"], "additionalProperties": False})
    dump(proposal_schema, {"type": "object", "properties": {
        "changed_basis": {"type": "string"},
        "paths": {"type": "array", "items": {"type": "object", "properties": {
            "affected_old_basis": {"type": "string"},
            "relation": {"type": "string", "enum": ["necessary", "possible", "none"]},
            "evidence_quote": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["affected_old_basis", "relation", "evidence_quote", "reason"],
            "additionalProperties": False}}},
        "required": ["changed_basis", "paths"], "additionalProperties": False})
    receipts, inputs = [], []
    for task in tasks:
        stem = task["id"].replace(":", "-")
        direct = direct_prompt(task)
        inputs.append({"id": task["id"], "stage": "direct", "prompt": direct})
        direct_receipt = call(out, empty, action_schema, f"{stem}-direct", direct)
        proposal_text = proposer_prompt(task)
        inputs.append({"id": task["id"], "stage": "bridge_proposer", "prompt": proposal_text})
        proposal_receipt = call(out, empty, proposal_schema, f"{stem}-proposer", proposal_text)
        proposal = proposal_receipt["output"] if isinstance(proposal_receipt["output"], dict) else {"changed_basis": "", "paths": []}
        judge_text = judge_prompt(task, proposal)
        inputs.append({"id": task["id"], "stage": "bridge_judge", "prompt": judge_text})
        judge_receipt = call(out, empty, action_schema, f"{stem}-judge", judge_text)
        receipts.append({"id": task["id"], "direct": direct_receipt,
                         "bridge_proposer": proposal_receipt, "bridge_judge": judge_receipt})
        write_rows(out / "inputs.jsonl", inputs)
        write_rows(out / "receipts.jsonl", receipts)
        print(task["id"], "direct", direct_receipt["output"] and direct_receipt["output"].get("action"),
              "bridge", judge_receipt["output"] and judge_receipt["output"].get("action"), flush=True)


def content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS and len(token) > 2}


def quantile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def valid_action(receipt: dict, task: dict):
    output = receipt["output"] if isinstance(receipt.get("output"), dict) else {}
    action, quote = output.get("action"), output.get("evidence_quote")
    shape = action in {"supersede", "retain", "ask"} and isinstance(quote, str)
    quote_ok = shape and ((action == "supersede" and bool(quote) and quote in task["later_observation"])
                          or (action != "supersede" and quote == ""))
    return action if shape else "invalid", bool(quote_ok)


def arm_metrics(arm: str, receipts: list[dict], tasks: dict, labels: dict):
    stage = "direct" if arm == "direct" else "bridge_judge"
    rows, invalid_spans = [], 0
    for receipt in receipts:
        task, label = tasks[receipt["id"]], labels[receipt["id"]]
        action, quote_ok = valid_action(receipt[stage], task)
        correct = receipt[stage]["returncode"] == 0 and quote_ok and action == label["action"]
        if action == "supersede" and not quote_ok:
            invalid_spans += 1
        rows.append({"id": receipt["id"], "kind": label["kind"], "gold": label["action"],
                     "prediction": action, "quote_valid": quote_ok, "correct": correct})
    positives = [row for row in rows if row["gold"] == "supersede"]
    negatives = [row for row in rows if row["gold"] == "retain"]
    return {
        "overall": {"correct": sum(row["correct"] for row in rows), "total": len(rows)},
        "positive": {"correct": sum(row["correct"] for row in positives), "total": len(positives)},
        "t1_positive": {"correct": sum(row["correct"] for row in positives if row["kind"] == "T1"), "total": 4},
        "t2_positive": {"correct": sum(row["correct"] for row in positives if row["kind"] == "T2"), "total": 4},
        "negative": {"correct": sum(row["correct"] for row in negatives), "total": len(negatives)},
        "predictions": dict(Counter(row["prediction"] for row in rows)),
        "invalid_span_predictions": invalid_spans,
        "rows": rows,
    }


def score(out: Path) -> None:
    tasks = {row["id"]: row for row in read_rows(out / "tasks.jsonl")}
    labels = {row["id"]: row for row in read_rows(out / "labels.private.jsonl")}
    receipts = read_rows(out / "receipts.jsonl")
    if len(receipts) != 16 or {row["id"] for row in receipts} != set(tasks):
        raise ValueError("expected sixteen complete task receipts")
    direct = arm_metrics("direct", receipts, tasks, labels)
    bridge = arm_metrics("bridge", receipts, tasks, labels)
    paired = Counter()
    for left, right in zip(direct["rows"], bridge["rows"]):
        paired["win" if right["correct"] and not left["correct"] else
               "loss" if left["correct"] and not right["correct"] else "tie"] += 1
    usage_keys = ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]
    costs = {}
    for name, stages in {"direct": ["direct"], "bridge": ["bridge_proposer", "bridge_judge"]}.items():
        parts = [receipt[stage] for receipt in receipts for stage in stages]
        wall = [part["wall_seconds"] for part in parts]
        costs[name] = {
            "calls": len(parts),
            "usage": {key: sum((part.get("usage") or {}).get(key, 0) for part in parts) for key in usage_keys},
            "wall_seconds": {"sum": sum(wall), "p50_per_call": quantile(wall, .5), "p95_per_call": quantile(wall, .95)},
        }
    surface = sum((bool(content_tokens(task["old_observation"]) & content_tokens(task["later_observation"]))
                   == (labels[task_id]["action"] == "supersede")) for task_id, task in tasks.items())
    pass_ = (bridge["overall"]["correct"] >= 14 and bridge["positive"]["correct"] >= 7
             and bridge["t2_positive"]["correct"] >= 3 and bridge["negative"]["correct"] >= 7
             and bridge["invalid_span_predictions"] == 0
             and bridge["t2_positive"]["correct"] > direct["t2_positive"]["correct"]
             and bridge["negative"]["correct"] >= direct["negative"]["correct"] - 1)
    summary = {
        "protocol": "topic3-b-stale-bridge-v1", "model": MODEL, "reasoning_effort": REASONING,
        "tasks": 16, "calls": 48,
        "completed": sum(part["returncode"] == 0 and isinstance(part["output"], dict)
                         for receipt in receipts for part in receipt.values() if isinstance(part, dict)),
        "direct": {key: value for key, value in direct.items() if key != "rows"},
        "bridge": {key: value for key, value in bridge.items() if key != "rows"},
        "paired_bridge_vs_direct": dict(paired),
        "baselines": {"always_supersede": {"correct": 8, "total": 16},
                      "always_retain": {"correct": 8, "total": 16},
                      "surface_any_content_token_overlap": {"correct": surface, "total": 16}},
        "cost": costs, "pass": pass_,
        "scope": "New STALE component holdout; bridge adds a structured reasoning call but no source evidence or labels. Not downstream probe quality, durable promotion, or production.",
    }
    dump(out / "score.json", {"summary": summary, "direct_rows": direct["rows"], "bridge_rows": bridge["rows"]})
    dump(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "infer", "score"])
    parser.add_argument("--parquet", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        if not args.parquet:
            parser.error("prepare requires --parquet")
        prepare(args.parquet, args.out)
    elif args.action == "infer":
        infer(args.out)
    else:
        score(args.out)


if __name__ == "__main__":
    main()
