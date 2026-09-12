import importlib.util
import json
from pathlib import Path
import sys
import time
from collections import Counter

PARENT=Path(__file__).resolve().parent.parent/'topic3-b-binding-v1'
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,PARENT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
BASE=module('binding_base','run.py')
READ=module('binding_read','normalize_probe.py')
TRACE=BASE.PROMPT.replace('Output only that integer turn number, or unknown if indeterminate.',
    'First briefly identify the final topic and trace any returns to its earlier occurrences, citing original turn numbers. '
    'Distinguish the latest visit to a topic from its first appearance. End with ANCHOR: followed by the earliest turn integer, or unknown.')


def prepare(source,out):
    tasks=[];labels={}
    selection=json.loads((source/'binding-v2-selection.json').read_text())
    for dialog in selection['dialogs']:
        history=[];topics={}
        for r in map(json.loads,(source/f'dialog_{dialog}.jsonl').open()):
            history.append({'turn':r['turn'],'text':r['user_query_verified']});topics[r['turn']]=r['active_topic']
            if r['turn']%5:continue
            key=f'dialog_{dialog}:{r["turn"]}'
            tasks.append({'id':key,'history':history.copy()})
            labels[key]=min(t for t,v in topics.items() if v==r['active_topic'])
    out.mkdir(parents=True,exist_ok=False)
    (out/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False));(out/'labels.json').write_text(json.dumps(labels))
    (out/'selection.json').write_text(json.dumps(selection,indent=2))


def infer(root,path):
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    with (root/'results.jsonl').open('x') as out:
        for i,t in enumerate(json.loads((root/'tasks.json').read_text())):
            arms={}
            for arm in ['direct','trace'] if i%2==0 else ['trace','direct']:
                prompt=tok.apply_chat_template([{'role':'system','content':BASE.PROMPT if arm=='direct' else TRACE},
                    {'role':'user','content':json.dumps({'development_examples':[],'current_sequence':t['history']},ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
                enc=tok(prompt,return_tensors='pt').to('cuda:0');n=enc['input_ids'].shape[1]
                rec={'text':'','prediction':None,'inputTokens':n,'outputTokens':0,'elapsedMs':0,'error':None}
                if n>32768:rec['error']='input_limit'
                else:
                    torch.cuda.synchronize();start=time.perf_counter()
                    with torch.inference_mode():ids=model.generate(**enc,do_sample=False,max_new_tokens=512,pad_token_id=tok.eos_token_id)
                    torch.cuda.synchronize();rec.update(text=tok.decode(ids[0,n:],skip_special_tokens=True),outputTokens=int(ids.shape[1]-n),elapsedMs=(time.perf_counter()-start)*1000)
                    allowed={m['turn'] for m in t['history']};value=rec['text'].strip()
                    if arm=='trace':rec['prediction']=READ.final_anchor(value,allowed,rec['outputTokens'])
                    elif value.isascii() and value.isdigit() and int(value) in allowed and rec['outputTokens']<512:rec['prediction']=int(value)
                    if rec['prediction'] is None:rec['error']='output_limit' if rec['outputTokens']>=512 else 'unreadable_or_unknown'
                arms[arm]=rec
            out.write(json.dumps({'id':t['id'],'arms':arms})+'\n');out.flush();print(json.dumps({'done':i+1,'total':20}),flush=True)


def score(root):
    g=json.loads((root/'labels.json').read_text());rs=[json.loads(l) for l in (root/'results.jsonl').open()];assert len(rs)==20 and {r['id'] for r in rs}==set(g)
    result={'arms':{},'paired':dict(win=0,loss=0,tie=0),'cheap_baselines':{'first':sum(x==1 for x in g.values()),'current':sum(x==int(k.split(':')[1]) for k,x in g.items()),'n':len(g)}}
    for arm in ['direct','trace']:
        c=Counter();groups={}
        for r in rs:
            p=r['arms'][arm];ok=p['prediction']==g[r['id']]
            c.update(n=1,exact=int(ok),unknown=int(p['prediction'] is None),inputTokens=p['inputTokens'],outputTokens=p['outputTokens'],elapsedMs=p['elapsedMs'])
            if p['error']:c[p['error']]+=1
            d=groups.setdefault(r['id'].split(':')[0],{'n':0,'exact':0});d['n']+=1;d['exact']+=ok
        result['arms'][arm]={**dict(c),'by_dialog':groups}
    for r in rs:
        a=r['arms']['direct']['prediction']==g[r['id']];b=r['arms']['trace']['prediction']==g[r['id']]
        result['paired']['win' if b and not a else 'loss' if a and not b else 'tie']+=1
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare(Path(sys.argv[2]),Path(sys.argv[3]))
    elif sys.argv[1]=='infer':infer(Path(sys.argv[2]),sys.argv[3])
    else:score(Path(sys.argv[2]))
