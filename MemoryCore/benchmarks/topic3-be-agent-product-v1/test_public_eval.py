import copy
import unittest
from pathlib import Path

from public_eval import evaluate, load_json, load_jsonl


HERE = Path(__file__).resolve().parent


class PublicEvalTest(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(HERE / "public-eval-manifest.json")
        self.rows = load_jsonl(HERE / "fixtures/cupid-method-v1.jsonl")

    def test_recomputes_frozen_public_comparison_and_cost(self):
        result = evaluate(self.manifest, self.rows)
        paired = result["metrics"]["paired_enabled_vs_baseline"]
        self.assertEqual((paired["wins"], paired["losses"], paired["ties"]), (3, 4, 5))
        self.assertEqual(paired["clusters"], 4)
        self.assertLessEqual(paired["cluster_bootstrap_95ci"]["low"], 0)
        self.assertEqual(result["metrics"]["arms"]["feedback"]["input_tokens"], 103354)
        self.assertAlmostEqual(
            result["metrics"]["enabled_vs_baseline_cost"]["input_token_ratio"],
            3.434372300126271,
        )
        self.assertEqual(result["acceptance"]["directional_quality_gain"]["status"], "fail")
        self.assertEqual(result["acceptance"]["high_confidence_quality_gain"]["status"], "fail")

    def test_rejects_selection_mismatch(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["id"] = "not-in-frozen-selection"
        with self.assertRaisesRegex(ValueError, "frozen selection"):
            evaluate(self.manifest, rows)

    def test_reports_instance_types_and_separate_storage_metrics(self):
        result = evaluate(self.manifest, self.rows)
        by_type = result["metrics"]["paired_enabled_vs_baseline"]["by_instance_type"]
        self.assertEqual(set(by_type), {"consistent", "contrastive", "changing"})
        self.assertEqual(result["metrics"]["l1_extraction"]["status"], "not_applicable")
        self.assertEqual(result["metrics"]["l0_retrieval"]["status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
