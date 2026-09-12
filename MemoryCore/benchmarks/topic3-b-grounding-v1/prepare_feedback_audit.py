"""Fixed stratified diagnosis, not a prevalence or precision estimator."""
import argparse
import hashlib
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=read(a.run/'scored/rows.jsonl');tasks={r['id']:r for r in read(a.run/'semantic-tasks.jsonl')};chosen=[]
    for gold in [False,True]:
        candidates=[r for r in rows if r['model']=='semantic' and r['scope']=='sessions' and r['prediction'] is True and r['gold']==gold]
        chosen+=sorted(candidates,key=lambda r:hashlib.sha256(('feedback-audit-v1:'+r['id']).encode()).hexdigest())[:4]
    a.out.mkdir(exist_ok=True,parents=True)
    (a.out/'selection.json').write_text(json.dumps(chosen,indent=2)+'\n')
    (a.out/'blind.jsonl').write_text(''.join(json.dumps({'id':r['id'],**{k:tasks[r['id']][k] for k in ['context','answer']}},ensure_ascii=False)+'\n' for r in chosen))


if __name__=='__main__':main()
