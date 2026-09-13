"""Audit released variant relations; no model input or labels are changed."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq


def fingerprint(session):
    return hashlib.sha256(json.dumps([(m['role'],m['content']) for m in session['dialogue']],ensure_ascii=False).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--parquet',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    groups=defaultdict(dict)
    for row in pq.read_table(a.parquet).to_pylist():
        assert row['instance_type'] not in groups[row['persona_id']]
        groups[row['persona_id']][row['instance_type']]=row
    counts=Counter();patterns=Counter();records=[]
    for group,variants in groups.items():
        assert set(variants)=={'consistent','contrastive','changing'}
        c,x,h=(variants[k] for k in ['consistent','contrastive','changing'])
        for name,other in [('contrastive',x),('changing',h)]:
            first={fingerprint(s):s for s in c['prior_interactions']};second={fingerprint(s):s for s in other['prior_interactions']}
            shared=set(first)&set(second);added=set(second)-set(first);removed=set(first)-set(second)
            pattern=(name,len(shared),len(removed),len(added));patterns[pattern]+=1
            same_request=c['current_request']==other['current_request']
            same_factor=c['current_context_factor']==other['current_context_factor']
            same_pref=c['current_contextual_preference']==other['current_contextual_preference']
            same_checklist=c['current_checklist']==other['current_checklist']
            preserved_order=[fingerprint(s) for s in c['prior_interactions'] if fingerprint(s) in shared]==[fingerprint(s) for s in other['prior_interactions'] if fingerprint(s) in shared]
            for key,value in [('same_request',same_request),('same_factor',same_factor),('same_preference',same_pref),('same_checklist',same_checklist),('shared_order_preserved',preserved_order)]:counts[name+':'+key]+=int(value)
            records.append({'group':group,'variant':name,'same_request':same_request,'same_factor':same_factor,
                'same_preference':same_pref,'same_checklist':same_checklist,'shared_order_preserved':preserved_order,
                'shared_sessions':len(shared),'removed_sessions':len(removed),'added_sessions':len(added),
                'added_matching_current_factor':sum(second[k]['context_factor']==other['current_context_factor'] for k in added)})
    summary={'mode':'released_cupid_pair_structure_audit','personas':len(groups),'pairs':len(records),
        'counts':dict(counts),'session_difference_patterns':[{'variant':k[0],'shared':k[1],'removed':k[2],'added':k[3],'pairs':v} for k,v in sorted(patterns.items())],
        'scope':'Published structural/annotation relations, not per-feedback semantic applicability or model learning. All-source schema audit; no task text displayed.'}
    a.out.mkdir(exist_ok=True,parents=True)
    (a.out/'pair-structure.json').write_text(json.dumps(summary,indent=2)+'\n')
    (a.out/'pair-relations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
