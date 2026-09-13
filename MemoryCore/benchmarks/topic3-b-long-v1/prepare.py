import importlib.util
import json
from pathlib import Path
import sys

def main(source,prior,output):
    path=Path(__file__).resolve().parent.parent/'topic3-be-v2/prepare.py'
    spec=importlib.util.spec_from_file_location('public_adapter',path);adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    known=json.loads(prior.read_text()); expected={r['id']:r for r in known}
    tasks=[];references={};unavailable=[]
    for raw in json.loads(source.read_text()):
        if adapter.opaque(raw['question_id']) not in expected:continue
        t,g,pair=adapter.convert(raw)
        if pair is None:unavailable.append(t['id']);continue
        assert pair==expected[t['id']]['pair']
        history=[m for m in t['messages'] if m['role']=='user' and m['order']<pair['later']['order']]
        assert pair['old']['id'] in {m['id'] for m in history}
        tasks.append(dict(id=t['id'],incoming={k:pair['later'][k] for k in ['id','content','order']},
                          messages=[{k:m[k] for k in ['id','role','content','order']} for m in history]))
        references[t['id']]=dict(old=pair['old'])
    assert len(tasks)+len(unavailable)==len(expected)
    output.mkdir(parents=True,exist_ok=False)
    for name,value in [('tasks',tasks),('references',references),('not-applicable',unavailable)]:
        (output/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False))
    print(json.dumps(dict(tasks=len(tasks),not_applicable=len(unavailable),writes=sum(len(t['messages']) for t in tasks))))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
