"""Combine completed dialogue evaluations without running or changing models."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


def read_rows(path):
    return [json.loads(line) for line in path.open()]


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = (len(values)-1)*q
    lo = int(index)
    hi = min(lo+1, len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(index-lo)


def cost(records):
    return {'calls':len(records),
            **{k:sum(r[k] for r in records) for k in ['inputTokens','outputTokens','elapsedMs']},
            'generation_p50_ms':quantile([r['elapsedMs'] for r in records], .5),
            'generation_p95_ms':quantile([r['elapsedMs'] for r in records], .95)}


def aggregate(development, evaluations, output):
    tasks, labels, predictions = [], {}, []
    by_dialog = {}
    for root in evaluations:
        t = json.loads((root/'tasks.json').read_text())
        g = json.loads((root/'labels.json').read_text())
        p = read_rows(root/'eval-predictions.jsonl')
        assert len(t) == len(g) == len(p)
        assert {v['id'] for v in t} == {v['id'] for v in p} == set(g)
        assert not labels.keys() & g.keys(), 'Duplicate task IDs across evaluations'
        tasks.extend(t); labels.update(g); predictions.extend(p)
        by_dialog[root.name] = json.loads((root/'eval-predictions-summary.json').read_text())
    spec = importlib.util.spec_from_file_location('feedback_report', Path(__file__).with_name('feedback.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        (temp/'tasks.json').write_text(json.dumps(tasks))
        (temp/'labels.json').write_text(json.dumps(labels))
        (temp/'predictions.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in predictions))
        module.score(temp, 'predictions.jsonl')
        result = json.loads((temp/'predictions-summary.json').read_text())
    result['by_dialog'] = by_dialog
    for arm, stats in result['arms'].items():
        stats['precision'] = stats['tp']/(stats['tp']+stats['fp']) if stats['tp']+stats['fp'] else None
        stats['recall'] = stats['tp']/(stats['tp']+stats['fn']) if stats['tp']+stats['fn'] else None
        stats['cost'] = cost([p['arms'][arm] for p in predictions])
    result['candidate_changes'] = {}
    for baseline in ['prose','unlabelled','direct']:
        counts = dict(tp_gain=0,tp_loss=0,fp_removed=0,fp_added=0,
                      jointly_readable_tasks=0,other_tasks=0)
        for p in predictions:
            a, b = p['arms'][baseline]['prediction'], p['arms']['structured']['prediction']
            if a is None or b is None:
                counts['other_tasks'] += 1
                continue
            counts['jointly_readable_tasks'] += 1
            gold = {k for k,v in labels[p['id']].items() if v['actionable_violation']}
            a,b = set(a),set(b)
            counts['tp_gain'] += len((b-a)&gold)
            counts['tp_loss'] += len((a-b)&gold)
            counts['fp_removed'] += len((a-b)-gold)
            counts['fp_added'] += len((b-a)-gold)
        result['candidate_changes']['structured_vs_'+baseline] = counts
    stage_costs = {'development_answers':cost(read_rows(development/'answers.jsonl'))}
    for name, root in [('development_reasoned', development),
                       ('development_compact', development/'compact-fit')]:
        stage_costs[name] = cost([v for p in read_rows(root/'fit-predictions.jsonl')
                                 for v in p['arms'].values()])
    for root in evaluations:
        stage_costs[root.name+'_answers'] = cost(read_rows(root/'answers.jsonl'))
        stage_costs[root.name+'_feedback'] = cost([v for p in read_rows(root/'eval-predictions.jsonl')
                                                   for v in p['arms'].values()])
    result['model_cost_by_stage'] = stage_costs
    result['model_cost_total'] = {k:sum(v[k] for v in stage_costs.values())
                                  for k in ['calls','inputTokens','outputTokens','elapsedMs']}
    result['limits'] = [
        'Two evaluation dialogue streams do not provide independent-checkpoint statistical generalization.',
        'Latency is model generation time, excluding loading, tokenization, checker and end-to-end service time.',
        'Candidate-change diagnostics require jointly readable predictions; all-task main results retain unknowns.',
        'Oracle historical rule-value candidates; no autonomous extraction or source-instance attribution.',
        'Feedback-set quality does not establish memory-fault causality or downstream answer improvement.'
    ]
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    aggregate(Path(sys.argv[1]), [Path(p) for p in sys.argv[3:]], Path(sys.argv[2]))
