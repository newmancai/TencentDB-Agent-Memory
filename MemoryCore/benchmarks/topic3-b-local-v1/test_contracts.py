import unittest
from run import decode
from policy import fit, choose
from score import metrics


class Contracts(unittest.TestCase):
    def setUp(self):
        self.turns=[{'id':0},{'id':1},{'id':2}]

    def test_final_or_unknown_evidence_is_not_accepted(self):
        for text in ['{"contradiction":true,"evidence":[2]}','{"contradiction":true,"evidence":[0,9]}']:
            self.assertIsNone(decode(text,self.turns)['contradiction'])

    def test_no_silent_grounding_repair(self):
        for text in ['{"contradiction":true,"evidence":[]}', '{"contradiction":false,"evidence":[0]}',
                     '{"contradiction":true,"evidence":[0,0]}', '{"contradiction":"true","evidence":[0]}']:
            self.assertIsNotNone(decode(text,self.turns)['error'])

    def test_valid_binary_and_grounding(self):
        self.assertEqual(decode('{"contradiction":true,"evidence":[0]}',self.turns)['evidence'],[0])
        self.assertFalse(decode('{"contradiction":false,"evidence":[]}',self.turns)['contradiction'])

    def test_feedback_changes_selection_and_off_reverts(self):
        state=fit([dict(label=True,direct=False,local=True)])
        self.assertEqual(choose(state)['arm'],'local')
        self.assertEqual(choose(state,enabled=False)['arm'],'direct')
        self.assertEqual(choose(fit([]))['arm'],'direct')

    def test_corrupt_state_and_capacity(self):
        for state in [None,{},dict(version=1,selected='local',feedback_count=65)]:
            self.assertEqual(choose(state)['arm'],'direct')
            self.assertTrue(choose(state)['fallback'])
        with self.assertRaises(ValueError):fit([dict(label=True,direct=True,local=True)]*65)

    def test_unannotated_positive_evidence_is_not_false_gold(self):
        d=dict(contradiction=True,evidence=[0,2],receipt=dict(text='{"contradiction":true}',inputTokens=1,outputTokens=1))
        m=metrics([dict(id='x',arms=dict(direct=d))],{'x':dict(contradiction=True,evidence=[])},'direct')
        self.assertEqual(m['correct'],1)
        self.assertEqual(m['positive_evidence_denominator'],0)
        self.assertIsNone(m['positive_evidence_exact'])


if __name__=='__main__':unittest.main()
