"""A bounded feedback-trained ranking head; scores are not confidence guarantees."""
import math


def probabilities(receipt):
    if not isinstance(receipt, dict) or receipt.get('error') or not isinstance(receipt.get('logits'), dict) or not receipt['logits']:
        raise ValueError('invalid scoring receipt')
    values = receipt['logits']
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError('non-finite logits')
    top = max(values.values())
    weights = {k: math.exp(v - top) for k, v in values.items()}
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def features(arms):
    # Two independent tests, each relative to its other possible answers.
    result = []
    for arm in ('sufficiency', 'misuse'):
        probabilities(arms[arm])  # validate provider result before using logits
        values = arms[arm]['logits']
        top = max(values['B'], values['C'])
        result.append(values['A'] - top - math.log(math.exp(values['B'] - top) + math.exp(values['C'] - top)))
    return result


def fit(examples):
    """Caller passes fit feedback only: iterable of (arms, binary outcome)."""
    import numpy as np
    if not 3 <= len(examples) <= 32:
        raise ValueError('feedback capacity is 3..32')
    x = np.asarray([features(arms) for arms, _ in examples], dtype=float)
    y = np.asarray([value for _, value in examples], dtype=float)
    if not set(y).issubset({0., 1.}):
        raise ValueError('binary verified outcome required')
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    design = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    coefficients = np.linalg.solve(design.T @ design + np.diag([0., 1., 1.]), design.T @ y)
    return dict(version=1, count=len(examples), mean=mean.tolist(), scale=scale.tolist(),
                coefficients=coefficients.tolist(), regularization=1)


def rank_score(arms, state, enabled=True):
    """Malformed/missing state or score reads hard-return the direct baseline."""
    try:
        baseline = probabilities(arms['direct'])['A']
    except (ValueError, KeyError, TypeError):
        baseline = 0.0
    if not enabled:
        return dict(score=baseline, fallback=False, mode='direct', reason='disabled')
    try:
        if state['version'] != 1 or not 3 <= state['count'] <= 32:
            raise ValueError('invalid policy version/count')
        mean, scale, coefficients = state['mean'], state['scale'], state['coefficients']
        if len(mean) != 2 or len(scale) != 2 or len(coefficients) != 3:
            raise ValueError('invalid policy dimensions')
        if not all(math.isfinite(v) for v in mean + scale + coefficients) or min(scale) <= 0:
            raise ValueError('invalid policy numbers')
        x = features(arms)
        score = coefficients[0] + sum(coefficients[i + 1] * (x[i] - mean[i]) / scale[i] for i in range(2))
        if not math.isfinite(score):
            raise ValueError('non-finite result')
        return dict(score=score, fallback=False, mode='feedback', reason='fitted')
    except (ValueError, KeyError, TypeError, OverflowError):
        return dict(score=baseline, fallback=True, mode='direct', reason='invalid_policy_or_receipt')


def factorized_stage(arms):
    if any(arms.get(name, {}).get('error', 'missing') for name in ('sufficiency', 'misuse')):
        return 'unknown'
    sufficient, misuse = arms['sufficiency']['choice'], arms['misuse']['choice']
    if sufficient == 'B':
        return 'memory'
    if sufficient == 'A':
        return {'A': 'response', 'B': 'non-memory', 'C': 'unknown'}.get(misuse, 'unknown')
    return 'unknown'
