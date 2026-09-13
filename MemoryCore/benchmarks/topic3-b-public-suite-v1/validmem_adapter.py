"""Adapt ValidMem v1.1 while keeping lifecycle labels evaluator-only."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from h6_adapter import sha256, source_revision, write_json


SOURCE_URL = "https://huggingface.co/datasets/Zhou11Alex/ValidMem"
SOURCE_REVISION = "786d5cd9f18e65bff6172d81fcb7c9009350a400"
CASES_SHA256 = "1bccc39b48a644919baef45808ae7a318e30504b383e916ccee6a2c142bb4db0"
MEMORIES_SHA256 = "46627076c4170070ef33aa2c036ade07fe83a827658c0e0a2e2b3602665ac521"
OPTION_SEED = 1309
LABEL_FIELDS = ("ground_truth", "superseded_decoys", "expired_decoys", "irrelevant_decoys")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL {path}:{number}: {error}") from None
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL row {path}:{number}")
        rows.append(value)
    return rows


def ordered_choices(case: dict) -> tuple[list[dict], str]:
    expected = case["expected_answer"]
    answers = [expected, *case["wrong_answers"]]
    if not all(isinstance(answer, str) and answer for answer in answers) or len(set(answers)) != len(answers):
        raise ValueError(f"invalid answer choices: {case.get('id')}")
    answers.sort(key=lambda answer: hashlib.sha256(
        f"{OPTION_SEED}:{case['id']}:{answer}".encode()
    ).digest())
    choices = [{"id": f"choice-{index + 1}", "text": answer}
               for index, answer in enumerate(answers)]
    correct = next(choice["id"] for choice in choices if choice["text"] == expected)
    return choices, correct


def adapt_case(case: dict, memories: dict[str, dict]) -> tuple[dict, dict]:
    case_id = case.get("id")
    refs = []
    for field in LABEL_FIELDS:
        values = case.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"invalid {field}: {case_id}")
        refs.extend(values)
    if len(refs) != len(set(refs)):
        raise ValueError(f"overlapping lifecycle labels: {case_id}")
    try:
        store = [memories[memory_id] for memory_id in refs]
    except KeyError as error:
        raise ValueError(f"missing memory {error.args[0]}: {case_id}") from None
    store.sort(key=lambda item: (item["created_day"], item["mem_id"]))
    choices, correct = ordered_choices(case)
    task = {
        "schema": 1,
        "id": case_id,
        "dataset": "validmem-v1.1",
        "query": case["query"],
        "currentDay": case["current_day"],
        "language": case["language"],
        "choices": choices,
        "memoryStore": [{
            "memoryId": item["mem_id"],
            "domain": item["domain"],
            "type": item["type"],
            "description": item["description"],
            "createdDay": item["created_day"],
            "expiresAtRaw": item["expires_at_raw"],
            "expiresDay": item["expires_day"],
            "language": item["language"],
        } for item in store],
    }
    gold = {
        "part": case["part"],
        "subcategory": case["subcategory"],
        "domain": case["domain"],
        "expectedAnswer": case["expected_answer"],
        "correctChoiceId": correct,
        "groundTruth": case["ground_truth"],
        "supersededDecoys": case["superseded_decoys"],
        "expiredDecoys": case["expired_decoys"],
        "irrelevantDecoys": case["irrelevant_decoys"],
    }
    return task, gold


def prepare(source: Path, output: Path, revision: str | None = None) -> dict:
    revision = revision or source_revision(source)
    if revision != SOURCE_REVISION:
        raise ValueError(f"ValidMem revision must be {SOURCE_REVISION}, got {revision}")
    cases_path, memories_path = source / "data/cases.jsonl", source / "data/memories.jsonl"
    if sha256(cases_path) != CASES_SHA256 or sha256(memories_path) != MEMORIES_SHA256:
        raise ValueError("unexpected ValidMem checksum")
    cases, memory_rows = read_jsonl(cases_path), read_jsonl(memories_path)
    memories = {row.get("mem_id"): row for row in memory_rows}
    if len(cases) != 466 or len(memory_rows) != 1393 or len(memories) != 1393 or None in memories:
        raise ValueError("unexpected ValidMem inventory")

    tasks, gold = [], {}
    for case in cases:
        task, labels = adapt_case(case, memories)
        if not isinstance(task["id"], str) or task["id"] in gold:
            raise ValueError(f"invalid or duplicate case ID: {task['id']!r}")
        tasks.append(task)
        gold[task["id"]] = labels

    parts = Counter(case["part"] for case in cases)
    case_languages = Counter(case["language"] for case in cases)
    memory_languages = Counter(row["language"] for row in memory_rows)
    referenced = {memory_id for case in cases for field in LABEL_FIELDS for memory_id in case[field]}
    empty_ground_truth = sum(not case["ground_truth"] for case in cases)
    choice_counts = Counter(1 + len(case["wrong_answers"]) for case in cases)
    store_counts = Counter(sum(len(case[field]) for field in LABEL_FIELDS) for case in cases)
    if parts != Counter({"B": 196, "A": 170, "C": 100}):
        raise ValueError(f"unexpected ValidMem partitions: {parts}")
    if case_languages != Counter({"en": 439, "zh": 17, "mixed": 10}):
        raise ValueError(f"unexpected case language distribution: {case_languages}")
    if memory_languages != Counter({"en": 1324, "zh": 62, "mixed": 7}):
        raise ValueError(f"unexpected memory language distribution: {memory_languages}")
    if empty_ground_truth != 69 or len(referenced) != 1381:
        raise ValueError("ValidMem empty/reachable contract changed")

    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "tasks.json", tasks)
    write_json(output / "gold.json", gold)
    manifest = {
        "schema": 1,
        "protocol": "topic3-b-public-suite-v1",
        "status": "prepared",
        "source": {"url": SOURCE_URL, "revision": SOURCE_REVISION, "version": "v1.1"},
        "inputHashes": {"cases.jsonl": CASES_SHA256, "memories.jsonl": MEMORIES_SHA256},
        "selection": "all_cases_no_subsampling",
        "evaluationUnit": "case",
        "optionPermutationSeed": OPTION_SEED,
        "cases": len(tasks),
        "memories": len(memory_rows),
        "reachableMemories": len(referenced),
        "emptyGroundTruthCasesRetained": empty_ground_truth,
        "partCounts": dict(sorted(parts.items())),
        "choiceCountDistribution": dict(sorted(choice_counts.items())),
        "storeSizeDistribution": dict(sorted(store_counts.items())),
        "caseLanguageCounts": dict(sorted(case_languages.items())),
        "memoryLanguageCounts": dict(sorted(memory_languages.items())),
        "labelsSeparated": True,
        "independentModelRun": "not_run",
    }
    manifest["outputHashes"] = {
        "tasks.json": sha256(output / "tasks.json"),
        "gold.json": sha256(output / "gold.json"),
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
