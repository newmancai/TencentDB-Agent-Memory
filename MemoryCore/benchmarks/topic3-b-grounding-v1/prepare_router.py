import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def mod(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser()
    for n in ['source','previous','recent','pair','model','out']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();extra={r['group']+':'+str(r['question_index']) for r in read(a.pair/'labels.jsonl')}
    base=a.out/'original';alt=a.out/'alternatives';joint=a.out/'joint'
    mod('pair_probe').prepare(a.source,a.previous,a.recent,a.model,base,extra_used=extra,per_group=10,seed='router-pairs-v1')
    mod('speaker_candidates').prepare(base,alt);mod('joint_probe').prepare(base,alt,a.model,joint)
    labels=read(base/'labels.jsonl');groups=sorted({r['group'] for r in labels},key=lambda g:hashlib.sha256(('router-split-v1:'+g).encode()).hexdigest());split={g:'feedback' if i<5 else 'validation' for i,g in enumerate(groups)}
    original_allowed=set(json.loads((base/'allowed.json').read_text()));joint_allowed=set(json.loads((joint/'allowed.json').read_text()));allowed=original_allowed&joint_allowed
    bad_pairs={r['pair'] for r in labels if r['id'] not in allowed};allowed={r['id'] for r in labels if r['pair'] not in bad_pairs}
    tasks=[]
    for name,directory in [('original',base),('joint',joint)]:
        for r in read(directory/'tasks.jsonl'):tasks.append({**r,'id':r['id']+'::'+name})
    (a.out/'tasks.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in tasks));(a.out/'allowed.json').write_text(json.dumps([r['id'] for r in tasks if r['id'].rsplit('::',1)[0] in allowed])+'\n');(a.out/'split.json').write_text(json.dumps(split,indent=2)+'\n')
    print({'groups':split,'endpoints':len(labels),'common_endpoints':len(allowed),'model_requests':2*len(allowed)})


if __name__=='__main__':main()
