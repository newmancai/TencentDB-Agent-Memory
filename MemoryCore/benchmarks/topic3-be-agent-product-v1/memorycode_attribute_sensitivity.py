#!/usr/bin/env python3
"""Post-hoc sensitivity for MemoryCode attributes when the receiver is not named self."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from memorycode_codex_update_full import TASK_IDS


ARMS = ("no_history", "raw_full")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class _ConstructorWrites(ast.NodeVisitor):
    """Collect direct receiver writes while excluding nested lexical scopes."""

    def __init__(self, receiver: str) -> None:
        self.receiver = receiver
        self.attributes: list[str] = []

    def _record(self, targets: list[ast.expr]) -> None:
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == self.receiver
            ):
                self.attributes.append(target.attr)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record(node.targets)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record([node.target])
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._record([node.target])
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def constructor_attributes(code: str) -> list[str] | None:
    """Find constructor writes through the actual first receiver argument."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    attributes = []
    for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        constructors = [
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__"
        ]
        for constructor in constructors:
            arguments = [*constructor.args.posonlyargs, *constructor.args.args]
            if not arguments:
                continue
            receiver = arguments[0].arg
            writes = _ConstructorWrites(receiver)
            for statement in constructor.body:
                writes.visit(statement)
            attributes.extend(writes.attributes)
    return attributes


def receiver_aware_attribute_score(code: str, pattern: str) -> float:
    attributes = constructor_attributes(code)
    if not attributes:
        return 0.0
    return float(all(re.match(pattern, attribute) for attribute in attributes))


def evaluate(packets_path: Path, receipts_path: Path) -> dict[str, Any]:
    packets = {row["task_id"]: row for row in read_jsonl(packets_path)}
    receipts = read_jsonl(receipts_path)
    by_key = {(row["task_id"], row["arm"]): row for row in receipts}
    expected = {(task_id, arm) for task_id in TASK_IDS for arm in ARMS}
    if len(receipts) != len(expected) or set(by_key) != expected:
        raise ValueError("receipts must contain the complete unique frozen matrix")
    if any(row.get("status") != "passed" for row in receipts):
        raise ValueError("sensitivity requires valid completed receipts")
    if any(task_id not in packets for task_id in TASK_IDS):
        raise ValueError("source packets do not contain every frozen task")

    pairs = []
    changed = []
    for task_id in TASK_IDS:
        packet = packets[task_id]
        if len(packet.get("targets", [])) != 1:
            raise ValueError(f"sensitivity requires one target: {task_id}")
        target = packet["targets"][0]
        scores = {}
        for arm in ARMS:
            receipt = by_key[(task_id, arm)]
            frozen = receipt["scores"]["target_strict"]
            sensitivity = frozen
            if target["object_type"] == "attribute":
                sensitivity = receiver_aware_attribute_score(receipt["output"], target["regex"])
            scores[arm] = sensitivity
            if sensitivity != frozen:
                changed.append(
                    {
                        "task_id": task_id,
                        "arm": arm,
                        "frozen": frozen,
                        "receiver_aware": sensitivity,
                        "attributes": constructor_attributes(receipt["output"]),
                    }
                )
        delta = scores["raw_full"] - scores["no_history"]
        pairs.append(
            {
                "task_id": task_id,
                **scores,
                "comparison": "win" if delta > 0 else "loss" if delta < 0 else "tie",
            }
        )
    return {
        "schema": 1,
        "protocol": "memorycode-receiver-aware-attribute-sensitivity-v1",
        "status": "post_hoc_sensitivity_not_primary",
        "quality": {
            "wins": sum(row["comparison"] == "win" for row in pairs),
            "losses": sum(row["comparison"] == "loss" for row in pairs),
            "ties": sum(row["comparison"] == "tie" for row in pairs),
            "no_history_accuracy": sum(row["no_history"] for row in pairs) / len(pairs),
            "raw_full_accuracy": sum(row["raw_full"] for row in pairs) / len(pairs),
            "pairs": pairs,
        },
        "changed_rows": changed,
        "source_sha256": {
            "packets": hashlib.sha256(packets_path.read_bytes()).hexdigest(),
            "receipts": hashlib.sha256(receipts_path.read_bytes()).hexdigest(),
        },
        "claim_boundary": (
            "Changes only attribute extraction to follow the constructor's actual receiver name; "
            "the frozen scorer remains the primary result."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = evaluate(arguments.packets, arguments.receipts)
    arguments.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "quality": result["quality"]}, default=str))


if __name__ == "__main__":
    main()
