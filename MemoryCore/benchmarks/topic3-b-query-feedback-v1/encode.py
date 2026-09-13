"""Frozen official last-token embedding contract, no silent truncation."""
import argparse,json,time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer,AutoModel

p=argparse.ArgumentParser();p.add_argument('--items',type=Path,required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
items=list(map(json.loads,a.items.read_text().splitlines()));tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,padding_side='left')
start=time.perf_counter();model=AutoModel.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval();load=time.perf_counter()-start
prepared=[];unknown=[]
for r in items:
 text=r['text'] if r['kind']=='document' else 'Instruct: Retrieve relevant dialogue messages that answer the question\nQuery:'+r['text']
 ids=tok(text,truncation=False)['input_ids']
 if len(ids)>4096:unknown.append({'id':r['id'],'tokens':len(ids),'error':'input_limit'})
 else:prepared.append((r['id'],ids))
# Length sorting only reduces padding; original IDs map all output rows.
prepared.sort(key=lambda r:len(r[1]));vectors=[];ids=[];batches=[]
for offset in range(0,len(prepared),32):
 batch=prepared[offset:offset+32];enc=tok.pad({'input_ids':[x[1] for x in batch]},padding=True,return_tensors='pt').to('cuda:0')
 assert bool(enc['attention_mask'][:,-1].all())
 torch.cuda.synchronize();start=time.perf_counter()
 with torch.inference_mode():v=F.normalize(model(**enc).last_hidden_state[:,-1].float(),p=2,dim=1)
 torch.cuda.synchronize();ms=(time.perf_counter()-start)*1000
 vectors.append(v.cpu().numpy());ids.extend(x[0] for x in batch);batches.append({'items':len(batch),'input_tokens':sum(len(x[1]) for x in batch),'padded_tokens':enc['input_ids'].numel(),'elapsed_ms':ms})
 if offset%320==0:print(offset+len(batch),len(prepared),flush=True)
np.save(a.out/'vectors.npy',np.concatenate(vectors));(a.out/'ids.json').write_text(json.dumps(ids)+'\n')
summary={'model':str(a.model),'dimension':1024,'load_seconds':load,'encoded':len(ids),'unknown':unknown,'input_tokens':sum(b['input_tokens'] for b in batches),'padded_tokens':sum(b['padded_tokens'] for b in batches),'forward_seconds':sum(b['elapsed_ms'] for b in batches)/1000,'batches':batches}
(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k!='batches'},flush=True)
