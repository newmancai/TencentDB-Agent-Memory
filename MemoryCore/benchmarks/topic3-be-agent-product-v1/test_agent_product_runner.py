import unittest

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from agent_product_runner import (command_for, parse_usage, read_manifest, run_command, summarize,
                                  task_arms, terminal_error, workspace_state)


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
        self.assertFalse(result["pass"])
        self.assertIn("missing_expected_manifest", result["contract_errors"])
        self.assertEqual(result["paired_memory_vs_clean"]["codex"]["win"], 1)
        self.assertEqual(result["paired_memory_vs_clean"]["claude"]["same_topic_control_tie"], 1)

    def test_claude_oauth_compatible_command_does_not_require_bare_mode(self):
        command = command_for("claude_clean", Path("/tmp/example"), "task", {})
        self.assertNotIn("--bare", command)
        self.assertIn("--no-session-persistence", command)
        self.assertIn("--strict-mcp-config", command)
        command = command_for("codex_clean", Path("/tmp/example"), "task", {})
        self.assertIn("project_doc_max_bytes=0", command)
        self.assertIn("memories.use_memories=false", command)

    def test_summary_requires_complete_matrix_and_controls_and_distinguishes_pilot(self):
        tasks, rows = [], []
        for cluster in range(4):
            for i in range(3):
                task = {"id": f"c{cluster}-{i}", "cluster_id": str(cluster),
                        "kind": "necessary_update" if i == 0 else "same_topic_control"}
                tasks.append(task)
                for backend in ("codex", "claude"):
                    for variant in ("clean", "memory"):
                        row = self.row(task["id"], task["kind"], f"{backend}_{variant}", variant == "memory" or i != 0)
                        row["cluster_id"] = str(cluster); rows.append(row)
        manifest = {"tasks": tasks, "evaluation_mode": "heldout"}
        self.assertTrue(summarize(rows, manifest)["pass"])
        self.assertFalse(summarize(rows[:-1], manifest)["pass"])
        self.assertFalse(summarize(rows + [rows[0]], manifest)["pass"])
        self.assertFalse(summarize(rows, {**manifest, "evaluation_mode": "pilot"})["pass"])
        self.assertFalse(summarize(rows, {**manifest, "tasks": tasks[:-1]})["pass"])

    def test_terminal_errors_and_both_claude_usage_formats(self):
        event = {"type": "result", "usage": {"input_tokens": 12}, "total_cost_usd": .03, "is_error": True}
        for stdout in (json.dumps(event, indent=2), '{}\n' + json.dumps(event)):
            self.assertEqual(parse_usage("claude", stdout)["reported_cost_usd"], .03)
            self.assertTrue(terminal_error(stdout))

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

    def test_workspace_state_preserves_leading_porcelain_status_column(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src"
            source.mkdir()
            target = source / "value.py"
            target.write_text("old\n")
            for command in (["git", "init", "-q"], ["git", "add", "."],
                            ["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                             "commit", "-qm", "base"]):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            target.write_text("new\n")
            self.assertEqual(workspace_state(root)["changes"], [" M src/value.py"])

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
