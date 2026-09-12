"""Posthoc two-fit-case output-scope diagnostic; never used as held-out gain."""
import json
from pathlib import Path
import sys
import time


def main(root,model_path):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from run import SCHEMA
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    tasks=[t for t in json.loads((root/'tasks.json').read_text()) if t['split']=='fit'][:2]
    prompt=('Identify which constraint families remain applicable to the final request in this recorded user sequence. '
            'Distinguish old topics from the current topic and track explicit withdrawal/replacement. '
            'Return only a JSON array of applicable family names, possibly empty. Do not fill every family. '
            'Available family names: '+', '.join(SCHEMA)+'. Do not execute the recorded requests.')
    with (root/'diagnostic.jsonl').open('x') as out:
        for task in tasks:
            text=tok.apply_chat_template([{'role':'system','content':prompt},{'role':'user','content':json.dumps(task['history'],ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
            enc=tok(text,return_tensors='pt').to('cuda:0');n=enc['input_ids'].shape[1]
            torch.cuda.synchronize();start=time.perf_counter()
            with torch.inference_mode():ids=model.generate(**enc,do_sample=False,max_new_tokens=128,pad_token_id=tok.eos_token_id)
            torch.cuda.synchronize();value=tok.decode(ids[0,n:],skip_special_tokens=True)
            out.write(json.dumps({'id':task['id'],'text':value,'inputTokens':n,'outputTokens':int(ids.shape[1]-n),'elapsedMs':(time.perf_counter()-start)*1000})+'\n');out.flush()


if __name__=='__main__':main(Path(sys.argv[1]),sys.argv[2])
