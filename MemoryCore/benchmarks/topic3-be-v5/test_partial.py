import json
import unittest
from partial import partial_feedback

class PartialContracts(unittest.TestCase):
    def setUp(self):
        self.targets=[dict(id='t0',fact='oldA'),dict(id='t1',fact='oldB')]
        self.evidence={'later':{'spans':[{'id':'n0','text':'new'}]}}
    def run_decisions(self,d):return partial_feedback(dict(text=json.dumps(dict(decisions=d))),self.targets,self.evidence)
    def test_unrelated_unknown_does_not_cancel_valid_change(self):
        r=self.run_decisions([dict(target_id='t0',relation='changed',new_ids=['n0']),dict(target_id='t1',relation='unknown')])
        self.assertEqual(r['relation'],'changed');self.assertEqual(r['issues'],[])
        self.assertEqual(r['feedback'][0]['target']['fact'],'oldA')
    def test_missing_is_not_same(self):
        r=self.run_decisions([dict(target_id='t0',relation='same',new_ids=['n0'])])
        self.assertEqual(r['relation'],'unknown');self.assertFalse(r['feedback'][1]['valid'])
    def test_duplicates_and_target_mutation_rejected(self):
        for d in [[dict(target_id='t0',relation='changed',new_ids=['n0'])]*2,
                  [dict(target_id='t0',relation='changed',new_ids=['n0'],fact='fabricated')]]:
            self.assertEqual(self.run_decisions(d)['relation'],'unknown')
if __name__=='__main__':unittest.main()
