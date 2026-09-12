import argparse
import hashlib
import json
from pathlib import Path
import time


def read(path):
    with path.open() as f:return [json.loads(line) for line in f]


def prepare(data, out):
    rows = [r for r in read(data/'observations.jsonl') if r['split']=='train']
    groups = set()
    for kind in sorted({r['source_kind'] for r in rows}):
        choices = {r['group'] for r in rows if r['source_kind']==kind}
        groups.update(sorted(choices,key=lambda g:hashlib.sha256(('grounding-baseline-v1:'+g).encode()).hexdigest())[:50])
    selected = [r for r in rows if r['group'] in groups]
    out.mkdir(parents=True,exist_ok=True)
    with (out/'tasks.jsonl').open('w') as f:
        for row in selected:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    (out/'selection.json').write_text(json.dumps({'groups':sorted(groups),'ids':[r['id'] for r in selected]},indent=2)+'\n')
    print(len(groups),len(selected))


def infer(tasks, model_path, out):
    import torch
    from transformers import AutoTokenizer,AutoModelForTokenClassification
    tokenizer = AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(model_path,local_files_only=True,
        attn_implementation='sdpa',reference_compile=False).to('cuda:0').eval()
    with out.open('x') as f:
        for row in read(tasks):
            encoded = tokenizer(row['context'],row['answer'],truncation=False,
                                return_offsets_mapping=True,return_tensors='pt')
            sequence = encoded.sequence_ids(0)
            offsets = encoded.pop('offset_mapping')[0].tolist()
            count = int(encoded['input_ids'].shape[1])
            record = {'id':row['id'],'group':row['group'],'source_kind':row['source_kind'],
                      'tokens':count,'error':None,'elapsed_ms':0,'answer_tokens':[]}
            if count>4096:
                record['error']='input_limit'
            else:
                inputs = {k:v.to('cuda:0') for k,v in encoded.items() if k in ['input_ids','attention_mask']}
                torch.cuda.synchronize();start=time.perf_counter()
                with torch.inference_mode():
                    logits = model(**inputs).logits[0]
                    prob = logits.float().softmax(-1)[:,1].cpu().tolist()
                    pred = logits.argmax(-1).cpu().tolist()
                torch.cuda.synchronize();record['elapsed_ms']=(time.perf_counter()-start)*1000
                record['answer_tokens']=[{'start':a,'end':b,'prob':prob[i],'pred':pred[i]}
                    for i,(a,b) in enumerate(offsets) if sequence[i]==1 and b>a]
                assert all(0<=t['start']<t['end']<=len(row['answer']) for t in record['answer_tokens'])
            f.write(json.dumps(record)+'\n');f.flush()
            print(row['id'],count,record['error'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','infer'])
    p.add_argument('--data',type=Path);p.add_argument('--tasks',type=Path)
    p.add_argument('--model');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.mode=='prepare':prepare(a.data,a.out)
    else:infer(a.tasks,a.model,a.out)
