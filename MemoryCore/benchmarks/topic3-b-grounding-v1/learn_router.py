import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import time
import numpy as np
from sklearn.tree import DecisionTreeRegressor,DecisionTreeClassifier

FEATURES=['question_words','log_answer_words','log_messages','named_speakers','named_answer_coverage','other_answer_coverage']


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]

def words(s):return set(re.findall(r'\w+',s.casefold()))

def features(t):
    context,q=t['context'].rsplit('\nQuestion: ',1);messages=[json.loads(x) for x in context.splitlines() if x.startswith('{')]
    names={m['speaker'] for m in messages};named={n for n in names if re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',q,re.I)};answer=words(t['answer'])
    coverage=lambda m:len(answer&words(m['text']))/max(1,len(answer))
    return [len(re.findall(r'\w+',q)),math.log1p(len(re.findall(r'\w+',t['answer']))),math.log1p(len(messages)),len(named),max([coverage(m) for m in messages if m['speaker'] in named] or [0]),max([coverage(m) for m in messages if m['speaker'] not in named] or [0])]


def prediction(r):return max(range(3),key=lambda i:r['logits'][i])!=0

def metrics(gold,pred):
    c=Counter()
    for g,p in zip(gold,pred):c['tp' if p and g else 'fp' if p else 'fn' if g else 'tn']+=1
    return {**dict(c),'correct':sum(g==p for g,p in zip(gold,pred)),'total':len(gold)}

def tree_state(model):
    t=model.tree_;return {'children_left':t.children_left.tolist(),'children_right':t.children_right.tolist(),'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value.tolist()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    tasks=read(a.run/'original/tasks.jsonl');labels={r['id']:r for r in read(a.run/'original/labels.jsonl')};split=json.loads((a.run/'split.json').read_text());preds=read(a.run/'predictions.jsonl');expected=read(a.run/'tasks.jsonl')
    assert len(preds)==len(expected) and {r['id'] for r in preds}=={r['id'] for r in expected}
    by_id={r['id']:r for r in preds};covered=[t for t in tasks if all(by_id[t['id']+'::'+arm]['error'] is None for arm in ['original','joint'])]
    train=[t for t in covered if split[labels[t['id']]['group']]=='feedback'];valid=[t for t in covered if split[labels[t['id']]['group']]=='validation']
    assert {labels[t['id']]['group'] for t in train}.isdisjoint({labels[t['id']]['group'] for t in valid})
    x=np.array([features(t) for t in train]);y=np.array([not labels[t['id']]['positive'] for t in train])
    arm_preds={arm:np.array([prediction(by_id[t['id']+'::'+arm]) for t in train]) for arm in ['original','joint']}
    delta=(arm_preds['joint']==y).astype(int)-(arm_preds['original']==y).astype(int)
    static='joint' if delta.sum()>0 else 'original'
    start=time.perf_counter();router=DecisionTreeRegressor(max_depth=2,min_samples_leaf=10,random_state=20260913).fit(x,delta)
    cheap=DecisionTreeClassifier(max_depth=2,min_samples_leaf=10,random_state=20260913).fit(x,y);fit_seconds=time.perf_counter()-start
    vx=np.array([features(t) for t in valid]);choice=['joint' if d>0 else 'original' for d in router.predict(vx)]
    # All policy decisions are now fixed. Validation gold is used only below.
    gold=[not labels[t['id']]['positive'] for t in valid]
    predictions={arm:[prediction(by_id[t['id']+'::'+arm]) for t in valid] for arm in ['original','joint']}
    predictions['static']=predictions[static];predictions['router']=[prediction(by_id[t['id']+'::'+arm]) for t,arm in zip(valid,choice)];predictions['cheap']=cheap.predict(vx).tolist()
    result={'training':{'unique_questions':len({(labels[t['id']]['group'],labels[t['id']]['question_index']) for t in train}),'covered':len(train),'all_endpoints':sum(split[l['group']]=='feedback' for l in labels.values()),'deltas':{str(k):int(v) for k,v in Counter(delta.tolist()).items()},'selected_static_arm':static,'fit_seconds':fit_seconds},
        'validation':{'unique_questions':len({(labels[t['id']]['group'],labels[t['id']]['question_index']) for t in valid}),'covered':len(valid),'all_endpoints':sum(split[l['group']]=='validation' for l in labels.values()),'router_choices':dict(Counter(choice))},
        'metrics':{k:metrics(gold,p) for k,p in predictions.items()},'cost':{},'paired_vs_static':dict(win=0,loss=0,tie=0)}
    for g,s,r in zip(gold,predictions['static'],predictions['router']):result['paired_vs_static']['tie' if s==r else 'win' if r==g else 'loss']+=1
    for name,arms in [('original',['original']*len(valid)),('joint',['joint']*len(valid)),('static',[static]*len(valid)),('router',choice)]:
        selected=[by_id[t['id']+'::'+arm] for t,arm in zip(valid,arms)]
        result['cost'][name]={'selected_forwards':len(selected),'tokens':sum(r['tokens'] for r in selected),'recorded_seconds':sum(r['elapsed_ms'] for r in selected)/1000}
    for name,ids in [('feedback_collection',{t['id'] for t in train}),('validation_full_information',{t['id'] for t in valid})]:
        records=[r for r in preds if r['id'].rsplit('::',1)[0] in ids and r['error'] is None]
        result['cost'][name]={'actual_forwards':len(records),'tokens':sum(r['tokens'] for r in records),'seconds':sum(r['elapsed_ms'] for r in records)/1000}
    result['actual_full_run']={'forwards':sum(r['error'] is None for r in preds),'tokens':sum(r['tokens'] for r in preds if r['error'] is None),'seconds':sum(r['elapsed_ms'] for r in preds)/1000,'errors':dict(Counter(r['error'] for r in preds if r['error']))}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'state.json').write_text(json.dumps({'features':FEATURES,'router':tree_state(router),'cheap_classifier':tree_state(cheap),'static':static},indent=2)+'\n')
    (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    rows=[{'id':t['id'],'group':labels[t['id']]['group'],'features':list(map(float,v)),'chosen':c,'gold_review_proxy':g,**{name:p[i] for name,p in predictions.items()}} for i,(t,v,c,g) in enumerate(zip(valid,vx,choice,gold))]
    (a.out/'validation.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
