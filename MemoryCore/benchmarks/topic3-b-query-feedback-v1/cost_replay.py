"""Replay saved states to measure local query transform+ranking; require identical outputs."""
import argparse,json,re,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();r=a.run
items=list(map(json.loads,(r/'prepared/items.jsonl').read_text().splitlines()));text={t['id']:t['text'] for t in items};meta={t['id']:t for t in map(json.loads,(r/'prepared/evaluation.jsonl').read_text().splitlines())};ids=json.loads((r/'encoded/ids.json').read_text());v=np.load(r/'encoded/vectors.npy').astype(np.float64);idx={s:i for i,s in enumerate(ids)};archive=np.load(r/'learned/state.npz');state={k:archive[k] for k in ('w','shuffled','mean')};archive.close();rows=list(map(json.loads,(r/'learned/rankings.jsonl').read_text().splitlines()));cost={arm:{'ms':[],'words':0} for arm in ('base','mean','learned','shuffled')}
for n,t in enumerate(rows):
 pool=sorted([s for s in ids if s.startswith('doc:'+t['source']+':')],key=lambda s:int(s.rsplit(':',1)[1]));docs=v[[idx[s] for s in pool]];q=v[idx[meta[t['id']]['query_id']]]
 arms=list(cost);arms=arms[n%4:]+arms[:n%4]
 for arm in arms:
  start=time.perf_counter();z=q if arm=='base' else q+state['mean'] if arm=='mean' else q+q@state['w' if arm=='learned' else 'shuffled'];z=z/np.linalg.norm(z);rank=np.argsort(-(docs@z),kind='stable')[:10];elapsed=(time.perf_counter()-start)*1000;found=[pool[i] for i in rank];assert found==t['rankings'][arm]
  cost[arm]['ms'].append(elapsed);cost[arm]['words']+=sum(len(re.findall(r'\w+',text[s])) for s in found)
summary={'identical_rankings':len(rows)*4,'scope':'CPU query transform+normalization+dot products+sorting; excludes model encoding, state load and document matrix construction','arms':{arm:{'returned_words':d['words'],'total_ms':sum(d['ms']),'p50_ms':float(np.quantile(d['ms'],.5)),'p95_ms':float(np.quantile(d['ms'],.95))} for arm,d in cost.items()}}
(r/'learned/cost-replay.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
