"""Isolate invalid target decisions without permitting target/evidence invention."""
from collections import Counter
from detect import parse

def partial_feedback(body,targets,evidence):
    obj,error=parse(body); allowed={s['id'] for s in evidence['later']['spans']}
    byid={t['id']:t for t in targets};issues=[];valid={}
    if error or not isinstance(obj.get('decisions') if obj else None,list):
        decisions=[];issues.append(error or 'decision_schema')
    else:decisions=obj['decisions']
    counts=Counter(d.get('target_id') for d in decisions if isinstance(d,dict) and isinstance(d.get('target_id'),str))
    for d in decisions:
        if not isinstance(d,dict):issues.append('non_object');continue
        tid=d.get('target_id')
        if not isinstance(tid,str) or tid not in byid:issues.append('unknown_target');continue
        if counts[tid]!=1:issues.append(f'{tid}:duplicate');continue
        if set(d)-{'target_id','relation','new_ids'} or d.get('relation') not in ('changed','same','unknown'):
            issues.append(f'{tid}:schema');continue
        ids=d.get('new_ids',[])
        if not isinstance(ids,list) or any(not isinstance(x,str) or x not in allowed for x in ids) or (not ids and d['relation']!='unknown'):
            issues.append(f'{tid}:source');continue
        valid[tid]=dict(target=byid[tid],relation=d['relation'],new_ids=ids,valid=True)
    output=[]
    for tid,t in byid.items():
        if tid not in valid:
            issues.append(f'{tid}:unresolved');output.append(dict(target=t,relation='unknown',new_ids=[],valid=False))
        else:output.append(valid[tid])
    relations={x['relation'] for x in output}
    aggregate='changed' if 'changed' in relations else 'unknown' if 'unknown' in relations or not relations else 'same'
    return dict(feedback=output,relation=aggregate,issues=issues)
