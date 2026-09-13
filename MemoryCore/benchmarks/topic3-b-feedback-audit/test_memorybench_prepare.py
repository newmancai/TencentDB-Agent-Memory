import unittest
from memorybench_prepare import adapt_log


class FeedbackAlignment(unittest.TestCase):
    def test_sparse_round_and_missing_terminal(self):
        row = {'test_idx': 4, 'dialog_b': [
            {'role': 'user', 'content': 'question'},
            {'role': 'assistant', 'content': 'first'},
            {'role': 'user', 'content': 'retry'},
            {'role': 'assistant', 'content': 'second'},
            {'role': 'user', 'content': 'later'},
            {'role': 'assistant', 'content': 'third'}],
            'implicit_feedback_b': [{'round': 2, 'implicit_action': 'dislike', 'terminated': False}],
            'info': {'golden_answer': 'OFFLINE ONLY'}}
        events = adapt_log(row, 'c', 'b')
        self.assertIsNone(events[0]['feedback'])
        self.assertEqual(events[1]['feedback']['round'], 2)
        self.assertIsNone(events[2]['feedback'])
        self.assertEqual(len(events[0]['history']), 2)
        self.assertEqual(events[1]['history'][-1]['content'], 'second')
        self.assertNotIn('info', events[0])
        self.assertNotIn('OFFLINE ONLY', str(events))

    def test_duplicate_receipt_rejected(self):
        receipt = {'round': 1, 'implicit_action': 'like', 'terminated': True}
        row = {'test_idx': 1, 'dialog_b': [{'role': 'assistant', 'content': 'a'}],
               'implicit_feedback_b': [receipt, receipt]}
        with self.assertRaises(AssertionError):
            adapt_log(row, 'c', 'b')


if __name__ == '__main__':
    unittest.main()
