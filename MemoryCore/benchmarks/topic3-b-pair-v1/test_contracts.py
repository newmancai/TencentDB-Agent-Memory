import unittest
from score import threshold,fit,predict


class Contracts(unittest.TestCase):
    def test_incomplete_pool_is_not_a_clean_negative(self):
        self.assertIsNone(predict(dict(complete=False,scores=[.1,None]),.5))

    def test_off_and_corrupt_state(self):
        self.assertEqual(threshold(dict(version=1,threshold=.9),False),.5)
        for state in [None,{},dict(version=1,threshold=float('nan')),dict(version=1,threshold=2)]:
            self.assertEqual(threshold(state),.5)

    def test_feedback_updates_bounded_threshold(self):
        rows=[dict(id='p',candidate_count=1,arms=dict(pairs=dict(complete=True,scores=[.3]))),
              dict(id='n',candidate_count=1,arms=dict(pairs=dict(complete=True,scores=[.1])))]
        gold={'p':dict(contradiction=True),'n':dict(contradiction=False)}
        self.assertEqual(threshold(fit(rows,gold,'pairs')),.3)
        with self.assertRaises(ValueError):fit(rows*33,gold,'pairs')


if __name__=='__main__':unittest.main()
