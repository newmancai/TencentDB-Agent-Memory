import json
import sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'logits.jsonl').read_text().splitlines()];original={}
for x in (root/'model/results.jsonl').read_text().splitlines():
 r=json.loads(x)
 for arm,a in r['arms'].items():
  for d in a['decisions']:original[(r['id'],d['target']['id'],arm)]=d['receipt'].get('text','').strip()
for x in (root/'order/results.jsonl').read_text().splitlines():
 r=json.loads(x)
 for d in r['decisions']:original[(r['id'],d['target']['id'],'reversed')]=d['receipt'].get('text','').strip()
summary=dict(fidelity={},reviews={})
for arm in ['none','unlabeled','labeled','reversed']:
 subset=[r for r in rows if r['arm']==arm]
 summary['fidelity'][arm]=dict(n=len(subset),agreement=sum(r['choice']==original[(r['id'],r['target'],arm)] for r in subset),global_non_choice=sum(r['global_token'] not in 'ABC' or len(r['global_token'])!=1 for r in subset))
for name in ['source-review','source-review-second']:
 labels={r['id']:r for r in json.loads((root/f'{name}.json').read_text())['rows']};arms={}
 for arm in ['none','unlabeled','labeled','reversed']:
  ranked=sorted([r for r in rows if r['arm']==arm],key=lambda r:(-r['score'],r['id'],r['target']));budgets={}
  for k in [11,33,89]:
   c=Counter()
   for r in ranked[:k]:
    l=labels[r['id']];c['selected']+=1;c['marked_change_hits']+=r['target'] in l.get('changed_target_ids',[])
    c['in_same_pairs']+=l['relation']=='same';c['in_unknown_pairs']+=l['relation']=='unknown'
   budgets[str(k)]=dict(c)
  arms[arm]=budgets
 summary['reviews'][name]=arms
(root/'rank-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
