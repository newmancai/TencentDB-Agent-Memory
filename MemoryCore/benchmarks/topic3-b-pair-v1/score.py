import json
import math
from pathlib import Path
import sys


def predict(arm, threshold):
    if not arm['complete']:return None
    return max(arm['scores'])>=threshold


def metrics(rows,labels,arm,threshold):
    tp=fp=fn=tn=unknown=0; buckets={}
    for r in rows:
        p=predict(r['arms'][arm],threshold);y=labels[r['id']]['contradiction']
        if p is None:unknown+=1
        elif p and y:tp+=1
        elif p:fp+=1
        elif y:fn+=1
        else:tn+=1
        key='0-2' if r['candidate_count']<=2 else '3-5' if r['candidate_count']<=5 else '6+'
        b=buckets.setdefault(key,dict(n=0,negative=0,false_positive=0,unknown=0))
        b['n']+=1;b['negative']+=not y;b['false_positive']+=p is True and not y;b['unknown']+=p is None
    positives=sum(labels[r['id']]['contradiction'] for r in rows);negatives=len(rows)-positives
    return dict(n=len(rows),threshold=threshold,positive=positives,correct=tp+tn,tp=tp,fp=fp,fn=fn,tn=tn,unknown=unknown,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/positives if positives else None,
        balanced_accuracy=((tp/positives if positives else 0)+(tn/negatives if negatives else 0))/2,buckets=buckets)


def fit(rows,labels,arm):
    if len(rows)>64:raise ValueError('feedback capacity exceeded')
    grid=[i/20 for i in range(21)]
    best=max(grid,key=lambda t:(metrics(rows,labels,arm,t)['balanced_accuracy'],t))
    return dict(version=1,threshold=best,feedback_count=len(rows),arm=arm)


def threshold(state,enabled=True):
    if not enabled:return .5
    if not isinstance(state,dict) or state.get('version')!=1:return .5
    t=state.get('threshold')
    if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=1:return .5
    return t


def main(root):
    rows=[json.loads(s) for s in (root/'results.jsonl').read_text().splitlines()];tasks=json.loads((root/'tasks.json').read_text());g=json.loads((root/'labels.json').read_text())
    assert len(rows)==len(tasks)==192 and {r['id'] for r in rows}=={t['id'] for t in tasks}
    fitting=[r for r in rows if r['split']=='fit'];policies={a:fit(fitting,g,a) for a in ['speaker_context','pairs']}
    (root/'policy.json').write_text(json.dumps(policies,indent=2)+'\n')
    summary=dict(scope='MNLI capability reference, not DECODE-trained model or memory-fault gold',policies=policies,splits={})
    for split in ['fit','eval']:
        sub=[r for r in rows if r['split']==split];arms={}
        for a in ['speaker_context','pairs']:
            cost={k:sum(r['arms'][a][k] for r in sub) for k in ['inputTokens','paddedTokens','requestedTokens','forwardBatches','elapsedMs','overLimit']}
            cost['inputPairs']=sum(sum(p is not None for p in r['arms'][a]['scores']) for r in sub)
            cost['time_scope']='forward_only_excludes_tokenization_and_padding'
            arms[a]=dict(fixed=metrics(sub,g,a,.5),learned=metrics(sub,g,a,threshold(policies[a])),cost=cost)
        wins=losses=ties=0
        for r in sub:
            y=g[r['id']]['contradiction'];b=predict(r['arms']['speaker_context'],threshold(policies['speaker_context']))==y;p=predict(r['arms']['pairs'],threshold(policies['pairs']))==y
            if p and not b:wins+=1
            elif b and not p:losses+=1
            else:ties+=1
        common=[r for r in sub if all(r['arms'][a]['complete'] for a in ['speaker_context','pairs'])]
        summary['splits'][split]=dict(arms=arms,learned_pair_vs_context=dict(wins=wins,losses=losses,ties=ties),
            common_complete_diagnostic={a:metrics(common,g,a,threshold(policies[a])) for a in ['speaker_context','pairs']})
    byid={r['id']:r for r in rows}; coverage=hits=gold_count=0
    for t in tasks:
        if t['split']!='fit' or not g[t['id']]['contradiction']:continue
        gold=set(g[t['id']]['evidence']);pool={c['id'] for c in t['candidates']};gold_count+=len(gold);coverage+=len(gold&pool)
        scores=byid[t['id']]['arms']['pairs']['scores']
        fired={c['id'] for c,p in zip(t['candidates'],scores) if p is not None and p>=threshold(policies['pairs'])}
        hits+=len(fired&gold)
    summary['fit_evidence']=dict(gold_items=gold_count,candidate_gold_items=coverage,learned_fired_gold_items=hits,note='Unmarked candidate pairs are not assumed to be semantically negative; eval lacks evidence gold.')
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main(Path(sys.argv[1]))
