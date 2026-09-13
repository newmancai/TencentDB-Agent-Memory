"""New-persona comparison of reviewed fragments against prior correction memory."""
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
    for name in ['views','scope-audit','learning']:
        used|=set(json.loads((root/name/'selection.json').read_text())['groups'])
    digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
    groups=sorted({r['group'] for r in observations if r['split']=='development'}-used,key=lambda g:digest('cupid-fragment-learning-v1:'+g))[:4]
    tasks=sorted([r for r in observations if r['group'] in groups],key=lambda r:digest('fragment-task:'+r['id']))
    state=json.loads((root/'learning/state.json').read_text())
    reviewed=json.loads((root/'compiled/reviewed-state.json').read_text())
    state['reviewed_examples']=reviewed['examples']
    assert len(tasks)==12 and len(groups)==4 and not set(groups)&used
    out.mkdir(parents=True,exist_ok=False)
    for name,records in [('tasks',tasks),('reference',[labels[r['id']] for r in tasks])]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    (out/'selection.json').write_text(json.dumps({'groups':groups,'excluded_personas':len(used),'ids':[r['id'] for r in tasks],
        'training_ids':[r['id'] for r in state['examples']],'scope':'new development personas; no validation inference'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--root',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',type=Path)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.out)
    else:run(a.out,a.model,reviewed=True)
