import unittest
from prepare import convert


class BoundaryTests(unittest.TestCase):
    def test_gold_and_answer_named_ids_stay_out_of_runtime(self):
        row = dict(question_id='answer_target', question='Which city?', answer='secret_gold',
                   question_type='knowledge-update',
                   haystack_dates=['2024/02/01 (Thu) 12:00', '2024/01/01 (Mon) 12:00'],
                   haystack_session_ids=['answer_new', 'answer_old'],
                   haystack_sessions=[[dict(role='user', content='I moved to B.', has_answer=True)],
                                      [dict(role='user', content='I live in A.', has_answer=True)]])
        t, g, pair = convert(row)
        import json
        encoded = json.dumps(t)
        for hidden in ['answer_target', 'answer_new', 'answer_old', 'has_answer', 'secret_gold', 'knowledge-update']:
            self.assertNotIn(hidden, encoded)
        self.assertEqual(pair['old']['content'], 'I live in A.')
        self.assertEqual(pair['later']['content'], 'I moved to B.')
        self.assertEqual(g['answer'], 'secret_gold')

    def test_long_turn_chunks_are_lossless_and_missing_pair_is_not_invented(self):
        content = 'unchanged text ' * 400
        t, g, pair = convert(dict(question_id='x', question='q', answer='a', question_type='single-session-user',
                                 haystack_dates=['2024/01/01 (Mon) 00:00'], haystack_session_ids=['answer_x'],
                                 haystack_sessions=[[dict(role='user', content=content, has_answer=True)]]))
        self.assertEqual(''.join(s['content'] for s in t['sources']), content)
        self.assertTrue(all(len(s['content']) <= 1600 for s in t['sources']))
        self.assertEqual({s['parent'] for s in t['sources']}, set(g['support']))
        self.assertIsNone(pair)


if __name__ == '__main__':
    unittest.main()
