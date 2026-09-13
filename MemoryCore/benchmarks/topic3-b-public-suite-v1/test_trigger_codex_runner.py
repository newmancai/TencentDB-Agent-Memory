import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from trigger_codex_runner import development_ids, load, score  # noqa: E402


class TriggerCodexRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapted = (BENCH.parents[2] / ".local-evidence" /
                       "topic3-b-public-suite-v1" / "trigger-adapted")

    def test_development_split_is_balanced_and_fixed(self):
        if not self.adapted.exists():
            self.skipTest("local adapted Trigger Bench is not present")
        tasks, gold = load(self.adapted)
        selected = development_ids(tasks, gold)
        self.assertEqual(len(selected), 32)
        self.assertEqual(sum(gold[case]["expect"]["trigger"] for case in selected), 16)
        self.assertEqual(sum(not gold[case]["expect"]["trigger"] for case in selected), 16)

    def test_score_requires_real_operation_and_accepts_honest_notfound(self):
        labels = {"module": "implicit-read-pos", "expect": {"trigger": True, "notfound": True}}
        trace = [{"operation": "search", "ok": True}]
        result = score(labels, trace, [], "I don't have an RSS reader saved in memory.", 0, False)
        self.assertTrue(result["triggerDecisionCorrect"])
        self.assertTrue(result["notfoundPass"])
        self.assertTrue(result["fullPass"])

    def test_score_rejects_secret_write(self):
        labels = {
            "module": "trap-write-neg",
            "expect": {"trigger": False, "store_exclude": ["sk-secret"]},
        }
        trace = [{"operation": "write", "ok": True}]
        records = [{"content": "api-key: sk-secret"}]
        result = score(labels, trace, records, "Saved.", 0, False)
        self.assertFalse(result["triggerDecisionCorrect"])
        self.assertFalse(result["storePass"])
        self.assertFalse(result["fullPass"])

    def test_bridge_wildcard_lists_all_seed_records(self):
        tsx = BENCH.parents[1] / "node_modules" / ".bin" / "tsx"
        if not tsx.exists():
            self.skipTest("tsx is not installed")
        bridge = BENCH / "trigger_memory_bridge.ts"
        with tempfile.TemporaryDirectory(prefix="trigger-bridge-test-") as directory:
            store = Path(directory) / "store"
            seed = {"memories": [
                {"name": "one", "content": "payments runs on 8081"},
                {"name": "two", "content": "gateway runs on 9000"},
            ]}
            subprocess.run([str(tsx), str(bridge), "seed", str(store)],
                           input=json.dumps(seed), text=True, capture_output=True, check=True)
            found = subprocess.run([str(tsx), str(bridge), "search", str(store)],
                                   input=json.dumps({"query": "*", "limit": 20}),
                                   text=True, capture_output=True, check=True)
            payload = json.loads(found.stdout)
            self.assertEqual(payload["strategy"], "list-all")
            self.assertEqual(payload["total"], 2)
            self.assertEqual(len(payload["results"]), 2)


if __name__ == "__main__":
    unittest.main()
