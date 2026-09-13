"""Fixed six-logit feedback calibration; no test-time fitting or model calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import joblib
import numpy as np
from scipy.special import log_softmax
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from run import LABELS, SEED, read, scores


def indexed(records, name):
    result = {}
    for row in records:
        identifier = row['id']
        if identifier in result:
            raise ValueError(f'{name}: duplicate ID {identifier}')
        result[identifier] = row
    return result


def classifier():
    return Pipeline([
        ('scale', StandardScaler()),
        ('head', LogisticRegression(C=1, class_weight='balanced',
                                    max_iter=2000, random_state=SEED)),
    ])


def probabilities(model, features):
    raw = model.predict_proba(features)
    output = np.zeros((len(features), len(LABELS)))
    for column, label in enumerate(model.classes_):
        output[:, LABELS.index(label)] = raw[:, column]
    return output


def acquisition_cost(records):
    return {'records': len(records),
            'input_tokens': sum(r['inputTokens'] for r in records),
            'summed_elapsed_ms': sum(r['elapsedMs'] for r in records)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--scores', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    observations = indexed(read(args.data / 'observations.jsonl'), 'observations')
    annotations = indexed(read(args.data / 'labels.jsonl'), 'labels')
    receipts = indexed(read(args.scores), 'scores')
    if observations.keys() != annotations.keys():
        raise ValueError('Observation and annotation ID sets differ')
    if receipts.keys() - observations.keys():
        raise ValueError('Scores contain IDs absent from observations')
    eligible, unknown = [], []
    for identifier, observation in observations.items():
        label = annotations[identifier].get('label')
        if label is None:
            unknown.append(identifier)
        elif label not in LABELS:
            raise ValueError(f'Unknown label for {identifier}: {label}')
        else:
            eligible.append(observation)
    missing = {row['id'] for row in eligible} - receipts.keys()
    if missing:
        raise ValueError(f'Missing scores for {len(missing)} labelled observations: {sorted(missing)}')
    for identifier, receipt in receipts.items():
        if 'error' not in receipt or receipt['error'] is not None:
            raise ValueError(f'Score error or missing error field: {identifier}')
        values = receipt.get('logits')
        if (not isinstance(values, list) or len(values) != len(LABELS)
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       for v in values) or not np.isfinite(values).all()):
            raise ValueError(f'Expected six finite numeric logits: {identifier}')
        tokens, elapsed = receipt.get('inputTokens'), receipt.get('elapsedMs')
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise ValueError(f'Invalid inputTokens: {identifier}')
        if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                or not np.isfinite(elapsed) or elapsed < 0):
            raise ValueError(f'Invalid elapsedMs: {identifier}')

    train = [r for r in eligible if r['source'] == 'lmsys']
    test = [r for r in eligible if r['source'] == 'wildchat']
    if not train or not test or len(train) + len(test) != len(eligible):
        raise ValueError('Expected nonempty LMSYS train and WildChat test only')
    if {r['group'] for r in train} & {r['group'] for r in test}:
        raise ValueError('Train/test conversation groups overlap')
    train_logits = np.asarray([receipts[r['id']]['logits'] for r in train], dtype=float)
    test_logits = np.asarray([receipts[r['id']]['logits'] for r in test], dtype=float)
    x_train, x_test = log_softmax(train_logits, axis=1), log_softmax(test_logits, axis=1)
    y_train = np.asarray([annotations[r['id']]['label'] for r in train])
    groups = [r['group'] for r in train]
    oof_probability = np.zeros((len(train), len(LABELS)))
    started = time.perf_counter()
    for fit, validation in GroupKFold(n_splits=5).split(x_train, y_train, groups):
        model = classifier().fit(x_train[fit], y_train[fit])
        oof_probability[validation] = probabilities(model, x_train[validation])
    cv_seconds = time.perf_counter() - started
    started = time.perf_counter()
    model = classifier().fit(x_train, y_train)
    fit_seconds = time.perf_counter() - started
    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'labels': LABELS, 'input_transform': 'log_softmax',
                 'seed': SEED}, args.out / 'model.joblib')
    started = time.perf_counter()
    learned_probability = probabilities(model, x_test)
    predict_seconds = time.perf_counter() - started
    label_array = np.asarray(LABELS)
    oof_learned = label_array[oof_probability.argmax(axis=1)]
    train_frozen = label_array[train_logits.argmax(axis=1)]
    oof_correct, train_frozen_correct = oof_learned == y_train, train_frozen == y_train
    learned = label_array[learned_probability.argmax(axis=1)]
    frozen = label_array[test_logits.argmax(axis=1)]
    # Test annotations are used only below, after fitting and prediction.
    gold = np.asarray([annotations[r['id']]['label'] for r in test])
    learned_correct, frozen_correct = learned == gold, frozen == gold
    unique_groups = sorted({r['group'] for r in test})
    group_indices = {g: [i for i, r in enumerate(test) if r['group'] == g]
                     for g in unique_groups}
    rng = np.random.default_rng(SEED)
    differences = []
    for _ in range(1000):
        indices = [i for group in rng.choice(unique_groups, len(unique_groups), replace=True)
                   for i in group_indices[group]]
        differences.append(
            f1_score(gold[indices], learned[indices], labels=LABELS,
                     average='macro', zero_division=0)
            - f1_score(gold[indices], frozen[indices], labels=LABELS,
                       average='macro', zero_division=0))
    summary = {
        'protocol': 'natural-feedback-semantic-v1', 'seed': SEED, 'labels': LABELS,
        'split': {name: {'events': len(rows), 'groups': len({r['group'] for r in rows}),
                         'labels': dict(Counter(annotations[r['id']]['label'] for r in rows))}
                  for name, rows in [('lmsys_train', train), ('wildchat_test', test)]},
        'unknown_unscored': unknown,
        'unknown_with_receipts': [identifier for identifier in unknown if identifier in receipts],
        'lmsys_group_oof_learned': scores(y_train, oof_learned, oof_probability),
        'lmsys_frozen': scores(y_train, train_frozen, np.exp(x_train)),
        'lmsys_oof_learned_vs_frozen': {
            'wins': int(np.sum(oof_correct & ~train_frozen_correct)),
            'losses': int(np.sum(~oof_correct & train_frozen_correct)),
            'both_correct': int(np.sum(oof_correct & train_frozen_correct)),
            'both_wrong': int(np.sum(~oof_correct & ~train_frozen_correct))},
        'wildchat_frozen': scores(gold, frozen, np.exp(x_test)),
        'wildchat_learned': scores(gold, learned, learned_probability),
        'learned_vs_frozen': {
            'wins': int(np.sum(learned_correct & ~frozen_correct)),
            'losses': int(np.sum(~learned_correct & frozen_correct)),
            'both_correct': int(np.sum(learned_correct & frozen_correct)),
            'both_wrong': int(np.sum(~learned_correct & ~frozen_correct)),
            'prediction_disagreements': int(np.sum(learned != frozen))},
        'paired_group_bootstrap_macro_f1_delta_95': np.quantile(differences, [.025, .975]).tolist(),
        'cost': {
            'shared_semantic_scoring_all_receipts': acquisition_cost(list(receipts.values())),
            'shared_semantic_scoring_train': acquisition_cost([receipts[r['id']] for r in train]),
            'shared_semantic_scoring_test': acquisition_cost([receipts[r['id']] for r in test]),
            'cv_seconds': cv_seconds, 'fit_seconds': fit_seconds,
            'batch_predict_seconds': predict_seconds,
            'features': len(LABELS), 'fit_iterations': model['head'].n_iter_.tolist()},
        'scope': 'Controlled supervised B behavior classification; not feedback factual correctness, '
                 'memory-fault attribution, or downstream task improvement. Bootstrap is descriptive; '
                 'summed receipt durations are not end-to-end wall time.'}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    with (args.out / 'predictions.jsonl').open('w') as stream:
        for i, row in enumerate(test):
            outcome = ('win' if learned_correct[i] and not frozen_correct[i]
                       else 'loss' if frozen_correct[i] and not learned_correct[i]
                       else 'both_correct' if learned_correct[i] else 'both_wrong')
            stream.write(json.dumps({
                'id': row['id'], 'group': row['group'], 'gold': gold[i],
                'frozen': frozen[i], 'learned': learned[i], 'outcome': outcome,
                'frozen_probability': dict(zip(LABELS, np.exp(x_test[i]).tolist())),
                'learned_probability': dict(zip(LABELS, learned_probability[i].tolist()))},
                ensure_ascii=False) + '\n')
    (args.out / 'train-ids.json').write_text(json.dumps([r['id'] for r in train]) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
