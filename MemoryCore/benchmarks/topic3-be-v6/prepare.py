"""Next development sources, exact original spans, no model-created old facts."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=Path(__file__).resolve().parent.parent
adapter=module('adapter',base/'topic3-be-v2/prepare.py');v4=module('v4',base/'topic3-be-v4/detect.py')
source,exclude,output=map(Path,sys.argv[1:]);rows=json.loads(source.read_text());excluded=set(json.loads(exclude.read_text()));selected=[]
for kind in ('knowledge-update','single-session-user'):
    eligible=[r for r in rows if r['question_type']==kind and r['question_id'] not in excluded]
    selected+=sorted(eligible,key=lambda r:hashlib.sha256(('topic3-be-v2:'+r['question_id']).encode()).hexdigest())[32:40]
runtime=[];gold={}
for row in selected:
    task,label,pair=adapter.convert(row);spans=[]
    if pair:
        offset=0
        for s in v4.segments(pair['old']['content'],'o'):
            if s['text'].strip():spans.append(dict(s,start=offset,end=offset+len(s['text'])))
            offset+=len(s['text'])
    runtime.append(dict(id=task['id'],pair=pair,targets=spans[:8],omitted=spans[8:]));gold[task['id']]=label
output.mkdir(parents=True,exist_ok=False)
(output/'pairs.json').write_text(json.dumps(runtime,ensure_ascii=False));(output/'offline.json').write_text(json.dumps(gold,ensure_ascii=False))
print(json.dumps(dict(tasks=len(runtime),pairs=sum(r['pair'] is not None for r in runtime),targets=sum(len(r['targets']) for r in runtime),omitted=sum(len(r['omitted']) for r in runtime))))
