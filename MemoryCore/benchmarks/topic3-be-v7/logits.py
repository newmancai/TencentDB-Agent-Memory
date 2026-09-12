"""Acquire original-prompt choice logits without reading evaluation labels."""
import argparse
import json
import time
from pathlib import Path
from detect import PROMPT,examples_for

def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--model',type=Path,required=True);p.add_argument('--batch-size',type=int,default=4);a=p.parse_args()
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM
 tokenizer=AutoTokenizer.from_pretrained(a.model,local_files_only=True);tokenizer.padding_side='left'
 if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
 ids=[tokenizer.encode(c,add_special_tokens=False) for c in 'ABC']
 if any(len(x)!=1 for x in ids):raise ValueError('choice is not one token')
 ids=[x[0] for x in ids]
 model=AutoModelForCausalLM.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
 rows=json.loads((a.root/'native/records.json').read_text());examples=json.loads((a.root/'adapted/examples.json').read_text())
 jobs=[]
 for row in rows:
  if not row['pair']:continue
  evidence={s:dict(content=row['pair'][s]['content'],date=row['pair'][s]['date']) for s in ['old','later']}
  for target in row['targets']:
   for arm in ['none','unlabeled','labeled','reversed']:
    ex=examples_for(list(reversed(examples)) if arm=='reversed' else examples,'labeled' if arm=='reversed' else arm)
    inp=dict(target=target,evidence=evidence,examples=ex)
    messages=[dict(role='system',content=PROMPT),dict(role='user',content=json.dumps(inp,ensure_ascii=False))]
    text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    jobs.append(dict(id=row['id'],target=target['id'],arm=arm,text=text))
 with (a.root/'logits.jsonl').open('x') as out:
  total_ms=0
  for start in range(0,len(jobs),a.batch_size):
   batch=jobs[start:start+a.batch_size];encoded=tokenizer([j['text'] for j in batch],padding=True,truncation=False,return_tensors='pt').to('cuda:0')
   if encoded['input_ids'].shape[1]>16384:raise ValueError('input exceeds provider cap')
   torch.cuda.synchronize();begin=time.perf_counter()
   with torch.inference_mode():
    values=model(**encoded).logits[:,-1,:].float();choices=values[:,ids];scores=choices[:,0]-torch.logsumexp(choices[:,1:],dim=1)
   torch.cuda.synchronize();elapsed=(time.perf_counter()-begin)*1000;total_ms+=elapsed
   for i,j in enumerate(batch):
    out.write(json.dumps(dict(id=j['id'],target=j['target'],arm=j['arm'],logits=choices[i].cpu().tolist(),score=scores[i].item(),choice='ABC'[choices[i].argmax().item()],global_token=tokenizer.decode([values[i].argmax().item()]),inputTokens=int(encoded['attention_mask'][i].sum()),batch=start//a.batch_size))+'\n')
   out.flush()
   if start%40==0:print(json.dumps(dict(done=min(start+a.batch_size,len(jobs)),total=len(jobs))),flush=True)
 (a.root/'logits-cost.json').write_text(json.dumps(dict(prompts=len(jobs),batch_size=a.batch_size,forward_service_ms=total_ms)))
if __name__=='__main__':main()
