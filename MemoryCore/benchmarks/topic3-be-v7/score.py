"""Separate controlled-label increment, case agreement, target reach and costs."""
import json
import sys
from collections import Counter
from pathlib import Path

root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'model/results.jsonl').read_text().splitlines()]
pairs=json.loads((root/'adapted/pairs.json').read_text());examples=json.loads((root/'adapted/examples.json').read_text())
source_texts={e['evidence'][side]['content'] for e in examples for side in ['old','later']}
overlap=set();duplicates=[];seen=set();unique=set()
for r in pairs:
 if not r['pair']:continue
 key=tuple(r['pair'][side]['content'] for side in ['old','later'])
 if any(s in source_texts for s in key):overlap.add(r['id'])
 if key in seen:duplicates.append(r['id'])
 else:seen.add(key);unique.add(r['id'])
summary=dict(scope='known-target development; controlled assistant-silver examples',source_overlap_ids=sorted(overlap),duplicate_pair_ids=duplicates,reviews={},costs={})
for name in ['source-review','source-review-second']:
 labels={r['id']:r for r in json.loads((root/f'{name}.json').read_text())['rows']};arms={};paired={}
 for arm in ['none','unlabeled','labeled']:
  c=Counter();confusion=Counter()
  for r in rows:
   if not r['arms']:c['not_run']+=1;continue
   x=r['arms'][arm];l=labels[r['id']];relation=l['relation'];targets=set(l.get('changed_target_ids',[]))
   pred={d['target']['id'] for d in x['decisions'] if d['relation']=='changed' and not d['error']}
   c['n']+=1;c['agreement']+=x['relation']==relation;c['error_tasks']+=bool(x['errors']);c['unknown_pairs']+=x['relation']=='unknown'
   c['changed_pairs']+=relation=='changed';c['matched_changed_pairs']+=x['relation']==relation=='changed';c['pred_changed_pairs']+=x['relation']=='changed'
   c['silver_changed_targets']+=len(targets);c['matched_changed_targets']+=len(targets&pred);c['pred_changed_targets']+=len(pred)
   c['alarms_in_silver_same_pairs']+=len(pred) if relation=='same' else 0
   c['unknown_targets']+=sum(d['relation']=='unknown' for d in x['decisions'])
   confusion[f"{relation}->{x['relation']}"]+=1
   if r['id'] in unique and r['id'] not in overlap:c['unique_no_overlap_n']+=1;c['unique_no_overlap_agreement']+=x['relation']==relation
  arms[arm]=dict(c,confusion=dict(confusion))
 for baseline in ['none','unlabeled']:
  c=Counter();target_changes=Counter()
  for r in rows:
   if not r['arms']:continue
   l=labels[r['id']]['relation'];a=r['arms']['labeled']['relation']==l;b=r['arms'][baseline]['relation']==l
   key='wins' if a and not b else 'losses' if b and not a else 'ties';c[key]+=1
   if r['id'] in unique and r['id'] not in overlap:c['unique_no_overlap_'+key]+=1
   old={d['target']['id']:d['relation'] for d in r['arms'][baseline]['decisions']}
   for d in r['arms']['labeled']['decisions']:target_changes[f"{old[d['target']['id']]}->{d['relation']}"]+=1
  paired[baseline]=dict(c,target_label_transitions=dict(target_changes))
 summary['reviews'][name]=dict(arms=arms,labeled_vs=paired)
for arm in ['none','unlabeled','labeled']:
 c=Counter()
 for r in rows:
  if not r['arms']:continue
  for d in r['arms'][arm]['decisions']:
   c['calls']+=1;c['errors']+=bool(d['error'])
   for k in ['inputTokens','outputTokens','elapsedMs']:c[k]+=d['receipt'].get(k,0)
 summary['costs'][arm]=dict(c)
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
