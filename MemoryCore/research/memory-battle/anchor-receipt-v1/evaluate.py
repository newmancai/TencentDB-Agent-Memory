"""Offline evaluator; only this process reads independent environment snapshots."""
import argparse,json,time,collections,dataclasses
from pathlib import Path
from receipts import ReceiptAdapter,FeedbackLedger,PreviewAsCompletion

MISSING=object()
def value(snapshot,fact):return snapshot.get(fact.entity,{}).get(fact.identity,{}).get(fact.field,MISSING)
def encode(x):
    if dataclasses.is_dataclass(x):return dataclasses.asdict(x)
    raise TypeError(type(x).__name__)

def main():
    p=argparse.ArgumentParser();p.add_argument('data',type=Path);p.add_argument('--split',required=True);a=p.parse_args()
    oracle={x['id']:x for x in map(json.loads,(a.data/'oracle.jsonl').open())};counts=collections.Counter();output=[]
    for task in map(json.loads,(a.data/'runtime.jsonl').open()):
        if task['split']!=a.split:continue
        adapter=ReceiptAdapter();ledger=FeedbackLedger();base=FeedbackLedger();naive_adapter=PreviewAsCompletion();naive=FeedbackLedger();events=[];start=time.perf_counter();b_ms=0;task_labels=[]
        for e,gold in zip(task['events'],oracle[task['id']]['events']):
            assert e['id']==gold['id']
            # Oracle never enters observe/consume. It judges identities after feedback is emitted.
            b_start=time.perf_counter();facts,source_kind=adapter.observe(e)
            b_ms+=(time.perf_counter()-b_start)*1000
            stale={r['id'] for r in ledger.active.values() if value(gold['after'],r['fact']) is not MISSING and value(gold['after'],r['fact'])!=r['fact'].value}
            b_start=time.perf_counter();signals,status=ledger.consume(facts,e['id'])
            b_ms+=(time.perf_counter()-b_start)*1000
            base.consume(facts,e['id'],enabled=False)
            naive_facts,_=naive_adapter.observe(e);naive_signals,_=naive.consume(naive_facts,e['id'])
            for s in naive_signals:
                actual=value(gold['after'],s['replacement']['fact'])
                counts['naive_accepted']+=1
                if actual is MISSING:counts['naive_unverified']+=1
                elif actual!=s['replacement']['fact'].value or actual==s['target']['fact'].value:counts['naive_false']+=1
            correct=[]
            for s in signals:
                old=s['target']['fact'];new=s['replacement']['fact'];actual=value(gold['after'],new)
                valid=None if actual is MISSING else actual==new.value and old.key==new.key and old.value!=actual
                correct.append(valid);counts['accepted']+=1;counts['correct']+=valid is True;counts['false_invalidation']+=valid is False
                counts['unverified']+=valid is None
                task_labels.append(valid)
            hit={s['target']['id'] for s,c in zip(signals,correct) if c}
            counts['stale_target_opportunities']+=len(stale);counts['stale_targets_resolved']+=len(stale&hit)
            counts['events']+=1;counts['events_with_feedback']+=bool(signals);counts['noncommit_events']+=source_kind=='noncommit'
            counts['noncommit_feedback']+=source_kind=='noncommit' and bool(signals)
            for name,l in [('base',base),('naive',naive),('E',ledger)]:
                for record in l.active.values():
                    actual=value(gold['after'],record['fact'])
                    if actual is not MISSING:counts[name+'_checked']+=1;counts[name+'_stale']+=actual!=record['fact'].value
            events.append(dict(event_id=e['id'],source_kind=source_kind,ledger_status=status,signals=signals,correct=correct,stale_targets=len(stale)))
        counts['tasks_with_feedback']+=bool(task_labels)
        counts['tasks_with_false_feedback']+=any(x is False for x in task_labels)
        counts['tasks_with_unverified_feedback']+=any(x is None for x in task_labels)
        output.append(dict(id=task['id'],split=a.split,events=events,history=ledger.history,active_ids=[r['id'] for r in ledger.active.values()],ms=(time.perf_counter()-start)*1000,b_ms=b_ms))
        counts['tasks']+=1
    result={'counts':dict(counts),'verified_fraction':counts['correct']/counts['accepted'] if counts['accepted'] else None,
            'precision_on_labeled':counts['correct']/(counts['accepted']-counts['unverified']) if counts['accepted']>counts['unverified'] else None,
            'opportunity_coverage':counts['stale_targets_resolved']/counts['stale_target_opportunities'] if counts['stale_target_opportunities'] else None,
            'B_ms':{'total':sum(x['b_ms'] for x in output),'per_task_mean':sum(x['b_ms'] for x in output)/len(output) if output else None},
            'iid_assumption_zero_error_task_risk_upper_95':1-0.05**(1/counts['tasks_with_feedback']) if counts['tasks_with_feedback'] and not counts['tasks_with_false_feedback'] and not counts['unverified'] else None,
            'note':'State consistency is a component measure, not agent task success. Opportunities are repeated stale record exposures per event, not independent samples.'}
    (a.data/(a.split+'-feedback.jsonl')).write_text(''.join(json.dumps(x,default=encode)+'\n' for x in output))
    (a.data/(a.split+'-metrics.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
