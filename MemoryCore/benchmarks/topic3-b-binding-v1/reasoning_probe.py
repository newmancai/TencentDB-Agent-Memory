"""Development-only reasoning-cost probe. No held-out cases or feedback fitting."""
import json
from pathlib import Path
import re
import sys
import time


def main(root,model_path):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from run import PROMPT
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    prompt=PROMPT.replace('Output only that integer turn number, or unknown if indeterminate.',
        'First briefly identify the final topic and trace any returns to its earlier occurrences, citing original turn numbers. '
        'Distinguish the latest visit to a topic from its first appearance. End with ANCHOR: followed by the earliest turn integer, or unknown.')
    with (root/'reasoning-probe.jsonl').open('x') as out:
        for t in json.loads((root/'tasks.json').read_text()):
            if t['split']!='fit':continue
            text=tok.apply_chat_template([{'role':'system','content':prompt},{'role':'user','content':json.dumps({'development_examples':[],'current_sequence':t['history']},ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
            enc=tok(text,return_tensors='pt').to('cuda:0');n=enc['input_ids'].shape[1]
            torch.cuda.synchronize();start=time.perf_counter()
            with torch.inference_mode():ids=model.generate(**enc,do_sample=False,max_new_tokens=512,pad_token_id=tok.eos_token_id)
            torch.cuda.synchronize();value=tok.decode(ids[0,n:],skip_special_tokens=True);matches=re.findall(r'ANCHOR:\s*(\d+|unknown)\s*$',value)
            pred=int(matches[0]) if len(matches)==1 and matches[0].isdigit() else None
            if pred not in {m['turn'] for m in t['history']} or ids.shape[1]-n>=512:pred=None
            r={'id':t['id'],'text':value,'prediction':pred,'inputTokens':n,'outputTokens':int(ids.shape[1]-n),'elapsedMs':(time.perf_counter()-start)*1000}
            out.write(json.dumps(r)+'\n');out.flush();print(t['id'],flush=True)


if __name__=='__main__':main(Path(sys.argv[1]),sys.argv[2])
