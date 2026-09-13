"""Development-only controlled feedback ranking; no changes to the detector."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression


def read(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def prepare(data, previous, out):
    rows=[r for r in read(data/'observations.jsonl') if r['split']=='train']
    old=set(json.loads(previous.read_text())['groups']);split={}
    for kind in sorted({r['source_kind'] for r in rows}):
        groups=sorted({r['group'] for r in rows if r['source_kind']==kind}-old,
            key=lambda g:hashlib.sha256(('grounding-feedback-v1:'+g).encode()).hexdigest())[:100]
        for i,g in enumerate(groups):split[g]='feedback' if i<50 else 'validation'
    out.mkdir(exist_ok=True,parents=True)
    (out/'tasks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows if r['group'] in split))
    (out/'split.json').write_text(json.dumps(split,indent=2)+'\n')


def candidates(predictions, labels, split):
    rows=[]
    for r in predictions:
        if r['error'] is not None:continue
        gold={i for s in labels[r['id']]['spans'] for i in range(s['start'],s['end'])}
        runs=[];active=[]
        for token in r['answer_tokens']:
            if token['pred']==1:active.append(token)
            elif active:runs.append(active);active=[]
        if active:runs.append(active)
        for run in runs:
            start,end=run[0]['start'],run[-1]['end'];p=np.array([t['prob'] for t in run])
            overlap=len(gold&set(range(start,end)))
            rows.append({'id':r['id'],'group':r['group'],'source_kind':r['source_kind'],
                'split':split[r['group']], 'start':start,'end':end,'overlap':overlap,
                'correct':2*overlap>=end-start,
                'features':[float(p.mean()),float(p.min()),float(p.max()),float(p.std()),math.log1p(end-start)]})
    return rows


def measure(rows, total_gold):
    chars=sum(r['end']-r['start'] for r in rows);overlap=sum(r['overlap'] for r in rows)
    return {'selected':len(rows),'selected_characters':chars,
        'mean_span_characters':chars/len(rows) if rows else None,
        'span_characters_p50_p95':np.quantile([r['end']-r['start'] for r in rows],[.5,.95]).tolist() if rows else None,
        'correct':sum(r['correct'] for r in rows),
        'candidate_precision':sum(r['correct'] for r in rows)/len(rows) if rows else None,
        'character_precision':overlap/chars if chars else None,
        'gold_character_coverage':overlap/total_gold if total_gold else None}


def evaluate(run, labels_path, out):
    tasks=read(run/'tasks.jsonl');predictions=read(run/'predictions.jsonl')
    assert len(predictions)==len(tasks) and len({r['id'] for r in predictions})==len(tasks)
    assert {r['id'] for r in predictions}=={r['id'] for r in tasks}
    split=json.loads((run/'split.json').read_text());labels={r['id']:r for r in read(labels_path)}
    rows=candidates(predictions,labels,split);train=[r for r in rows if r['split']=='feedback'];valid=[r for r in rows if r['split']=='validation']
    assert {r['group'] for r in train}.isdisjoint({r['group'] for r in valid})
    x=np.array([r['features'] for r in train]);y=np.array([r['correct'] for r in train])
    start=time.perf_counter();model=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=1000))
    model.fit(x,y);fit_seconds=time.perf_counter()-start
    for r,p in zip(valid,model.predict_proba([r['features'] for r in valid])[:,1]):r['learned']=float(p)
    chosen={'all':valid}
    for budget in [.25,.5]:
        for name,score in [('mean',lambda r:r['features'][0]),('max',lambda r:r['features'][2]),('learned',lambda r:r['learned'])]:
            chosen[f'{name}_{budget}']=sorted(valid,key=lambda r:(-score(r),r['id'],r['start']))[:math.ceil(len(valid)*budget)]
    result={'feedback':{'sources':sum(v=='feedback' for v in split.values()),
        'annotated_answers':sum(split[r['group']]=='feedback' for r in tasks),
        'candidates':len(train),'correct':sum(r['correct'] for r in train),'fit_seconds':fit_seconds},
        'validation':{'sources':sum(v=='validation' for v in split.values()),
        'answers':sum(split[r['group']]=='validation' for r in tasks),'candidates':len(valid)},'layers':{}}
    for kind in ['all']+sorted({r['source_kind'] for r in valid}):
        ids=[r['id'] for r in tasks if split[r['group']]=='validation' and (kind=='all' or r['source_kind']==kind)]
        total_gold=sum(len({i for s in labels[id]['spans'] for i in range(s['start'],s['end'])}) for id in ids)
        result['layers'][kind]={name:measure([r for r in selected if kind=='all' or r['source_kind']==kind],total_gold) for name,selected in chosen.items()}
    # Resample sources, preserving globally frozen selection. No refit or reranking.
    groups=sorted(g for g in split if split[g]=='validation')
    counts=[]
    for name in ['learned_0.5','mean_0.5']:
        counts.append(np.array([[sum(r['correct'] for r in chosen[name] if r['group']==g),sum(r['group']==g for r in chosen[name])] for g in groups]))
    rng=np.random.default_rng(20260913);diff=[]
    for _ in range(2000):
        indices=rng.integers(0,len(groups),len(groups));a,b=[c[indices].sum(axis=0) for c in counts]
        if a[1] and b[1]:diff.append(a[0]/a[1]-b[0]/b[1])
    result['primary_precision_difference_ci95']=np.quantile(diff,[.025,.975]).tolist()
    result['inference']={'forwards':sum(r['error'] is None for r in predictions),
        'unknown':sum(r['error'] is not None for r in predictions),
        'processed_tokens':sum(r['tokens'] for r in predictions if r['error'] is None),
        'forward_seconds':sum(r['elapsed_ms'] for r in predictions)/1000}
    scaler=model[0];classifier=model[1]
    out.mkdir(exist_ok=True,parents=True)
    (out/'model.json').write_text(json.dumps({'feature_order':['mean','min','max','std','log1p_chars'],
        'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'coef':classifier.coef_.tolist(),
        'intercept':classifier.intercept_.tolist(),'classes':classifier.classes_.tolist()},indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'candidates.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','evaluate'])
    for key in ['data','previous','run','labels','out']:p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':prepare(a.data,a.previous,a.out)
    else:evaluate(a.run,a.labels,a.out)
