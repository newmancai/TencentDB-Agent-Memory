"""Example-content vs verified-label control; evaluation labels never opened."""
import argparse
import importlib.util
import json
import urllib.request
from pathlib import Path

spec=importlib.util.spec_from_file_location('v6',Path(__file__).resolve().parent.parent/'topic3-be-v6/detect.py')
v6=importlib.util.module_from_spec(spec);spec.loader.exec_module(v6)
PROMPT=v6.PROMPT+' Prior examples, if supplied, are separate past cases. A relation field is a prior reviewed label; without it infer no label. Use them only to understand the judgment, never as facts about the current target.'
def examples_for(examples,arm):
 if arm=='none':return []
 return [{k:v for k,v in e.items() if k!='source_pair' and (arm=='labeled' or k!='relation')} for e in examples]

def main():
 p=argparse.ArgumentParser();p.add_argument('records',type=Path);p.add_argument('examples',type=Path);p.add_argument('out',type=Path);p.add_argument('--endpoint',default='http://127.0.0.1:18787');a=p.parse_args()
 rows=json.loads(a.records.read_text());examples=json.loads(a.examples.read_text());a.out.mkdir(parents=True,exist_ok=False)
 with (a.out/'results.jsonl').open('x') as out:
  for i,row in enumerate(rows):
   result=dict(id=row['id'],arms={arm:dict(decisions=[]) for arm in ['none','unlabeled','labeled']} if row['pair'] else {})
   if row['pair']:
    evidence={s:dict(content=row['pair'][s]['content'],date=row['pair'][s]['date']) for s in ['old','later']}
    for j,target in enumerate(row['targets']):
     arms=['none','unlabeled','labeled'];start=(i+j)%3;arms=arms[start:]+arms[:start]
     for arm in arms:
      inp=dict(target=target,evidence=evidence,examples=examples_for(examples,arm))
      req=dict(messages=[dict(role='system',content=PROMPT),dict(role='user',content=json.dumps(inp,ensure_ascii=False))],maxTokens=8)
      try:
       request=urllib.request.Request(a.endpoint,json.dumps(req).encode(),{'Content-Type':'application/json'})
       with urllib.request.urlopen(request,timeout=180) as response:body=json.load(response)
      except Exception as e:body=dict(error=str(e))
      relation,error=v6.decode(body)
      result['arms'][arm]['decisions'].append(dict(target=target,record=row['record'],receipt=body,relation=relation,error=error))
    for arm,x in result['arms'].items():x.update(relation=v6.aggregate(x['decisions']),errors=sum(bool(d['error']) for d in x['decisions']))
   out.write(json.dumps(result,ensure_ascii=False)+'\n');out.flush()
   print(json.dumps(dict(id=row['id'],arms={k:[v['relation'],v['errors']] for k,v in result['arms'].items()})),flush=True)
if __name__=='__main__':main()
