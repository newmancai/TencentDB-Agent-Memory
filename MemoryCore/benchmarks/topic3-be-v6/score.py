"""Pair relation plus silver target coverage; precision requires separate audit."""
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]
summary=dict(scope='known-pair development; independent assistant silver',reviews={},costs={})
for name in ['source-review','source-review-second']:
    labels={r['id']:r for r in json.loads((root/f'{name}.json').read_text())['rows']};arms={};paired=Counter()
    for arm in ['whole','spans']:
        c=Counter();confusion=Counter()
        for row in rows:
            if not row['arms']:c['not_run']+=1;continue
            label=labels[row['id']];x=row['arms'][arm];relation=label['relation']
            c['n']+=1;c['agreement']+=x['relation']==relation;c['error_tasks']+=x['errors']>0
            c['pred_changed']+=x['relation']=='changed';c['silver_changed']+=relation=='changed';c['matched_changed']+=x['relation']==relation=='changed'
            c['unknown']+=x['relation']=='unknown';confusion[f"{relation}->{x['relation']}"]+=1
            if arm=='spans':
                targets=set(label.get('changed_target_ids',[]));pred={d['target']['id'] for d in x['decisions'] if d['relation']=='changed' and not d['error']}
                c['silver_changed_targets']+=len(targets);c['matched_changed_targets']+=len(targets&pred);c['pred_changed_targets']+=len(pred)
        arms[arm]=dict(c,confusion=dict(confusion))
    for row in rows:
        if not row['arms']:continue
        label=labels[row['id']]['relation'];s=row['arms']['spans']['relation']==label;w=row['arms']['whole']['relation']==label
        paired['wins' if s and not w else 'losses' if w and not s else 'ties']+=1
    summary['reviews'][name]=dict(arms=arms,spans_vs_whole=dict(paired))
for arm in ['whole','spans']:
    c=Counter()
    for row in rows:
        if not row['arms']:continue
        for d in row['arms'][arm]['decisions']:
            c['calls']+=1;c['errors']+=bool(d['error'])
            for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=d['receipt'].get(k,0)
    summary['costs'][arm]=dict(c)
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
