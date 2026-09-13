import json
import sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'order/results.jsonl').read_text().splitlines()]
original={r['id']:r for r in [json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]}
summary=dict(reviews={},costs={})
for name in ['source-review','source-review-second']:
 labels={r['id']:r for r in json.loads((root/f'{name}.json').read_text())['rows']};c=Counter();paired=Counter();transitions=Counter()
 for r in rows:
  if not r['decisions']:c['not_run']+=1;continue
  l=labels[r['id']];pred={d['target']['id'] for d in r['decisions'] if d['relation']=='changed'};targets=set(l.get('changed_target_ids',[]))
  c['n']+=1;c['agreement']+=r['relation']==l['relation'];c['pred_changed_targets']+=len(pred);c['matched_changed_targets']+=len(pred&targets)
  c['unknown_pairs']+=r['relation']=='unknown';c['pred_changed_pairs']+=r['relation']=='changed';c['errors']+=r['errors']
  a=r['relation']==l['relation'];b=original[r['id']]['arms']['labeled']['relation']==l['relation']
  paired['wins' if a and not b else 'losses' if b and not a else 'ties']+=1
  old={d['target']['id']:d['relation'] for d in original[r['id']]['arms']['labeled']['decisions']}
  for d in r['decisions']:transitions[f"{old[d['target']['id']]}->{d['relation']}"]+=1
 summary['reviews'][name]=dict(c,vs_original=dict(paired),target_transitions=dict(transitions))
c=Counter()
for r in rows:
 for d in r['decisions']:
  c['calls']+=1
  for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=d['receipt'].get(k,0)
summary['costs']=dict(c);(root/'order-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
