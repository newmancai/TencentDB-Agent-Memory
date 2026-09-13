"""Adapt Agent Memory Trigger Bench without exposing trigger expectations."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from h6_adapter import file_map, sha256, source_revision, write_json


SOURCE_URL = "https://huggingface.co/datasets/wallfacers/agent-memory-trigger-bench"
SOURCE_REVISION = "f64b921474c9d84d073a588ed13568e917275a1c"
FILES = {
    "implicit-read.json": "ba0aceddb8a57ae63cb4d930e67080d8353d472cf27b323205ec682dffc091fe",
    "implicit-write.json": "2fd49e1e2773fca211c316ef3842cf6d716154c6683754ca7d1aaea6f4e919ea",
    "trap.json": "b5c22a5eba0df3c9b23eb3a1bc8b86c39cd1aaf871375423c27637a425ee1bf1",
    "trigger-evals.json": "f77344f54bdcbd8494d7378f26a44258e3bff9422f419ac0a053e1506502a645",
}


def regression_id(index: int, prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    return f"regression-{index + 1:03d}-{digest}"


def adapt_case(case: dict, *, index: int | None = None) -> tuple[dict, dict]:
    regression = "query" in case
    prompt = case.get("query") if regression else case.get("prompt")
    case_id = regression_id(index, prompt) if regression and index is not None else case.get("id")
    expected_trigger = case.get("should_trigger") if regression else (case.get("expect") or {}).get("trigger")
    if not isinstance(case_id, str) or not case_id or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("invalid trigger case identity or prompt")
    if not isinstance(expected_trigger, bool):
        raise ValueError(f"missing trigger expectation: {case_id}")
    seeds = case.get("seed") or []
    if not isinstance(seeds, list) or not all(
        isinstance(item, dict) and isinstance(item.get("name"), str)
        and isinstance(item.get("content"), str) for item in seeds
    ):
        raise ValueError(f"invalid seed: {case_id}")
    files = case.get("files") or []
    file_map(files)

    task = {
        "schema": 1,
        "id": case_id,
        "dataset": "agent-memory-trigger-bench",
        "prompt": prompt,
        "language": case.get("lang", "unspecified"),
        "initialMemory": [{"name": item["name"], "content": item["content"]} for item in seeds],
        "workspaceFiles": files,
    }
    gold = {
        "module": "regression" if regression else case["module"],
        "category": "regression" if regression else case["category"],
        "source": "frozen_legacy" if regression else case["source"],
        "expect": {"trigger": expected_trigger} if regression else case["expect"],
    }
    return task, gold


def prepare(source: Path, output: Path, revision: str | None = None) -> dict:
    revision = revision or source_revision(source)
    if revision != SOURCE_REVISION:
        raise ValueError(f"Trigger Bench revision must be {SOURCE_REVISION}, got {revision}")
    for name, expected in FILES.items():
        if sha256(source / name) != expected:
            raise ValueError(f"unexpected Trigger Bench checksum: {name}")

    cases = []
    for name, expected_count in (("implicit-write.json", 56), ("implicit-read.json", 56), ("trap.json", 28)):
        payload = json.loads((source / name).read_text())
        rows = payload.get("cases")
        if not isinstance(rows, list) or len(rows) != expected_count:
            raise ValueError(f"unexpected Trigger Bench inventory: {name}")
        cases.extend(rows)
    regression = json.loads((source / "trigger-evals.json").read_text())
    if not isinstance(regression, list) or len(regression) != 32:
        raise ValueError("unexpected trigger regression inventory")

    tasks, gold = [], {}
    for case in cases:
        task, labels = adapt_case(case)
        if task["id"] in gold:
            raise ValueError(f"duplicate trigger case ID: {task['id']}")
        tasks.append(task)
        gold[task["id"]] = labels
    for index, case in enumerate(regression):
        task, labels = adapt_case(case, index=index)
        tasks.append(task)
        gold[task["id"]] = labels

    modules = Counter(labels["module"] for labels in gold.values())
    languages = Counter(task["language"] for task in tasks)
    positive = sum(labels["expect"]["trigger"] for labels in gold.values())
    seeded = sum(bool(task["initialMemory"]) for task in tasks)
    workspaces = sum(bool(task["workspaceFiles"]) for task in tasks)
    expected_modules = Counter({
        "implicit-write-pos": 28, "implicit-write-neg": 28,
        "implicit-read-pos": 28, "implicit-read-neg": 28,
        "trap-read-pos": 18, "trap-write-neg": 6, "trap-read-neg": 4,
        "regression": 32,
    })
    if len(tasks) != 172 or modules != expected_modules or positive != 90:
        raise ValueError("Trigger Bench module/label contract changed")
    if languages != Counter({"zh": 72, "en": 68, "unspecified": 32}):
        raise ValueError(f"unexpected language distribution: {languages}")
    if seeded != 46 or workspaces != 2:
        raise ValueError("Trigger Bench environment inventory changed")

    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "tasks.json", tasks)
    write_json(output / "gold.json", gold)
    manifest = {
        "schema": 1,
        "protocol": "topic3-b-public-suite-v1",
        "status": "prepared",
        "source": {"url": SOURCE_URL, "revision": SOURCE_REVISION},
        "inputHashes": FILES,
        "selection": "all_cases_no_subsampling",
        "evaluationUnit": "isolated_cli_turn",
        "cases": len(tasks),
        "triggerPositive": positive,
        "triggerNegative": len(tasks) - positive,
        "seededCases": seeded,
        "workspaceCases": workspaces,
        "moduleCounts": dict(sorted(modules.items())),
        "languageCounts": dict(sorted(languages.items())),
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
