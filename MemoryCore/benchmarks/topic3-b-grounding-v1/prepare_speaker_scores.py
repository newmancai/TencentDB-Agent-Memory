import argparse
import importlib.util
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser()
    for n in ['previous','run','model']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True)
    spec=importlib.util.spec_from_file_location('sem',Path(__file__).with_name('semantic_probe.py'));sem=importlib.util.module_from_spec(spec);spec.loader.exec_module(sem)
    previous={r['id']:r for r in read(a.previous/'tasks.jsonl')};scores={r['id']:r for r in read(a.previous/'predictions.jsonl')}
    cache={(t['context'],t['answer']):scores[i] for i,t in previous.items() if scores[i]['error'] is None}
    original_allowed=set(json.loads((a.previous/'allowed.json').read_text()));reused=[];pending=[];allowed=[]
    for t in read(a.run/'tasks.jsonl'):
        origin=t['id'].rsplit('::swap',1)[0]
        prompt=tok.apply_chat_template([{'role':'system','content':sem.PROMPT},{'role':'user','content':t['context']+'\nCandidate answer: '+t['answer']}],tokenize=False,add_generation_prompt=True)
        eligible=origin in original_allowed and len(tok.encode(prompt))<=4096
        key=(t['context'],t['answer'])
        if eligible and key in cache:reused.append({**cache[key],'id':t['id'],'reused':True})
        else:
            pending.append(t)
            if eligible:allowed.append(t['id'])
    (a.run/'reused.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in reused))
    (a.run/'pending.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in pending));(a.run/'allowed.json').write_text(json.dumps(allowed)+'\n')
    print({'reused':len(reused),'pending':len(pending),'new_forwards_allowed':len(allowed)})


if __name__=='__main__':main()
