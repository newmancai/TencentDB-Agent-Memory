"""Reproduce three-lane reports and frozen calibration from saved raw outputs."""
import argparse
import json
from pathlib import Path
from evaluate import evaluate
from calibrate import select, score_heldout


def main():
    p=argparse.ArgumentParser()
    p.add_argument('candidates',type=Path);p.add_argument('gold',type=Path)
    p.add_argument('directory',type=Path);p.add_argument('--split',required=True,
        choices=['development','calibration','heldout'])
    p.add_argument('--generation',type=Path);p.add_argument('--policy',type=Path)
    a=p.parse_args()
    def read(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    rows=[r for r in read(a.generation or a.directory/f'{a.split}.outputs.jsonl') if r['arm']=='direct']
    for name in ['nli','assertion-nli']:rows+=read(a.directory/f'{a.split}.{name}.jsonl')
    cases=json.loads(a.candidates.read_text())
    if len(cases)!=16 or any(c['split']!=a.split for c in cases):raise ValueError('require complete fixed split candidates')
    report=evaluate(cases,json.loads(a.gold.read_text()),rows)
    selected=[r for r in report if r['split']==a.split]
    if any(r['missing'] for r in selected):raise ValueError('incomplete outputs')
    (a.directory/f'{a.split}.metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    if a.policy:
        if a.split=='calibration':
            with a.policy.open('x') as out:json.dump(select(report,['direct','nli','assertion_nli']),out,indent=2)
        elif a.split=='heldout':
            result=score_heldout(report,json.loads(a.policy.read_text()))
            (a.directory/'heldout.calibrated.json').write_text(json.dumps(result,indent=2)+'\n')
        else:raise ValueError('development does not select a policy')
    print(json.dumps([{k:r[k] for k in ['arm','accepted','localized','errors','seconds']} for r in selected]))


if __name__=='__main__':main()
