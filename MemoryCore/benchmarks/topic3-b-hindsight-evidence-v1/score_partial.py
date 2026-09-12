"""Summarize mechanical validity/cost; prepare fixed semantic audit, not automatic quality scores."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    tasks={r['id']:r for r in map(json.loads,(a.run/'tasks.jsonl').read_text().splitlines())};rows=list(map(json.loads,(a.run/'predictions.jsonl').read_text().splitlines()))
    assert len(rows)==len(tasks) and {r['id'] for r in rows}==set(tasks)
    summary={'mode':'partial_feedback_representation_v1','tasks':len(tasks),'arms':{}}
    for arm in ('ordinary','parts'):
        records=[r['arms'][arm] for r in rows]
        summary['arms'][arm]={'valid':sum(r['error'] is None for r in records),'errors':dict(Counter(r['error'] for r in records if r['error'])),'actual_generations':sum(r['output_tokens']>0 for r in records),'input_tokens':sum(r['input_tokens'] for r in records if r['output_tokens']>0),'output_tokens':sum(r['output_tokens'] for r in records),'generation_seconds':sum(r['elapsed_ms'] for r in records)/1000}
    common=[r for r in rows if all(v['error'] is None for v in r['arms'].values())];summary['common_valid']=len(common)
    chosen=sorted(common,key=lambda r:hashlib.sha256(('partial-audit-v1:'+r['id']).encode()).hexdigest())[:6]
    packets=[];mapping=[]
    for i,r in enumerate(chosen):
        names=['ordinary','parts'];flip=hashlib.sha256(('partial-mask-v1:'+r['id']).encode()).digest()[0]%2
        if flip:names.reverse()
        aid=f'pair-{i+1:02}'
        packets.append({'id':aid,'task':{k:v for k,v in tasks[r['id']].items() if k!='id'},'X':r['arms'][names[0]]['parsed'],'Y':r['arms'][names[1]]['parsed']})
        mapping.append({'id':aid,'task_id':r['id'],'X':names[0],'Y':names[1]})
    a.out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('summary.json',summary),('audit-packets.json',packets),('audit-mapping.json',mapping)]:
        (a.out/name).write_text(json.dumps(obj,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
