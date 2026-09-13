import argparse,json,time
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);a=p.parse_args();r=a.run
ids=json.loads((a.vectors/'ids.json').read_text());v=np.load(a.vectors/'vectors.npy');idx={x:i for i,x in enumerate(ids)};tasks=list(map(json.loads,(r/'prepared/tasks.jsonl').read_text().splitlines()));scores={x['id']:x['score'] for x in map(json.loads,(r/'reranked/scores.jsonl').read_text().splitlines())};rows=list(map(json.loads,(r/'baseline-rows.jsonl').read_text().splitlines()));byid={x['id']:x for x in rows};times=[];updates=[]
for t in tasks:
 q=torch.tensor(v[idx[t['query_id']]],requires_grad=True);docs=torch.tensor(v[[idx[s] for s in t['candidate_ids'][:20]]]);teacher=torch.tensor([scores[t['id']+'::'+str(i)] for i in range(20)]);start=time.perf_counter();fallback=None
 if not torch.isfinite(teacher).all() or float(teacher.max()-teacher.min())==0:fallback='invalid_or_flat_teacher'
 else:
  target=torch.softmax((teacher-teacher.min())/(teacher.max()-teacher.min())/2,dim=0)
  for _ in range(100):
   student=docs@q;span=student.max()-student.min()
   if not torch.isfinite(span) or float(span.detach())==0:fallback='invalid_or_flat_student';break
   loss=torch.nn.functional.kl_div(torch.log_softmax((student-student.min())/span,dim=0),target,reduction='sum');loss.backward()
   with torch.no_grad():q-=.005*q.grad
   q.grad=None
 updated=v[idx[t['query_id']]] if fallback else q.detach().numpy();times.append((time.perf_counter()-start)*1000);updates.append(updated)
 pool=sorted([s for s in ids if s.startswith('doc:'+t['source']+':')],key=lambda s:int(s.rsplit(':',1)[1]));matrix=v[[idx[s] for s in pool]];best=int(torch.argmax(teacher));centroid=.5*(v[idx[t['query_id']]]+v[idx[t['candidate_ids'][best]]])
 for arm,vector in [('updated',updated),('centroid',centroid)]:byid[t['id']]['rankings'][arm]=[pool[i] for i in np.argsort(-(matrix@vector),kind='stable')[:10]]
 byid[t['id']]['fallback']=fallback
labels={t['id']:set(t['gold_document_ids']) for t in map(json.loads,(r/'prepared/labels.jsonl').read_text().splitlines())};summary={'n':len(rows),'metrics':{},'paired':{},'update_ms_total':sum(times),'update_ms_p50':float(np.quantile(times,.5)),'update_ms_p95':float(np.quantile(times,.95))}
for arm in ('dense','rerank20','rerank25','updated','centroid'):
 hits=[labels[x['id']]&set(x['rankings'][arm]) for x in rows];summary['metrics'][arm]={'any':sum(bool(s) for s in hits),'all':sum(s==labels[x['id']] for x,s in zip(rows,hits)),'macro_recall':sum(len(s)/len(labels[x['id']]) for x,s in zip(rows,hits))/len(rows)}
for arm in ('dense','rerank20','rerank25','centroid'):
 c={'win':0,'loss':0,'tie':0}
 for x in rows:
  g=labels[x['id']];u=g<=set(x['rankings']['updated']);b=g<=set(x['rankings'][arm]);c['tie' if u==b else 'win' if u else 'loss']+=1
 summary['paired']['updated_vs_'+arm]=c
np.save(r/'updated-vectors.npy',np.stack(updates));(r/'update-rows.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows));(r/'update-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
