import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validmem_codex_runner import ARMS, parse_answers, prompt_for, score, select, summarize


def fixture():
    tasks, gold = [], {}
    for part in "ABC":
        for index in range(25):
            case_id = f"{part}-{index:02d}"
            tasks.append({
                "id": case_id, "currentDay": 10, "query": "Current value?",
                "choices": [{"id": "choice-1", "text": "new"}, {"id": "choice-2", "text": "old"}],
                "memoryStore": [
                    {"memoryId": "old", "createdDay": 1, "expiresDay": None,
                     "type": "user", "description": "old"},
                    {"memoryId": "new", "createdDay": 2, "expiresDay": None,
                     "type": "user", "description": "new"},
                ],
            })
            gold[case_id] = {"part": part, "subcategory": "demo", "correctChoiceId": "choice-1",
                             "supersededDecoys": ["old"], "expiredDecoys": []}
    return tasks, gold


class ValidMemCodexRunnerTest(unittest.TestCase):
    def test_split_is_fixed_disjoint_and_stratified(self):
        tasks, gold = fixture()
        development = select(tasks, gold, "development")
        holdout = select(tasks, gold, "holdout")
        self.assertEqual((len(development), len(holdout)), (60, 15))
        self.assertEqual({part: sum(gold[x["id"]]["part"] == part for x in development)
                          for part in "ABC"}, {"A": 20, "B": 20, "C": 20})
        self.assertFalse({x["id"] for x in development} & {x["id"] for x in holdout})

    def test_prompt_has_visible_fields_but_not_lifecycle_labels(self):
        tasks, _ = fixture()
        prompt = prompt_for(tasks[:1], ARMS[2])
        self.assertIn("selectedMemoryIds", prompt)
        self.assertIn("greater than 14", prompt)
        self.assertNotIn("supersededDecoys", prompt)
        self.assertNotIn("correctChoiceId", prompt)

    def test_parse_and_score_reject_invalid_evidence(self):
        tasks, gold = fixture()
        answer = {"id": "A-00", "choiceId": "choice-1", "selectedMemoryIds": ["new"]}
        parsed = parse_answers('{"answers": [' + __import__("json").dumps(answer) + ']}', {"A-00"})
        self.assertTrue(score(tasks[0], gold["A-00"], parsed["A-00"])["crrPass"])
        answer["selectedMemoryIds"] = ["missing"]
        result = score(tasks[0], gold["A-00"], answer)
        self.assertFalse(result["correct"])
        self.assertFalse(result["validSelection"])

    def test_three_arm_summary_requires_every_case(self):
        tasks, gold = fixture()
        chosen = select(tasks, gold, "development")
        rows = []
        for arm in ARMS:
            for task in chosen:
                rows.append({"id": task["id"], "arm": arm, "part": gold[task["id"]]["part"],
                             "correct": True, "crrPass": True, "earPass": True,
                             "validSelection": True})
        calls = [{"arm": arm, "caseIds": [task["id"] for task in chosen], "latencyMs": 1,
                  "promptCharacters": 10, "usage": {}, "parseError": None, "returnCode": 0}
                 for arm in ARMS]
        self.assertEqual(summarize(chosen, gold, rows, calls, "development", 8)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
