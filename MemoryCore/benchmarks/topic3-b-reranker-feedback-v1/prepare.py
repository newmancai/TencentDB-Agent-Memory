import argparse,hashlib,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
meta=list(map(json.loads,(a.run/'prepared/evaluation.jsonl').read_text().splitlines()));items={r['id']:r for r in map(json.loads,(a.run/'prepared/items.jsonl').read_text().splitlines())};ids=json.loads((a.run/'encoded/ids.json').read_text());v=np.load(a.run/'encoded/vectors.npy');idx={s:i for i,s in enumerate(ids)};tasks=[];pairs=[];labels=[]
for source in sorted({t['source'] for t in meta}):
 pool=sorted([s for s in ids if s.startswith('doc:'+source+':')],key=lambda s:int(s.rsplit(':',1)[1]));d=v[[idx[s] for s in pool]]
 selected=sorted([t for t in meta if t['source']==source],key=lambda t:hashlib.sha256(('reranker-feedback-v1:'+t['id']).encode()).hexdigest())[:10]
 for t in selected:
  scores=d@v[idx[t['query_id']]];rank=np.argsort(-scores,kind='stable')[:25];docs=[pool[i] for i in rank]
  tasks.append({'id':t['id'],'source':source,'query_id':t['query_id'],'candidate_ids':docs})
  labels.append({'id':t['id'],'gold_document_ids':t['gold_document_ids']})
  for j,doc in enumerate(docs):pairs.append({'id':t['id']+'::'+str(j),'query':items[t['query_id']]['text'],'document':items[doc]['text']})
a.out.mkdir(parents=True,exist_ok=True)
for name,rs in [('tasks.jsonl',tasks),('pairs.jsonl',pairs),('labels.jsonl',labels)]: (a.out/name).write_text(''.join(json.dumps(r)+'\n' for r in rs))
print({'questions':len(tasks),'pairs':len(pairs),'answer_input':False})
