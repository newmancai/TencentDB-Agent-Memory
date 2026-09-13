"""Only example order changes; correct example associations remain intact."""
import argparse
import json
import urllib.request
from pathlib import Path
from detect import PROMPT,examples_for,v6

def main():
 p=argparse.ArgumentParser();p.add_argument('records',type=Path);p.add_argument('examples',type=Path);p.add_argument('out',type=Path);p.add_argument('--endpoint',default='http://127.0.0.1:18787');a=p.parse_args()
 rows=json.loads(a.records.read_text());examples=list(reversed(json.loads(a.examples.read_text())));a.out.mkdir(parents=True,exist_ok=False)
 with (a.out/'results.jsonl').open('x') as out:
  for row in rows:
   result=dict(id=row['id'],decisions=[])
   if row['pair']:
    evidence={s:dict(content=row['pair'][s]['content'],date=row['pair'][s]['date']) for s in ['old','later']}
    for target in row['targets']:
     inp=dict(target=target,evidence=evidence,examples=examples_for(examples,'labeled'))
     req=dict(messages=[dict(role='system',content=PROMPT),dict(role='user',content=json.dumps(inp,ensure_ascii=False))],maxTokens=8)
     try:
      request=urllib.request.Request(a.endpoint,json.dumps(req).encode(),{'Content-Type':'application/json'})
      with urllib.request.urlopen(request,timeout=180) as response:body=json.load(response)
     except Exception as e:body=dict(error=str(e))
     relation,error=v6.decode(body)
     result['decisions'].append(dict(target=target,record=row['record'],receipt=body,relation=relation,error=error))
    result.update(relation=v6.aggregate(result['decisions']),errors=sum(bool(d['error']) for d in result['decisions']))
   out.write(json.dumps(result,ensure_ascii=False)+'\n');out.flush()
   print(json.dumps(dict(id=row['id'],relation=result.get('relation'),errors=result.get('errors'))),flush=True)
if __name__=='__main__':main()
