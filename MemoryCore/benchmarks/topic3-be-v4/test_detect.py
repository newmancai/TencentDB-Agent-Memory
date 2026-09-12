import json
import unittest
from detect import segments,validate

class ContractTests(unittest.TestCase):
    def test_lossless(self):
        for s in ['A 3.10 version.\nLater?  Yes!', 'a\n\nb', 'No punctuation']:
            self.assertEqual(''.join(x['text'] for x in segments(s,'o')),s)
    def test_wrong_side_id(self):
        evidence={s:dict(spans=segments('text',p)) for s,p in [('old','o'),('later','n')]}
        obj=dict(subject='',attribute='',scope='',old_fact='',new_fact='',old_ids=['n0'],new_ids=['n0'],relation='same')
        self.assertEqual(validate(dict(text=json.dumps(obj)),evidence)[1],'source_id')
        self.assertEqual(validate(dict(text='[]'),evidence)[1],'schema')
if __name__=='__main__': unittest.main()
