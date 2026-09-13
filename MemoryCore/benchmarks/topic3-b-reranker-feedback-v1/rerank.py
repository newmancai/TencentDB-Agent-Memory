import argparse,json,time
from pathlib import Path
import torch
from transformers import AutoTokenizer,AutoModelForCausalLM
p=argparse.ArgumentParser();p.add_argument('--pairs',type=Path,required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,padding_side='left');start=time.perf_counter();model=AutoModelForCausalLM.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval();load=time.perf_counter()-start
prefix='<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n';suffix='<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n';pre=tok.encode(prefix,add_special_tokens=False);post=tok.encode(suffix,add_special_tokens=False);yes=tok.convert_tokens_to_ids('yes');no=tok.convert_tokens_to_ids('no');pairs=list(map(json.loads,a.pairs.read_text().splitlines()));ready=[];unknown=[]
for r in pairs:
 text='<Instruct>: Retrieve relevant dialogue messages that answer the question\n<Query>: '+r['query']+'\n<Document>: '+r['document'];ids=pre+tok.encode(text,add_special_tokens=False)+post
 if len(ids)>4096:unknown.append({'id':r['id'],'error':'input_limit'})
 else:ready.append((r['id'],ids))
ready.sort(key=lambda x:len(x[1]));batches=[]
with (a.out/'scores.jsonl').open('x') as f:
 for offset in range(0,len(ready),16):
  batch=ready[offset:offset+16];enc=tok.pad({'input_ids':[x[1] for x in batch]},padding=True,return_tensors='pt').to('cuda:0');assert bool(enc['attention_mask'][:,-1].all());torch.cuda.synchronize();start=time.perf_counter()
  with torch.inference_mode():logits=model(**enc).logits[:,-1].float();scores=(logits[:,yes]-logits[:,no]).cpu().tolist()
  torch.cuda.synchronize();elapsed=(time.perf_counter()-start)*1000
  for (i,ids),score in zip(batch,scores):f.write(json.dumps({'id':i,'score':score,'tokens':len(ids)})+'\n')
  f.flush();batches.append({'pairs':len(batch),'tokens':sum(len(x[1]) for x in batch),'padded_tokens':enc['input_ids'].numel(),'ms':elapsed})
  if offset%320==0:print(offset+len(batch),len(ready),flush=True)
summary={'pairs':len(ready),'unknown':unknown,'load_seconds':load,'forward_seconds':sum(b['ms'] for b in batches)/1000,'tokens':sum(b['tokens'] for b in batches),'padded_tokens':sum(b['padded_tokens'] for b in batches),'batches':batches};(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k!='batches'},flush=True)
