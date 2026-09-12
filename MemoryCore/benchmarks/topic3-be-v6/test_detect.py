import unittest
from detect import aggregate,decode

class FeedbackBoundary(unittest.TestCase):
 def test_no_generated_explanation_accepted(self):
  self.assertEqual(decode({'text':'A because it changed'}),('unknown','format'))
  self.assertEqual(decode({'text':' A '}),('changed',None))
 def test_failed_unrelated_target_does_not_cancel_change(self):
  self.assertEqual(aggregate([{'relation':'changed'},{'relation':'unknown'}]),'changed')
  self.assertEqual(aggregate([{'relation':'same'},{'relation':'unknown'}]),'unknown')
  self.assertEqual(aggregate([]),'unknown')
if __name__=='__main__':unittest.main()
