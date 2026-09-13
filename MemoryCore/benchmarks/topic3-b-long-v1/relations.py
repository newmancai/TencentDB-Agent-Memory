import argparse
import json
import time
from pathlib import Path


def main(root,model_path):
    import torch
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    start=time.perf_counter();tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(model_path,local_files_only=True).to('cuda:0').eval()
    assert model.config.id2label[0].upper()=='CONTRADICTION'
    (root/'model.json').write_text(json.dumps(dict(model=str(model_path),loadSeconds=time.perf_counter()-start)))
    native={r['id']:r for r in json.loads((root/'native/results.json').read_text())}
    reference=json.loads((root/'references.json').read_text());tasks=json.loads((root/'tasks.json').read_text())
    with (root/'relations.jsonl').open('x') as out:
        for i,t in enumerate(tasks):
            pools={a:native[t['id']][a]['results'] for a in ['fts','recent']}
            candidates={m['id']:m['content'] for pool in pools.values() for m in pool}
            online_ids=set(candidates)
            old=reference[t['id']]['old']
            candidates[old['id']]=old['content']
            # Oracle-only reference is separately accounted and never inserted in a retrieval pool.
            result=dict(id=t['id'],pools={a:[m['id'] for m in pool] for a,pool in pools.items()},scores={})
            for key,text in candidates.items():
                enc=tok(text,t['incoming']['content'],truncation=False,return_tensors='pt');n=enc['input_ids'].shape[1]
                r=dict(inputTokens=n,oracle_only=key not in online_ids,score=None,error=None,elapsedMs=0.)
                if n>512:r['error']='input_limit'
                else:
                    enc=enc.to('cuda:0');torch.cuda.synchronize();start=time.perf_counter()
                    with torch.inference_mode():p=model(**enc).logits.softmax(-1)[0,0].item()
                    torch.cuda.synchronize();r.update(score=p,elapsedMs=(time.perf_counter()-start)*1000)
                result['scores'][key]=r
            out.write(json.dumps(result)+'\n');out.flush();print(json.dumps(dict(done=i+1,total=len(tasks))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--model',type=Path,required=True);a=p.parse_args();main(a.root,a.model)
