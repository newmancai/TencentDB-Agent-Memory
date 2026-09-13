"""Audit public feedback data without treating its labels as memory fault gold."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile

import pyarrow.parquet as pq


def distribution(values):
    values = sorted(values)
    return {"min": values[0], "median": values[len(values) // 2],
            "max": values[-1], "at_least_20": sum(v >= 20 for v in values)}


def feedback(path):
    rows = pq.read_table(path).to_pylist()
    report = {"rows": len(rows), "sources": {}, "alignment_errors": [],
              "blank_neutral_texts": 0, "partial_unique_text_alignment": []}
    for source in sorted({r["dataset_source"] for r in rows}):
        subset = [r for r in rows if r["dataset_source"] == source]
        labels = collections.Counter()
        for r in subset:
            users = [t["content"] for t in r["conversation"] if t["role"] == "user"]
            cats = r["user_feedback_category"]
            labels.update(cats)
            errors = []
            texts = r["user_feedback_text"]
            report["blank_neutral_texts"] += sum(c == "NEU" and t == "" for c, t in zip(cats, texts))
            if len(texts) != len(cats):
                errors.append("text_label_count_mismatch")
            if len(cats) != len(users) - 1:
                errors.append("label_count_mismatch")
                # Diagnose exact unique matches only; never invent omitted labels.
                positions = [[i for i, u in enumerate(users[1:], 1) if t and t == u] for t in texts]
                if all(len(p) == 1 for p in positions):
                    chosen = [p[0] for p in positions]
                    if chosen == sorted(set(chosen)):
                        report["partial_unique_text_alignment"].append({
                            "id": r["conversation_id"], "user_indices": chosen,
                            "unlabeled_user_indices": [i for i in range(1, len(users)) if i not in chosen]})
            elif len(texts) == len(cats):
                for i, (u, t, c) in enumerate(zip(users[1:], texts, cats), 1):
                    if u != t and not (c == "NEU" and t == ""):
                        errors.append(f"non_neutral_text_mismatch_at_user_{i}")
            if len(users) != r["total_turns"]:
                errors.append("total_turns_mismatch")
            if errors:
                report["alignment_errors"].append({"id": r["conversation_id"], "errors": errors})
        report["sources"][source] = {
            "conversations": len(subset), "labels": dict(labels),
            "messages": distribution([len(r["conversation"]) for r in subset]),
            "user_turns": distribution([sum(t["role"] == "user" for t in r["conversation"]) for r in subset]),
        }
    report["duplicate_source_ids"] = len(rows) - len({(r["dataset_source"], r["conversation_id"]) for r in rows})
    return report


def decode(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "084aab98652a04ce4a78c1a63d91575f5ab416a0c474b962ca1f4508a56b7484"
    report = {"sha256": digest, "splits": {}}
    base_ids = {}
    with zipfile.ZipFile(path) as archive:
        for split in ["train", "dev", "test", "human-bot", "a2t", "rct"]:
            rows = [json.loads(line) for line in archive.read(f"decode_v0.1/{split}.jsonl").splitlines()]
            issues = []
            for r in rows:
                ids = {t["turn_id"] for t in r["turns"]}
                evidence = r["aggregated_contradiction_indices"]
                if any(i not in ids for i in evidence):
                    issues.append({"id": r["record_id"], "error": "evidence_outside_turn_ids"})
            base_ids[split] = {r["conversation_id"].split("#")[0] for r in rows}
            report["splits"][split] = {
                "rows": len(rows), "messages": distribution([len(r["turns"]) for r in rows]),
                "contradictions": sum(bool(r["is_contradiction"]) for r in rows),
                "evidence_errors": issues,
                "unique_base_conversation_ids": len(base_ids[split]),
            }
    report["base_id_overlap"] = {
        f"{a}/{b}": len(base_ids[a] & base_ids[b])
        for a, b in [("train", "dev"), ("train", "test"), ("dev", "test"), ("test", "a2t"), ("test", "rct")]
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = {
        "kind": "source_and_label_audit_not_model_evaluation",
        "feedback_revision": "5339f4d77871636030bf4e43ff26b0756cb1fb2d",
        "feedback": feedback(args.evidence_dir / "dense-00000-of-00001.parquet"),
        "decode": decode(args.evidence_dir / "decode_v0.1.zip"),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
