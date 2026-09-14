#!/usr/bin/env python3
"""Paired benchmark for the final project-memory bridge runtime paths."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_AGENT = PROJECT_ROOT / "scripts" / "project-agent"
sys.path.insert(0, str(PROJECT_AGENT))

from project_agent import compact_json, next_order, render_context, save_json  # noqa: E402
from project_memory_bridge_benchmark import ACTION, BUDGET, PATHS, latency, seed  # noqa: E402


ITERATIONS = 20
TWO_CALL_OPERATIONS = ["loadContext", "ingest"]
ONE_SHOT_OPERATIONS = ["prepareRun"]


class Bridge:
    def __init__(self, database: Path, command: list[str]):
        self.database = database
        self.command = command
        self.operations: list[str] = []

    def store(self, operation: str, **payload):
        self.operations.append(operation)
        request = {
            "database": str(self.database),
            "owner": "benchmark-owner",
            "project": "benchmark-project",
            "operation": operation,
            **payload,
        }
        completed = subprocess.run(
            self.command,
            cwd=PROJECT_ROOT,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=30,
        )
        try:
            response = json.loads(completed.stdout)
        except ValueError as error:
            raise RuntimeError(
                "bridge returned invalid JSON: " + completed.stderr[-1000:]
            ) from error
        if completed.returncode or not response.get("ok"):
            raise RuntimeError(response.get("error", completed.stderr[-1000:]))
        return response["result"]


def context_options() -> dict:
    return {"paths": PATHS, "action": ACTION, "maxBytes": BUDGET}


def task(index: int, order: int | None = None) -> dict:
    observation = {
        "id": f"task-{index}",
        "role": "user",
        "text": f"Implement bounded retry behavior for case {index}.",
    }
    if order is None:
        return observation
    return {
        "id": observation["id"],
        "order": order,
        "role": observation["role"],
        "text": observation["text"],
    }


def two_call_prepare(bridge: Bridge, index: int) -> tuple[dict, float, list[str]]:
    bridge.operations.clear()
    started = time.perf_counter()
    loaded = bridge.store("loadContext", options=context_options())
    snapshot = loaded["snapshot"]
    context = render_context(snapshot, "scoped", loaded["selection"], BUDGET)
    bridge.store(
        "ingest",
        observation=task(index, next_order(snapshot)),
        proposals=[],
    )
    return context, time.perf_counter() - started, list(bridge.operations)


def one_shot_prepare(bridge: Bridge, index: int) -> tuple[dict, float, list[str]]:
    bridge.operations.clear()
    started = time.perf_counter()
    prepared = bridge.store(
        "prepareRun",
        options=context_options(),
        observation=task(index),
    )
    if prepared["task"]["error"] is not None:
        raise RuntimeError(prepared["task"]["error"])
    context = render_context(prepared["snapshot"], "scoped", prepared["selection"], BUDGET)
    return context, time.perf_counter() - started, list(bridge.operations)


def ratios(candidate: dict, baseline: dict) -> dict:
    return {
        field: candidate[field] / baseline[field]
        for field in ("total_seconds", "mean_seconds", "p50_seconds", "p95_seconds")
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=PROJECT_ROOT / "dist" / "project-agent-store.mjs",
    )
    arguments = parser.parse_args()
    if arguments.iterations < 2 or arguments.iterations > 50:
        raise ValueError("iterations must be between 2 and 50")
    bundle = arguments.bundle.resolve()
    if not bundle.is_file():
        raise ValueError("precompiled bridge is missing; run npm run build first")

    source_command = [
        "node",
        "--import",
        "tsx",
        str(PROJECT_AGENT / "store.ts"),
    ]
    bundle_command = ["node", str(bundle)]
    arm_specs = {
        "source_tsx_two_call": (source_command, two_call_prepare, TWO_CALL_OPERATIONS),
        "precompiled_two_call": (bundle_command, two_call_prepare, TWO_CALL_OPERATIONS),
        "precompiled_one_shot": (bundle_command, one_shot_prepare, ONE_SHOT_OPERATIONS),
    }

    with TemporaryDirectory() as directory:
        root = Path(directory)
        bridges = {
            name: Bridge(root / f"{name}.sqlite", command)
            for name, (command, _, _) in arm_specs.items()
        }
        for bridge in bridges.values():
            seed(bridge)

        times: dict[str, list[float]] = {name: [] for name in arm_specs}
        operations: dict[str, list[list[str]]] = {name: [] for name in arm_specs}
        contexts_equal: list[bool] = []
        names = list(arm_specs)
        for index in range(arguments.iterations):
            offset = index % len(names)
            execution_order = names[offset:] + names[:offset]
            outcomes = {}
            for name in execution_order:
                _, prepare, _ = arm_specs[name]
                context, elapsed, invoked = prepare(bridges[name], index)
                outcomes[name] = context
                times[name].append(elapsed)
                operations[name].append(invoked)
            rendered = {compact_json(context) for context in outcomes.values()}
            contexts_equal.append(len(rendered) == 1)

        snapshots = {name: bridge.store("snapshot") for name, bridge in bridges.items()}

    timings = {name: latency(values) for name, values in times.items()}
    snapshots_equal = len({compact_json(snapshot) for snapshot in snapshots.values()}) == 1
    operation_sequences_match = all(
        row == expected for name, (_, _, expected) in arm_specs.items() for row in operations[name]
    )
    comparisons = {
        "precompiled_vs_source": ratios(
            timings["precompiled_two_call"], timings["source_tsx_two_call"]
        ),
        "one_shot_vs_precompiled": ratios(
            timings["precompiled_one_shot"], timings["precompiled_two_call"]
        ),
        "final_vs_source": ratios(timings["precompiled_one_shot"], timings["source_tsx_two_call"]),
    }
    promotion_gates = {
        "all_rendered_contexts_equal": all(contexts_equal),
        "final_snapshots_equal": snapshots_equal,
        "operation_sequences_match_protocol": operation_sequences_match,
        "final_aggregate_wall_time_lower": comparisons["final_vs_source"]["total_seconds"] < 1,
        "final_p95_wall_time_lower": comparisons["final_vs_source"]["p95_seconds"] < 1,
    }
    result = {
        "schema": 1,
        "protocol": "project-memory-runtime-optimization-v2",
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
            "execution_order": "rotating matched triplets",
        },
        "expected_operations": {name: expected for name, (_, _, expected) in arm_specs.items()},
        "operations": operations,
        "latency": timings,
        "latency_ratio": comparisons,
        "promotion_gates": promotion_gates,
        "promoted": all(promotion_gates.values()),
        "claim_boundary": (
            "local Python-to-Node startup plus SQLite context-load and task-ingest only; "
            "excludes model, checker, network, token, and end-to-end task latency"
        ),
    }
    save_json(arguments.output, result)
    print(compact_json(result))


if __name__ == "__main__":
    main()
