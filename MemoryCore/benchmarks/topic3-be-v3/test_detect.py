import unittest
from detect import validate

class BoundaryTest(unittest.TestCase):
    def test_non_object_does_not_crash(self):
        for value in ['[]', '1', 'null', '"changed"']:
            self.assertEqual(validate(dict(text=value), {})[1], 'schema')

    def test_invalid_quote_preserves_raw_relation(self):
        import json
        fields = dict(subject='user', attribute='count', scope='current', old_fact='four', new_fact='seven',
                      old_quote='invented', new_quote='seven', relation='changed')
        parsed, error = validate(dict(text=json.dumps(fields)), dict(old=dict(content='four'), later=dict(content='seven')))
        self.assertEqual(error, 'quote')
        self.assertEqual(parsed['relation'], 'changed')

if __name__ == '__main__':
    unittest.main()
