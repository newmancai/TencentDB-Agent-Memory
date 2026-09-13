import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from amb_failed_approach_runner import observed_memory_inputs, parse_usage, prompt_for


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

    def test_observed_memory_uses_a_scored_failure_without_prescribing_a_fix(self):
        content = "def consolidate(paths):\n    return []\n"
        digest = hashlib.sha256(content.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "clean.artifact.json").write_text(json.dumps({"content": content}))
            (run / "receipts.jsonl").write_text(json.dumps({
                "arm": "clean", "checkerPass": False, "workspaceInputDigest": "workspace",
                "artifactSha256": digest, "checkerVerdict": "records were dropped",
            }) + "\n")
            memories = observed_memory_inputs(run, "workspace")
            with self.assertRaises(ValueError):
                observed_memory_inputs(run, "different-workspace")
        self.assertIsNone(memories["e_only_replay"])
        candidate = json.loads(memories["observed_failure_replay"]["content"])
        self.assertEqual(candidate["failed_artifact_sha256"], digest)
        self.assertEqual(candidate["checker_outcome"], "records were dropped")
        self.assertIn("does not prescribe", candidate["unresolved"])


if __name__ == "__main__":
    unittest.main()
