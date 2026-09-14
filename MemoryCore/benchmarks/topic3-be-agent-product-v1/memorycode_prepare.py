#!/usr/bin/env python3
"""Audit MemoryCode and freeze a balanced, label-blind method subset."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SESSION_COUNTS = (1, 2, 3, 4, 5, 10, 15, 20, 30, 40, 50, 100)
SELECTION_DOMAIN = "topic3-be-memorycode-method-v1"


def _hash(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def _dialogue_id(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def _latest_instructions(dialogue: dict[str, Any]) -> dict[int, tuple[int, int, int]]:
    latest: dict[int, tuple[int, int, int]] = {}
    occurrences: Counter[int] = Counter()
    for session_id, pairs in enumerate(dialogue["instructions"]):
        if pairs == [-1]:
            continue
        for instruction_id, update_id in pairs:
            occurrences[instruction_id] += 1
            latest[instruction_id] = (session_id, update_id, occurrences[instruction_id])
    return latest


def _query_targets(
    dialogue: dict[str, Any], query: str, instruction_by_query: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    latest = _latest_instructions(dialogue)
    targets = []
    for instruction in instruction_by_query[query]:
        instruction_id = instruction["id"]
        if instruction_id not in latest:
            continue
        session_id, update_id, occurrence = latest[instruction_id]
        targets.append(
            {
                "instruction_id": instruction_id,
                "update_id": update_id,
                "occurrence": occurrence,
                "source_session_id": session_id,
                "object_type": instruction["regex"][update_id][0],
                "regex": instruction["regex"][update_id][1],
            }
        )
    if not targets:
        raise ValueError(f"no active instruction for query: {query}")
    return targets


def _target_status(targets: list[dict[str, Any]]) -> str:
    return "update" if any(target["occurrence"] > 1 for target in targets) else "add"


def _tree_digest(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def prepare(dataset_root: Path) -> dict[str, Any]:
    dialogue_dir = dataset_root / "dataset"
    topics_path = dataset_root / "topics.json"
    files = sorted(dialogue_dir.glob("dialogue_*.json"), key=_dialogue_id)
    if len(files) != 360 or [_dialogue_id(path) for path in files] != list(range(1, 361)):
        raise ValueError("expected the official 360 consecutively numbered dialogues")

    topics = json.loads(topics_path.read_text())
    instruction_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for instruction in topics["instructions"]:
        instruction_by_query[instruction["eval_query"]].append(instruction)

    dialogues: list[tuple[int, dict[str, Any]]] = []
    type_counts: Counter[str] = Counter()
    session_lengths: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()
    total_session_evals = 0
    total_history_evals = 0
    for path in files:
        dialogue = json.loads(path.read_text())
        dialogues.append((_dialogue_id(path), dialogue))
        for session in dialogue["sessions"]:
            type_counts.update(item for item in session["type"] if item)
            session_lengths[session["session_length"]] += 1
            object_counts.update(object_type for object_type, _ in session["session_regex"])
            total_session_evals += len(session["session_eval_query"])
        total_history_evals += len(dialogue["sessions"][-1]["history_eval_query"])

    selected: list[dict[str, Any]] = []
    for session_count in SESSION_COUNTS:
        used_dialogues: set[int] = set()
        desired_statuses = ("add", "add" if session_count <= 2 else "update")
        for slot, desired_status in enumerate(desired_statuses):
            candidates = []
            for dialogue_id, dialogue in dialogues:
                if len(dialogue["sessions"]) != session_count or dialogue_id in used_dialogues:
                    continue
                eligible = []
                for query in dialogue["sessions"][-1]["history_eval_query"]:
                    targets = _query_targets(dialogue, query, instruction_by_query)
                    if _target_status(targets) == desired_status:
                        eligible.append((query, targets))
                if eligible:
                    candidates.append(
                        (_hash(SELECTION_DOMAIN, session_count, slot, desired_status, dialogue_id),
                         dialogue_id, dialogue, eligible)
                    )
            if not candidates:
                raise ValueError(f"no {desired_status} candidate for {session_count} sessions")
            _, dialogue_id, dialogue, eligible = min(candidates, key=lambda row: row[0])
            query, targets = min(
                eligible, key=lambda row: _hash(SELECTION_DOMAIN, dialogue_id, row[0])
            )
            used_dialogues.add(dialogue_id)
            selected.append(
                {
                    "id": f"memorycode-{dialogue_id:03d}",
                    "dialogue_id": dialogue_id,
                    "session_count": session_count,
                    "history_class": "short" if dialogue_id <= 210 else "long",
                    "target_status": desired_status,
                    "eval_query": query,
                    "targets": targets,
                }
            )

    return {
        "schema": 1,
        "protocol": SELECTION_DOMAIN,
        "dataset": {
            "name": "CohereLabsCommunity/MemoryCode",
            "source_commit": "1ab87e119b2f9a498de8075219e1c07f6041b394",
            "hf_revision": "32d888b11c73c67be91414e571dfe98c5c20feac",
            "hf_parquet_bytes": 11666648,
            "hf_parquet_sha256": "1edb12380ea3410c888fffa795f6ddd3251e4e634b84a7142c8386e7c2869733",
            "license": "Apache-2.0",
            "dialogue_count": len(files),
            "dialogue_tree_sha256": _tree_digest(files),
            "topics_sha256": hashlib.sha256(topics_path.read_bytes()).hexdigest(),
        },
        "audit": {
            "sessions": sum(len(dialogue["sessions"]) for _, dialogue in dialogues),
            "session_counts": list(SESSION_COUNTS),
            "session_lengths": dict(sorted(session_lengths.items())),
            "event_types": dict(sorted(type_counts.items())),
            "evaluations": {
                "session": total_session_evals,
                "final_history": total_history_evals,
            },
            "objects": dict(sorted(object_counts.items())),
        },
        "selection": {
            "unit": "dialogue",
            "method": (
                "two independent dialogues per official session-count stratum; "
                "domain-separated SHA-256 ordering; one final-history query per dialogue; "
                "one add and one update where updates exist"
            ),
            "seed": SELECTION_DOMAIN,
            "task_count": len(selected),
            "cluster_count": len(selected),
            "tasks": selected,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.dataset_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
