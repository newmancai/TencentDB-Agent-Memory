"""Prepare actual response/follow-up triples and cross-conversation controls."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from run import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    labels = {r['id']: r.get('label') for r in read(args.data/'labels.jsonl')}
    rows = [r for r in read(args.data/'observations.jsonl')
            if r['source'] == 'lmsys' and labels[r['id']] is not None]
    assert all(len(r['history']) >= 2 and r['history'][-1]['role'] == 'assistant'
               and r['history'][-2]['role'] == 'user' for r in rows)
    # Fixed global minimum character-length mismatch, without category labels.
    lengths = np.array([len(r['incoming']['text']) for r in rows])
    costs = abs(np.log1p(lengths[:, None])-np.log1p(lengths[None, :]))
    for i, left in enumerate(rows):
        for j, right in enumerate(rows):
            if left['group'] == right['group']:
                costs[i, j] = np.inf
    left, right = linear_sum_assignment(costs)
    assert len(left) == len(rows) and np.isfinite(costs[left, right]).all()
    assignment = dict(zip(left.tolist(), right.tolist()))
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out/'tasks.jsonl').open('w') as stream:
        for i, row in enumerate(rows):
            donor = rows[assignment[i]]
            stream.write(json.dumps({'id': row['id'], 'group': row['group'],
                'history': row['history'][-2:-1], 'answer': row['history'][-1],
                'followup': row['incoming'], 'control_followup': donor['incoming'],
                'control_donor_id': donor['id'], 'control_donor_group': donor['group']},
                ensure_ascii=False)+'\n')
    summary = {'events': len(rows), 'groups': len({r['group'] for r in rows}),
               'labels_in_tasks': False, 'wildchat_in_tasks': False,
               'control_same_group': sum(rows[i]['group'] == rows[j]['group'] for i,j in assignment.items()),
               'control_unique_donors': len(set(assignment.values())),
               'control_log_character_length_gap_p50_p95': np.quantile(costs[left,right],[.5,.95]).tolist(),
               'scope': 'Development signal diagnostic only; original logged answers, not new agent actions. Donor text is not an actual response to the recipient answer.'}
    (args.out/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
