import copy
import unittest
from prepare import extract
from score_model import model_input
from feedback import fit, rank_score


def graph():
    def node(key, category, value, class_name=None, time='1'):
        return dict(full_node_id=key, category=category, value=repr(value),
                    class_name=class_name, created_at=time)
    def edge(source, target, operation):
        return dict(source_full_node_id=source, target_full_node_id=target,
                    op_id=operation, created_at='2')
    return dict(nodes=[node('q', 'message & query', 'query', 'query'),
                       node('m', 'memory_entry', 'original 🚀'),
                       node('c', 'memory_context', 'original 🚀'),
                       node('p', 'llm_response', 'prediction', time='3'),
                       node('gold', 'golden_answers', 'SECRET')],
                operations=[dict(op_id='r', op_name='memory_system.retrieve', created_at='2'),
                            dict(op_id='a', op_name='question-answering', created_at='2')],
                edges=[edge('q', 'm', 'r'), edge('m', 'c', 'a'),
                       edge('q', 'p', 'a'), edge('c', 'p', 'a')],
                annotations=[dict(reason='SECRET', final_op_id='r')])


def arms(s, m):
    def receipt(a):
        return dict(error=None, logits=dict(A=a, B=0., C=-1.))
    return dict(direct=receipt(0.5), sufficiency=receipt(s), misuse=receipt(m))


class Contracts(unittest.TestCase):
    def test_actual_two_hop_inputs_ignore_annotations(self):
        original = graph()
        expected = extract(original, 'p')
        modified = copy.deepcopy(original)
        modified['annotations'] = [{'final_op_id': 'a', 'reason': 'DIFFERENT'}]
        modified['nodes'][-1]['value'] = repr('DIFFERENT GOLD')
        self.assertEqual(extract(modified, 'p'), expected)
        self.assertEqual(expected[0]['context'], 'original 🚀')
        self.assertEqual(expected[1], {'memory': 'r', 'response': 'a'})
        self.assertNotIn('prediction', model_input(expected[0], 'context', 'sufficiency'))
        self.assertNotIn('answer', model_input(expected[0], 'context', 'sufficiency'))

    def test_future_context_rejected(self):
        item = graph()
        item['nodes'][2]['created_at'] = '4'
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            extract(item, 'p')

    def test_feedback_changes_order_and_invalid_state_returns_baseline(self):
        examples = [(arms(3., -1.), 0), (arms(2., 0.), 0),
                    (arms(-2., 0.), 1), (arms(-3., 1.), 1)]
        state = fit(examples)
        self.assertGreater(rank_score(arms(-1., 0.), state)['score'], rank_score(arms(1., 0.), state)['score'])
        baseline = rank_score(arms(-1., 0.), state, enabled=False)['score']
        for broken in (None, {}, {**state, 'coefficients': [float('nan'), 0, 0]},
                       {**state, 'scale': [0, 1]}):
            result = rank_score(arms(-1., 0.), broken)
            self.assertTrue(result['fallback'])
            self.assertEqual(result['score'], baseline)
        bad_receipt = arms(-1., 0.)
        bad_receipt['sufficiency']['error'] = 'timeout'
        self.assertEqual(rank_score(bad_receipt, state)['score'], baseline)
        bad_receipt['sufficiency'] = None
        self.assertEqual(rank_score(bad_receipt, state)['score'], baseline)


if __name__ == '__main__':
    unittest.main()
