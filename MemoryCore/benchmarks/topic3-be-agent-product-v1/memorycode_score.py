#!/usr/bin/env python3
"""Score MemoryCode receipts with official-compatible and strict coverage metrics."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ARMS = ("full_history", "memorycore_l0", "latest_guidelines_oracle")
BOOTSTRAP_SEED = 20260913


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _canonical_receipts(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: (row["dialogue_id"], row["arm"]))
    return "".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n" for row in ordered)


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "sum": sum(values),
        "mean": statistics.mean(values) if values else None,
        "p50": _quantile(values, 0.5),
        "p95": _quantile(values, 0.95),
    }


def _extract_code(text: str) -> str:
    matches = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
    if not matches:
        matches = re.findall(r"```(.*?)```", text, re.DOTALL)
    return matches[0] if matches else text


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


class _Objects(ast.NodeVisitor):
    """Object projection compatible with MemoryCode's pinned extractor."""

    names = (
        "function", "function argument", "function docstring", "function try",
        "function assert", "function annotation", "function decorator", "class",
        "class decorator", "method", "method docstring", "method try", "method assert",
        "method annotation", "method decorator", "attribute", "variable", "import", "comment",
    )

    def __init__(self) -> None:
        self.objects: dict[str, list[Any]] = {name: [] for name in self.names}
        self.current_class: ast.ClassDef | None = None

    @staticmethod
    def _annotations(node: ast.FunctionDef) -> list[ast.expr]:
        values = [argument.annotation for argument in node.args.args if argument.annotation]
        if node.returns:
            values.append(node.returns)
        return values

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        decorators = [name for item in node.decorator_list if (name := _decorator_name(item))]
        tries = [item for item in node.body if isinstance(item, ast.Try)]
        asserts = [item for item in node.body if isinstance(item, ast.Assert)]
        if self.current_class is None:
            self.objects["function"].append([node.name])
            self.objects["function argument"].append([arg.arg for arg in node.args.args])
            docstring = ast.get_docstring(node)
            self.objects["function docstring"].append([docstring] if docstring else [])
            self.objects["function try"].append(tries)
            self.objects["function assert"].append(asserts)
            self.objects["function annotation"].append(self._annotations(node))
            self.objects["function decorator"].append(decorators)
        elif node.name == "__init__":
            attributes = []
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            attributes.append(target.attr)
            self.objects["attribute"].append(attributes)
        elif not node.name.startswith("__"):
            self.objects["method"].append([node.name])
            docstring = ast.get_docstring(node)
            self.objects["method docstring"].append([docstring] if docstring else [])
            self.objects["method try"].append(tries)
            self.objects["method assert"].append(asserts)
            self.objects["method annotation"].append(self._annotations(node))
            self.objects["method decorator"].append(decorators)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.objects["class"].append([node.name])
        self.objects["class decorator"].append(
            [name for item in node.decorator_list if (name := _decorator_name(item))]
        )
        previous = self.current_class
        self.current_class = node
        self.generic_visit(node)
        self.current_class = previous

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.objects["variable"].append([target.id])
            elif isinstance(target, ast.Tuple):
                self.objects["variable"].extend(
                    [[item.id] for item in target.elts if isinstance(item, ast.Name)]
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        target = node.target
        if isinstance(target, ast.Name):
            self.objects["variable"].append([target.id])
        elif isinstance(target, ast.Tuple):
            self.objects["variable"].extend(
                [[item.id] for item in target.elts if isinstance(item, ast.Name)]
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.objects["import"].extend(alias.name for alias in node.names)
        self.generic_visit(node)


def extract_objects(text: str) -> dict[str, list[Any]] | None:
    code = _extract_code(text)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    visitor = _Objects()
    visitor.visit(tree)
    visitor.objects["comment"] = [re.findall(r"#.*", code)]
    return visitor.objects


def criterion(objects: dict[str, list[Any]] | None, object_type: str, regex: Any) -> float | None:
    if objects is None:
        return 0.0
    found = objects[object_type]
    if not found and object_type not in ("comment", "import"):
        return None
    if isinstance(regex, bool):
        present = [len(item) > 0 for item in found]
        return float(all(present) if regex else not any(present))
    if isinstance(regex, list):
        name, expected = regex
        if object_type not in ("comment", "import"):
            return float(all((name in item) == expected for item in found))
        return float((name in found) == expected)
    matched = [bool(re.match(str(regex), item[0])) for item in found if item]
    return float(bool(matched) and all(matched))


def score_receipt(packet: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    passed = receipt["status"] == "passed"
    objects = extract_objects(receipt["output"]) if passed else None
    syntax_valid = passed and objects is not None
    active = [criterion(objects, rule["object_type"], rule["regex"])
              for rule in packet["active_rules"]]
    targets = [criterion(objects, rule["object_type"], rule["regex"])
               for rule in packet["targets"]]
    official_values = [value for value in active if value is not None]
    covered_targets = [value for value in targets if value is not None] if syntax_valid else []
    return {
        "task_id": packet["task_id"],
        "arm": receipt["arm"],
        "history_class": packet["history_class"],
        "session_count": packet["session_count"],
        "target_status": packet["target_status"],
        "run_passed": passed,
        "syntax_valid": syntax_valid,
        "official_compatible": statistics.mean(official_values) if official_values else 0.0,
        "target_coverage": len(covered_targets) / len(targets),
        "target_conditional": statistics.mean(covered_targets) if covered_targets else None,
        "target_strict": statistics.mean(value if value is not None else 0.0 for value in targets),
    }


def _aggregate(rows: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(row["task_id"], row["arm"]): row for row in rows}
    arm_receipts = defaultdict(list)
    for receipt in receipts:
        arm_receipts[receipt["arm"]].append(receipt)
    result = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        costs = arm_receipts[arm]
        result[arm] = {
            "mode": costs[0]["mode"],
            "tasks": len(arm_rows),
            "run_passed": sum(row["run_passed"] for row in arm_rows),
            "syntax_valid": sum(row["syntax_valid"] for row in arm_rows),
            "output_truncated": sum(row["output_truncated"] for row in costs),
            "scores": {
                "official_compatible": statistics.mean(row["official_compatible"] for row in arm_rows),
                "target_coverage": statistics.mean(row["target_coverage"] for row in arm_rows),
                "target_conditional": statistics.mean(
                    row["target_conditional"] for row in arm_rows if row["target_conditional"] is not None
                ) if any(row["target_conditional"] is not None for row in arm_rows) else None,
                "target_strict": statistics.mean(row["target_strict"] for row in arm_rows),
            },
            "by_target_status": {
                status: {
                    "tasks": len(part),
                    "target_strict": statistics.mean(row["target_strict"] for row in part),
                    "official_compatible": statistics.mean(row["official_compatible"] for row in part),
                }
                for status in ("add", "update")
                if (part := [row for row in arm_rows if row["target_status"] == status])
            },
            "cost": {
                "input_tokens": _distribution([row["input_tokens"] for row in costs]),
                "output_tokens": _distribution([row["output_tokens"] for row in costs]),
                "generation_seconds": _distribution([row["generation_seconds"] for row in costs]),
            },
        }
    return result


def _paired(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    by_key = {(row["task_id"], row["arm"]): row for row in rows}
    task_ids = sorted({row["task_id"] for row in rows})
    deltas = [
        by_key[(task_id, "memorycore_l0")][metric] - by_key[(task_id, "full_history")][metric]
        for task_id in task_ids
    ]
    wins = sum(delta > 0 for delta in deltas)
    losses = sum(delta < 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    non_ties = wins + losses
    sign_p = min(1.0, 2 * sum(math.comb(non_ties, k) for k in range(0, min(wins, losses) + 1)) / 2**non_ties) if non_ties else 1.0
    randomizer = random.Random(BOOTSTRAP_SEED)
    bootstrap = [statistics.mean(randomizer.choices(deltas, k=len(deltas))) for _ in range(10_000)]
    return {
        "metric": metric,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_delta": statistics.mean(deltas),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_95ci": [_quantile(bootstrap, 0.025), _quantile(bootstrap, 0.975)],
        "exact_sign_p_two_sided": sign_p,
    }


def evaluate(packets_path: Path, receipt_paths: list[Path]) -> dict[str, Any]:
    packets = _read_jsonl(packets_path)
    packet_by_id = {packet["task_id"]: packet for packet in packets}
    receipts = [row for path in receipt_paths for row in _read_jsonl(path)]
    keys = [(row["task_id"], row["arm"]) for row in receipts]
    expected = {(task_id, arm) for task_id in packet_by_id for arm in ARMS}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("receipts must contain exactly one row per task and arm")
    for receipt in receipts:
        packet_arm = packet_by_id[receipt["task_id"]]["arms"][receipt["arm"]]
        prompt_hash = hashlib.sha256(
            (packet_arm["system"] + "\0" + packet_arm["user"]).encode()
        ).hexdigest()
        if receipt["prompt_sha256"] != prompt_hash or receipt["source_session_ids"] != packet_arm["source_session_ids"]:
            raise ValueError(f"receipt alignment failed: {receipt['task_id']} {receipt['arm']}")

    scored = [score_receipt(packet_by_id[receipt["task_id"]], receipt) for receipt in receipts]
    aggregates = _aggregate(scored, receipts)
    paired_strict = _paired(scored, "target_strict")
    paired_official = _paired(scored, "official_compatible")
    retrievals = [packet["retrieval"] for packet in packets]
    receipt_text = _canonical_receipts(receipts)
    shard_loads = {
        str(shard): next(row["load_seconds"] for row in receipts if row["shard"] == shard)
        for shard in sorted({row["shard"] for row in receipts})
    }
    full_tokens = aggregates["full_history"]["cost"]["input_tokens"]["sum"]
    memory_tokens = aggregates["memorycore_l0"]["cost"]["input_tokens"]["sum"]
    gates = {
        "protocol_complete": all(row["status"] == "passed" for row in receipts),
        "memorycore_directional_gain": paired_strict["mean_delta"] > 0,
        "memorycore_high_confidence_gain": (
            paired_strict["bootstrap_95ci"][0] > 0
            and paired_strict["exact_sign_p_two_sided"] < 0.05
        ),
        "memorycore_update_no_net_loss": (
            aggregates["memorycore_l0"]["by_target_status"]["update"]["target_strict"]
            >= aggregates["full_history"]["by_target_status"]["update"]["target_strict"]
        ),
        "memorycore_input_cost_below_full_history": memory_tokens < full_tokens,
    }
    return {
        "schema": 1,
        "protocol": "topic3-be-memorycode-score-v1",
        "status": "pass" if gates["protocol_complete"] else "fail",
        "claim_boundary": {
            "memorycore_l0": "label-blind raw-session retrieval/injection method validation",
            "latest_guidelines_oracle": "privileged extraction ceiling; excluded from product-gain gates",
            "l1_extraction": "not evaluated",
            "business_or_coding_agent_utility": "not evaluated",
        },
        "tasks": len(packets),
        "independent_dialogue_clusters": len(packets),
        "execution": {
            "model": receipts[0]["model"],
            "decoding": receipts[0]["decoding"],
            "max_input_tokens": receipts[0]["max_input_tokens"],
            "max_new_tokens": receipts[0]["max_new_tokens"],
            "parallel_shards": len(shard_loads),
            "model_load_seconds_by_shard": shard_loads,
            "generation_latency_includes_prefill": True,
            "generation_latency_excludes_model_load": True,
        },
        "packets": {
            "rows": len(packets),
            "bytes": packets_path.stat().st_size,
            "sha256": hashlib.sha256(packets_path.read_bytes()).hexdigest(),
            "committed": False,
        },
        "receipts": {
            "rows": len(receipts),
            "bytes": len(receipt_text.encode()),
            "sha256": hashlib.sha256(receipt_text.encode()).hexdigest(),
        },
        "arms": aggregates,
        "paired": {
            "memorycore_l0_vs_full_history_target_strict": paired_strict,
            "memorycore_l0_vs_full_history_official_compatible": paired_official,
        },
        "retrieval": {
            "k": retrievals[0]["k"],
            "target_session_recall": sum(row["target_recall"] for row in retrievals) / len(retrievals),
            "target_session_recall_by_status": {
                status: sum(packet["retrieval"]["target_recall"] for packet in part) / len(part)
                for status in ("add", "update")
                if (part := [packet for packet in packets if packet["target_status"] == status])
            },
            "selected_sessions": _distribution([row["selected_count"] for row in retrievals]),
            "latency_ms": _distribution([row["elapsed_ms"] for row in retrievals]),
            "strategies": dict(Counter(row["strategy"] for row in retrievals)),
        },
        "cost_comparison": {
            "memorycore_over_full_input_ratio": memory_tokens / full_tokens,
            "memorycore_input_token_delta": memory_tokens - full_tokens,
        },
        "gates": gates,
        "metric_definitions": {
            "official_compatible": "mean over active rules whose Python object appears; syntax errors score zero",
            "target_coverage": "fraction of query-target rules producing a non-null official-compatible judgment",
            "target_conditional": "correctness among covered query-target rules",
            "target_strict": "query-target correctness with absent target objects scored zero",
            "target_session_recall": "all latest source sessions for the query target occur in injected records",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--normalized-receipts-output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.packets, args.receipts)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if args.normalized_receipts_output:
        args.normalized_receipts_output.write_text(
            _canonical_receipts([row for path in args.receipts for row in _read_jsonl(path)])
        )


if __name__ == "__main__":
    main()
