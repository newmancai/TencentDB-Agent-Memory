import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from memorycode_prepare import _latest_instructions, _query_targets, _target_status
from memorycode_score import criterion, evaluate, extract_objects


class MemoryCodePrepareTest(unittest.TestCase):
    def test_update_status_uses_occurrence_not_shuffled_version_id(self):
        dialogue = {"instructions": [[[6, 4]], [-1], [[6, 1]]]}
        self.assertEqual(_latest_instructions(dialogue)[6], (2, 1, 2))
        instructions = {"task": [{"id": 6, "regex": [["function", "^a"], ["function", "^b"],
                                                     ["function", "^c"], ["function", "^d"],
                                                     ["function", "^x"]]}]}
        targets = _query_targets(dialogue, "task", instructions)
        self.assertEqual(_target_status(targets), "update")
        self.assertEqual(targets[0]["source_session_id"], 2)


class MemoryCodeScoreTest(unittest.TestCase):
    def test_official_absence_and_strict_target_are_distinguishable(self):
        objects = extract_objects("def good_x(value_x):\n    return value_x\n")
        self.assertEqual(criterion(objects, "function", ".*_x$"), 1.0)
        self.assertIsNone(criterion(objects, "class", "^C"))
        self.assertEqual(criterion(extract_objects("not python !!!"), "function", ".*_x$"), 0.0)

    def test_structured_evaluation_checks_alignment_and_missing_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            arms = {}
            receipts = []
            outputs = {
                "full_history": "def plain(value):\n    return value\n",
                "memorycore_l0": "def kept_x(value):\n    return value\n",
                "latest_guidelines_oracle": "def kept_x(value):\n    return value\n",
            }
            for arm, output in outputs.items():
                mode = "baseline" if arm == "full_history" else "enabled" if arm == "memorycore_l0" else "oracle"
                arms[arm] = {"mode": mode, "system": "s", "user": "u", "source_session_ids": [0]}
                receipts.append({
                    "task_id": "t", "dialogue_id": 1, "arm": arm, "mode": mode,
                    "model": "fixture-model", "decoding": "greedy",
                    "status": "passed", "output": output,
                    "prompt_sha256": hashlib.sha256(b"s\0u").hexdigest(), "source_session_ids": [0],
                    "input_tokens": 10, "max_input_tokens": 1024, "max_new_tokens": 128,
                    "output_tokens": 5, "generation_seconds": 0.1,
                    "output_truncated": False,
                    "shard": 0, "load_seconds": 0.01,
                })
            packet = {
                "task_id": "t", "dialogue_id": 1, "history_class": "short", "session_count": 3,
                "target_status": "update", "arms": arms,
                "targets": [{"object_type": "function", "regex": ".*_x$"}],
                "active_rules": [{"object_type": "function", "regex": ".*_x$"}],
                "retrieval": {"k": 1, "target_recall": True, "selected_count": 1,
                              "elapsed_ms": 0.1, "strategy": "fts"},
            }
            packets = root / "packets.jsonl"
            runs = root / "runs.jsonl"
            packets.write_text(json.dumps(packet) + "\n")
            runs.write_text("".join(json.dumps(row) + "\n" for row in receipts))
            result = evaluate(packets, [runs])
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["paired"]["memorycore_l0_vs_full_history_target_strict"]["wins"], 1)
            self.assertEqual(result["arms"]["full_history"]["scores"]["target_strict"], 0.0)
            self.assertEqual(result["execution"]["model_load_seconds_by_shard"], {"0": 0.01})

            receipts[0].pop("shard")
            runs.write_text("".join(json.dumps(row) + "\n" for row in receipts))
            with self.assertRaisesRegex(ValueError, "missing required fields: shard"):
                evaluate(packets, [runs])

            receipts[0]["shard"] = 0
            receipts[0]["model"] = "mixed-model"
            runs.write_text("".join(json.dumps(row) + "\n" for row in receipts))
            with self.assertRaisesRegex(ValueError, "inconsistent execution metadata: model"):
                evaluate(packets, [runs])


if __name__ == "__main__":
    unittest.main()
