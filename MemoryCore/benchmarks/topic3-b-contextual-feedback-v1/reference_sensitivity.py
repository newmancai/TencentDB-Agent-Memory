"""Read-only sensitivity report; does not relabel, rerank, or replace primary results."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    for name in ['decoded','flags','out']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    primary=json.loads(args.decoded.read_text())
    flags=json.loads(args.flags.read_text())
    ids={r['id'] for r in primary['decoded']}
    flagged={r['id'] for r in flags['records']}
    if not flagged<=ids:raise ValueError('Flag references absent task')
    comparisons=['frozen','unlabelled','feedback']
    cohorts={'primary_unchanged':primary['decoded'],
        'flagged_reference_strength':[r for r in primary['decoded'] if r['id'] in flagged],
        'other_tasks_diagnostic_only':[r for r in primary['decoded'] if r['id'] not in flagged]}
    result={'protocol':'cupid-reference-strength-sensitivity-v1',
        'selection':'post-hoc independent-review flags, not a new evaluation split',
        'gold_changed':False,'rankings_changed':False,
        'training_implication':'A reference coverage gap alone is not a verified contradiction of observed user feedback; flags are clause-level, not whole-task exclusion rules.',
        'cohorts':{name:{'tasks':len(rows),'ids':[r['id'] for r in rows],
            'reviewed_comparison':{arm:dict(Counter(r['reviewed_comparison'][arm] for r in rows)) for arm in comparisons}}
            for name,rows in cohorts.items()}}
    assert result['cohorts']['primary_unchanged']['reviewed_comparison']==primary['reviewed_comparison']
    with args.out.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
