"""Offline oracle-candidate construction; current applicability never enters tasks."""
import importlib
import json
import os
from pathlib import Path
import sys
import types
from collections import Counter

CLASSES = {
    'startwith': ('start_with', 'StartWithInstruction'),
    'endwith': ('end_with', 'EndWithInstruction'),
    'format': ('format_instruction', 'FormatInstruction'),
    'countableItems': ('countable_items', 'CountableItemsInstruction'),
    'length': ('length', 'LengthInstruction'),
    'existence': ('existence', 'ExistenceInstruction'),
    'forbidden': ('forbidden', 'ForbiddenInstruction'),
    'case': ('change_case', 'ChangeCaseInstruction'),
    'punctuation': ('punctuation', 'PunctuationInstruction'),
}


def signature(rule):
    return json.dumps([rule['id'], rule['args']], sort_keys=True, ensure_ascii=False)


def build(source, run, upstream):
    source, run, upstream = source.resolve(), run.resolve(), upstream.resolve()
    # Import only deterministic classes, without package __init__ and LLM judges.
    package = types.ModuleType('instruction')
    package.__path__ = [str(upstream / 'src' / 'instruction')]
    sys.modules['instruction'] = package
    previous_cwd = Path.cwd()
    try:
        # Upstream utilities load their bundled topic table relative to the repo.
        os.chdir(upstream)
        classes = {k: getattr(importlib.import_module('instruction.'+m), c)
                   for k, (m, c) in CLASSES.items()}
    finally:
        os.chdir(previous_cwd)
    rows = [json.loads(l) for l in (source / 'dialog_1.jsonl').open()]
    answers = {r['turn']: r for r in map(json.loads, (run / 'answers.jsonl').open())}
    assert set(answers) == set(range(1, 51)), 'Complete the common trajectory first'
    candidates = {}
    history = []
    tasks, gold, receipts = [], {}, []
    for row in rows:
        turn = row['turn']
        history.append({'turn': turn, 'user': row['user_query_verified']})
        for rule in row['instructions']:
            if rule['id'] not in CLASSES:
                continue
            # The sentence-count implementation depends on external NLTK resources.
            # Exclude this mode a priori instead of scoring missing resources as failures.
            if rule['id'] == 'length' and rule['args'].get('mode') == 'sentence':
                continue
            key = signature(rule)
            if key not in candidates:
                candidates[key] = {'id': f'R{len(candidates)+1}', 'family': rule['id'],
                                   'args': rule['args'], 'first_observed_turn': turn}
        answer = answers[turn]
        if turn % 5:
            continue
        current = {signature(r) for r in row['instructions']}
        public = []
        labels = {}
        for key, candidate in candidates.items():
            checker = classes[candidate['family']]()
            checker.args = candidate['args']
            error = None
            try:
                ok = checker.check_following(answer['text'])
                assert isinstance(ok, bool)
            except Exception as exc:
                ok, error = None, type(exc).__name__
            # Cap is observable to every arm; keep literal checker result separately.
            public.append({**candidate, 'checker_pass': ok, 'checker_error': error})
            labels[candidate['id']] = {'currently_applicable': key in current,
                'actionable_violation': key in current and ok is False,
                'checker_observable': ok is not None}
            receipts.append({'turn': turn, 'candidate': candidate['id'], 'pass': ok,
                             'error': error, 'active': key in current})
        tasks.append({'id': f'dialog_1:{turn}', 'history': history.copy(),
            'answer': answer['text'], 'answer_error': answer['error'], 'candidates': public})
        gold[tasks[-1]['id']] = labels
    counts = Counter()
    for r in receipts:
        counts['pairs'] += 1
        if r['pass'] is None:
            counts['checker_unknown'] += 1
        elif not r['pass']:
            counts['literal_failures'] += 1
            counts['active_failures' if r['active'] else 'inactive_failures'] += 1
    for name, value in [('tasks.json', tasks), ('labels.json', gold),
                        ('checker-receipts.json', receipts), ('candidate-summary.json', dict(counts))]:
        (run / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    build(*(Path(p) for p in sys.argv[1:4]))
