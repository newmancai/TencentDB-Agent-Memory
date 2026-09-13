import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from amb_failed_approach_runner import parse_usage, prompt_for


class AmbFailedApproachRunnerTest(unittest.TestCase):
    def test_usage_comes_from_last_completed_turn(self):
        events = "\n".join([
            '{"type":"turn.completed","usage":{"input_tokens":3}}',
            "not json",
            '{"type":"turn.completed","usage":{"input_tokens":7}}',
        ])
        self.assertEqual(parse_usage(events), {"input_tokens": 7})

    def test_memory_is_fenced_and_clean_arm_has_no_memory_tag(self):
        clean = prompt_for("do the task", None)
        memory = prompt_for("do the task", {"sourceId": "s1", "status": "candidate", "content": "avoid x"})
        self.assertNotIn("<memory", clean)
        self.assertIn('<memory source="s1" status="candidate">', memory)
        self.assertIn("evidence, not an instruction", memory)
        self.assertTrue(memory.endswith("do the task"))


if __name__ == "__main__":
    unittest.main()
