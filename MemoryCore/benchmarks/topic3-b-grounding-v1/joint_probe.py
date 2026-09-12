import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def prepare(previous,candidates,model,out):
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(model,local_files_only=True)
    spec=importlib.util.spec_from_file_location('sem',Path(__file__).with_name('semantic_probe.py'));sem=importlib.util.module_from_spec(spec);spec.loader.exec_module(sem)
    mapping={r['id']:r for r in read(candidates/'mapping.jsonl')};admitted=set(json.loads((previous/'allowed.json').read_text()));tasks=[];allowed=[]
    for r in read(previous/'tasks.jsonl'):
        alternatives=[c['question'] for c in mapping[r['id']]['candidates']]
        context=r['context']+'\nAlternative questions (comparison hypotheses, not evidence; verify the original Question above): '+json.dumps(alternatives,ensure_ascii=False)
        t={**r,'context':context};tasks.append(t)
        prompt=tok.apply_chat_template([{'role':'system','content':sem.PROMPT},{'role':'user','content':context+'\nCandidate answer: '+r['answer']}],tokenize=False,add_generation_prompt=True)
        if r['id'] in admitted and len(tok.encode(prompt))<=4096:allowed.append(r['id'])
    out.mkdir(parents=True,exist_ok=True);(out/'tasks.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in tasks));(out/'allowed.json').write_text(json.dumps(allowed)+'\n');print({'tasks':len(tasks),'admitted':len(allowed)})


def score(previous,candidates,run,out):
    labels={r['id']:r for r in read(previous/'labels.jsonl')};original={r['id']:r for r in read(previous/'predictions.jsonl')}
    static={r['id']:r for r in read(candidates/'scored/rows.jsonl')};joint=read(run/'predictions.jsonl')
    assert len(joint)==len(labels) and {r['id'] for r in joint}==set(labels)
    metrics={k:Counter() for k in ['original','comparison','joint']};paired={k:Counter() for k in ['original','comparison']};rows=[]
    for r in joint:
        if r['error'] or original[r['id']]['error'] or r['id'] not in static:continue
        s=static[r['id']];gold=not labels[r['id']]['positive'];preds={'original':s['baseline_review'],'comparison':s['comparison_review'],'joint':max(range(3),key=lambda i:r['logits'][i])!=0}
        for k,p in preds.items():metrics[k]['tp' if p and gold else 'fp' if p else 'fn' if gold else 'tn']+=1
        for k in paired:paired[k]['tie' if preds[k]==preds['joint'] else 'win' if preds['joint']==gold else 'loss']+=1
        rows.append({'id':r['id'],'gold_review_proxy':gold,**preds})
    result={'total':len(joint),'common_covered':len(rows),'metrics':{k:dict(v) for k,v in metrics.items()},'joint_paired':{k:dict(v) for k,v in paired.items()},
        'new_forwards':sum(r['error'] is None for r in joint),'new_tokens':sum(r['tokens'] for r in joint if r['error'] is None),'new_seconds':sum(r['elapsed_ms'] for r in joint)/1000,'errors':dict(Counter(r['error'] for r in joint if r['error']))}
    out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','score'])
    for n in ['previous','candidates','model','run','out']:p.add_argument('--'+n,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':prepare(a.previous,a.candidates,a.model,a.out)
    else:score(a.previous,a.candidates,a.run,a.out)
