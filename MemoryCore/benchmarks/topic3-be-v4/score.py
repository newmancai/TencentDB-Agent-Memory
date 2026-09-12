"""Agreement against both independent silver reviews; logical costs include draft."""
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(sys.argv[1]); rows=[json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]
result=dict(scope='development known-pair silver agreement',reviews={},costs={})
for name in ['source-review','source-review-second']:
    labels={r['id']:r['relation'] for r in json.loads((root/f'{name}.json').read_text())['rows']}
    arms={}; paired={}
    for arm in ['draft','ordinary','support']:
        c=Counter(); confusion=Counter()
        for row in rows:
            if not row['arms']: c['not_run']+=1;continue
            label=labels[row['id']]; x=row['arms'][arm]
            pred=x['parsed'].get('relation') if isinstance(x['parsed'],dict) else 'invalid'
            c['n']+=1;c['agreement']+=pred==label;c['contract_errors']+=bool(x['contract_error'])
            c['valid_agreement']+=pred==label and not x['contract_error']
            c['silver_changed']+=label=='changed';c['pred_changed']+=pred=='changed';c['matched_changed']+=pred==label=='changed'
            confusion[f'{label}->{pred}']+=1
        arms[arm]=dict(c,confusion=dict(confusion))
    for base in ['draft','ordinary']:
        c=Counter()
        for row in rows:
            if not row['arms']:continue
            def ok(arm):
                x=row['arms'][arm]['parsed'];return isinstance(x,dict) and x.get('relation')==labels[row['id']]
            a,b=ok('support'),ok(base);c['wins' if a and not b else 'losses' if b and not a else 'ties']+=1
        paired[base]=dict(c)
    result['reviews'][name]=dict(arms=arms,support_vs=paired)
for arm in ['draft','ordinary','support']:
    c=Counter()
    for row in rows:
        if not row['arms']:continue
        for phase in (['draft'] if arm=='draft' else ['draft',arm]):
            x=row['arms'][phase]['receipt'];c['calls']+=1
            for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=x.get(k,0)
    result['costs'][arm]=dict(c)
raw=[json.loads(x)['result'] for x in (root/'model-calls.jsonl').read_text().splitlines()]
result['actual']=dict(calls=len(raw),**{k:sum(x.get(k,0) for x in raw) for k in ['inputTokens','outputTokens','elapsedMs']})
(root/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
