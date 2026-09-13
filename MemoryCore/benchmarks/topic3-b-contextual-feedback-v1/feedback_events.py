"""Extract development reply events, without manufacturing semantic labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def hash_text(s):return hashlib.sha256(s.encode()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--adapted',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    with (a.adapted/'observations.jsonl').open() as f:
        rows=[r for l in f if l.strip() for r in [json.loads(l)] if r['split']=='development']
    old=set(json.loads((a.adapted/'preparation-summary.json').read_text())['smoke_development_ids'])
    used_groups={r['group'] for r in rows if r['id'] in old}
    # Deduplicate identical sessions reused by the three instance variants.
    unique={};owners={};boundaries=Counter()
    for r in rows:
        for s in r['history']:
            content=[{'role':m['role'],'content':m['content']} for m in s['messages']]
            fingerprint=hash_text(json.dumps(content,ensure_ascii=False))
            unique.setdefault(fingerprint,content);owners.setdefault(fingerprint,set()).add(r['group'])
    events=[]
    for fingerprint,messages in sorted(unique.items()):
        if len(owners[fingerprint])!=1:raise ValueError('Shared session has ambiguous persona')
        group=next(iter(owners[fingerprint]))
        for i,m in enumerate(messages):
            if m['role']!='user' or i==0:continue
            boundaries[messages[i-1]['role']+'->user']+=1
            if messages[i-1]['role']!='assistant':continue
            identifier=hash_text(fingerprint+':'+str(i))[:24]
            events.append({'id':identifier,'group':group,'source':'cupid','split':'development',
                'session_content_id':fingerprint,'response_id':f't{i}', 'feedback_id':f't{i+1}',
                'prefix':[dict(message,evidence_id=f't{j+1}') for j,message in enumerate(messages[:i+1])]})
    pool_groups=sorted({e['group'] for e in events}-used_groups,key=lambda x:hash_text('cupid-local-feedback-v1:'+x))[:8]
    selected=[]
    for group in pool_groups:
        selected.extend(sorted([e for e in events if e['group']==group],key=lambda e:hash_text('local-event:'+e['id']))[:2])
    assert len(selected)==16 and not ({e['group'] for e in selected}&used_groups)
    a.out.mkdir(parents=True,exist_ok=True)
    for name,records in [('events',events),('audit-inputs',selected)]:
        with (a.out/f'{name}.jsonl').open('w') as f:
            for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary={'protocol':'cupid-local-feedback-events-v1','development_unique_sessions':len(unique),
        'events':len(events),'boundary_counts':dict(boundaries),'selected_events':len(selected),
        'selected_personas':len(pool_groups),'overlap_previous_smoke_personas':0,
        'selected_ids':[e['id'] for e in selected],
        'scope':'Reply adjacency only, not endorsement or correction gold. Full causal prefix; no future turns, session preference or current hidden labels. No model/annotation run.'}
    (a.out/'event-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
