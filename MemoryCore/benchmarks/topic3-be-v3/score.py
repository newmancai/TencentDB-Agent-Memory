"""Offline agreement with disclosed assistant silver labels, never runtime gold."""
import argparse
import json
from collections import Counter
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    a = p.parse_args(); root = a.root
    audit = json.loads((root / 'source-review.json').read_text())
    labels = {r['id']: r['relation'] for r in audit['rows']}
    rows = [json.loads(line) for line in (root / 'model/results.jsonl').read_text().splitlines()]
    summary = dict(scope='known-pair development reuse; assistant silver agreement, not calibrated semantic truth', arms={}, paired={})
    for arm in ['direct', 'roles', 'grounded']:
        counts = Counter(); confusion = Counter()
        for r in rows:
            if arm not in r['arms']:
                counts['not_run'] += 1; continue
            x = r['arms'][arm]; label = labels[r['id']]
            raw = x['parsed'].get('relation') if isinstance(x['parsed'], dict) else 'invalid'
            counts['n'] += 1; counts['raw_agreement'] += raw == label
            counts['contract_errors'] += bool(x['contract_error'])
            counts['contract_valid_agreement'] += raw == label and not x['contract_error']
            counts['silver_changed'] += label == 'changed'
            counts['predicted_changed'] += raw == 'changed'
            counts['matched_changed'] += label == raw == 'changed'
            confusion[f'{label}->{raw}'] += 1
            for k in ['inputTokens', 'outputTokens', 'elapsedMs']:
                counts[k] += x['receipt'].get(k, 0)
        summary['arms'][arm] = dict(counts, confusion=dict(confusion))
    for baseline in ['direct', 'roles']:
        counts = Counter()
        for r in rows:
            if not r['arms']: continue
            label = labels[r['id']]
            def correct(arm):
                x = r['arms'][arm]
                return isinstance(x['parsed'], dict) and x['parsed'].get('relation') == label
            g, b = correct('grounded'), correct(baseline)
            counts['wins' if g and not b else 'losses' if b and not g else 'ties'] += 1
        summary['paired'][f'grounded_vs_{baseline}'] = dict(counts)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
