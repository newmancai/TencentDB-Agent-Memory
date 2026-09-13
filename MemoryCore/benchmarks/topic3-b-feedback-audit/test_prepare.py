import unittest
from prepare import adapt, align


def row(users, labels, texts):
    messages = []
    for u in users:
        messages.extend([{"role": "user", "content": u}, {"role": "assistant", "content": "answer " + u}])
    return {"dataset_source": "test", "conversation_id": "one", "conversation": messages,
            "user_feedback_category": labels, "user_feedback_text": texts}


class ContractTests(unittest.TestCase):
    def test_sparse_does_not_shift_or_fill_unknown(self):
        e, g, u = adapt(row(["start", "failure", "new request", "second failure"],
                            ["NEG_3", "NEG_3"], ["failure", "second failure"]))
        self.assertEqual([x["label"] for x in g], ["NEG_3", None, "NEG_3"])
        self.assertEqual(u, [])

    def test_duplicate_annotation_is_not_duplicate_event(self):
        e, g, u = adapt(row(["start", "fix"], ["NEG_2", "NEG_2"], ["fix", "fix"]))
        self.assertEqual(len(e), 1)
        self.assertEqual(g[0]["annotation_indices"], [0, 1])
        self.assertEqual(g[0]["status"], "duplicate_consistent")

    def test_ambiguous_empty_neutral_is_not_guessed(self):
        a, u = align(row(["start", "one", "two"], ["NEU"], [""]))
        self.assertEqual(a, {})
        self.assertEqual(len(u), 1)

    def test_prefix_is_invariant_to_future_and_labels(self):
        r = row(["start", "fix", "future"], ["NEG_2", "NEU"], ["fix", ""])
        old = adapt(r)[0][0]
        r["conversation"][3]["content"] = "future answer with hidden gold"
        r["conversation"][4]["content"] = "different future user"
        r["user_feedback_category"] = ["POS", "NEU"]
        r["user_feedback_text"] = ["fix", ""]
        self.assertEqual(adapt(r)[0][0], old)
        self.assertEqual(old["incoming"]["id"], "m2")
        self.assertEqual([m["id"] for m in old["history"]], ["m0", "m1"])

    def test_whitespace_preserves_original_text(self):
        r = row(["start", "fix  "], ["NEG_2"], ["fix"])
        e, g, _ = adapt(r)
        self.assertEqual(e[0]["incoming"]["text"], "fix  ")
        self.assertEqual(g[0]["label"], "NEG_2")


if __name__ == "__main__":
    unittest.main()
