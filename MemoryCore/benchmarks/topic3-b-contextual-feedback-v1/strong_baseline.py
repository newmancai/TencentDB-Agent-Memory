"""Fixed, costed model-capability comparison; no feedback learning claim."""
import argparse
import hashlib
import json
from pathlib import Path
from feedback_learning import rows, run


def prepare(root, out):
    observations=rows(root/'adapted/observations.jsonl')
    labels={r['id']:r for r in rows(root/'adapted/labels.jsonl')}
    smoke=json.loads((root/'adapted/preparation-summary.json').read_text())['smoke_development_ids']
    used={r['group'] for r in observations if r['id'] in smoke}
    used|={r['group'] for r in rows(root/'events/audit-inputs.jsonl')}
    for name in ['views','scope-audit','learning','fragments','capability']:
        used|=set(json.loads((root/name/'selection.json').read_text())['groups'])
    digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
    groups=sorted({r['group'] for r in observations if r['split']=='development'}-used,key=lambda g:digest('cupid-strong-baseline-v1:'+g))[:2]
    tasks=sorted([r for r in observations if r['group'] in groups],key=lambda r:digest('strong-baseline-task:'+r['id']))
    assert len(tasks)==6 and len(groups)==2 and not set(groups)&used
    out.mkdir(parents=True,exist_ok=False)
    (out/'reference.jsonl').write_text(''.join(json.dumps(labels[r['id']],ensure_ascii=False)+'\n' for r in tasks))
    for arm in ['4b','30b']:
        folder=out/arm;folder.mkdir()
        (folder/'tasks.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in tasks))
        (folder/'state.json').write_text(json.dumps({'version':1,'capacity':2,'examples':[]})+'\n')
    (out/'selection.json').write_text(json.dumps({'groups':groups,'excluded_personas':len(used),'ids':[r['id'] for r in tasks],
        'scope':'new development personas; fixed ordinary inference, not B learning or matched compute'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--root',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--shard-gpus',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.out)
    else:run(a.out,a.model,arms_override=['frozen'],shard_gpus=a.shard_gpus,protocol='cupid-strong-baseline-v1')
