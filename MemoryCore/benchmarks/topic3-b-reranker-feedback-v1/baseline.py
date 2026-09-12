import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();r=a.run
tasks=list(map(json.loads,(r/'prepared/tasks.jsonl').read_text().splitlines()));labels={t['id']:set(t['gold_document_ids']) for t in map(json.loads,(r/'prepared/labels.jsonl').read_text().splitlines())};scores={x['id']:x['score'] for x in map(json.loads,(r/'reranked/scores.jsonl').read_text().splitlines())};rows=[];unknown=[]
for t in tasks:
 if any(t['id']+'::'+str(i) not in scores for i in range(25)):unknown.append(t['id']);continue
 rankings={'dense':t['candidate_ids'][:10]}
 for k in (20,25):
  order=sorted(range(k),key=lambda i:(-scores[t['id']+'::'+str(i)],i));rankings['rerank'+str(k)]=[t['candidate_ids'][i] for i in order[:10]]
 rows.append({'id':t['id'],'rankings':rankings})
summary={'n':len(rows),'unknown':unknown,'metrics':{},'paired':{}}
for arm in ('dense','rerank20','rerank25'):
 hits=[labels[x['id']]&set(x['rankings'][arm]) for x in rows];summary['metrics'][arm]={'any':sum(bool(s) for s in hits),'all':sum(s==labels[x['id']] for x,s in zip(rows,hits)),'macro_recall':sum(len(s)/len(labels[x['id']]) for x,s in zip(rows,hits))/len(rows)}
for arm in ('rerank20','rerank25'):
 c={'win':0,'loss':0,'tie':0}
 for x in rows:
  g=labels[x['id']];u=g<=set(x['rankings'][arm]);b=g<=set(x['rankings']['dense']);c['tie' if u==b else 'win' if u else 'loss']+=1
 summary['paired'][arm+'_vs_dense']=c
(r/'baseline-rows.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows));(r/'baseline-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
