"""Batch immutable target labels; v6.1 development cost control."""
import argparse
import json
import urllib.request
from pathlib import Path
from detect import PROMPT,aggregate

BATCH=PROMPT.replace('Judge ONLY the supplied old target,','Judge EACH supplied old target independently in the given order,').replace('Return exactly one letter:','For each target use:').replace('Do not explain.','Return ONLY a string of A/B/C letters, exactly one per target in order. No IDs, punctuation or explanations.')

def decode_batch(body,n):
    if body.get('error') or body.get('truncated'):return ['unknown']*n,'provider_failure'
    labels=''.join(body.get('text','').split())
    if len(labels)!=n or any(x not in 'ABC' for x in labels):return ['unknown']*n,'label_count_or_format'
    return [{'A':'changed','B':'same','C':'unknown'}[x] for x in labels],None

def main():
    p=argparse.ArgumentParser();p.add_argument('records',type=Path);p.add_argument('out',type=Path);p.add_argument('--endpoint',default='http://127.0.0.1:18786');a=p.parse_args()
    rows=json.loads(a.records.read_text());a.out.mkdir(parents=True,exist_ok=False)
    with (a.out/'results.jsonl').open('x') as out:
        for row in rows:
            result=dict(id=row['id'])
            if row['pair']:
                inp=dict(targets=row['targets'],evidence={s:dict(content=row['pair'][s]['content'],date=row['pair'][s]['date']) for s in ['old','later']})
                req=dict(messages=[dict(role='system',content=BATCH),dict(role='user',content=json.dumps(inp,ensure_ascii=False))],maxTokens=16)
                try:
                    request=urllib.request.Request(a.endpoint,json.dumps(req).encode(),{'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=180) as response:body=json.load(response)
                except Exception as e:body=dict(error=str(e))
                labels,error=decode_batch(body,len(row['targets']))
                decisions=[dict(target=t,relation=label) for t,label in zip(row['targets'],labels)]
                result.update(receipt=body,error=error,decisions=decisions,relation=aggregate(decisions))
            out.write(json.dumps(result,ensure_ascii=False)+'\n');out.flush();print(json.dumps(dict(id=row['id'],relation=result.get('relation'),error=result.get('error'))),flush=True)
if __name__=='__main__':main()
