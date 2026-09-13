"""Fit only controlled LoCoMo feedback, freeze transfer scores, then assess labels."""
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from feedback import features, fit, probabilities, rank_score, factorized_stage

LABELS = {'RetrievalError': 'memory', 'ResponseError': 'response',
          'AnnotationError': 'non-memory', 'JudgeError': 'non-memory'}


def main():
    root = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'model'
    destination = root if mode == 'model' else root / mode
    rows = [json.loads(line) for line in (root / mode / 'results.jsonl').read_text().splitlines()]
    labels = json.loads((root / 'adapted/feedback.json').read_text())
    feedback = []
    rejected = []
    for row in rows:
        if row['split'] != 'fit':
            continue
        label = LABELS.get(labels[row['id']]['error_type'])
        try:
            features(row['arms'])
            if label is None:
                raise ValueError('unknown label')
            feedback.append((row['arms'], int(label == 'memory')))
        except (ValueError, KeyError):
            rejected.append(row['id'])
    state = fit(feedback)
    training_majority = 'memory' if sum(y for _, y in feedback) >= len(feedback) / 2 else 'non-memory'
    (destination / 'policy.json').write_text(json.dumps(state, indent=2))
    predictions = []
    for row in rows:
        arms = row['arms']
        direct = arms.get('direct', {})
        stage = {'A': 'memory', 'B': 'response', 'C': 'non-memory', 'D': 'unknown'}.get(direct.get('choice'), 'unknown') if not direct.get('error') else 'unknown'
        try:
            p = probabilities(arms['sufficiency'])
            insufficient = p['B']
        except (ValueError, KeyError):
            insufficient = 0.
        learned = rank_score(arms, state)
        predictions.append(dict(id=row['id'], group=row['group'], split=row['split'],
                                direct=stage, factorized=factorized_stage(arms),
                                scores=dict(direct=rank_score(arms, None, enabled=False)['score'],
                                            insufficiency=insufficient, feedback=learned['score']),
                                learned=learned))
    # No evaluation outcome enters fitting or prediction. All score-based choices
    # use these frozen values; metadata IDs break ties before any label is read.
    (destination / 'predictions.json').write_text(json.dumps(predictions, indent=2))
    labels.update(json.loads((root / 'adapted/reference.json').read_text()))
    summary = dict(scope='selected failed-query attribution; external RAG, not MemoryCore faults',
                   fitting=dict(n=len(feedback), rejected=rejected), splits={}, costs={})
    for split in ('fit', 'eval'):
        subset = [p for p in predictions if p['split'] == split]
        stages, budgets = {}, {}
        for arm in ('direct', 'factorized', 'always_memory', 'always_non_memory', 'training_majority'):
            c = Counter(); confusion = Counter()
            for row in subset:
                label = LABELS.get(labels[row['id']]['error_type'])
                if label is None:
                    c['unmapped'] += 1; continue
                predicted = row[arm] if arm in ('direct', 'factorized') else training_majority if arm == 'training_majority' else 'non-memory' if arm == 'always_non_memory' else 'memory'
                c['n'] += 1; c['agreement'] += predicted == label
                c['memory_labels'] += label == 'memory'; c['memory_predictions'] += predicted == 'memory'
                c['memory_hits'] += predicted == label == 'memory'
                c['non_memory_blame'] += predicted == 'memory' and label != 'memory'
                c['unknown'] += predicted == 'unknown'
                op = labels[row['id']]['operation']
                c['operation_labels'] += label in ('memory', 'response')
                c['candidate_operation_reached'] += label in ('memory', 'response') and op is not None
                c['operation_hits'] += label in ('memory', 'response') and predicted == op
                confusion[label + '->' + predicted] += 1
            stages[arm] = dict(c, confusion=dict(confusion))
        groups = defaultdict(list)
        for row in subset:
            groups[row['group']].append(row)
        for k in (1, 2):
            arms = {}
            for arm in ('direct', 'insufficiency', 'feedback', 'id_order'):
                results = []
                for group, items in sorted(groups.items()):
                    ranked = sorted(items, key=lambda r: (0 if arm == 'id_order' else -r['scores'][arm], r['id']))[:k]
                    results.append(dict(group=group, selected=[r['id'] for r in ranked],
                                        hits=sum(labels[r['id']]['error_type'] == 'RetrievalError' for r in ranked)))
                arms[arm] = dict(selected=sum(len(g['selected']) for g in results), hits=sum(g['hits'] for g in results), groups=results)
            budgets[str(k)] = arms
        summary['splits'][split] = dict(stages=stages, budgets=budgets)
    for split in ('fit', 'eval'):
        costs = {}
        for arm in ('direct', 'sufficiency', 'misuse'):
            receipts = [r['arms'][arm] for r in rows if r['split'] == split and arm in r['arms']]
            times = sorted(r['elapsedMs'] for r in receipts if 'elapsedMs' in r)
            costs[arm] = dict(requests=len(receipts), forward_calls=len(times), errors=sum(bool(r['error']) for r in receipts),
                              inputTokens=sum(r['inputTokens'] for r in receipts),
                              executedInputTokens=sum(r['inputTokens'] for r in receipts if 'elapsedMs' in r), serviceMs=sum(times),
                              p50Ms=statistics.median(times) if times else None,
                              p95Ms=times[max(0, math.ceil(len(times) * .95) - 1)] if times else None)
        summary['costs'][split] = costs
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
