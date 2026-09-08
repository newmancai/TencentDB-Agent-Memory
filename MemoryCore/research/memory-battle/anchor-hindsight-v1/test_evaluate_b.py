import json
import tempfile
import unittest
from pathlib import Path
from evaluate_b import evaluate, source_agreement


class ProvenanceScoringTest(unittest.TestCase):
    def test_missing_lineage_is_unknown_not_wrong(self):
        c = dict(id='native-fact', sourceDocumentIds=['another-source'])
        self.assertEqual(source_agreement(c, {'target'}, {'native-fact'}), 'unknown_provenance')
        self.assertEqual(source_agreement(c, {'target'}, set()), 'no_source_overlap')

    def test_overlap_is_source_level_even_if_other_lineage_missing(self):
        c = dict(id='native-fact', sourceDocumentIds=['target', 'another-source'])
        self.assertEqual(source_agreement(c, {'target'}, {'native-fact'}), 'source_overlap')

    def test_native_incomplete_remains_in_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'case.json').write_text(json.dumps({'status': 'error'}))
            result = evaluate([dict(id='case', split='development')],
                              {'case': {'target_record_ids': ['source']}}, p, [], 'development', ['direct'])
            self.assertEqual(result['arms']['direct']['total'], 1)
            self.assertEqual(result['arms']['direct']['native_incomplete'], 1)
            self.assertNotIn('abstained', result['arms']['direct'])

    def test_later_reflect_error_does_not_erase_b_result(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'case.json').write_text(json.dumps({'status': 'error', 'b_recall': {}, 'b_provenance_issues': []}))
            (p/'case.b-candidates.json').write_text(json.dumps([{'id': 'case', 'candidates': [
                {'id': 'native-fact', 'sourceDocumentIds': ['source']}]}]))
            prediction = dict(id='case', arm='direct', parsed={'target_id': 'native-fact'},
                              error=None, input_tokens=12, output_tokens=4, seconds=1.)
            result = evaluate([dict(id='case', split='development')],
                              {'case': {'target_record_ids': ['source']}}, p, [prediction], 'development', ['direct'])
            c = result['arms']['direct']
            self.assertEqual(c['native_incomplete'], 1)
            self.assertEqual(c['source_overlap'], 1)
            self.assertEqual(c['accepted'], 1)


if __name__ == '__main__':
    unittest.main()
