import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from amb_adapter import materialize, read_session, tree_digest


class AmbAdapterTest(unittest.TestCase):
    def test_tree_digest_ignores_interpreter_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "task.json").write_text("{}")
            before = tree_digest(root)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "task.cpython-312.pyc").write_bytes(b"generated")
            self.assertEqual(tree_digest(root), before)

    def test_session_requires_json_events_with_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "session.jsonl"
            path.write_text(json.dumps({"role": "user", "content": "feedback"}) + "\n")
            self.assertEqual(read_session(path)[0]["content"], "feedback")
            path.write_text(json.dumps({"role": "tool", "content": "feedback"}) + "\n")
            with self.assertRaisesRegex(ValueError, "invalid event"):
                read_session(path)

    def test_materialize_copies_only_the_task_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "source", Path(temp) / "work"
            tree = source / "tasks" / "fa-demo" / "tree"
            tree.mkdir(parents=True)
            (tree / "README.md").write_text("visible")
            (tree.parent / "task.json").write_text("{}")
            (tree.parent / "checker.py").write_text("hidden")
            result = materialize(source, "fa-demo", output)
            self.assertEqual(result["files"], 1)
            self.assertTrue((output / "README.md").is_file())
            self.assertFalse((output / "checker.py").exists())


if __name__ == "__main__":
    unittest.main()
