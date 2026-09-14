import unittest

from memorycode_focus import (
    active_rule_semantic_score,
    cacheable_history_prefix,
    cached_compiler_prompt,
    cached_focused_prompt,
    compact_prompt,
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

    def test_compact_prompt_omits_raw_history(self):
        prompt = compact_prompt(self.packet(), "- attributes end in _t")
        self.assertNotIn("use suffix _old", prompt)
        self.assertIn("attributes end in _t", prompt)
        self.assertIn("write a Linked list class", prompt)

    def test_cached_prompts_share_verbatim_history_prefix(self):
        prefix = cacheable_history_prefix(self.packet())
        compiler = cached_compiler_prompt(self.packet())
        code = cached_focused_prompt(self.packet(), "- attributes end in _t")
        self.assertTrue(compiler.startswith(prefix))
        self.assertTrue(code.startswith(prefix))
        self.assertIn("use suffix _old", prefix)
        self.assertNotIn("write a Linked list class", prefix)

    def test_semantic_attribute_score_follows_actual_receiver(self):
        output = "class Node:\n    def __init__(node, value):\n        node.value_t = value\n"
        self.assertEqual(semantic_target_score(self.packet(), output, 0.0), 1.0)

    def test_active_semantic_score_follows_actual_receiver(self):
        packet = self.packet()
        packet["active_rules"] = [
            {"object_type": "attribute", "regex": ".*value.*"},
            {"object_type": "attribute", "regex": ".*_t$"},
        ]
        output = "class Node:\n    def __init__(node, value):\n        node.value_t = value\n"
        self.assertEqual(active_rule_semantic_score(packet, output), 1.0)

    def test_active_semantic_score_penalizes_missing_target_object(self):
        packet = self.packet()
        packet["active_rules"] = [
            {"object_type": "attribute", "regex": ".*value.*"},
            {"object_type": "attribute", "regex": ".*_t$"},
        ]
        self.assertEqual(
            active_rule_semantic_score(packet, "class Node:\n    pass\n"), 0.0
        )

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
                            "official_compatible": 1.0,
                            "active_rule_semantic": 1.0,
                            "target_frozen_strict": (
                                1.0 if arm == "focus_raw" else raw_score
                            ),
                            "target_semantic_strict": (
                                1.0 if arm == "focus_raw" else raw_score
                            ),
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
        self.assertEqual(
            result["quality"]["official_compatible_mean"],
            {"raw_full": 1.0, "focus_raw": 1.0},
        )
        self.assertEqual(
            result["quality"]["active_rule_semantic_mean"],
            {"raw_full": 1.0, "focus_raw": 1.0},
        )

    def test_summary_accepts_compact_focus_arm(self):
        packets = [{"task_id": "one"}]
        receipts = []
        for arm, calls in (("raw_full", 1), ("focus_compact", 2)):
            receipts.append(
                {
                    "task_id": "one",
                    "arm": arm,
                    "status": "passed",
                    "stages": [{"status": "passed"}] * calls,
                    "usage": {
                        key: 0
                        for key in (
                            "input_tokens",
                            "cached_input_tokens",
                            "output_tokens",
                            "reasoning_output_tokens",
                        )
                    },
                    "wall_seconds": 0.0,
                    "scores": {
                        "official_compatible": 1.0,
                        "active_rule_semantic": 1.0,
                        "target_frozen_strict": 1.0,
                        "target_semantic_strict": 1.0,
                    },
                }
            )
        result = summarize(
            packets,
            receipts,
            focus_arm="focus_compact",
            protocol="memorycode-focus-compact-infra-v1",
        )
        self.assertEqual(result["quality"]["focus_arm"], "focus_compact")
        self.assertEqual(result["quality"]["focus_compact_accuracy"], 1.0)
        self.assertEqual(result["cost"]["focus_compact"]["model_calls"], 2)


if __name__ == "__main__":
    unittest.main()
