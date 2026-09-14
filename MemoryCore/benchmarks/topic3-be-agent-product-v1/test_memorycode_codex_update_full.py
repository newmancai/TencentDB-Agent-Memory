import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from memorycode_codex_update_full import ARMS, TASK_IDS, selected_packets, summarize


class CompleteUpdateDiagnosticTest(unittest.TestCase):
    def test_selection_is_the_complete_frozen_update_stratum(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packets.jsonl"
            rows = [
                {
                    "task_id": task_id,
                    "target_status": "update",
                    "targets": [{"object_type": "function", "regex": ".*"}],
                    "session_count": index + 1,
                }
                for index, task_id in enumerate(TASK_IDS)
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(
                [row["task_id"] for row in selected_packets(path, expected_hash)], list(TASK_IDS)
            )
            rows[-1]["target_status"] = "add"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            changed_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "ten frozen IDs"):
                selected_packets(path, changed_hash)

    def test_summary_counts_independent_pairs_and_cost(self):
        receipts = []
        for index, task_id in enumerate(TASK_IDS):
            for arm in ARMS:
                score = 0.0 if arm == "no_history" and index < 2 else 1.0
                receipts.append(
                    {
                        "task_id": task_id,
                        "arm": arm,
                        "status": "passed",
                        "history_class": "short" if index < 5 else "long",
                        "session_count": index + 1,
                        "scores": {"target_strict": score},
                        "usage": {
                            "input_tokens": 10,
                            "cached_input_tokens": 4,
                            "output_tokens": 2,
                            "reasoning_output_tokens": 1,
                        },
                        "wall_seconds": 0.5,
                    }
                )
        result = summarize({"task_ids": list(TASK_IDS)}, receipts)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(
            (result["quality"]["wins"], result["quality"]["losses"], result["quality"]["ties"]),
            (2, 0, 8),
        )
        self.assertEqual(result["quality"]["by_history_class"]["short"]["wins"], 2)
        self.assertEqual(result["cost"]["raw_full"]["noncached_input_tokens"], 60)


if __name__ == "__main__":
    unittest.main()

