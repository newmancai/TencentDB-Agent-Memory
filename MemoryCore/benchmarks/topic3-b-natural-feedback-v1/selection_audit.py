"""Post-hoc cached-score audit: fixed labels, no training or threshold selection."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import logsumexp
from sklearn.metrics import roc_auc_score


def read(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def curve(confidence, errors, tie):
    order = np.lexsort((tie, -confidence))
    return np.cumsum(errors[order]) / np.arange(1, len(order) + 1), order


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--scores', type=Path, required=True)
    parser.add_argument('--temperature', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows = read(args.predictions)
    raw_receipts = read(args.scores)
    receipts = {r['id']: r for r in raw_receipts}
    assert len(receipts) == len(raw_receipts)
    assert len({r['id'] for r in rows}) == len(rows)
    assert all(receipts[r['id']].get('error') is None for r in rows)
    labels = ['NEG_1', 'NEG_2', 'NEG_3', 'NEG_4', 'POS', 'NEU']
    temperature = json.loads(args.temperature.read_text())['temperature']
    logits = np.array([receipts[r['id']]['logits'] for r in rows])
    assert logits.shape == (len(rows), 6) and np.isfinite(logits).all()
    assert np.isfinite(temperature) and temperature > 0
    frozen = logits.argmax(axis=1)
    assert [labels[i] for i in frozen] == [r['frozen'] for r in rows]
    tie = np.array([hashlib.sha256(r['id'].encode()).hexdigest() for r in rows])
    # Winner-vs-rest log odds preserves posterior ordering without softmax=1 ties.
    remaining = logits.copy()
    remaining[np.arange(len(rows)), frozen] = -np.inf
    learned_p = np.array([r['learned_probability'][r['frozen']] for r in rows])
    assert ((learned_p > 0) & (learned_p < 1)).all()
    confidence = {
        'frozen': logits[np.arange(len(rows)), frozen] - logsumexp(remaining, axis=1),
        'temperature': logits[np.arange(len(rows)), frozen] / temperature - logsumexp(remaining / temperature, axis=1),
        'learned': np.log(learned_p) - np.log1p(-learned_p),
    }
    assert all(np.isfinite(v).all() for v in confidence.values())
    errors = np.array([r['frozen'] != r['gold'] for r in rows], dtype=int)
    summaries, curves = {}, {}
    for name, values in confidence.items():
        risk, order = curve(values, errors, tie)
        curves[name] = risk
        summaries[name] = {'aurc': float(risk.mean()), 'unique_confidence_scores': len(np.unique(values)),
                           'correctness_auroc': float(roc_auc_score(1-errors, values)),
                           'coverage_points': []}
        for fraction in [.25, .5, .75, 1.0]:
            n = int(np.ceil(fraction * len(rows)))
            summaries[name]['coverage_points'].append({'retained': n, 'coverage': n / len(rows),
                'errors': int(errors[order[:n]].sum()), 'risk': float(risk[n-1])})
    groups = sorted({r['group'] for r in rows})
    indices = {g: np.array([i for i, r in enumerate(rows) if r['group'] == g]) for g in groups}
    rng = np.random.default_rng(20260913)
    delta = {name: [] for name in ['frozen', 'temperature']}
    for _ in range(1000):
        sample = np.concatenate([indices[g] for g in rng.choice(groups, len(groups), replace=True)])
        sampled = {name: curve(v[sample], errors[sample], tie[sample])[0].mean()
                   for name, v in confidence.items()}
        for name in delta:
            delta[name].append(sampled['learned'] - sampled[name])
    result = {'protocol': 'fixed-label-confidence-selection-diagnostic-v1', 'events': len(rows),
        'groups': len(groups), 'fixed_correct': int((1-errors).sum()), 'temperature': temperature,
        'methods': summaries,
        'paired_group_bootstrap_aurc_delta_learned_minus_reference_95': {
            name: np.quantile(values, [.025, .975]).tolist() for name, values in delta.items()},
        'scope': 'Historical WildChat reuse, post-hoc diagnostic. All labels fixed to prior frozen predictions. '
                 'No fitted threshold, new training, model calls, or generalization claim. '
                 'Lower AURC better. Feedback behavior correctness only; no memory-fault truth.'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'selection-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    (args.out / 'selection-curves.json').write_text(json.dumps({k: v.tolist() for k,v in curves.items()})+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
