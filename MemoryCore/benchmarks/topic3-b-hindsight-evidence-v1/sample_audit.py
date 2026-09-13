"""Fixed source-balanced sample; reference membership is exported separately."""
import argparse
import hashlib
import json
from pathlib import Path


def visible(m):
    return {k:m[k] for k in ('speaker','dia_id','text')}


def sample(source, receipts):
    packets=[]; mapping=[]
    for src in source:
        pool=[r for r in receipts if r['source']==src['sample_id'] and set(r['arms']['qa']['ids'])-set(r['arms']['q']['ids'])]
        r=min(pool,key=lambda r:hashlib.sha256(('hindsight-audit-v1:'+r['id']).encode()).hexdigest())
        mid=next(i for i in r['arms']['qa']['ids'] if i not in r['arms']['q']['ids'])
        q=src['qa'][int(r['id'].rsplit(':',1)[1])]
        for key,session in src['conversation'].items():
            if not isinstance(session,list):continue
            for i,m in enumerate(session):
                if m['dia_id']!=mid:continue
                aid='audit-'+str(len(packets)+1).zfill(2)
                packets.append({'id':aid,'question':q['question'],'accepted_answer':str(q['answer']),'candidate':visible(m),'neighbors':[visible(n) for n in session[max(0,i-1):i]+session[i+1:i+2]],'session_date':src['conversation'].get(key+'_date_time')})
                mapping.append({'id':aid,'task_id':r['id'],'candidate_id':mid,'listed_reference':mid in q['evidence']})
    return packets,mapping


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--receipts',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    packets,mapping=sample(json.loads(a.source.read_text()),[json.loads(r) for r in a.receipts.read_text().splitlines()])
    a.out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('packets.json',packets),('mapping.json',mapping)]:
        (a.out/name).write_text(json.dumps(rows,indent=2)+'\n')
