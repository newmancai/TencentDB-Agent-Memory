"""Fresh development inputs for a source-only capability diagnostic, not a learning comparison."""
import argparse
import hashlib
import json
from pathlib import Path
from feedback_learning import rows, visible, run
from compare_views import SYSTEM


def prepare(root,out):
    observations=rows(root/'adapted/observations.jsonl')
    labels={r['id']:r for r in rows(root/'adapted/labels.jsonl')}
    smoke=json.loads((root/'adapted/preparation-summary.json').read_text())['smoke_development_ids']
    used={r['group'] for r in observations if r['id'] in smoke}
    used|={r['group'] for r in rows(root/'events/audit-inputs.jsonl')}
    for name in ['views','scope-audit','learning','fragments']:
        used|=set(json.loads((root/name/'selection.json').read_text())['groups'])
    digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
    groups=sorted({r['group'] for r in observations if r['split']=='development'}-used,key=lambda g:digest('cupid-capability-v1:'+g))[:2]
    tasks=sorted([r for r in observations if r['group'] in groups],key=lambda r:digest('capability-task:'+r['id']))
    assert len(tasks)==6 and len(groups)==2 and not set(groups)&used
    out.mkdir(parents=True,exist_ok=False)
    packets=[{'id':r['id'],'instruction':SYSTEM,'observation':visible(r)} for r in tasks]
    (out/'isolated').mkdir()
    for i,packet in enumerate(packets):
        (out/'isolated'/f'input-{i}.json').write_text(json.dumps(packet,ensure_ascii=False)+'\n')
    for name,records in [('tasks',tasks),('reference',[labels[r['id']] for r in tasks]),('blind-inputs',packets)]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    (out/'state.json').write_text(json.dumps({'version':1,'capacity':2,'examples':[]})+'\n')
    (out/'selection.json').write_text(json.dumps({'groups':groups,'excluded_personas':len(used),'ids':[r['id'] for r in tasks],
        'scope':'new development personas; assistant and local model are not matched in compute budget'},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--root',type=Path);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--model',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.root,args.out)
    else:run(args.out,args.model,arms_override=['frozen'])
