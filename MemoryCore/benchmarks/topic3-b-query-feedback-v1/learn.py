"""Fixed residual ridge with mean and shuffled-feedback controls."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--encoded',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
ids=json.loads((a.encoded/'ids.json').read_text());v=np.load(a.encoded/'vectors.npy').astype(np.float64);idx={s:i for i,s in enumerate(ids)};tasks=list(map(json.loads,(a.prepared/'evaluation.jsonl').read_text().splitlines()));assert not json.loads((a.encoded/'summary.json').read_text())['unknown'], 'Incomplete encoding: define a shared eligible cohort before learning';train=[t for t in tasks if t['split']=='feedback'];valid=[t for t in tasks if t['split']=='validation']
x=v[[idx[t['query_id']] for t in train]];d=v[[idx[t['teacher_id']] for t in train]]-x
order=sorted(range(len(train)),key=lambda i:hashlib.sha256(('query-feedback-shuffle-v1:'+train[i]['id']).encode()).hexdigest());perm=np.empty(len(train),dtype=int)
for n,i in enumerate(order):perm[i]=order[(n+1)%len(order)]
assert all(i!=j for i,j in enumerate(perm));start=time.perf_counter();gram=x.T@x+np.eye(x.shape[1]);w=np.linalg.solve(gram,x.T@d);shuffled=np.linalg.solve(gram,x.T@d[perm]);mean=d.mean(axis=0);fit=time.perf_counter()-start
rows=[]
for t in valid:
 q=v[idx[t['query_id']]];queries={'base':q,'mean':q+mean,'learned':q+q@w,'shuffled':q+q@shuffled}
 pool=sorted([s for s in ids if s.startswith('doc:'+t['source']+':')],key=lambda s:int(s.rsplit(':',1)[1]));docs=v[[idx[s] for s in pool]];out={}
 for arm,z in queries.items():
  z=z/np.linalg.norm(z);rank=np.argsort(-(docs@z),kind='stable')[:10];out[arm]=[pool[i] for i in rank]
 rows.append({'id':t['id'],'source':t['source'],'rankings':out})
# No validation gold used until all predictions are fixed.
labels={t['id']:set(t['gold_document_ids']) for t in valid};summary={'mode':'fixed_residual_feedback_v1','fit_seconds':fit,'training':len(train),'validation':len(valid),'metrics':{},'paired':{},'by_source':{}}
for arm in ('base','mean','learned','shuffled'):
 h=[set(r['rankings'][arm])&labels[r['id']] for r in rows];summary['metrics'][arm]={'any':sum(bool(s) for s in h),'all':sum(s==labels[r['id']] for r,s in zip(rows,h)),'macro_recall':sum(len(s)/len(labels[r['id']]) for r,s in zip(rows,h))/len(rows)}
for other in ('base','mean','shuffled'):
 c={'win':0,'loss':0,'tie':0}
 for r in rows:
  g=labels[r['id']];u=g<=set(r['rankings']['learned']);b=g<=set(r['rankings'][other]);c['tie' if u==b else 'win' if u else 'loss']+=1
 summary['paired']['learned_vs_'+other]=c
for s in sorted({r['source'] for r in rows}):
 rs=[r for r in rows if r['source']==s];summary['by_source'][s]={'n':len(rs),**{arm:sum(labels[r['id']]<=set(r['rankings'][arm]) for r in rs) for arm in summary['metrics']}}
a.out.mkdir(parents=True,exist_ok=True);np.savez_compressed(a.out/'state.npz',w=w,shuffled=shuffled,mean=mean,permutation=perm);(a.out/'rankings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
