"""Candidate-only dependency expansion on a fresh balanced STALE holdout."""
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
SEED = "topic3-b-stale-candidate-v1:"
EXCLUDED = {
    "6e8a7e72-3158-4676-9aa4-a4ce492015fd", "9ce11bb3-9680-4e92-86fc-5f450d36405b",
    "cc9aaa40-77d3-47f7-8551-8e216bb47887", "f5a0a3c8-4300-4b37-a45b-8584af2be8f2",
    "f50107f1-364f-4c07-bdd6-bf144c6da875", "7b568b27-c87a-4a93-9596-e65478544681",
    "f57e6cfd-16a4-47b8-ab87-1b50838580e9", "11e0c473-dbd3-4645-964a-86affc5f998d",
    "284d2ed9-8551-444a-8b97-d230cd144967", "872d8b8c-24f3-4472-a6e3-a7e42d04ff40",
    "e1703b4d-f093-43cf-8003-75f8949c69d0", "0c199bef-29ae-489f-b772-af9a43d6eb0e",
    "830a2e06-981f-411c-bef0-99ec4190fbfa", "36da4cf0-035a-41fc-aae1-5080fe2e2460",
    "26910318-c4ce-431f-8b6f-8eaad3ffd8b8", "6f69a06e-01a9-442e-927b-70f40d6cc8f3",
}
NEGATIVE_RATIONALES = {
    "4ed6936e-58e4-40c9-83e7-743bb7ff7bbb": "Clean-up planning and political identification can both remain true.",
    "3125238e-b0a5-4162-9cb9-e893f5f60531": "Political identification and online-forum responsibility can both remain true.",
    "93a1c511-92d3-4d00-b714-4f27096df346": "Forum responsibility and residential moves can both remain true.",
    "a4b2e2fd-b0c4-4529-98f7-c00a658f0d70": "Residential stability and newborn care can both remain true.",
    "19bb9fc3-a962-4055-bf8f-e3b194fcf7d3": "Weekly socializing and residential moves can both remain true.",
    "47911ef2-a067-4c92-acc0-fe0de42666d9": "Student status and online-forum responsibility can both remain true.",
    "d586678b-29de-4aae-82fd-7dec44fde9ec": "Hand-tool use and political identification can both remain true.",
    "36d4a45d-833a-4f1b-a3bf-4f47a729eba0": "Vehicle ownership and newborn care can both remain true.",
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
    out.mkdir(parents=True, exist_ok=False)
    tasks, labels, audit = [], [], []
    for kind in ("T1", "T2"):
        for index, row in enumerate(selected[kind]):
            positive = f"{row['uid']}:positive"
            tasks.append({"id": positive, "old_observation": row["M_old"], "later_observation": row["M_new"]})
            labels.append({"id": positive, "affected": True, "kind": kind,
                           "source_uid": row["uid"], "explanation": row["explanation"]})
            paired = selected["T1"][(index + 1) % 4] if kind == "T1" else selected["T1"][3 - index]
            negative = f"{row['uid']}:negative"
            tasks.append({"id": negative, "old_observation": row["M_old"],
                          "later_observation": paired["M_new"]})
            labels.append({"id": negative, "affected": False, "kind": f"{kind}_negative",
                           "source_uid": row["uid"], "paired_later_uid": paired["uid"]})
            audit.append({"id": negative, "label": "unaffected", "audit": NEGATIVE_RATIONALES[row["uid"]],
                          "source_uid": row["uid"], "paired_later_uid": paired["uid"],
                          "audited_before_inference": True})
    if any(len(values) != 4 for values in selected.values()) or set(row["uid"] for values in selected.values() for row in values) & EXCLUDED:
        raise ValueError("selection contract failed")
    write_rows(out / "tasks.jsonl", tasks)
    write_rows(out / "labels.private.jsonl", labels)
    dump(out / "negative-audit.json", audit)
    dump(out / "selection.json", {
        "protocol": "topic3-b-stale-candidate-v1", "excluded_positive_uids": sorted(EXCLUDED),
        "selected": {kind: [row["uid"] for row in values] for kind, values in selected.items()},
        "positive_pairs": 8, "negative_pairs": 8,
        "selection": "exclude prior sixteen; four per type by SHA256(topic3-b-stale-candidate-v1:+uid)",
        "negative_pairing": "T1 next-index T1 later; T2 reverse-index T1 later",
    })


INSTRUCTION = """Identify whether a later user observation creates any direct or indirect reason to revisit an exact basis in an older memory. This is candidate-scope expansion, not a deletion decision.
Return zero or more bounded dependency paths. Mark a path necessary when the old current-default is no longer safe, possible when the later change gives a concrete reason to verify it, and none only to explain an apparent but irrelevant connection. Shared topic alone is not a dependency. Every necessary or possible path must quote a non-empty exact substring of later_observation. Do not browse or call tools. Return only JSON matching the schema.
"""


def prompt(task: dict) -> str:
    pair = {"old_observation": task["old_observation"], "later_observation": task["later_observation"]}
    return INSTRUCTION + "\n" + json.dumps(pair, ensure_ascii=False)


def infer(out: Path) -> None:
    tasks = read_rows(out / "tasks.jsonl")
    (out / "raw").mkdir()
    empty = out / "empty-workdir"
    empty.mkdir()
    schema = out / "output-schema.json"
    dump(schema, {"type": "object", "properties": {
        "changed_basis": {"type": "string"},
        "paths": {"type": "array", "items": {"type": "object", "properties": {
            "affected_old_basis": {"type": "string"},
            "relation": {"type": "string", "enum": ["necessary", "possible", "none"]},
            "evidence_quote": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["affected_old_basis", "relation", "evidence_quote", "reason"],
            "additionalProperties": False}}},
        "required": ["changed_basis", "paths"], "additionalProperties": False})
    write_rows(out / "inputs.jsonl", ({"id": task["id"], "prompt": prompt(task)} for task in tasks))
    receipts = []
    for task in tasks:
        stem = task["id"].replace(":", "-")
        message = out / "raw" / f"{stem}.message.json"
        started = time.perf_counter()
        run = subprocess.run([
            "codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"',
            "--sandbox", "read-only", "-C", str(empty.resolve()), "--skip-git-repo-check",
            "--ephemeral", "--ignore-user-config", "--ignore-rules", "--output-schema",
            str(schema.resolve()), "--json", "--output-last-message", str(message.resolve()), "-",
        ], input=prompt(task), text=True, capture_output=True, timeout=300)
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
        receipts.append({"id": task["id"], "returncode": run.returncode, "wall_seconds": wall,
                         "output": parsed, "usage": usage})
        write_rows(out / "receipts.jsonl", receipts)
        print(task["id"], run.returncode, flush=True)


def content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS and len(token) > 2}


def quantile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def score(out: Path) -> None:
    tasks = {row["id"]: row for row in read_rows(out / "tasks.jsonl")}
    labels = {row["id"]: row for row in read_rows(out / "labels.private.jsonl")}
    receipts = read_rows(out / "receipts.jsonl")
    if len(receipts) != 16 or {row["id"] for row in receipts} != set(tasks):
        raise ValueError("expected sixteen complete receipts")
    rows, invalid_quotes = [], 0
    for receipt in receipts:
        task, label = tasks[receipt["id"]], labels[receipt["id"]]
        output = receipt["output"] if isinstance(receipt.get("output"), dict) else {}
        paths = output.get("paths") if isinstance(output.get("paths"), list) else []
        active = [path for path in paths if isinstance(path, dict) and path.get("relation") in {"necessary", "possible"}]
        quote_ok = all(isinstance(path.get("evidence_quote"), str) and path["evidence_quote"]
                       and path["evidence_quote"] in task["later_observation"] for path in active)
        predicted = bool(active)
        valid = receipt["returncode"] == 0 and isinstance(receipt.get("output"), dict) and quote_ok
        correct = valid and predicted == label["affected"]
        invalid_quotes += int(bool(active) and not quote_ok)
        rows.append({"id": receipt["id"], "kind": label["kind"], "gold_affected": label["affected"],
                     "predicted_affected": predicted, "active_paths": len(active),
                     "quote_valid": quote_ok, "correct": correct})
    positives = [row for row in rows if row["gold_affected"]]
    negatives = [row for row in rows if not row["gold_affected"]]
    overall = sum(row["correct"] for row in rows)
    positive = sum(row["correct"] for row in positives)
    t1 = sum(row["correct"] for row in positives if row["kind"] == "T1")
    t2 = sum(row["correct"] for row in positives if row["kind"] == "T2")
    negative = sum(row["correct"] for row in negatives)
    surface = sum((bool(content_tokens(task["old_observation"]) & content_tokens(task["later_observation"]))
                   == labels[task_id]["affected"]) for task_id, task in tasks.items())
    usage_keys = ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]
    wall = [receipt["wall_seconds"] for receipt in receipts]
    summary = {
        "protocol": "topic3-b-stale-candidate-v1", "model": MODEL, "reasoning_effort": REASONING,
        "calls": 16,
        "completed": sum(receipt["returncode"] == 0 and isinstance(receipt["output"], dict) for receipt in receipts),
        "overall": {"correct": overall, "total": 16},
        "positive_candidate_recall": {"correct": positive, "total": 8},
        "t1_positive_recall": {"correct": t1, "total": 4},
        "t2_positive_recall": {"correct": t2, "total": 4},
        "negative_retention": {"correct": negative, "total": 8},
        "predictions": dict(Counter("affected" if row["predicted_affected"] else "unaffected" for row in rows)),
        "invalid_active_path_quotes": invalid_quotes,
        "baselines": {"always_affected": {"correct": 8, "total": 16},
                      "always_unaffected": {"correct": 8, "total": 16},
                      "surface_any_content_token_overlap": {"correct": surface, "total": 16}},
        "usage": {key: sum((receipt.get("usage") or {}).get(key, 0) for receipt in receipts) for key in usage_keys},
        "wall_seconds": {"sum": sum(wall), "p50": quantile(wall, .5), "p95": quantile(wall, .95)},
        "pass": overall >= 14 and positive >= 7 and t2 >= 3 and negative >= 7 and invalid_quotes == 0,
        "scope": "Fresh STALE component holdout; candidate nomination only, not invalidation, persistence, or downstream answer quality.",
    }
    dump(out / "score.json", {"summary": summary, "rows": rows})
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
