"""Input-schema and information-boundary contracts; fixtures are smoke only."""
import json
import tempfile
import unittest
from pathlib import Path
from adapters import neutral, longmemeval


class AdapterTests(unittest.TestCase):
    def test_neutral_excludes_gold_and_preserves_user_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            p.write_text(json.dumps([dict(id="t", owner="u", query="q", answer="secret-gold",
                messages=[dict(role="user", content="x" * 1700), dict(role="assistant", content="not user evidence")])]))
            tasks, gold = neutral(p)
            self.assertNotIn("secret-gold", json.dumps(tasks))
            self.assertEqual("".join(s["content"] for s in tasks[0]["sources"]), "x" * 1700)
            self.assertEqual(gold["t"]["answer"], "secret-gold")

    def test_longmemeval_sorts_dates_and_does_not_promote_answer_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            p.write_text(json.dumps([dict(question_id="t", question="q", answer="private-label",
                question_type="knowledge-update", answer_session_ids=["label-source"],
                haystack_dates=["2024/02/02 (Fri) 12:00", "2024/02/01 (Thu) 12:00"],
                haystack_sessions=[[dict(role="user", content="later")], [dict(role="user", content="earlier")]])]))
            tasks, gold = longmemeval(p)
            self.assertEqual([s["content"] for s in tasks[0]["sources"]], ["earlier", "later"])
            self.assertNotIn("label-source", json.dumps(tasks))
            self.assertEqual(gold["t"]["answer"], "private-label")


if __name__ == "__main__":
    unittest.main()
