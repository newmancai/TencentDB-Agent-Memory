"""Score predeclared same-cohort batch control without changing v6 results."""
import json
import sys
from collections import Counter
from pathlib import Path
root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'batch/results.jsonl').read_text().splitlines()]
baseline={r['id']:r for r in [json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]}
summary=dict(reviews={},costs={})
for name in ['source-review','source-review-second']:
    labels={r['id']:r for r in json.loads((root/f'{name}.json').read_text())['rows']};c=Counter();paired=Counter();target_paired=Counter()
    for r in rows:
        if 'relation' not in r:c['not_run']+=1;continue
        l=labels[r['id']];c['n']+=1;c['agreement']+=r['relation']==l['relation'];c['errors']+=bool(r['error'])
        target_labels=set(l.get('changed_target_ids',[]));pred={d['target']['id'] for d in r['decisions'] if d['relation']=='changed'}
        c['changed_targets']+=len(target_labels);c['matched_changed_targets']+=len(target_labels&pred);c['pred_changed_targets']+=len(pred)
        c['pred_changed_pairs']+=r['relation']=='changed';c['unknown']+=r['relation']=='unknown'
        a=r['relation']==l['relation'];b=baseline[r['id']]['arms']['spans']['relation']==l['relation']
        paired['wins' if a and not b else 'losses' if b and not a else 'ties']+=1
        old={d['target']['id']:d['relation'] for d in baseline[r['id']]['arms']['spans']['decisions']}
        for d in r['decisions']:target_paired[f"{old[d['target']['id']]}->{d['relation']}"]+=1
    summary['reviews'][name]=dict(c,vs_spans=dict(paired),target_label_transitions=dict(target_paired))
c=Counter()
for r in rows:
    if 'receipt' not in r:continue
    c['calls']+=1
    for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=r['receipt'].get(k,0)
summary['costs']=dict(c);(root/'batch-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
