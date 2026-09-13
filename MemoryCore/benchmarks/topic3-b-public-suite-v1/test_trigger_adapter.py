import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from trigger_adapter import adapt_case, regression_id


class TriggerAdapterTest(unittest.TestCase):
    def test_keeps_expectation_out_of_visible_task(self):
        case = {
            "id": "read-1", "module": "implicit-read-pos", "lang": "en",
            "category": "direct", "prompt": "Which manager?",
            "expect": {"trigger": True, "answer_include": ["pnpm"]},
            "seed": [{"name": "manager", "content": "Use pnpm."}],
            "files": [{"path": "package.json", "content": "{}"}], "source": "initial",
        }
        task, gold = adapt_case(case)
        self.assertNotIn("expect", task)
        self.assertNotIn("module", task)
        self.assertEqual(task["initialMemory"][0]["content"], "Use pnpm.")
        self.assertTrue(gold["expect"]["trigger"])

    def test_stable_regression_id_and_unsafe_workspace_rejection(self):
        case = {"query": "Remember tea.", "should_trigger": True}
        task, _ = adapt_case(case, index=0)
        self.assertEqual(task["id"], regression_id(0, case["query"]))
        unsafe = {
            "id": "bad", "module": "trap-read-pos", "lang": "en", "category": "trap",
            "prompt": "Inspect.", "expect": {"trigger": True}, "source": "initial",
            "files": [{"path": "../escape", "content": "x"}],
        }
        with self.assertRaisesRegex(ValueError, "unsafe dataset path"):
            adapt_case(unsafe)


if __name__ == "__main__":
    unittest.main()
