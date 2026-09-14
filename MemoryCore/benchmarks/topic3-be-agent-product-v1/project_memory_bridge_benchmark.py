#!/usr/bin/env python3
"""Paired benchmark for project-memory bridge process consolidation."""

from __future__ import annotations

import argparse
import math
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_AGENT = Path(__file__).resolve().parents[2] / "scripts" / "project-agent"
sys.path.insert(0, str(PROJECT_AGENT))

from project_agent import Host, compact_json, next_order, render_context, save_json  # noqa: E402


ITERATIONS = 20
BUDGET = 12_000
PATHS = ["src/api"]
ACTION = "edit"


class CountingHost(Host):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.operations: list[str] = []

    def store(self, operation: str, **payload):
        self.operations.append(operation)
        return super().store(operation, **payload)


def host_args(root: Path, name: str) -> argparse.Namespace:
    workspace = root / "workspace"
    workspace.mkdir(exist_ok=True)
    return argparse.Namespace(
        state=root / name,
        workspace=workspace,
        owner="benchmark-owner",
        project="benchmark-project",
        backend="codex",
        model=None,
        effort="medium",
        timeout=30,
        mode="scoped",
        paths=PATHS,
        action=ACTION,
        max_bytes=BUDGET,
        check=None,
    )


def seed(host: CountingHost) -> None:
    policy = {
        "id": "policy-1",
        "order": 1,
        "role": "user",
        "text": "For src/api edits, preserve explicit zero values.",
    }
    host.store(
        "ingest",
        observation=policy,
        proposals=[
            {
                "key": "explicit-zero",
                "quote": policy["text"],
                "scope": {"paths": PATHS, "actions": [ACTION]},
            }
        ],
    )
    host.store(
        "ingest",
        observation={
            "id": "raw-2",
            "order": 2,
            "role": "user",
            "text": "Keep cancellation support as well.",
        },
        proposals=[],
    )
    host.operations.clear()


def options(snapshot: dict) -> dict:
    return {
        "paths": PATHS,
        "action": ACTION,
        "beforeOrder": next_order(snapshot),
        "maxBytes": BUDGET,
    }


def legacy_prepare(host: CountingHost, index: int) -> tuple[dict, float, list[str]]:
    host.operations.clear()
    started = time.perf_counter()
    snapshot = host.store("snapshot")
    selected = host.store("context", options=options(snapshot))
    context = render_context(snapshot, "scoped", selected, BUDGET)
    write_snapshot = host.store("snapshot")
    observation = {
        "id": f"task-{index}",
        "order": next_order(write_snapshot),
        "role": "user",
        "text": f"Implement bounded retry behavior for case {index}.",
    }
    host.store("ingest", observation=observation, proposals=[])
    return context, time.perf_counter() - started, list(host.operations)


def optimized_prepare(host: CountingHost, index: int) -> tuple[dict, float, list[str]]:
    host.operations.clear()
    started = time.perf_counter()
    loaded = host.store(
        "loadContext",
        options={"paths": PATHS, "action": ACTION, "maxBytes": BUDGET},
    )
    snapshot = loaded["snapshot"]
    context = render_context(snapshot, "scoped", loaded["selection"], BUDGET)
    observation = {
        "id": f"task-{index}",
        "order": next_order(snapshot),
        "role": "user",
        "text": f"Implement bounded retry behavior for case {index}.",
    }
    host.store("ingest", observation=observation, proposals=[])
    return context, time.perf_counter() - started, list(host.operations)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def latency(values: list[float]) -> dict:
    return {
        "samples_seconds": values,
        "total_seconds": sum(values),
        "mean_seconds": statistics.mean(values),
        "p50_seconds": statistics.median(values),
        "p95_seconds": percentile(values, 0.95),
        "min_seconds": min(values),
        "max_seconds": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.iterations < 2 or arguments.iterations > 50:
        raise ValueError("iterations must be between 2 and 50")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        legacy = CountingHost(host_args(root, "legacy-state"))
        optimized = CountingHost(host_args(root, "optimized-state"))
        seed(legacy)
        seed(optimized)

        legacy_times: list[float] = []
        optimized_times: list[float] = []
        legacy_operations: list[list[str]] = []
        optimized_operations: list[list[str]] = []
        contexts_equal = []
        for index in range(arguments.iterations):
            if index % 2 == 0:
                old, old_time, old_ops = legacy_prepare(legacy, index)
                new, new_time, new_ops = optimized_prepare(optimized, index)
            else:
                new, new_time, new_ops = optimized_prepare(optimized, index)
                old, old_time, old_ops = legacy_prepare(legacy, index)
            legacy_times.append(old_time)
            optimized_times.append(new_time)
            legacy_operations.append(old_ops)
            optimized_operations.append(new_ops)
            contexts_equal.append(compact_json(old) == compact_json(new))

        legacy_snapshot = legacy.store("snapshot")
        optimized_snapshot = optimized.store("snapshot")

    old_latency = latency(legacy_times)
    new_latency = latency(optimized_times)
    expected_legacy = ["snapshot", "context", "snapshot", "ingest"]
    expected_optimized = ["loadContext", "ingest"]
    equality = {
        "all_rendered_contexts_equal": all(contexts_equal),
        "final_snapshots_equal": compact_json(legacy_snapshot) == compact_json(optimized_snapshot),
    }
    operations = {
        "legacy_per_iteration": legacy_operations,
        "optimized_per_iteration": optimized_operations,
        "legacy_expected_every_iteration": all(row == expected_legacy for row in legacy_operations),
        "optimized_expected_every_iteration": all(
            row == expected_optimized for row in optimized_operations
        ),
        "legacy_pre_model_bridge_calls": len(expected_legacy),
        "optimized_pre_model_bridge_calls": len(expected_optimized),
        "call_ratio": len(expected_optimized) / len(expected_legacy),
    }
    promotion_gates = {
        **equality,
        "operation_sequences_match_protocol": (
            operations["legacy_expected_every_iteration"]
            and operations["optimized_expected_every_iteration"]
        ),
        "aggregate_wall_time_lower": new_latency["total_seconds"] < old_latency["total_seconds"],
        "p95_wall_time_lower": new_latency["p95_seconds"] < old_latency["p95_seconds"],
    }
    result = {
        "schema": 1,
        "protocol": "project-memory-bridge-hot-path-v1",
        "iterations": arguments.iterations,
        "environment": {
            "python": platform.python_version(),
            "node": subprocess.run(
                ["node", "--version"], text=True, capture_output=True, check=True
            ).stdout.strip(),
            "platform": platform.platform(),
        },
        "fixed_input": {
            "paths": PATHS,
            "action": ACTION,
            "budget_bytes": BUDGET,
            "initial_observations": 2,
            "initial_compiled_constraints": 1,
            "model_calls": 0,
            "execution_order": "alternating paired arms",
        },
        "equivalence": equality,
        "operations": operations,
        "latency": {"legacy": old_latency, "optimized": new_latency},
        "latency_ratio": {
            "total": new_latency["total_seconds"] / old_latency["total_seconds"],
            "mean": new_latency["mean_seconds"] / old_latency["mean_seconds"],
            "p50": new_latency["p50_seconds"] / old_latency["p50_seconds"],
            "p95": new_latency["p95_seconds"] / old_latency["p95_seconds"],
        },
        "promotion_gates": promotion_gates,
        "promoted": all(promotion_gates.values()),
        "claim_boundary": (
            "local Python-to-Node process and SQLite bridge only; excludes model, checker, "
            "network, token, and end-to-end task latency"
        ),
    }
    save_json(arguments.output, result)
    print(compact_json(result))


if __name__ == "__main__":
    main()
