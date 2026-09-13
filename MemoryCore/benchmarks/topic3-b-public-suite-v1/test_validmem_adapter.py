import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validmem_adapter import adapt_case, ordered_choices


class ValidMemAdapterTest(unittest.TestCase):
    def setUp(self):
        self.memories = {
            "m-old": {"mem_id": "m-old", "domain": "project", "type": "feedback",
                      "description": "Use npm.", "created_day": 1, "expires_at_raw": "null",
                      "expires_day": None, "language": "en"},
            "m-new": {"mem_id": "m-new", "domain": "project", "type": "feedback",
                      "description": "Use pnpm.", "created_day": 2, "expires_at_raw": None,
                      "expires_day": None, "language": "en"},
        }
        self.case = {
            "id": "case-1", "part": "A", "subcategory": "replacement", "domain": "project",
            "current_day": 3, "query": "Which package manager?", "expected_answer": "pnpm",
            "wrong_answers": ["npm"], "ground_truth": ["m-new"],
            "superseded_decoys": ["m-old"], "expired_decoys": [],
            "irrelevant_decoys": [], "language": "en",
        }

    def test_keeps_lifecycle_labels_out_of_visible_task(self):
        task, gold = adapt_case(self.case, self.memories)
        self.assertEqual([row["memoryId"] for row in task["memoryStore"]], ["m-old", "m-new"])
        self.assertEqual(task["memoryStore"][0]["expiresAtRaw"], "null")
        self.assertNotIn("groundTruth", task)
        self.assertNotIn("supersededDecoys", task)
        self.assertEqual(gold["groundTruth"], ["m-new"])
        self.assertIn(gold["correctChoiceId"], {row["id"] for row in task["choices"]})
        self.assertEqual(ordered_choices(self.case), ordered_choices(self.case))

    def test_rejects_overlapping_or_missing_memory_labels(self):
        case = dict(self.case, expired_decoys=["m-old"])
        with self.assertRaisesRegex(ValueError, "overlapping"):
            adapt_case(case, self.memories)
        case = dict(self.case, ground_truth=["missing"])
        with self.assertRaisesRegex(ValueError, "missing memory"):
            adapt_case(case, self.memories)


if __name__ == "__main__":
    unittest.main()
