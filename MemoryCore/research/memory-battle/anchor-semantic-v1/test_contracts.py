import unittest
from infer import align_quote
from tool_envelope import parse_tool_output


class Contracts(unittest.TestCase):
    def test_typography_does_not_erase_semantic_changes(self):
        self.assertEqual(align_quote("I'm home",'I’m home.',True),'typographic')
        for quote,source in [('I am home','I am not home'),('1.0','10'),
                             ('Alice moved','Bob moved'),('I moved','I might move')]:
            self.assertIsNone(align_quote(quote,source,True))

    def test_complete_tool_envelope_and_plain_text(self):
        value=parse_tool_output('Looking up. <tool_call>{"name":"recall","arguments":{"query":"x"}}</tool_call>',{'recall'},'a')
        self.assertEqual(value['content'],'Looking up.')
        self.assertEqual(value['tool_calls'][0]['function']['arguments'],'{"query": "x"}')
        self.assertEqual(parse_tool_output('answer',set(),'a'),{'role':'assistant','content':'answer'})

    def test_does_not_repair_or_allow_unknown_calls(self):
        for text in ['<tool_call>{', '<tool_call>{"name":"delete","arguments":{}}</tool_call>',
                     '<tool_call>{"name":"recall","arguments":[]}</tool_call>']:
            with self.assertRaises(ValueError):parse_tool_output(text,{'recall'},'a')


if __name__=='__main__':unittest.main()
