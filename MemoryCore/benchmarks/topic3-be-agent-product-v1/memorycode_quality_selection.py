#!/usr/bin/env python3
"""Select a disjoint public MemoryCode update set for quality validation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from memorycode_prepare import _dialogue_id, _query_targets, _target_status


SESSION_COUNTS = (3, 4, 5, 10, 15, 20, 30, 40, 50, 100)
DEFAULT_SELECTION_DOMAIN = "topic3-be-memorycode-focus-quality-v1"


def selection_hash(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def select(
    dataset_root: Path,
    excluded_selections: list[Path],
    selection_domain: str,
) -> dict[str, Any]:
    excluded = {
        row["dialogue_id"]
        for selection_path in excluded_selections
        for row in json.loads(selection_path.read_text())["selection"]["tasks"]
    }
    topics = json.loads((dataset_root / "topics.json").read_text())
    instructions_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for instruction in topics["instructions"]:
        instructions_by_query[instruction["eval_query"]].append(instruction)

    dialogues = {
        _dialogue_id(path): json.loads(path.read_text())
        for path in (dataset_root / "dataset").glob("dialogue_*.json")
    }
    if len(dialogues) != 360:
        raise ValueError("expected all 360 public MemoryCode dialogues")

    selected = []
    for session_count in SESSION_COUNTS:
        candidates = []
        for dialogue_id, dialogue in dialogues.items():
            if dialogue_id in excluded or len(dialogue["sessions"]) != session_count:
                continue
            for query in dialogue["sessions"][-1]["history_eval_query"]:
                targets = _query_targets(dialogue, query, instructions_by_query)
                if _target_status(targets) != "update" or len(targets) != 1:
                    continue
                candidates.append(
                    (
                        selection_hash(
                            selection_domain, session_count, dialogue_id, query
                        ),
                        dialogue_id,
                        query,
                        targets,
                    )
                )
        if not candidates:
            raise ValueError(
                f"no disjoint single-target update for {session_count} sessions"
            )
        _, dialogue_id, query, targets = min(candidates)
        selected.append(
            {
                "id": f"memorycode-{dialogue_id:03d}",
                "dialogue_id": dialogue_id,
                "session_count": session_count,
                "history_class": "short" if dialogue_id <= 210 else "long",
                "target_status": "update",
                "eval_query": query,
                "targets": targets,
            }
        )

    return {
        "schema": 1,
        "protocol": selection_domain,
        "dataset": "CohereLabsCommunity/MemoryCode",
        "selection": {
            "unit": "dialogue",
            "method": (
                "one disjoint single-target update dialogue per update-capable official "
                "session-count stratum, selected by domain-separated SHA-256 ordering"
            ),
            "excluded_dialogue_count": len(excluded),
            "tasks": selected,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--exclude-selection", type=Path, nargs="+", required=True)
    parser.add_argument("--domain", default=DEFAULT_SELECTION_DOMAIN)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = select(
        arguments.dataset_root,
        arguments.exclude_selection,
        arguments.domain,
    )
    arguments.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
