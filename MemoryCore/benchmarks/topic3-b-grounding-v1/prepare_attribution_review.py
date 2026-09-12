"""Label-blind, arm-anonymized diagnostic review packet; not population evaluation."""
import argparse
import hashlib
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    tasks=read(a.run/'tasks.jsonl');pred={r['id']:r for r in read(a.run/'predictions.jsonl')};assert len(pred)==len(tasks)
    selected=sorted(tasks,key=lambda r:hashlib.sha256(('attribution-review-v1:'+r['id']).encode()).hexdigest())[:4]
    packets=[];keys=[]
    for t in selected:
        arms=['direct','attribution']
        if int(hashlib.sha256(t['id'].encode()).hexdigest(),16)%2:arms.reverse()
        packets.append({'id':t['id'],'observation':t,'outputs':{name:pred[t['id']]['arms'][arm]['text'] for name,arm in zip(['A','B'],arms)}})
        keys.append({'id':t['id'],'arms':dict(zip(['A','B'],arms))})
    a.out.mkdir(exist_ok=True,parents=True)
    (a.out/'blind.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in packets))
    (a.out/'key.json').write_text(json.dumps(keys,indent=2)+'\n')


if __name__=='__main__':main()
