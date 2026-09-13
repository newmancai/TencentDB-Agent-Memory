import unittest

from pathlib import Path

from agent_product_runner import command_for, summarize


class ProductRunnerTest(unittest.TestCase):
    def test_paired_summary_keeps_backends_separate(self):
        rows = []
        for backend in ("codex", "claude"):
            rows.extend([
                self.row("update", "necessary_update", f"{backend}_clean", False),
                self.row("update", "necessary_update", f"{backend}_memory", True),
                self.row("control", "same_topic_control", f"{backend}_clean", True),
                self.row("control", "same_topic_control", f"{backend}_memory", True),
            ])
        result = summarize(rows)
        self.assertTrue(result["pass"])
        self.assertEqual(result["paired_memory_vs_clean"]["codex"]["win"], 1)
        self.assertEqual(result["paired_memory_vs_clean"]["claude"]["same_topic_control_tie"], 1)

    def test_claude_oauth_compatible_command_does_not_require_bare_mode(self):
        command = command_for("claude_clean", Path("/tmp/example"), "task", {})
        self.assertNotIn("--bare", command)
        self.assertIn("--no-session-persistence", command)

    @staticmethod
    def row(task_id, kind, arm, passed):
        return {
            "task_id": task_id,
            "kind": kind,
            "arm": arm,
            "backend": arm.split("_", 1)[0],
            "status": "completed",
            "checker_pass": passed,
            "severe_regression": False,
            "agent_wall_seconds": 1.0,
            "usage": {"input_tokens": 10},
        }


if __name__ == "__main__":
    unittest.main()
