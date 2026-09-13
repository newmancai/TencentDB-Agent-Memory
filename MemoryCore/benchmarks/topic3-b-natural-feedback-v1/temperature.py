"""Same-label scalar calibration reference; fit NLL on LMSYS only."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import log_softmax

from run import LABELS, read, scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--scores', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    observations = read(args.data / 'observations.jsonl')
    labels = {r['id']: r.get('label') for r in read(args.data / 'labels.jsonl')}
    receipts = {r['id']: r for r in read(args.scores)}
    train = [r for r in observations if r['source'] == 'lmsys' and labels[r['id']] is not None]
    test = [r for r in observations if r['source'] == 'wildchat' and labels[r['id']] is not None]
    logits = np.array([receipts[r['id']]['logits'] for r in train])
    y = np.array([LABELS.index(labels[r['id']]) for r in train])
    started = time.perf_counter()
    fit = minimize_scalar(lambda log_t: -log_softmax(logits / np.exp(log_t), axis=1)[np.arange(len(y)), y].mean(),
                          bounds=(np.log(.1), np.log(10)), method='bounded')
    assert fit.success
    temperature = float(np.exp(fit.x))
    fit_seconds = time.perf_counter() - started
    test_logits = np.array([receipts[r['id']]['logits'] for r in test])
    probability = np.exp(log_softmax(test_logits / temperature, axis=1))
    predicted = [LABELS[i] for i in probability.argmax(axis=1)]
    result = {'temperature': temperature, 'training_nll': float(fit.fun),
              'fit_seconds': fit_seconds, 'evaluations': fit.nfev,
              'wildchat_temperature': scores([labels[r['id']] for r in test], predicted, probability),
              'scope': 'Post-semantic-aggregate strong calibration reference, fitted only on LMSYS; '
                       'not an additional unseen evaluation. Argmax identical to frozen.'}
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
