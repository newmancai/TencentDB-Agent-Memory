"""Remaining fixed KU cohort and equal controls; four prior controlled examples."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=Path(__file__).resolve().parent.parent
adapter=module('adapter',base/'topic3-be-v2/prepare.py');v4=module('v4',base/'topic3-be-v4/detect.py')
def rank(s):return hashlib.sha256(('topic3-be-v2:'+s).encode()).hexdigest()
source,exclude,prior,output=map(Path,sys.argv[1:]);rows=json.loads(source.read_text());excluded=set(json.loads(exclude.read_text()))
def eligible(kind):return sorted([r for r in rows if r['question_type']==kind and r['question_id'] not in excluded],key=lambda r:rank(r['question_id']))
ku=eligible('knowledge-update')[40:];selected=ku+eligible('single-session-user')[40:40+len(ku)]
runtime=[];gold={}
for row in selected:
 task,label,pair=adapter.convert(row);spans=[]
 if pair:
  offset=0
  for s in v4.segments(pair['old']['content'],'o'):
   if s['text'].strip():spans.append(dict(s,start=offset,end=offset+len(s['text'])))
   offset+=len(s['text'])
 runtime.append(dict(id=task['id'],pair=pair,targets=spans[:8],omitted=spans[8:]));gold[task['id']]=label
prior_rows={r['id']:r for r in json.loads((prior/'native/records.json').read_text())}
a={r['id']:r for r in json.loads((prior/'source-review.json').read_text())['rows']}
b={r['id']:r for r in json.loads((prior/'source-review-second.json').read_text())['rows']}
chosen=[]
for relation in ['changed','same']:
 candidates=[]
 for key,t in prior_rows.items():
  if not t['pair'] or a[key]['relation']!=relation or b[key]['relation']!=relation:continue
  ids=set(a[key].get('changed_target_ids',[]))&set(b[key].get('changed_target_ids',[])) if relation=='changed' else {s['id'] for s in t['targets']}
  for s in t['targets']:
   if s['id'] in ids:candidates.append((rank(key+':'+s['id']),key,s))
 used=set()
 for _,key,s in sorted(candidates):
  if key in used:continue
  used.add(key);t=prior_rows[key]
  chosen.append(dict(source_pair=key,target=s,evidence={side:dict(content=t['pair'][side]['content'],date=t['pair'][side]['date']) for side in ['old','later']},relation='A' if relation=='changed' else 'B'))
  if len(used)==2:break
 if len(used)!=2:raise ValueError('insufficient consensus examples')
chosen.sort(key=lambda e:rank(e['source_pair']+':'+e['target']['id']))
example_pairs={tuple(e['evidence'][s]['content'] for s in ['old','later']) for e in chosen}
overlaps=[r['id'] for r in runtime if r['pair'] and tuple(r['pair'][s]['content'] for s in ['old','later']) in example_pairs]
output.mkdir(parents=True,exist_ok=False)
for name,obj in [('pairs',runtime),('offline',gold),('examples',chosen),('manifest',dict(tasks=len(runtime),pairs=sum(bool(r['pair']) for r in runtime),targets=sum(len(r['targets']) for r in runtime),ku=len(ku),omitted=sum(len(r['omitted']) for r in runtime),example_pair_overlap=overlaps))]:
 (output/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False))
print((output/'manifest.json').read_text())
