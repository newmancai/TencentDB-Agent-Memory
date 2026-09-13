"""Offline silver agreement, coverage, costs and duplicate-aware sensitivity."""
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]
pairs=json.loads((root/'adapted/pairs.json').read_text());seen=set();unique=set();duplicates=[]
for row in pairs:
    if not row['pair']:continue
    key=tuple(row['pair'][s]['content'] for s in ['old','later'])
    if key in seen:duplicates.append(row['id'])
    else:seen.add(key);unique.add(row['id'])
summary=dict(scope='assistant silver, development reuse, known pairs',duplicate_text_ids=duplicates,reviews={},costs={})
for name in ['source-review','source-review-second']:
    labels={r['id']:r['relation'] for r in json.loads((root/f'{name}.json').read_text())['rows']}
    arms={};paired={}
    for arm in ['direct','joint','old_only']:
        c=Counter();confusion=Counter()
        for row in rows:
            if not row['arms']:c['not_run']+=1;continue
            x=row['arms'][arm];label=labels[row['id']];pred=x['relation']
            c['n']+=1;c['agreement']+=pred==label;c['contract_errors']+=bool(x['contract_error'])
            c['empty_targets']+=bool(x.get('empty_targets'));c['target_count']+=len(x.get('targets',[]))
            c['nonabstain']+=pred in ('same','changed') and not x['contract_error']
            c['valid_agreement']+=pred==label and not x['contract_error']
            c['silver_changed']+=label=='changed';c['pred_changed']+=pred=='changed';c['matched_changed']+=pred==label=='changed'
            if row['id'] in unique:c['unique_n']+=1;c['unique_agreement']+=pred==label
            confusion[f'{label}->{pred}']+=1
        arms[arm]=dict(c,confusion=dict(confusion))
    for baseline in ['direct','joint']:
        c=Counter()
        for row in rows:
            if not row['arms']:continue
            a=row['arms']['old_only']['relation']==labels[row['id']];b=row['arms'][baseline]['relation']==labels[row['id']]
            label='wins' if a and not b else 'losses' if b and not a else 'ties';c[label]+=1
            if row['id'] in unique:c['unique_'+label]+=1
        paired[baseline]=dict(c)
    summary['reviews'][name]=dict(arms=arms,old_only_vs=paired)
for arm in ['direct','joint','old_only']:
    c=Counter()
    for row in rows:
        if not row['arms']:continue
        for x in row['arms'][arm]['calls']:
            c['calls']+=1;c['truncated']+=bool(x.get('truncated'))
            for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=x.get(k,0)
    summary['costs'][arm]=dict(c)
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
