import unittest
from detect import examples_for
class ExampleIsolation(unittest.TestCase):
 def test_only_label_differs(self):
  examples=[dict(source_pair='private',target={'text':'old'},evidence={'old':'old','later':'new'},relation='A')]
  labeled=examples_for(examples,'labeled');unlabeled=examples_for(examples,'unlabeled')
  self.assertEqual([{k:v for k,v in x.items() if k!='relation'} for x in labeled],unlabeled)
  self.assertNotIn('source_pair',labeled[0]);self.assertEqual(examples_for(examples,'none'),[])
  self.assertIn('relation',examples[0])
if __name__=='__main__':unittest.main()
