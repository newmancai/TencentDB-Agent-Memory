"""Create prefix-only B observations; keep public feedback labels offline."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def align(row):
    users = [m for m in row["conversation"] if m["role"] == "user"][1:]
    cats, texts = row["user_feedback_category"], row["user_feedback_text"]
    if len(cats) != len(texts):
        raise ValueError("label/text length mismatch")
    matched = defaultdict(list)
    unresolved = []
    positional = len(users) == len(cats) and all(
        (c == "NEU" and t == "") or u["content"].strip() == t.strip()
        for u, c, t in zip(users, cats, texts))
    for j, (c, t) in enumerate(zip(cats, texts)):
        positions = [j] if positional else [
            i for i, u in enumerate(users) if t.strip() and u["content"].strip() == t.strip()]
        if len(positions) == 1:
            matched[positions[0]].append((j, c))
        else:
            unresolved.append({"annotation_index": j, "label": c,
                               "reason": "ambiguous_or_missing_text", "positions": positions})
    labels = {}
    for i, annotations in matched.items():
        unique = {c for _, c in annotations}
        labels[i] = {"label": next(iter(unique)) if len(unique) == 1 else None,
                     "annotation_indices": [j for j, _ in annotations],
                     "status": "conflicting" if len(unique) > 1 else
                     "duplicate_consistent" if len(annotations) > 1 else "aligned"}
    return labels, unresolved


def adapt(row):
    labels, unresolved = align(row)
    events, gold = [], []
    user_index = -1
    for i, message in enumerate(row["conversation"]):
        if message["role"] != "user":
            continue
        user_index += 1
        if user_index == 0:
            continue
        group = row["dataset_source"] + ":" + row["conversation_id"]
        key = hashlib.sha256(f"{group}:{i}".encode()).hexdigest()[:24]
        # No answer after the feedback turn, labels, category text or future messages.
        events.append({"id": key, "group": group, "source": row["dataset_source"],
                       "history": [{"id": f"m{k}", "role": m["role"], "text": m["content"]}
                                   for k, m in enumerate(row["conversation"][:i])],
                       "incoming": {"id": f"m{i}", "role": "user", "text": message["content"]}})
        gold.append({"id": key, **labels.get(user_index - 1,
                     {"label": None, "annotation_indices": [], "status": "unlabeled"})})
    return events, gold, unresolved


def main():
    import pyarrow.parquet as pq
    parser = argparse.ArgumentParser()
    parser.add_argument("parquet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    events, gold, diagnostics = [], [], []
    for row in pq.read_table(args.parquet).to_pylist():
        e, g, u = adapt(row)
        events.extend(e)
        gold.extend(g)
        if u:
            diagnostics.append({"source": row["dataset_source"], "conversation_id": row["conversation_id"],
                                "unresolved_annotations": u})
    assert len({e["id"] for e in events}) == len(events)
    for name, records in [("observations", events), ("labels", gold), ("diagnostics", diagnostics)]:
        (args.output / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    from collections import Counter
    summary = {"observations": len(events), "status": dict(Counter(g["status"] for g in gold)),
               "labels": dict(Counter(g["label"] for g in gold)), "unresolved_conversations": len(diagnostics),
               "kind": "public_user_feedback_labels_not_memory_fault_labels"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
