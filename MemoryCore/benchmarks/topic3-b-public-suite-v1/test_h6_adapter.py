import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from h6_adapter import (INVENTORY_HASH, SOURCE_REVISION, checker_smoke,
                        materialize, prepare, safe_path)


TRAPS = [
    "config-shadowing", "flaky-looking-test", "hidden-invariant",
    "misleading-error-message", "stale-cache-illusion", "wrong-layer-fix",
]


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value)


def make_source(root: Path) -> None:
    tasks = []
    pilot, main = [], []
    for index in range(30):
        task_id = f"h6-task-{index + 1:02d}"
        split = "pilot" if index < 12 else "main"
        (pilot if split == "pilot" else main).append(task_id)
        variants = []
        for variant_index in range(1, 4):
            case_id = f"{task_id}-v{variant_index}"
            base_files = [
                {"path": "TASK.md", "content": f"Repair {case_id}."},
                {"path": "test/check.js", "content": "const fs=require('fs'); process.exit(['good','safe'].includes(fs.readFileSync('src/fix.txt','utf8').trim()) ? 0 : 1);\n"},
                {"path": "src/fix.txt", "content": "base\n"},
            ]
            alpha = {"id": "candidate-alpha", "description": "Alpha.",
                     "files": [{"path": "src/fix.txt", "content": "bad\n"}]}
            beta = {"id": "candidate-beta", "description": "Beta.",
                    "files": [{"path": "src/fix.txt", "content": "good\n"}]}
            variants.append({
                "variantId": case_id, "variantIndex": variant_index, "distance": variant_index,
                "strategyCandidates": [alpha, beta], "badStrategyPatch": alpha,
                "goodStrategyPatch": beta, "files": base_files,
                "noTrapControlFiles": [{**item, "content": "safe\n"} if item["path"] == "src/fix.txt" else item
                                       for item in base_files],
                "cleanRevisionSha": "1" * 40, "trapRevisionSha": "2" * 40,
                "rightRevisionSha": "3" * 40, "noTrapRevisionSha": "4" * 40,
            })
            for item in base_files:
                write(root / "tasks" / task_id / "variants" / f"variant-{variant_index}" / item["path"], item["content"])
        task = {
            "id": task_id, "split": split, "trapId": TRAPS[index // 5],
            "fingerprint": {"version": 1, "strategyId": "candidate-alpha"},
            "description": f"Repair task {index + 1}.", "checkCommand": "node test/check.js",
            "normalizedActionIntent": {"version": 1, "actionType": "edit", "targetSymbol": "fix",
                                       "filePath": "src/fix.txt", "contextHash": f"hash-{index}"},
            "maxAttemptCap": 3, "maxTokenCap": 8192,
            "offlineFailureMark": "FAILED", "offlineCheckMark": "FIXED",
            "variants": variants,
        }
        tasks.append(task)
        write(root / "tasks" / task_id / "task.json", task)
    write(root / "dataset.json", {
        "version": 1, "seed": 81, "inventoryHash": INVENTORY_HASH,
        "supportArtifactHashes": {}, "splits": {"dev": [], "pilot": pilot, "main": main},
        "tasks": tasks,
    })


class H6AdapterTest(unittest.TestCase):
    def test_prepare_separates_visible_cases_and_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp) / "source", Path(temp) / "adapted"
            make_source(root)
            digest = hashlib.sha256((root / "dataset.json").read_bytes()).hexdigest()
            with patch("h6_adapter.DATASET_SHA256", digest):
                manifest = prepare(root, output, SOURCE_REVISION)
                tasks = json.loads((output / "tasks.json").read_text())
                gold = json.loads((output / "gold.json").read_text())

                self.assertEqual((manifest["tasks"], manifest["cases"]), (30, 90))
                self.assertEqual(manifest["splitCounts"], {"main": 18, "pilot": 12})
                self.assertTrue(manifest["labelsSeparated"])
                self.assertNotIn("badStrategyId", tasks[0])
                self.assertNotIn("goodStrategyId", tasks[0])
                self.assertEqual(gold[tasks[0]["id"]]["badStrategyId"], "candidate-alpha")

                workspace = Path(temp) / "workspace"
                result = materialize(root, tasks[0]["id"], workspace, strategy="candidate-beta",
                                     revision=SOURCE_REVISION)
                self.assertEqual(result["files"], 3)
                self.assertEqual((workspace / "src/fix.txt").read_text(), "good\n")
                smoke = checker_smoke(root, SOURCE_REVISION)
                self.assertEqual((smoke["status"], smoke["sampledTasks"], smoke["checks"]),
                                 ("pass", 6, 24))

    def test_rejects_wrong_revision_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            make_source(root)
            with self.assertRaisesRegex(ValueError, "revision must be"):
                prepare(root, Path(temp) / "adapted", "0" * 40)
        with self.assertRaisesRegex(ValueError, "unsafe dataset path"):
            safe_path(Path("."), "../escape")


if __name__ == "__main__":
    unittest.main()
