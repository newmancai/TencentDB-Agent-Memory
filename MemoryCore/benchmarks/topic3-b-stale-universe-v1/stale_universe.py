"""Measure whether ordinary lexical retrieval exposes the stale old session."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import time


SEED = "topic3-b-stale-universe-v1:"
K1 = 1.2
B = 0.75
EXCLUDED = {
    "6e8a7e72-3158-4676-9aa4-a4ce492015fd", "9ce11bb3-9680-4e92-86fc-5f450d36405b",
    "cc9aaa40-77d3-47f7-8551-8e216bb47887", "f5a0a3c8-4300-4b37-a45b-8584af2be8f2",
    "f50107f1-364f-4c07-bdd6-bf144c6da875", "7b568b27-c87a-4a93-9596-e65478544681",
    "f57e6cfd-16a4-47b8-ab87-1b50838580e9", "11e0c473-dbd3-4645-964a-86affc5f998d",
    "284d2ed9-8551-444a-8b97-d230cd144967", "872d8b8c-24f3-4472-a6e3-a7e42d04ff40",
    "e1703b4d-f093-43cf-8003-75f8949c69d0", "0c199bef-29ae-489f-b772-af9a43d6eb0e",
    "830a2e06-981f-411c-bef0-99ec4190fbfa", "36da4cf0-035a-41fc-aae1-5080fe2e2460",
    "26910318-c4ce-431f-8b6f-8eaad3ffd8b8", "6f69a06e-01a9-442e-927b-70f40d6cc8f3",
    "4ed6936e-58e4-40c9-83e7-743bb7ff7bbb", "3125238e-b0a5-4162-9cb9-e893f5f60531",
    "93a1c511-92d3-4d00-b714-4f27096df346", "a4b2e2fd-b0c4-4529-98f7-c00a658f0d70",
    "19bb9fc3-a962-4055-bf8f-e3b194fcf7d3", "47911ef2-a067-4c92-acc0-fe0de42666d9",
    "d586678b-29de-4aae-82fd-7dec44fde9ec", "36d4a45d-833a-4f1b-a3bf-4f47a729eba0",
}
STOPWORDS = set("a an and are as at be been but by for from had has have i in into is it my no not of on or so that the their they this to was were with you your".split())
KS = (1, 5, 8, 16, 32)


def tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) > 2 and token not in STOPWORDS]


def user_text(session: list[dict]) -> str:
    return " ".join(message["content"] for message in session if message["role"] == "user")


def bm25_rank(documents: list[str], query: str, target: int) -> tuple[int, bool]:
    docs = [tokens(document) for document in documents]
    query_terms = set(tokens(query))
    lengths = [len(doc) for doc in docs]
    average_length = sum(lengths) / len(lengths) if lengths else 1.0
    frequencies = [Counter(doc) for doc in docs]
    document_frequency = Counter(term for term in query_terms for doc in frequencies if term in doc)
    scores = []
    for index, frequency in enumerate(frequencies):
        score = 0.0
        for term in query_terms:
            tf = frequency.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(docs) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            denominator = tf + K1 * (1 - B + B * lengths[index] / average_length)
            score += idf * tf * (K1 + 1) / denominator
        scores.append((score, index))
    ordered = sorted(scores, key=lambda value: (-value[0], value[1]))
    rank = 1 + [index for _, index in ordered].index(target)
    return rank, bool(query_terms & set(docs[target]))


def quantile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def summarize(rows: list[dict]) -> dict:
    ranks = [row["rank"] for row in rows]
    latency = [row["latency_ms"] for row in rows]
    return {
        "rows": len(rows),
        "recall": {f"at_{k}": sum(rank <= k for rank in ranks) / len(ranks) for k in KS},
        "median_rank": quantile(ranks, .5),
        "zero_target_overlap": sum(not row["target_has_query_overlap"] for row in rows),
        "latency_ms": {"p50": quantile(latency, .5), "p95": quantile(latency, .95), "sum": sum(latency)},
    }


def run(parquet: Path, output: Path) -> None:
    import pyarrow.parquet as pq

    source = pq.read_table(parquet, columns=["uid", "M_new", "type", "relevant_session_index", "haystack_session"]).to_pylist()
    selected = {
        kind: sorted((row for row in source if row["type"] == kind and row["uid"] not in EXCLUDED),
                     key=lambda row: hashlib.sha256((SEED + row["uid"]).encode()).hexdigest())[:100]
        for kind in ("T1", "T2")
    }
    rows = []
    for kind, items in selected.items():
        for item in items:
            old_index, new_index = item["relevant_session_index"]
            if not 0 <= old_index < new_index < len(item["haystack_session"]):
                raise ValueError(f"invalid relevant-session order: {item['uid']}")
            documents = [user_text(session) for session in item["haystack_session"][:new_index]]
            queries = {"observed_session": user_text(item["haystack_session"][new_index]),
                       "normalized_m_new": item["M_new"]}
            for mode, query in queries.items():
                started = time.perf_counter()
                rank, overlap = bm25_rank(documents, query, old_index)
                rows.append({"uid": item["uid"], "kind": kind, "query_mode": mode, "rank": rank,
                             "candidate_count": len(documents), "target_has_query_overlap": overlap,
                             "latency_ms": (time.perf_counter() - started) * 1000})
    metrics = {}
    for mode in ("observed_session", "normalized_m_new"):
        metrics[mode] = {kind: summarize([row for row in rows if row["query_mode"] == mode
                                         and (kind == "all" or row["kind"] == kind)])
                         for kind in ("all", "T1", "T2")}
    observed = metrics["observed_session"]
    summary = {
        "protocol": "topic3-b-stale-universe-v1", "rows": 200, "rankings": 400,
        "retriever": {"name": "fixed_bm25", "k1": K1, "b": B, "document": "user text per prior session"},
        "metrics": metrics,
        "pass": observed["all"]["recall"]["at_8"] >= .8 and observed["T2"]["recall"]["at_8"] >= .7,
        "scope": "Candidate-universe retrieval only; no LLM, answer probes, memory mutation, or production traffic.",
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (output / "selection.json").write_text(json.dumps({
        "seed": SEED, "excluded_uids": sorted(EXCLUDED),
        "selected": {kind: [row["uid"] for row in items] for kind, items in selected.items()},
    }, indent=2) + "\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.parquet, args.output)


if __name__ == "__main__":
    main()
