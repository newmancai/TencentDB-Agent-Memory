"""Fixed, costed model-capability comparison; no feedback learning claim."""
import argparse
import hashlib
import json
from pathlib import Path
from feedback_learning import rows, run, visible


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


def review(folder):
    """Keep source-only judgment separate from later reference coverage review."""
    tasks=rows(folder/'4b/tasks.jsonl')
    if tasks!=rows(folder/'30b/tasks.jsonl'):raise ValueError('Different tasks between models')
    ids=[r['id'] for r in tasks]
    if len(ids)!=6 or len(set(ids))!=6:raise ValueError('Expected all six unique tasks')
    receipts={};prompts={};costs={}
    for arm in ['4b','30b']:
        records=rows(folder/arm/'receipts.jsonl')
        if len(records)!=len(ids) or {r['id'] for r in records}!=set(ids):
            raise ValueError(f'{arm}: incomplete or duplicated receipts; retain missing tasks as unfinished')
        receipts[arm]={r['id']:r['arms']['frozen'] for r in records}
        inputs=rows(folder/arm/'inputs.jsonl')
        if len(inputs)!=6 or {r['id'] for r in inputs}!=set(ids) or any(r['arm']!='frozen' for r in inputs):
            raise ValueError(f'{arm}: missing, duplicate, or wrong-arm actual prompts')
        prompts[arm]={r['id']:r['prompt'] for r in inputs}
        for task in tasks:
            if json.dumps(visible(task),ensure_ascii=False) not in prompts[arm][task['id']]:
                raise ValueError(f'{arm}: actual prompt does not contain expected observation')
        values=list(receipts[arm].values())
        seconds=sorted(r['generation_ms']/1000 for r in values if r['output_tokens']>0)
        def quantile(q):
            if not seconds:return None
            index=(len(seconds)-1)*q;lo=int(index)
            return seconds[lo]+(seconds[min(lo+1,len(seconds)-1)]-seconds[lo])*(index-lo)
        costs[arm]={'input_tokens':sum(r['input_tokens'] for r in values),
            'output_tokens':sum(r['output_tokens'] for r in values),
            'generation_seconds':sum(r['generation_ms']/1000 for r in values),
            'generated_calls':len(seconds),'p50_generated_seconds':quantile(.5),'p95_generated_seconds':quantile(.95),
            'error_ids':[i for i,r in receipts[arm].items() if r['error']],
            'over_100_words':[i for i,r in receipts[arm].items() if len(r['text'].split())>100],
            'runtime':json.loads((folder/arm/'cost.json').read_text())}
    packets=[];mapping={}
    for task in tasks:
        ident=task['id']
        arms=['4b','30b']
        if int(hashlib.sha256(('strong-blind:'+ident).encode()).hexdigest(),16)%2:arms.reverse()
        mapping[ident]=dict(zip(['A','B'],arms))
        packets.append({'id':ident,'observation':visible(task),
            'outputs':{label:{'text':receipts[arm][ident]['text'],'error':receipts[arm][ident]['error']}
                       for label,arm in mapping[ident].items()}})
    # Reference stays in a separate file and is opened only after source judgments are saved.
    references=rows(folder/'reference.jsonl')
    if len(references)!=6 or {r['id'] for r in references}!=set(ids):raise ValueError('Reference alignment mismatch')
    out=folder/'review';out.mkdir(exist_ok=False)
    def write_rows(name,values):
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values))
    write_rows('source-packets.jsonl',packets)
    write_rows('reference-coverage-only.jsonl',references)
    write_rows('cross-source-packets.jsonl',packets[:2])
    (out/'private-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
    (out/'costs.json').write_text(json.dumps({'arms':costs,'actual_prompt_equal':{
        i:prompts['4b'][i]==prompts['30b'][i] for i in ids},
        'persona_ids':{g:[r['id'] for r in tasks if r['group']==g] for g in sorted({r['group'] for r in tasks})}},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','review']);p.add_argument('--root',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--shard-gpus',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.out)
    elif a.action=='review':review(a.out)
    else:run(a.out,a.model,arms_override=['frozen'],shard_gpus=a.shard_gpus,protocol='cupid-strong-baseline-v1')
