"""Pin and adapt H6 without exposing evaluator-only strategy labels."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath


SOURCE_URL = "https://huggingface.co/datasets/joshuaswarren/h6-failure-gate-tasks"
SOURCE_REVISION = "20017969711c7c72c649d9e4d70a8df730ec6176"
DATASET_SHA256 = "0757c8ede7248ebb233234bedda7d81ac2a4a8a2cd2f9abdb6a79bb0e39d39bf"
INVENTORY_HASH = "687615b5f7ff46977d268a03e30018070f7d0bec9d01e04da2d0c723e59a5b27"
TRAPS = {
    "config-shadowing", "flaky-looking-test", "hidden-invariant",
    "misleading-error-message", "stale-cache-illusion", "wrong-layer-fix",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if not relative or "\\" in relative or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe dataset path: {relative!r}")
    return root.joinpath(*path.parts)


def source_revision(source: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def file_map(files: list[dict]) -> dict[str, str]:
    mapped = {}
    for item in files:
        path, content = item.get("path"), item.get("content")
        if not isinstance(path, str) or not isinstance(content, str) or path in mapped:
            raise ValueError("invalid or duplicate file payload")
        safe_path(Path("."), path)
        mapped[path] = content
    return mapped


def validate_materialized(root: Path, files: list[dict]) -> None:
    for relative, content in file_map(files).items():
        path = safe_path(root, relative)
        if not path.is_file() or path.read_text() != content:
            raise ValueError(f"materialized file mismatch: {path}")


def load(source: Path, revision: str | None = None) -> dict:
    revision = revision or source_revision(source)
    if revision != SOURCE_REVISION:
        raise ValueError(f"H6 revision must be {SOURCE_REVISION}, got {revision}")
    dataset_path = source / "dataset.json"
    if sha256(dataset_path) != DATASET_SHA256:
        raise ValueError("unexpected H6 dataset.json checksum")
    dataset = json.loads(dataset_path.read_text())
    if dataset.get("version") != 1 or dataset.get("inventoryHash") != INVENTORY_HASH:
        raise ValueError("unexpected H6 schema or inventory")
    for relative, expected in dataset.get("supportArtifactHashes", {}).items():
        path = safe_path(source, relative)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"support artifact hash mismatch: {relative}")
    return dataset


def adapt(source: Path, revision: str | None = None) -> tuple[list[dict], dict, dict]:
    dataset = load(source, revision)
    tasks, gold = [], {}
    split_counts, trap_counts = Counter(), Counter()
    declared_splits = {name: set(ids) for name, ids in dataset.get("splits", {}).items()}

    if len(dataset.get("tasks", [])) != 30 or set(declared_splits) != {"dev", "pilot", "main"}:
        raise ValueError("unexpected H6 task inventory")
    for task in dataset["tasks"]:
        task_id, split, trap = task["id"], task["split"], task["trapId"]
        task_path = source / "tasks" / task_id
        stored_task = json.loads((task_path / "task.json").read_text())
        if stored_task != task or task_id not in declared_splits.get(split, set()):
            raise ValueError(f"task index mismatch: {task_id}")
        if trap not in TRAPS or task["checkCommand"] != "node test/check.js":
            raise ValueError(f"unsupported task contract: {task_id}")
        if task["fingerprint"]["strategyId"] != task["variants"][0]["badStrategyPatch"]["id"]:
            raise ValueError(f"fingerprint/strategy mismatch: {task_id}")
        if len(task["variants"]) != 3:
            raise ValueError(f"unexpected variant count: {task_id}")
        split_counts[split] += 1
        trap_counts[trap] += 1

        for variant in task["variants"]:
            case_id = variant["variantId"]
            candidates = variant["strategyCandidates"]
            candidate_ids = [candidate["id"] for candidate in candidates]
            if len(candidates) != 2 or len(set(candidate_ids)) != 2:
                raise ValueError(f"invalid strategy set: {case_id}")
            bad, good = variant["badStrategyPatch"], variant["goodStrategyPatch"]
            if bad["id"] == good["id"] or {bad["id"], good["id"]} != set(candidate_ids):
                raise ValueError(f"invalid strategy labels: {case_id}")
            if next(item for item in candidates if item["id"] == bad["id"]) != bad:
                raise ValueError(f"bad strategy payload mismatch: {case_id}")
            if next(item for item in candidates if item["id"] == good["id"]) != good:
                raise ValueError(f"good strategy payload mismatch: {case_id}")
            files = file_map(variant["files"])
            no_trap = file_map(variant["noTrapControlFiles"])
            if "TASK.md" not in files or "test/check.js" not in files or not no_trap:
                raise ValueError(f"incomplete variant payload: {case_id}")
            validate_materialized(task_path / "variants" / f"variant-{variant['variantIndex']}", variant["files"])

            tasks.append({
                "schema": 1,
                "id": case_id,
                "dataset": "h6-failure-gate",
                "split": split,
                "taskId": task_id,
                "variantIndex": variant["variantIndex"],
                "distance": variant["distance"],
                "prompt": files["TASK.md"],
                "workspace": {"payload": "variant.files", "fileCount": len(files)},
                "checkCommand": ["node", "test/check.js"],
                "actionIntent": task["normalizedActionIntent"],
                "strategyCandidates": [
                    {"id": candidate["id"], "description": candidate["description"]}
                    for candidate in candidates
                ],
                "limits": {"attempts": task["maxAttemptCap"], "tokens": task["maxTokenCap"]},
            })
            gold[case_id] = {
                "taskId": task_id,
                "trapId": trap,
                "trapFingerprint": task["fingerprint"],
                "badStrategyId": bad["id"],
                "goodStrategyId": good["id"],
                "offlineFailureMark": task["offlineFailureMark"],
                "offlineCheckMark": task["offlineCheckMark"],
                "revisions": {
                    "clean": variant["cleanRevisionSha"],
                    "trap": variant["trapRevisionSha"],
                    "right": variant["rightRevisionSha"],
                    "noTrap": variant["noTrapRevisionSha"],
                },
            }

    if split_counts != Counter({"main": 18, "pilot": 12}) or trap_counts != Counter({trap: 5 for trap in TRAPS}):
        raise ValueError("unexpected H6 split or trap distribution")
    if declared_splits["dev"] or declared_splits["pilot"] | declared_splits["main"] != {task["id"] for task in dataset["tasks"]}:
        raise ValueError("invalid H6 declared splits")

    manifest = {
        "schema": 1,
        "protocol": "topic3-b-public-suite-v1",
        "status": "prepared",
        "source": {"url": SOURCE_URL, "revision": SOURCE_REVISION},
        "datasetJsonSha256": sha256(source / "dataset.json"),
        "declaredInventoryHash": INVENTORY_HASH,
        "selectionSeed": dataset["seed"],
        "evaluationUnit": "task_variant_seed_arm",
        "tasks": len(dataset["tasks"]),
        "cases": len(tasks),
        "splitCounts": dict(sorted(split_counts.items())),
        "trapCounts": dict(sorted(trap_counts.items())),
        "labelsSeparated": True,
        "independentModelRun": "not_run",
    }
    return tasks, gold, manifest


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def prepare(source: Path, output: Path, revision: str | None = None) -> dict:
    tasks, gold, manifest = adapt(source, revision)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "tasks.json", tasks)
    write_json(output / "gold.json", gold)
    manifest["outputHashes"] = {
        "tasks.json": sha256(output / "tasks.json"),
        "gold.json": sha256(output / "gold.json"),
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def find_variant(dataset: dict, case_id: str) -> dict:
    for task in dataset["tasks"]:
        for variant in task["variants"]:
            if variant["variantId"] == case_id:
                return variant
    raise ValueError(f"unknown H6 case: {case_id}")


def materialize(source: Path, case_id: str, output: Path, state: str = "baseline",
                strategy: str | None = None, revision: str | None = None) -> dict:
    dataset = load(source, revision)
    variant = find_variant(dataset, case_id)
    if state not in {"baseline", "no-trap"} or state == "no-trap" and strategy:
        raise ValueError("state must be baseline or no-trap; strategies apply only to baseline")
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    files = variant["files"] if state == "baseline" else variant["noTrapControlFiles"]
    mapped = file_map(files)
    if strategy:
        candidates = {item["id"]: item for item in variant["strategyCandidates"]}
        if strategy not in candidates:
            raise ValueError(f"unknown strategy {strategy!r} for {case_id}")
        mapped.update(file_map(candidates[strategy]["files"]))
    output.mkdir(parents=True)
    for relative, content in mapped.items():
        path = safe_path(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return {"caseId": case_id, "state": state, "strategy": strategy, "files": len(mapped)}


def checker_smoke(source: Path, revision: str | None = None) -> dict:
    dataset = load(source, revision)
    sampled = {}
    for task in sorted(dataset["tasks"], key=lambda item: item["id"]):
        sampled.setdefault(task["trapId"], task)
    receipts = []
    with tempfile.TemporaryDirectory(prefix="h6-checker-smoke-") as temp:
        for trap, task in sorted(sampled.items()):
            variant = min(task["variants"], key=lambda item: item["variantIndex"])
            states = [
                ("baseline", "baseline", None, False),
                ("bad", "baseline", variant["badStrategyPatch"]["id"], False),
                ("good", "baseline", variant["goodStrategyPatch"]["id"], True),
                ("no-trap", "no-trap", None, True),
            ]
            for label, state, strategy, expected_pass in states:
                workspace = Path(temp) / f"{variant['variantId']}-{label}"
                materialize(source, variant["variantId"], workspace, state, strategy, revision)
                completed = subprocess.run(
                    ["node", "test/check.js"], cwd=workspace, text=True,
                    capture_output=True, timeout=30,
                )
                output = (completed.stdout + completed.stderr).strip().splitlines()
                observed_pass = completed.returncode == 0
                receipts.append({
                    "caseId": variant["variantId"], "trapId": trap, "state": label,
                    "checkerReturnCode": completed.returncode,
                    "checkerPass": observed_pass, "expectedPass": expected_pass,
                    "matchedExpectation": observed_pass == expected_pass,
                    "lastOutputLine": output[-1] if output else "",
                })
    return {
        "schema": 1, "protocol": "topic3-b-public-suite-v1", "mode": "checker_smoke",
        "status": "pass" if all(row["matchedExpectation"] for row in receipts) else "fail",
        "sampling": "lexicographically first task in each trap class, variant 1",
        "sampledTasks": len(sampled), "checks": len(receipts), "receipts": receipts,
        "modelCalls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--source", type=Path, required=True)
    materialize_parser.add_argument("--case-id", required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)
    materialize_parser.add_argument("--state", choices=["baseline", "no-trap"], default="baseline")
    materialize_parser.add_argument("--strategy")
    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--source", type=Path, required=True)
    smoke_parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.source, args.output)
    elif args.action == "materialize":
        result = materialize(args.source, args.case_id, args.output, args.state, args.strategy)
    else:
        result = checker_smoke(args.source)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
