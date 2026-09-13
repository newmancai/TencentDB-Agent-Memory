import unittest
from normalize_probe import final_anchor


class Readout(unittest.TestCase):
    def test_presentation_equivalence(self):
        for text in ['ANCHOR: 5','Analysis.\nANCHOR: 5','Analysis.\n**ANCHOR: 5**']:
            self.assertEqual(final_anchor(text,range(1,11),30),5)

    def test_no_inference_from_partial_or_other_numbers(self):
        for text,tokens in [('Turn 5 seems relevant.',30),('ANCHOR: 5\nBut more reasoning follows',30),
                            ('ANCHOR: 51',30),('ANCHOR: unknown',30),('ANCHOR: 5',512)]:
            self.assertIsNone(final_anchor(text,range(1,11),tokens))


if __name__=='__main__':unittest.main()
