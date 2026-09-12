import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read(path):return [json.loads(x) for x in path.read_text().splitlines()]


def prepare(source,out):
    tasks=[];labels=[];excluded=[]
    for conv in json.loads(source.read_text()):
        messages={}
        for name,session in conv['conversation'].items():
            if name.startswith('session_') and isinstance(session,list):
                for turn in session:messages[turn['dia_id']]={'timestamp':conv['conversation'].get(name+'_date_time'),**turn}
        pools={k:[] for k in [1,2,4,5]}
        for i,q in enumerate(conv['qa']):
            ident=f"{conv['sample_id']}:{i}"
            reason=None
            if q['category'] not in pools:reason='category_not_strict_grounding'
            elif not q.get('evidence'):reason='no_linked_evidence'
            elif any(e not in messages for e in q['evidence']):reason='unresolved_link'
            if reason:excluded.append({'id':ident,'reason':reason});continue
            pools[q['category']].append((ident,q))
        for category,pool in pools.items():
            for ident,q in sorted(pool,key=lambda pair:hashlib.sha256(('question-relation-v1:'+pair[0]).encode()).hexdigest())[:5]:
                answer=str(q['adversarial_answer'] if category==5 else q['answer'])
                evidence='Evidence:\n'+'\n'.join(json.dumps(messages[e],ensure_ascii=False) for e in q['evidence'])
                prefix='Question: '+q['question']+'\nAnswer: '
                for mode in ['ordinary','question_bound']:
                    output=answer if mode=='ordinary' else prefix+answer
                    offset=0 if mode=='ordinary' else len(prefix)
                    tasks.append({'id':ident+'::'+mode,'group':conv['sample_id'],'source_kind':str(category),
                        'context':evidence+'\nQuestion: '+q['question'] if mode=='ordinary' else evidence,
                        'answer':output})
                    labels.append({'id':ident+'::'+mode,'pair':ident,'mode':mode,'category':category,
                        'unsupported_proxy':category==5,'answer_start':offset,'answer_end':offset+len(answer)})
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('tasks',tasks),('labels',labels),('excluded',excluded)]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print({'pairs':len(labels)//2,'excluded':dict(Counter(r['reason'] for r in excluded))})


def evaluate(run,out):
    labels={r['id']:r for r in read(run/'labels.jsonl')};preds=read(run/'predictions.jsonl')
    tasks={r['id']:r for r in read(run/'tasks.jsonl')}
    assert len(preds)==len(labels) and {r['id'] for r in preds}==set(labels)
    rows=[]
    for p in preds:
        l=labels[p['id']];text=tasks[p['id']]['answer']
        tokens=[]
        for t in p['answer_tokens']:
            if t['end']<=l['answer_start'] or t['start']>=l['answer_end']:continue
            assert not text[t['start']:l['answer_start']].strip() if t['start']<l['answer_start'] else True
            assert not text[l['answer_end']:t['end']].strip() if t['end']>l['answer_end'] else True
            tokens.append(t)
        unknown=p['error'] is not None or not tokens
        prediction=any(t['pred']==1 for t in tokens) if not unknown else None
        rows.append({**l,'unknown':unknown,'prediction':prediction,'correct':prediction==l['unsupported_proxy'] if not unknown else None,
            'tokens':p['tokens'],'elapsed_ms':p['elapsed_ms'],'answer_tokens':len(tokens)})
    result={}
    for mode in ['ordinary','question_bound']:
        selected=[r for r in rows if r['mode']==mode];covered=[r for r in selected if not r['unknown']]
        tp=sum(r['prediction'] and r['unsupported_proxy'] for r in covered);fp=sum(r['prediction'] and not r['unsupported_proxy'] for r in covered)
        fn=sum(not r['prediction'] and r['unsupported_proxy'] for r in covered);tn=sum(not r['prediction'] and not r['unsupported_proxy'] for r in covered)
        result[mode]={'total':len(selected),'covered':len(covered),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'balanced_accuracy':.5*(tp/(tp+fn)+tn/(tn+fp)) if tp+fn and tn+fp else None,
            'categories':{str(k):{'total':sum(r['category']==k for r in covered),'correct':sum(r['category']==k and r['correct'] for r in covered)} for k in [1,2,4,5]},
            'processed_tokens':sum(p['tokens'] for p in preds if labels[p['id']]['mode']==mode and p['error'] is None),'forward_seconds':sum(r['elapsed_ms'] for r in selected)/1000}
    paired={}
    for row in rows:paired.setdefault(row['pair'],{})[row['mode']]=row
    counts=Counter()
    for pair in paired.values():
        a,b=pair['ordinary'],pair['question_bound']
        if a['unknown'] or b['unknown']:counts['unknown']+=1
        elif a['correct']==b['correct']:counts['tie']+=1
        elif b['correct']:counts['question_bound_win']+=1
        else:counts['question_bound_loss']+=1
    result['paired']=dict(counts)
    out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','evaluate'])
    for n in ['source','run','out']:p.add_argument('--'+n,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':prepare(a.source,a.out)
    else:evaluate(a.run,a.out)
