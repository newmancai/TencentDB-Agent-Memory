"""Score remembered answers BEFORE consuming subsequent real public read results."""
import argparse,json,collections
from pathlib import Path
from receipts import ReceiptAdapter,PreviewAsCompletion,FeedbackLedger

def main():
    p=argparse.ArgumentParser();p.add_argument('data',type=Path);a=p.parse_args();summaries={};details=[]
    for task in map(json.loads,(a.data/'runtime.jsonl').open()):
        c=summaries.setdefault(task['split'],collections.Counter());adapter=ReceiptAdapter();na=PreviewAsCompletion()
        ledgers={k:FeedbackLedger() for k in ['base','naive','E']}
        for e in task['events']:
            facts,kind=adapter.observe(e)
            if kind=='read':
                # The actual tool response is offline evaluation truth for this read,
                # not evidence that was available in memory before the call.
                prior=[f for f in facts if f.key in ledgers['base'].active]
                c['read_calls']+=1;c['first_seen_fields']+=len(facts)-len(prior)
                if prior:
                    per_arm={}
                    for arm,l in ledgers.items():
                        matches=[f.key in l.active and l.active[f.key]['fact'].value==f.value for f in prior]
                        per_arm[arm]=all(matches);c[arm+'_fields_correct']+=sum(matches);c[arm+'_read_correct']+=all(matches)
                    c['repeat_read_calls']+=1;c['repeat_fields']+=len(prior)
                    c['E_improved_vs_base']+=per_arm['E'] and not per_arm['base']
                    c['E_regressed_vs_base']+=per_arm['base'] and not per_arm['E']
                    c['E_improved_vs_naive']+=per_arm['E'] and not per_arm['naive']
                    c['E_regressed_vs_naive']+=per_arm['naive'] and not per_arm['E']
                    details.append(dict(task=task['id'],event=e['id'],query_tool=e['tool'],arguments=e['arguments'],known_fields=len(prior),correct=per_arm))
            # Evidence becomes visible only after that pre-read assessment.
            ledgers['base'].consume(facts,e['id'],enabled=False);ledgers['E'].consume(facts,e['id'])
            nf,_=na.observe(e);ledgers['naive'].consume(nf,e['id'])
    (a.data/'subsequent-read-details.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in details))
    report={'splits':{k:dict(v) for k,v in summaries.items()},'limit':'Real public read queries and executable returns; evaluates previously remembered fields before new evidence. Not a new autonomous agent run, and first-seen fields are excluded explicitly.'}
    (a.data/'subsequent-read-metrics.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
