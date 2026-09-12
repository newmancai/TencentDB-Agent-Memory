"""Fixed source-transfer baseline; adapter observations and labels stay separate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline

LABELS = ['NEG_1', 'NEG_2', 'NEG_3', 'NEG_4', 'POS', 'NEU']
SEED = 20260913


def read(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def visible_input(observation):
    parts, clipped = [], 0
    for message in observation['history'][-2:] + [observation['incoming']]:
        value = message['text']
        if len(value) > 8192:
            value = value[:4096] + '\n[middle omitted]\n' + value[-4096:]
            clipped += 1
        parts.append(message['role'] + ':\n' + value)
    return '\n\n'.join(parts), clipped


def classifier():
    return Pipeline([
        ('features', FeatureUnion([
            ('word', TfidfVectorizer(ngram_range=(1, 2), max_features=20000,
                                     sublinear_tf=True)),
            ('char', TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                                     max_features=30000, sublinear_tf=True)),
        ])),
        ('head', LogisticRegression(C=1, class_weight='balanced', max_iter=2000,
                                     random_state=SEED)),
    ])


def scores(gold, predicted, probability=None):
    neg_gold = np.array([x.startswith('NEG_') for x in gold])
    neg_pred = np.array([x.startswith('NEG_') for x in predicted])
    result = {
        'n': len(gold), 'accuracy': float(accuracy_score(gold, predicted)),
        'macro_f1': float(f1_score(gold, predicted, labels=LABELS,
                                  average='macro', zero_division=0)),
        'per_class': classification_report(gold, predicted, labels=LABELS,
                                           output_dict=True, zero_division=0),
        'negative': {'tp': int(sum(neg_gold & neg_pred)),
                     'fp': int(sum(~neg_gold & neg_pred)),
                     'fn': int(sum(neg_gold & ~neg_pred)),
                     'tn': int(sum(~neg_gold & ~neg_pred))},
    }
    if probability is not None:
        target = np.array([[int(y == label) for label in LABELS] for y in gold])
        result['brier_sum_over_classes'] = float(np.mean(np.sum((probability-target)**2, axis=1)))
        confidence = probability.max(axis=1)
        correct = np.array(gold) == np.array(predicted)
        result['confidence_bins'] = []
        for lo, hi in [(0, .4), (.4, .6), (.6, .8), (.8, 1.000001)]:
            mask = (confidence >= lo) & (confidence < hi)
            result['confidence_bins'].append({'lower': lo, 'upper': min(hi, 1),
                'n': int(mask.sum()), 'accuracy': float(correct[mask].mean()) if mask.any() else None,
                'mean_confidence': float(confidence[mask].mean()) if mask.any() else None})
    return result


def probabilities(model, texts):
    raw = model.predict_proba(texts)
    return np.array([[row[list(model.classes_).index(label)] if label in model.classes_ else 0
                      for label in LABELS] for row in raw])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    observations = read(args.data / 'observations.jsonl')
    labels = read(args.data / 'labels.jsonl')
    assert len({x['id'] for x in observations}) == len(observations)
    assert len({x['id'] for x in labels}) == len(labels)
    by_id = {x['id']: x for x in labels}
    rows, unknown = [], []
    for observation in observations:
        label = by_id[observation['id']].get('label')
        if label is None:
            unknown.append(observation['id'])
            continue
        assert label in LABELS
        text, clipped = visible_input(observation)
        rows.append({**observation, 'target': label, 'visible': text, 'clipped': clipped})
    train = [r for r in rows if r['source'] == 'lmsys']
    test = [r for r in rows if r['source'] == 'wildchat']
    assert train and test and len(train) + len(test) == len(rows)
    assert not ({r['group'] for r in train} & {r['group'] for r in test})
    with (args.out / 'semantic-tasks.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps({'id': row['id'], 'visible': row['visible']}, ensure_ascii=False)+'\n')
    x = [r['visible'] for r in train]
    y = np.array([r['target'] for r in train])
    groups = [r['group'] for r in train]
    oof = np.empty(len(train), dtype=object)
    cv_seconds = time.perf_counter()
    for fit, validation in GroupKFold(n_splits=5).split(x, y, groups):
        model = classifier().fit([x[i] for i in fit], y[fit])
        oof[validation] = model.predict([x[i] for i in validation])
    cv_seconds = time.perf_counter() - cv_seconds
    started = time.perf_counter()
    model = classifier().fit(x, y)
    fit_seconds = time.perf_counter() - started
    # Test targets never enter fitting; persist the state before test scoring.
    joblib.dump(model, args.out / 'model.joblib')
    started = time.perf_counter()
    probability = probabilities(model, [r['visible'] for r in test])
    predict_seconds = time.perf_counter() - started
    predicted = np.array([LABELS[i] for i in probability.argmax(axis=1)])
    gold = np.array([r['target'] for r in test])
    majority = Counter(y).most_common(1)[0][0]
    baseline = np.array([majority] * len(test))
    unique_groups = sorted({r['group'] for r in test})
    group_indices = {g: [i for i, r in enumerate(test) if r['group'] == g] for g in unique_groups}
    rng = np.random.default_rng(SEED)
    differences = []
    for _ in range(1000):
        indices = [i for group in rng.choice(unique_groups, len(unique_groups), replace=True)
                   for i in group_indices[group]]
        differences.append(f1_score(gold[indices], predicted[indices], labels=LABELS,
                           average='macro', zero_division=0) -
                           f1_score(gold[indices], baseline[indices], labels=LABELS,
                           average='macro', zero_division=0))
    summary = {'protocol': 'natural-feedback-v1', 'seed': SEED,
        'split': {name: {'events': len(data), 'groups': len({r['group'] for r in data}),
                         'labels': dict(Counter(r['target'] for r in data)),
                         'clipped_messages': sum(r['clipped'] for r in data)}
                  for name, data in [('lmsys_train', train), ('wildchat_test', test)]},
        'unknown_unscored': unknown, 'majority_label': majority,
        'lmsys_group_oof': scores(y, oof),
        'wildchat_tfidf': scores(gold, predicted, probability),
        'wildchat_majority': scores(gold, baseline),
        'paired_group_bootstrap_macro_f1_delta_95': np.quantile(differences, [.025, .975]).tolist(),
        'cost': {'cv_seconds': cv_seconds, 'fit_seconds': fit_seconds,
                 'batch_predict_seconds': predict_seconds,
                 'features': sum(len(v.vocabulary_) for _, v in model['features'].transformer_list),
                 'fit_iterations': model['head'].n_iter_.tolist()}}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    with (args.out / 'predictions.jsonl').open('w') as stream:
        for row, pred, prob in zip(test, predicted, probability):
            stream.write(json.dumps({'id': row['id'], 'group': row['group'],
                'gold': row['target'], 'predicted': pred, 'mode': 'supervised_tfidf',
                'probability': dict(zip(LABELS, prob.tolist())),
                'passed': bool(pred == row['target'])}) + '\n')
    (args.out / 'train-ids.json').write_text(json.dumps([r['id'] for r in train]) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
