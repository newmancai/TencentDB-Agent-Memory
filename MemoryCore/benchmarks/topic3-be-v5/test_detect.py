import json
import unittest
from detect import targets_from,feedback_from

class TargetContracts(unittest.TestCase):
    def setUp(self):
        self.evidence={'old':{'spans':[{'id':'o0','text':'old'}]},'later':{'spans':[{'id':'n0','text':'new'}]}}
        self.targets=[dict(id='t0',subject='service',attribute='version',scope='test',fact='v1',old_ids=['o0'])]
    def test_cannot_rewrite_or_add_target(self):
        for d in [dict(target_id='t9',relation='changed',new_ids=['n0']),dict(target_id='t0',relation='changed',new_ids=['n0'],fact='v2')]:
            self.assertIsNotNone(feedback_from(dict(text=json.dumps({'decisions':[d]})),self.targets,self.evidence)[2])
    def test_host_preserves_old_target(self):
        d=dict(target_id='t0',relation='changed',new_ids=['n0'])
        feedback,relation,error=feedback_from(dict(text=json.dumps({'decisions':[d]})),self.targets,self.evidence)
        self.assertIsNone(error);self.assertEqual(relation,'changed');self.assertEqual(feedback[0]['target'],self.targets[0])
    def test_empty_not_fabricated(self):
        self.assertEqual(targets_from(dict(text='{"targets":[]}'),self.evidence),([],None))
        self.assertIsNotNone(targets_from(dict(text='[]'),self.evidence)[1])
if __name__=='__main__':unittest.main()
