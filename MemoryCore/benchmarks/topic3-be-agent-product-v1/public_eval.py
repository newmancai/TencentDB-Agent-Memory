"""Aggregate a public long-dialogue paired experiment without model calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random


OUTCOMES = {"win": 1, "tie": 0, "loss": -1}


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def exact_sign_p(positive: int, negative: int) -> float | None:
    trials = positive + negative
    if trials == 0:
        return None
    tail = sum(math.comb(trials, index) for index in range(min(positive, negative) + 1)) / 2 ** trials
    return min(1.0, 2 * tail)


def validate(manifest: dict, rows: list[dict]) -> None:
    if manifest.get("schema") != 1 or not rows:
        raise ValueError("manifest schema=1 and non-empty observations are required")
    arms = manifest.get("arms")
    if not isinstance(arms, dict) or len(arms) < 2:
        raise ValueError("at least two named arms are required")
    baseline, enabled = manifest.get("baseline_arm"), manifest.get("enabled_arm")
    if baseline not in arms or enabled not in arms or baseline == enabled:
        raise ValueError("baseline_arm and enabled_arm must name different arms")
    expected_ids = manifest.get("dataset", {}).get("subset", {}).get("selected_task_ids")
    row_ids = [row.get("id") for row in rows]
    if len(set(row_ids)) != len(row_ids) or set(row_ids) != set(expected_ids or []):
        raise ValueError("observation IDs must exactly match the frozen selection")
    comparison = manifest.get("comparison")
    for row in rows:
        if not row.get("cluster") or not row.get("instance_type") or set(row.get("arms", {})) != set(arms):
            raise ValueError(f"invalid observation identity/arms: {row.get('id')}")
        if set(row.get("coverage", {})) != set(arms):
            raise ValueError(f"coverage is incomplete: {row['id']}")
        if row.get("paired", {}).get(comparison) not in OUTCOMES:
            raise ValueError(f"paired outcome is missing: {row['id']}")
        for metrics in row["arms"].values():
            numeric = (metrics.get("input_tokens"), metrics.get("output_tokens"), metrics.get("generation_ms"))
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 for value in numeric):
                raise ValueError(f"invalid arm metrics: {row['id']}")


def arm_summary(rows: list[dict], arm: str, mode: str) -> dict:
    metrics = [row["arms"][arm] for row in rows]
    latency = [item["generation_ms"] for item in metrics if item.get("error") is None]
    return {
        "mode": mode,
        "calls": len(metrics),
        "errors": sum(item.get("error") is not None for item in metrics),
        "input_tokens": sum(item["input_tokens"] for item in metrics),
        "output_tokens": sum(item["output_tokens"] for item in metrics),
        "generation_latency_ms": {
            "p50": quantile(latency, .5), "p95": quantile(latency, .95), "sum": sum(latency),
        },
        "coverage": dict(Counter(row["coverage"][arm] for row in rows)),
    }


def paired_summary(rows: list[dict], comparison: str, seed: int, samples: int) -> dict:
    outcomes = [row["paired"][comparison] for row in rows]
    counts = Counter(outcomes)
    by_cluster: dict[str, list[int]] = defaultdict(list)
    by_type: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        outcome = row["paired"][comparison]
        by_cluster[row["cluster"]].append(OUTCOMES[outcome])
        by_type[row["instance_type"]][outcome] += 1
    cluster_means = {cluster: sum(values) / len(values) for cluster, values in by_cluster.items()}
    generator = random.Random(seed)
    clusters = sorted(cluster_means)
    bootstrap = [sum(cluster_means[generator.choice(clusters)] for _ in clusters) / len(clusters)
                 for _ in range(samples)]
    cluster_positive = sum(value > 0 for value in cluster_means.values())
    cluster_negative = sum(value < 0 for value in cluster_means.values())
    return {
        "tasks": len(rows),
        "clusters": len(clusters),
        "wins": counts["win"], "losses": counts["loss"], "ties": counts["tie"],
        "utility_per_task": sum(OUTCOMES[outcome] for outcome in outcomes) / len(outcomes),
        "cluster_mean_utility": sum(cluster_means.values()) / len(cluster_means),
        "cluster_bootstrap_95ci": {
            "low": quantile(bootstrap, .025), "high": quantile(bootstrap, .975),
            "seed": seed, "samples": samples, "unit": "persona cluster",
        },
        "cluster_sign_test": {
            "positive": cluster_positive, "negative": cluster_negative,
            "zero": len(clusters) - cluster_positive - cluster_negative,
            "two_sided_p": exact_sign_p(cluster_positive, cluster_negative),
        },
        "by_instance_type": {name: dict(counts) for name, counts in sorted(by_type.items())},
    }


def evaluate(manifest: dict, rows: list[dict], *, manifest_hash: str | None = None,
             observations_hash: str | None = None) -> dict:
    validate(manifest, rows)
    arms = {name: arm_summary(rows, name, mode) for name, mode in manifest["arms"].items()}
    paired = paired_summary(rows, manifest["comparison"], manifest["bootstrap"]["seed"],
                            manifest["bootstrap"]["samples"])
    baseline, enabled = arms[manifest["baseline_arm"]], arms[manifest["enabled_arm"]]
    input_delta = [row["arms"][manifest["enabled_arm"]]["input_tokens"]
                   - row["arms"][manifest["baseline_arm"]]["input_tokens"] for row in rows]
    quality_gain = paired["wins"] > paired["losses"]
    confidence = paired["cluster_bootstrap_95ci"]["low"] > 0 \
        and (paired["cluster_sign_test"]["two_sided_p"] or 1) < .05
    return {
        "schema": 1,
        "suite": manifest["suite"],
        "mode": "public_method_validation",
        "dataset": manifest["dataset"],
        "alignment": manifest["alignment"],
        "execution": manifest["execution"],
        "metrics": {
            "definitions": manifest["metric_definitions"],
            "arms": arms,
            "paired_enabled_vs_baseline": paired,
            "enabled_vs_baseline_cost": {
                "input_token_ratio": enabled["input_tokens"] / baseline["input_tokens"],
                "input_token_delta": enabled["input_tokens"] - baseline["input_tokens"],
                "per_task_input_delta": {"p50": quantile(input_delta, .5), "p95": quantile(input_delta, .95)},
                "output_token_ratio": enabled["output_tokens"] / baseline["output_tokens"],
                "generation_time_ratio": enabled["generation_latency_ms"]["sum"]
                / baseline["generation_latency_ms"]["sum"],
            },
            "l1_extraction": {"status": "not_applicable"},
            "l0_retrieval": {"status": "not_applicable"},
        },
        "acceptance": {
            "artifacts_and_alignment": {"status": "pass"},
            "baseline_present": {"status": "pass", "arm": manifest["baseline_arm"]},
            "directional_quality_gain": {"status": "pass" if quality_gain else "fail"},
            "high_confidence_quality_gain": {
                "status": "pass" if confidence else "fail",
                "criterion": "positive persona-cluster bootstrap lower bound and cluster sign p<0.05",
            },
            "production_memory_effect": {"status": "not_claimed"},
        },
        "artifact_sha256": {"manifest": manifest_hash, "observations": observations_hash},
    }


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=here / "public-eval-manifest.json")
    parser.add_argument("--observations", type=Path, default=here / "fixtures/cupid-method-v1.jsonl")
    parser.add_argument("--output", type=Path, default=here / "public-eval-results.json")
    args = parser.parse_args()
    manifest, rows = load_json(args.manifest), load_jsonl(args.observations)
    result = evaluate(manifest, rows, manifest_hash=sha256(args.manifest),
                      observations_hash=sha256(args.observations))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["acceptance"]["artifacts_and_alignment"]["status"],
                      "quality_gain": result["acceptance"]["directional_quality_gain"]["status"],
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
