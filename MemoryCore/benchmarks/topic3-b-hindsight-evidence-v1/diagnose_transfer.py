"""Posthoc reference upper bounds and narrow in-memory fallback verification."""
import argparse
from collections import Counter
import json
from pathlib import Path
from lexical_probe import adapt
from transfer_probe import Sidecar


def diagnose(source,run):
    _,_,labels,_=adapt(source);splits=json.loads((run/'split.json').read_text());states=json.loads((run/'states.json').read_text())
    ranks=list(map(json.loads,(run/'rankings.jsonl').read_text().splitlines()));bindings=list(map(json.loads,(run/'bindings.jsonl').read_text().splitlines()));c=Counter()
    for b in bindings:
        for key in ('q_bound','qa_bound'):c[key+'_in_reference']+=b[key] in labels[b['id']]
    for r in ranks:
        gold=labels[r['id']];base=set(r['outputs']['base']);alias=set(r['outputs']['feedback_alias']);sid=r['source']
        bound={e['message_id'] for e in states[sid]['feedback_alias']};prior=set().union(*(labels[i] for i in splits[sid]['feedback']))
        c['validation_has_prior_reference_overlap']+=bool(gold&prior)
        if not gold<=base:
            c['base_all_failure']+=1;c['all_repairable_by_current_binding_pool_upper_bound']+=gold<=(base|bound);c['all_repairable_by_prior_gold_pool_upper_bound']+=gold<=(base|prior)
        if gold<=base and not gold<=alias:
            c['all_regression']+=1;c['reference_hits_displaced_in_regressions']+=len(gold-alias)
    checks=[];base=['m1','m2']
    for name,state in [('empty',[]),('malformed',[{'text':'x'}]),('oversized',[{'text':'x','message_id':'m1'}]*65)]:
        side=Sidecar(state,set(base));v,log=side.select('x',base);assert v==base;checks.append({'case':name,**log});side.close()
    side=Sidecar([{'text':'target','message_id':'m2'}],set(base));v,log=side.select('target',base,enabled=False);assert v==base;checks.append({'case':'disabled',**log});side.close()
    v,log=side.select('target',base);assert v==base and log['fallback']=='read_failed';checks.append({'case':'closed_database',**log})
    return {'posthoc_reference_audit':dict(c),'fallback_checks':checks,'interpretation':'Gold-pool repairability is an oracle upper bound, never a deployed policy or future-answer input.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.write_text(json.dumps(diagnose(a.source,a.run),indent=2)+'\n')
