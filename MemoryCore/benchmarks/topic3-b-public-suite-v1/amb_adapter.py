"""Adapt the pinned Agent Memory Bench snapshot without exposing task evidence."""

import argparse
import ast
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from h6_adapter import safe_path, sha256, write_json


SOURCE_URL = "https://github.com/GiulioDER/agent-memory-bench"
SOURCE_REVISION = "e0859d1ca757f65747b4d32e21f158d55c595879"
ARCHIVE_SHA256 = "8d7f5970ecf81810ddec75ce24eccd94f77320625c4922aaf12a1e5d562e2208"
CORPUS_MANIFEST_SHA256 = "58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814"
TASK_TREE_SHA256 = "00b2cdf5605040853dc4fc1e4968e25a20ae54b36841af380c41c3ccb9936b4b"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def read_session(path: Path) -> list[dict]:
    events = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL {path}:{number}: {error}") from None
        if event.get("role") not in {"user", "assistant"} or not isinstance(event.get("content"), str):
            raise ValueError(f"invalid event {path}:{number}")
        events.append(event)
    return events


def prepare(source: Path, output: Path, revision: str = SOURCE_REVISION) -> dict:
    if revision != SOURCE_REVISION:
        raise ValueError(f"AMB revision must be {SOURCE_REVISION}, got {revision}")
    corpus_manifest_path = source / "corpus" / "manifest.json"
    if sha256(corpus_manifest_path) != CORPUS_MANIFEST_SHA256:
        raise ValueError("unexpected AMB corpus manifest checksum")
    if tree_digest(source / "tasks") != TASK_TREE_SHA256:
        raise ValueError("unexpected AMB task tree checksum")

    corpus_manifest = json.loads(corpus_manifest_path.read_text()).get("sessions")
    if not isinstance(corpus_manifest, dict) or len(corpus_manifest) != 196:
        raise ValueError("unexpected AMB corpus inventory")
    for relative, expected in corpus_manifest.items():
        if not relative.startswith(("sessions/", "distractors/")):
            raise ValueError(f"invalid corpus manifest path: {relative}")
        path = safe_path(source / "corpus", relative)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"corpus hash mismatch: {relative}")

    task_dirs = sorted(path.parent for path in (source / "tasks").glob("*/task.json"))
    if len(task_dirs) != 34:
        raise ValueError("expected 34 executable AMB tasks")
    tasks, gold = [], {}
    groups, synthesis, conditions = Counter(), Counter(), Counter()
    for task_dir in task_dirs:
        data = json.loads((task_dir / "task.json").read_text())
        task_id, prompt = data.get("task_id"), data.get("prompt")
        if task_id != task_dir.name or data.get("kind") != "primary" or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"invalid AMB task: {task_dir.name}")
        if not (task_dir / "tree").is_dir() or not (task_dir / "checker.py").is_file():
            raise ValueError(f"incomplete AMB task: {task_id}")
        ast.parse((task_dir / "checker.py").read_text(), filename=str(task_dir / "checker.py"))
        references = sorted(path.stem for path in (task_dir / "reference").glob("*.py"))
        if not {"naive", "informed"}.issubset(references):
            raise ValueError(f"missing AMB reference pair: {task_id}")
        fact_terms = data.get("fact_terms")
        if not isinstance(fact_terms, list) or not fact_terms or not all(isinstance(term, str) and term for term in fact_terms):
            raise ValueError(f"invalid AMB fact terms: {task_id}")
        group = task_id.split("-", 1)[0]
        groups[group] += 1
        shape = (data.get("synthesis") or {}).get("shape", "single")
        synthesis[shape] += 1
        plants_path = task_dir / "plants.json"
        plant_conditions = []
        if plants_path.is_file():
            plant_conditions = sorted(json.loads(plants_path.read_text()).get("conditions", {}).keys())
            conditions.update(plant_conditions)
        relevant = sorted(
            f"corpus/{relative}" for relative in corpus_manifest
            if relative.startswith(f"sessions/{task_id}/")
        )
        if not relevant:
            raise ValueError(f"task has no relevant corpus source: {task_id}")
        workspace_files = sum(path.is_file() for path in (task_dir / "tree").rglob("*"))
        tasks.append({
            "schema": 1, "id": task_id, "dataset": "agent-memory-bench",
            "kind": "failed_approach" if group == "fa" else "cross_session" if group == "xs" else "prior_convention",
            "prompt": prompt,
            "workspace": {"payload": f"tasks/{task_id}/tree", "fileCount": workspace_files},
            "corpus": {"manifest": "corpus/manifest.json", "visibleSessions": 196},
            "checker": {"interface": "check(workdir, oracle_dir)", "source": f"tasks/{task_id}/checker.py"},
        })
        gold[task_id] = {
            "factTerms": fact_terms,
            "memoryBundleId": data.get("memory_bundle_id"),
            "relevantSourceIds": relevant,
            "synthesis": data.get("synthesis"),
            "references": references,
            "plantConditions": plant_conditions,
        }

    if groups != Counter({"ts": 30, "xs": 3, "fa": 1}):
        raise ValueError(f"unexpected AMB task groups: {groups}")
    if synthesis != Counter({"single": 31, "evolve": 1, "join": 1, "widen": 1}):
        raise ValueError(f"unexpected AMB synthesis inventory: {synthesis}")
    if conditions != Counter({"absent": 15, "adjacent": 15, "contradictory": 14, "superseded": 14}):
        raise ValueError(f"unexpected AMB condition inventory: {conditions}")

    fa_events = read_session(source / gold["fa-dedup-key"]["relevantSourceIds"][0])
    final_user = next(event["content"] for event in reversed(fa_events) if event["role"] == "user")
    if ("What must not happen again is deduplicating on order_id" not in final_user
            or "not choosing the replacement key" not in final_user
            or any("supplier" in term.lower() and "order_id" in term.lower()
                   for term in gold["fa-dedup-key"]["factTerms"])):
        raise ValueError("fa-dedup-key no-answer failure contract changed")
    if not {"naive", "whole_record", "informed", "alternative"}.issubset(gold["fa-dedup-key"]["references"]):
        raise ValueError("fa-dedup-key multi-solution references changed")

    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "tasks.json", tasks)
    write_json(output / "gold.json", gold)
    manifest = {
        "schema": 1, "protocol": "topic3-b-public-suite-v1", "status": "prepared",
        "source": {"url": SOURCE_URL, "revision": SOURCE_REVISION, "archiveSha256": ARCHIVE_SHA256},
        "taskTreeSha256": TASK_TREE_SHA256, "corpusManifestSha256": CORPUS_MANIFEST_SHA256,
        "tasks": 34, "groups": dict(sorted(groups.items())), "corpusSessions": 196,
        "synthesis": dict(sorted(synthesis.items())), "conditionTaskCounts": dict(sorted(conditions.items())),
        "labelsSeparated": True, "officialWritePathMeasured": False,
        "independentModelRun": "not_run",
    }
    manifest["outputHashes"] = {"tasks.json": sha256(output / "tasks.json"), "gold.json": sha256(output / "gold.json")}
    write_json(output / "manifest.json", manifest)
    return manifest


def materialize(source: Path, task_id: str, output: Path) -> dict:
    if not task_id or "/" in task_id or "\\" in task_id or task_id in {".", ".."}:
        raise ValueError("invalid task ID")
    tree = source / "tasks" / task_id / "tree"
    if not (tree.is_dir() and (tree.parent / "task.json").is_file()) or output.exists():
        raise ValueError("unknown task or existing output")
    shutil.copytree(tree, output)
    return {"taskId": task_id, "files": sum(path.is_file() for path in output.rglob("*"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--source", type=Path, required=True)
    materialize_parser.add_argument("--task-id", required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output) if args.action == "prepare" else materialize(args.source, args.task_id, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
