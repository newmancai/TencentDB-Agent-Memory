import unittest
from batch import decode_batch

class BatchMapping(unittest.TestCase):
 def test_positional_mapping_and_count(self):
  self.assertEqual(decode_batch({'text':'A B\nC'},3),(['changed','same','unknown'],None))
  self.assertIsNotNone(decode_batch({'text':'AB'},3)[1])
  self.assertIsNotNone(decode_batch({'text':'[A,B,C]'},3)[1])
if __name__=='__main__':unittest.main()
