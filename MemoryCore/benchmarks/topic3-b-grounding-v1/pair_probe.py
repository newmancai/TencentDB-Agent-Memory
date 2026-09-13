import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]

def prepare(source,previous,recent,model,out,extra_used=(),per_group=3,seed="paired-grounding-v1"):
    from transformers import AutoTokenizer
    spec=importlib.util.spec_from_file_location('semantic_probe',Path(__file__).with_name('semantic_probe.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tok=AutoTokenizer.from_pretrained(model,local_files_only=True)
    used={r['pair'] for r in read(previous/'labels.jsonl')}|{r['id'] for r in read(recent/'labels.jsonl')}|set(extra_used)
    tasks=[];labels=[];allowed=[];edges=[];excluded=[];counts=Counter()
    for c in json.loads(source.read_text()):
        sessions={n:v for n,v in c['conversation'].items() if n.startswith('session_') and isinstance(v,list)};ids={m['dia_id'] for s in sessions.values() for m in s};pool=[]
        for ni,n in enumerate(c['qa']):
            if n['category']!=5:continue
            matches=[(pi,p) for pi,p in enumerate(c['qa']) if p['category'] in [1,2,4] and str(p['answer'])==str(n['adversarial_answer']) and n.get('evidence') and set(p.get('evidence',[]))==set(n['evidence'])]
            counts['negative_questions']+=1;counts['negative_with_matches']+=bool(matches)
            for pi,p in matches:edges.append({'group':c['sample_id'],'positive_index':pi,'negative_index':ni,'same_question':p['question']==n['question']})
            if not matches:continue
            ident=f"{c['sample_id']}:{ni}"
            reason=None
            if any(p['question']==n['question'] for _,p in matches):reason='identical_question_opposite_labels'
            elif not set(n['evidence'])<=ids:reason='unresolved_evidence'
            else:
                matches=[(pi,p) for pi,p in matches if f"{c['sample_id']}:{pi}" not in used]
                if ident in used or not matches:reason='previous_probe_endpoint'
            if reason:excluded.append({'id':ident,'reason':reason});continue
            pi,p=matches[0];pool.append((ident,pi,p,n))
        for ident,pi,p,n in sorted(pool,key=lambda x:hashlib.sha256((seed+':'+x[0]).encode()).hexdigest())[:per_group]:
            names=[name for name,s in sessions.items() if any(m['dia_id'] in n['evidence'] for m in s)]
            evidence='Evidence:\n'+'\n'.join(json.dumps({'timestamp':c['conversation'].get(name+'_date_time'),**m},ensure_ascii=False) for name in sorted(names,key=lambda name:int(name.split('_')[1])) for m in sessions[name])
            items=[(p,True,pi),(n,False,int(ident.rsplit(':',1)[1]))]
            if int(hashlib.sha256(ident.encode()).hexdigest(),16)%2:items.reverse()
            pair_tasks=[];pair_labels=[];lengths=[]
            for side,(q,positive,index) in zip(['X','Y'],items):
                task={'id':ident+'::'+side,'context':evidence+'\nQuestion: '+q['question'],'answer':str(n['adversarial_answer'])}
                prompt=tok.apply_chat_template([{'role':'system','content':module.PROMPT},{'role':'user','content':task['context']+'\nCandidate answer: '+task['answer']}],tokenize=False,add_generation_prompt=True)
                lengths.append(len(tok.encode(prompt)))
                pair_tasks.append(task);pair_labels.append({'id':task['id'],'pair':ident,'group':c['sample_id'],'question_index':index,'positive':positive})
            tasks+=pair_tasks;labels+=pair_labels
            if max(lengths)<=4096:allowed.extend(t['id'] for t in pair_tasks)
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('tasks',tasks),('labels',labels),('edges',edges),('excluded',excluded)]: (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    (out/'allowed.json').write_text(json.dumps(allowed)+'\n');(out/'selection-summary.json').write_text(json.dumps({**counts,'edges':len(edges),'selected_pairs':len(labels)//2,'admitted_pairs':len(allowed)//2,'excluded':dict(Counter(r['reason'] for r in excluded))},indent=2)+'\n')
    print((out/'selection-summary.json').read_text())


def score(run,out):
    labels={r['id']:r for r in read(run/'labels.jsonl')};rows=read(run/'predictions.jsonl');assert len(rows)==len(labels) and {r['id'] for r in rows}==set(labels)
    pairs={};counts=Counter();details=[]
    for r in rows:
        l=labels[r['id']];pairs.setdefault(l['pair'],{})[l['positive']]=r
    for pair,arms in pairs.items():
        p,n=arms[True],arms[False]
        if p['error'] or n['error']:counts['unknown_pairs']+=1;continue
        prob=lambda r:math.exp(r['logits'][0]-max(r['logits']))/sum(math.exp(x-max(r['logits'])) for x in r['logits'])
        pp,np=prob(p),prob(n);pc=max(range(3),key=lambda i:p['logits'][i])==0;nc=max(range(3),key=lambda i:n['logits'][i])!=0
        counts['covered_pairs']+=1;counts['positive_correct']+=pc;counts['negative_correct']+=nc;counts['both_correct']+=pc and nc
        counts['rank_win' if pp>np else 'rank_loss' if pp<np else 'rank_tie']+=1
        details.append({'pair':pair,'positive_support_score':pp,'negative_support_score':np,'positive_correct':pc,'negative_correct':nc})
    result={**counts,'forwards':sum(r['error'] is None for r in rows),'tokens':sum(r['tokens'] for r in rows if r['error'] is None),'seconds':sum(r['elapsed_ms'] for r in rows)/1000}
    out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in details));print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','score'])
    for key in ['source','previous','recent','model','run','out']:p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':prepare(a.source,a.previous,a.recent,a.model,a.out)
    else:score(a.run,a.out)
