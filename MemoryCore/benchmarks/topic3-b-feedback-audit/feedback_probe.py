"""Offline diagnostic: QA reward is not a source-coverage label or causal credit.

Only published evidence strings are matched; absence is not proof that the
answer cannot be inferred from other retrieved text.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


def main(root, output, review=None):
    def read(name):
        return [json.loads(line) for line in (root/name).open()]
    gold = {r['id']: r['gold'] for r in read('offline-gold.jsonl')}
    queries = {r['id']: r for r in read('queries.jsonl')}
    groups = defaultdict(list)
    for event in read('learning-events.jsonl'):
        assert queries[event['query_id']]['split'] == 'train'
        groups[event['query_id']].append(event)
    rows = []
    for key, events in groups.items():
        first = events[0]
        prompt = first['history'][0]['content']
        references = gold[key].get('evidence', [])
        matches = [{'memory_id': r['dia_id'], 'exact_text_present': r['text'] in prompt}
                   for r in references]
        found = sum(m['exact_text_present'] for m in matches)
        coverage = ('no_reference' if not matches else 'complete' if found == len(matches)
                    else 'none' if found == 0 else 'partial')
        extra_users = [m['content'] for m in events[-1]['history'][1:] if m['role'] == 'user']
        rows.append({'id': key, 'coverage': coverage, 'references': matches,
                     'first_action': first['feedback']['implicit_action'] if first['feedback'] else None,
                     'observed_actions': [e['feedback']['implicit_action'] for e in events if e['feedback']],
                     'answers': len(events), 'feedback_receipts': sum(e['feedback'] is not None for e in events),
                     'initial_prompt_identical': all(e['history'][0]['content'] == prompt for e in events),
                     'additional_user_messages': extra_users,
                     'unique_answers': len({e['history'][-1]['content'] for e in events})})
    matrix = Counter((r['first_action'], r['coverage']) for r in rows)
    report = {'scope': '20 training queries; published evidence exact presence, not memory-fault gold',
              'queries': len(rows),
              'first_action_by_reference_coverage': [{'action': a, 'coverage': c, 'n': n}
                                                    for (a, c), n in sorted(matrix.items())],
              'unchanged_initial_prompt_queries': sum(r['initial_prompt_identical'] for r in rows),
              'distinct_additional_user_messages': sorted({s for r in rows for s in r['additional_user_messages']}),
              'observed_dislike_to_like_queries': sum('dislike' in r['observed_actions'] and
                  'like' in r['observed_actions'][r['observed_actions'].index('dislike')+1:] for r in rows),
              'retry_queries': sum(r['answers'] > 1 for r in rows),
              'unchanged_answers_on_retry': sum(r['answers'] > 1 and r['unique_answers'] == 1 for r in rows)}
    if review is not None:
        annotations = json.loads(review.read_text())['rows']
        by_id = {r['id']: r for r in rows}
        assert len(annotations) == len(rows)
        assert {a['query_id'] for a in annotations} == set(by_id)
        cross = Counter((by_id[a['query_id']]['first_action'], a['judgment']) for a in annotations)
        report['assistant_silver_comparison_not_official_gold'] = [
            {'action': action, 'judgment': judgment, 'n': n}
            for (action, judgment), n in sorted(cross.items())]
    output.mkdir(parents=True, exist_ok=True)
    (output/'probe-rows.json').write_text(json.dumps(rows, indent=2)+'\n')
    (output/'probe-summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
