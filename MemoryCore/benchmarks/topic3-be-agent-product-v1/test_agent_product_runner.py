import unittest

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_product_runner import command_for, read_manifest, run_command, summarize, task_arms


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

    def test_default_arm_order_rotates(self):
        self.assertEqual(task_arms({}, 0), (
            "codex_clean", "codex_memory", "claude_clean", "claude_memory",
        ))
        self.assertEqual(task_arms({}, 2), (
            "claude_clean", "claude_memory", "codex_clean", "codex_memory",
        ))

    def test_manifest_rejects_unsafe_task_id_before_creating_artifacts(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({
                "schema": 1,
                "tasks": [{
                    "id": "../escape", "kind": "necessary_update", "workspaces": {},
                    "prompt": "fix it", "checker": ["true"],
                }],
            }))
            with self.assertRaisesRegex(ValueError, "invalid task"):
                read_manifest(path)

    def test_missing_backend_is_a_structured_launch_error(self):
        result = run_command(["definitely-not-a-real-agent-command"], Path("/tmp"), 1)
        self.assertEqual(result["status"], "launch_error")
        self.assertIsNone(result["returncode"])

    def test_execution_failure_cannot_pass_the_protocol(self):
        rows = []
        for backend in ("codex", "claude"):
            rows.extend([
                self.row("update", "necessary_update", f"{backend}_clean", False),
                self.row("update", "necessary_update", f"{backend}_memory", True),
                self.row("control", "same_topic_control", f"{backend}_clean", True),
                self.row("control", "same_topic_control", f"{backend}_memory", True),
            ])
        rows[1].update({"status": "timeout", "agent_returncode": None})
        result = summarize(rows)
        self.assertFalse(result["pass"])
        self.assertEqual(result["arms"]["codex_memory"]["execution_failures"], 1)

    @staticmethod
    def row(task_id, kind, arm, passed):
        return {
            "task_id": task_id,
            "kind": kind,
            "arm": arm,
            "backend": arm.split("_", 1)[0],
            "status": "completed",
            "agent_returncode": 0,
            "checker_status": "completed",
            "checker_pass": passed,
            "severe_regression": False,
            "agent_wall_seconds": 1.0,
            "usage": {"input_tokens": 10},
        }


if __name__ == "__main__":
    unittest.main()
