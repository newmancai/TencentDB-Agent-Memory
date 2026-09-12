"""Prepare blinded development packets; factor equality stays in offline reference."""
import argparse
import hashlib
import json
from pathlib import Path


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapted', type=Path, required=True)
    parser.add_argument('--prior-events', type=Path, required=True)
    parser.add_argument('--prior-views', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    observations = read_rows(args.adapted / 'observations.jsonl')
    labels = {r['id']: r for r in read_rows(args.adapted / 'labels.jsonl')}
    smoke = json.loads((args.adapted / 'preparation-summary.json').read_text())['smoke_development_ids']
    used = {r['group'] for r in observations if r['id'] in smoke}
    used |= {r['group'] for r in read_rows(args.prior_events)}
    used |= set(json.loads(args.prior_views.read_text())['groups'])
    groups = sorted({r['group'] for r in observations if r['split'] == 'development'} - used,
                    key=lambda s: hashlib.sha256(('cupid-scope-audit-v1:' + s).encode()).hexdigest())[:2]
    selected = [r for r in observations if r['group'] in groups and labels[r['id']]['instance_type'] == 'consistent']
    packets, references = [], []
    for row in selected:
        annotation = labels[row['id']]
        for session, prior in zip(row['history'], annotation['prior_annotations'], strict=True):
            assert session['session_id'] == prior['session_id']
            identifier = row['id'] + ':' + session['session_id']
            packets.append({'id': identifier, 'current_request': row['current_request'], 'historical_session': session})
            references.append({'id': identifier,
                'same_context_factor': prior['context_factor'] == annotation['current_context_factor'],
                'historical_factor': prior['context_factor'], 'current_factor': annotation['current_context_factor']})
    assert len(selected) == 2 and len(packets) == 16
    args.out.mkdir(parents=True, exist_ok=False)
    for name, rows in [('packets', packets), ('reference', references)]:
        (args.out / (name + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    (args.out / 'selection.json').write_text(json.dumps({'groups': groups, 'excluded_personas': len(used),
        'observation_ids': [r['id'] for r in selected], 'packet_ids': [r['id'] for r in packets],
        'scope': 'development source-label applicability audit, no model training'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
