"""Score frozen Q and training-only Q+A. No fitted policy."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--encoded',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
ids=json.loads((a.encoded/'ids.json').read_text());v=np.load(a.encoded/'vectors.npy');assert v.shape==(len(ids),1024) and np.isfinite(v).all();assert np.allclose(np.linalg.norm(v,axis=1),1,atol=1e-5)
lookup={i:n for n,i in enumerate(ids)};tasks=list(map(json.loads,(a.prepared/'evaluation.jsonl').read_text().splitlines()));rows=[];unknown=[]
for t in tasks:
 queries={'q':t['query_id']}
 if t['teacher_id']:queries['qa']=t['teacher_id']
 pool=[i for i in ids if i.startswith('doc:'+t['source']+':')];pool.sort(key=lambda i:int(i.rsplit(':',1)[1]));gold=set(t['gold_document_ids'])
 if not gold<=set(pool) or any(i not in lookup for i in queries.values()):unknown.append(t['id']);continue
 docs=v[[lookup[i] for i in pool]];arms={}
 for arm,qid in queries.items():
  scores=docs@v[lookup[qid]];rank=np.argsort(-scores,kind='stable')[:10];hits=[pool[i] for i in rank];intersection=gold&set(hits)
  arms[arm]={'ids':hits,'any':bool(intersection),'all':gold<=set(hits),'recall':len(intersection)/len(gold)}
 rows.append({'id':t['id'],'source':t['source'],'split':t['split'],'arms':arms})
summary={'mode':'frozen_query_embedding_v1','unknown':unknown,'metrics':{},'feedback_qa_vs_q':{'win':0,'loss':0,'tie':0}}
for split in ('feedback','validation'):
 rs=[r for r in rows if r['split']==split]
 for arm in (('q','qa') if split=='feedback' else ('q',)):
  summary['metrics'][split+'_'+arm]={'n':len(rs),'any':sum(r['arms'][arm]['any'] for r in rs),'all':sum(r['arms'][arm]['all'] for r in rs),'macro_recall':sum(r['arms'][arm]['recall'] for r in rs)/len(rs)}
for r in rows:
 if r['split']=='feedback':
  x=r['arms']['qa']['all'];y=r['arms']['q']['all'];summary['feedback_qa_vs_q']['tie' if x==y else 'win' if x else 'loss']+=1
a.out.mkdir(parents=True,exist_ok=True);(a.out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
