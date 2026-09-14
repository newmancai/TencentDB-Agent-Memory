from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from changes import capture_changes


class ChangesTest(unittest.TestCase):
    def test_review_includes_new_files_and_marks_omissions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            evidence = root / "evidence"
            evidence.mkdir()
            (repo / "tracked").write_text("old\n")
            for command in [
                ["git", "init", "-q"],
                ["git", "add", "."],
                [
                    "git",
                    "-c",
                    "user.name=T",
                    "-c",
                    "user.email=t@example.invalid",
                    "commit",
                    "-qm",
                    "base",
                ],
            ]:
                subprocess.run(command, cwd=repo, capture_output=True, check=True)
            (repo / "tracked").write_text("new\n")
            (repo / "new.txt").write_text("new file\n")
            state = repo / "state"
            state.mkdir()
            (state / "private").write_text("PRIVATE")
            (repo / "link").symlink_to(state / "private")
            result = capture_changes(repo, evidence, state)
            text = Path(result["diff"]).read_text()
            self.assertIn("+new\n", text)
            self.assertIn("+new file", text)
            self.assertNotIn("PRIVATE", text)
            self.assertEqual({x["path"] for x in result["omitted"]}, {"link", "state/private"})
            self.assertIn("preexisting_edits", result["scope"])


if __name__ == "__main__":
    unittest.main()
