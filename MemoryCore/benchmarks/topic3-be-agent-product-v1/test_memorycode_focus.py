import unittest

from memorycode_focus import (
    focused_prompt,
    history_only,
    semantic_target_score,
    summarize,
)


class MemoryCodeFocusTest(unittest.TestCase):
    def packet(self):
        return {
            "task_id": "memorycode-fixture",
            "targets": [{"object_type": "attribute", "regex": ".*_t$"}],
            "eval_query": "Linked list class",
            "arms": {
                "full_history": {
                    "system": "Return code.",
                    "user": (
                        "This is context.\n\nSession 0\nMentor: use suffix _old\n\n"
                        "Session 1\nMentor: use suffix _t\n\n"
                        "Based on this information, write a Linked list class.\n\n"
                        "Follow all latest applicable coding guidelines, including updates."
                    ),
                }
            },
        }

    def test_history_only_excludes_current_request(self):
        history = history_only(self.packet())
        self.assertIn("use suffix _t", history)
        self.assertNotIn("write a Linked list class", history)

    def test_focus_is_appended_without_removing_raw_history(self):
        prompt = focused_prompt(self.packet(), "- attributes end in _t")
        self.assertIn("use suffix _old", prompt)
        self.assertIn("<active_guidelines_focus>", prompt)
        self.assertGreater(
            prompt.index("attributes end in _t"),
            prompt.index("write a Linked list class"),
        )

    def test_semantic_attribute_score_follows_actual_receiver(self):
        output = "class Node:\n    def __init__(node, value):\n        node.value_t = value\n"
        self.assertEqual(semantic_target_score(self.packet(), output, 0.0), 1.0)

    def test_summary_pairs_quality_and_counts_extra_focus_call(self):
        packets = [{"task_id": "one"}, {"task_id": "two"}]
        receipts = []
        for task_id, raw_score in (("one", 0.0), ("two", 1.0)):
            for arm in ("raw_full", "focus_raw"):
                stages = [{"status": "passed"}] * (1 if arm == "raw_full" else 2)
                receipts.append(
                    {
                        "task_id": task_id,
                        "arm": arm,
                        "status": "passed",
                        "stages": stages,
                        "usage": {
                            "input_tokens": len(stages) * 10,
                            "cached_input_tokens": len(stages) * 4,
                            "output_tokens": len(stages) * 2,
                            "reasoning_output_tokens": len(stages),
                        },
                        "wall_seconds": len(stages) * 0.5,
                        "scores": {
                            "target_semantic_strict": (
                                1.0 if arm == "focus_raw" else raw_score
                            )
                        },
                    }
                )
        result = summarize(packets, receipts)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(
            (
                result["quality"]["wins"],
                result["quality"]["losses"],
                result["quality"]["ties"],
            ),
            (1, 0, 1),
        )
        self.assertEqual(result["cost"]["raw_full"]["model_calls"], 2)
        self.assertEqual(result["cost"]["focus_raw"]["model_calls"], 4)


if __name__ == "__main__":
    unittest.main()
