"""Bounded STALE implicit-update binder with balanced pre-call controls."""
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
SEED = "topic3-b-stale-binding-v1:"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "i", "in", "into", "is", "it", "my", "no",
    "not", "of", "on", "or", "so", "that", "the", "their", "they", "this",
    "to", "was", "were", "with", "you", "your",
}
NEGATIVE_RATIONALES = {
    "6e8a7e72-3158-4676-9aa4-a4ce492015fd": "Software subscription status and physical stamina can both remain true.",
    "9ce11bb3-9680-4e92-86fc-5f450d36405b": "Physical stamina and daylight in a living room can both remain true.",
    "cc9aaa40-77d3-47f7-8551-8e216bb47887": "Daylight intensity and preference for dense decor can both remain true.",
    "f5a0a3c8-4300-4b37-a45b-8584af2be8f2": "Decor preference and software subscription status can both remain true.",
    "f50107f1-364f-4c07-bdd6-bf144c6da875": "Possession of a borrowed blanket and decor preference can both remain true.",
    "7b568b27-c87a-4a93-9596-e65478544681": "Local file-storage preference and room daylight can both remain true.",
    "f57e6cfd-16a4-47b8-ab87-1b50838580e9": "Belongings-insurance status and physical stamina can both remain true.",
    "11e0c473-dbd3-4645-964a-86affc5f998d": "Neighbor relationships and software subscription status can both remain true.",
}


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_rows(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))


def read_rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def hash_key(uid: str) -> str:
    return hashlib.sha256((SEED + uid).encode()).hexdigest()


def prepare(parquet: Path, out: Path) -> None:
    import pyarrow.parquet as pq

    table = pq.read_table(parquet, columns=["uid", "M_old", "M_new", "explanation", "type"])
    source = table.to_pylist()
    selected = {
        kind: sorted((row for row in source if row["type"] == kind), key=lambda row: hash_key(row["uid"]))[:4]
        for kind in ("T1", "T2")
    }
    if any(len(values) != 4 for values in selected.values()):
        raise ValueError("expected four selected rows per STALE conflict type")

    out.mkdir(parents=True, exist_ok=False)
    tasks = []
    labels = []
    audit = []
    for kind in ("T1", "T2"):
        for index, row in enumerate(selected[kind]):
            task_id = f"{row['uid']}:positive"
            tasks.append({"id": task_id, "old_observation": row["M_old"], "later_observation": row["M_new"]})
            labels.append({"id": task_id, "action": "supersede", "kind": kind,
                           "source_uid": row["uid"], "explanation": row["explanation"]})

            paired = selected["T1"][(index + 1) % 4] if kind == "T1" else selected["T1"][3 - index]
            negative_id = f"{row['uid']}:negative"
            tasks.append({"id": negative_id, "old_observation": row["M_old"],
                          "later_observation": paired["M_new"]})
            labels.append({"id": negative_id, "action": "retain", "kind": f"{kind}_negative",
                           "source_uid": row["uid"], "paired_later_uid": paired["uid"]})
            audit.append({"id": negative_id, "source_uid": row["uid"],
                          "paired_later_uid": paired["uid"], "label": "retain",
                          "audit": NEGATIVE_RATIONALES[row["uid"]],
                          "audited_before_inference": True})

    write_rows(out / "tasks.jsonl", tasks)
    write_rows(out / "labels.private.jsonl", labels)
    dump(out / "negative-audit.json", audit)
    dump(out / "selection.json", {
        "protocol": "topic3-b-stale-binding-v1",
        "dataset_rows": len(source),
        "dataset_types": dict(Counter(row["type"] for row in source)),
        "selected": {kind: [row["uid"] for row in values] for kind, values in selected.items()},
        "positive_pairs": 8,
        "negative_pairs": 8,
        "selection": "four per type by SHA256(topic3-b-stale-binding-v1:+uid)",
        "negative_pairing": "T1 cycles to next T1 later observation; T2 maps to reverse-index T1 later observation",
    })


def prompt(task: dict) -> str:
    return """Decide whether a later user observation makes an older memory unsafe to use as current.
Return supersede only when the later observation directly conflicts with the old memory or necessarily invalidates it through a clear commonsense dependency. Return retain when both can remain true. Return ask when evidence is insufficient.
For supersede, evidence_quote must be a non-empty exact substring of later_observation supporting the update. For retain or ask, evidence_quote must be an empty string. Do not browse or call tools. Return only JSON matching the schema.

""" + json.dumps({"old_observation": task["old_observation"],
                     "later_observation": task["later_observation"]}, ensure_ascii=False)


def infer(out: Path) -> None:
    tasks = read_rows(out / "tasks.jsonl")
    raw = out / "raw"
    raw.mkdir()
    empty = out / "empty-workdir"
    empty.mkdir()
    schema = out / "output-schema.json"
    dump(schema, {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["supersede", "retain", "ask"]},
            "evidence_quote": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["action", "evidence_quote", "reason"],
        "additionalProperties": False,
    })
    write_rows(out / "inputs.jsonl", ({"id": task["id"], "prompt": prompt(task)} for task in tasks))
    receipts = []
    for task in tasks:
        stem = task["id"].replace(":", "-")
        message = raw / f"{stem}.message.json"
        started = time.perf_counter()
        run = subprocess.run([
            "codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"',
            "--sandbox", "read-only", "-C", str(empty.resolve()), "--skip-git-repo-check",
            "--ephemeral", "--ignore-user-config", "--ignore-rules", "--output-schema",
            str(schema.resolve()), "--json", "--output-last-message", str(message.resolve()), "-",
        ], input=prompt(task), text=True, capture_output=True, timeout=300)
        wall = time.perf_counter() - started
        (raw / f"{stem}.events.jsonl").write_text(run.stdout)
        (raw / f"{stem}.stderr.txt").write_text(run.stderr)
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
        receipt = {"id": task["id"], "returncode": run.returncode, "wall_seconds": wall,
                   "output": parsed, "usage": usage}
        receipts.append(receipt)
        write_rows(out / "receipts.jsonl", receipts)
        print(task["id"], run.returncode, parsed and parsed.get("action"), flush=True)


def content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS and len(token) > 2}


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def score(out: Path) -> None:
    tasks = {row["id"]: row for row in read_rows(out / "tasks.jsonl")}
    labels = {row["id"]: row for row in read_rows(out / "labels.private.jsonl")}
    receipts = read_rows(out / "receipts.jsonl")
    if len(receipts) != len(tasks) or {row["id"] for row in receipts} != set(tasks):
        raise ValueError("receipt/task mismatch")
    counts = Counter()
    rows = []
    exact_span_failures = 0
    for receipt in receipts:
        task = tasks[receipt["id"]]
        label = labels[receipt["id"]]
        output = receipt["output"] if isinstance(receipt["output"], dict) else {}
        action = output.get("action")
        quote = output.get("evidence_quote")
        shape = action in {"supersede", "retain", "ask"} and isinstance(quote, str)
        quote_ok = shape and ((action == "supersede" and bool(quote) and quote in task["later_observation"])
                              or (action != "supersede" and quote == ""))
        correct = receipt["returncode"] == 0 and shape and quote_ok and action == label["action"]
        counts[f"gold_{label['action']}"] += 1
        counts[f"correct_{label['action']}"] += int(correct)
        counts[f"pred_{action if shape else 'invalid'}"] += 1
        if label["action"] == "supersede" and action == "supersede" and not quote_ok:
            exact_span_failures += 1
        rows.append({"id": receipt["id"], "kind": label["kind"], "gold": label["action"],
                     "prediction": action if shape else "invalid", "quote_valid": bool(quote_ok),
                     "correct": bool(correct)})

    positives = [row for row in rows if row["gold"] == "supersede"]
    negatives = [row for row in rows if row["gold"] == "retain"]
    t2 = [row for row in positives if row["kind"] == "T2"]
    overall = sum(row["correct"] for row in rows)
    positive_correct = sum(row["correct"] for row in positives)
    negative_correct = sum(row["correct"] for row in negatives)
    t2_correct = sum(row["correct"] for row in t2)
    surface = []
    for task_id, task in tasks.items():
        prediction = "supersede" if content_tokens(task["old_observation"]) & content_tokens(task["later_observation"]) else "retain"
        surface.append(prediction == labels[task_id]["action"])
    wall = [receipt["wall_seconds"] for receipt in receipts]
    usage_keys = ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]
    summary = {
        "protocol": "topic3-b-stale-binding-v1",
        "model": MODEL,
        "reasoning_effort": REASONING,
        "calls": len(receipts),
        "completed": sum(receipt["returncode"] == 0 and isinstance(receipt["output"], dict) for receipt in receipts),
        "overall": {"correct": overall, "total": len(rows)},
        "positive_supersession": {"correct": positive_correct, "total": len(positives)},
        "t1_positive": {"correct": sum(row["correct"] for row in positives if row["kind"] == "T1"), "total": 4},
        "t2_propagated_positive": {"correct": t2_correct, "total": len(t2)},
        "negative_retention": {"correct": negative_correct, "total": len(negatives)},
        "predictions": dict(sorted((key.removeprefix("pred_"), value) for key, value in counts.items() if key.startswith("pred_"))),
        "exact_span_failures_on_predicted_positive": exact_span_failures,
        "baselines": {
            "always_supersede": {"correct": len(positives), "total": len(rows)},
            "always_retain": {"correct": len(negatives), "total": len(rows)},
            "surface_any_content_token_overlap": {"correct": sum(surface), "total": len(surface)},
        },
        "usage": {key: sum((receipt.get("usage") or {}).get(key, 0) for receipt in receipts) for key in usage_keys},
        "wall_seconds": {"sum": sum(wall), "p50": quantile(wall, .5), "p95": quantile(wall, .95)},
        "pass": overall >= 14 and positive_correct >= 7 and t2_correct >= 3
                and negative_correct >= 7 and exact_span_failures == 0,
        "scope": "Expert-reviewed synthetic STALE positives plus pre-call audited cross-attribute negatives; component binding only, not downstream answer quality or durable promotion.",
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
