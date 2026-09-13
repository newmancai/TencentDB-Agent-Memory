"""Bounded controlled-feedback arm selection with a direct baseline fallback."""


def fit(feedback):
    rows = list(feedback)
    if len(rows) > 64:
        raise ValueError('feedback capacity exceeded')
    direct = sum(r['direct'] == r['label'] for r in rows)
    local = sum(r['local'] == r['label'] for r in rows)
    return dict(version=1, selected='local' if local > direct else 'direct',
                feedback_count=len(rows), criterion='classification_correct', tie='direct', capacity=1)


def choose(state, enabled=True):
    if not enabled:
        return dict(arm='direct', fallback=False, reason='disabled')
    if not isinstance(state, dict) or state.get('version') != 1 or state.get('selected') not in ('direct','local'):
        return dict(arm='direct', fallback=True, reason='invalid_state')
    if type(state.get('feedback_count')) is not int or not 0 <= state['feedback_count'] <= 64:
        return dict(arm='direct', fallback=True, reason='invalid_state')
    return dict(arm=state['selected'], fallback=False, reason='feedback_selected')
