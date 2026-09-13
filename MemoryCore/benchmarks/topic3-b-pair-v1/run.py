import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path


def prepare(archive, old, root):
    previous=json.loads(old.read_text()); used={r['group'] for r in previous}
    fit_ids={r['id'] for r in previous if r['split']=='fit'}
    tasks=[]; gold={}
    with zipfile.ZipFile(archive) as z:
        for source,split in [('dev','fit'),('human-bot','eval')]:
            rows=[json.loads(l) for l in z.read(f'decode_v0.1/{source}.jsonl').splitlines()]
            rows.sort(key=lambda r:hashlib.sha256(('20260914:'+r['record_id']).encode()).hexdigest())
            count=0
            for r in rows:
                group=r['conversation_id'].split('#')[0]
                if split=='fit' and r['record_id'] not in fit_ids:continue
                if split=='eval' and group in used:continue
                used.add(group);count+=1; last=r['turns'][-1]
                candidates=[dict(id=t['turn_id'],text=t['text']) for t in r['turns'][:-1] if t['agent_id']==last['agent_id']]
                assert len(candidates)<=16
                tasks.append(dict(id=r['record_id'],group=group,split=split,target=dict(id=last['turn_id'],text=last['text']),candidates=candidates))
                gold[r['record_id']]=dict(contradiction=bool(r['is_contradiction']),evidence=[i for i in r['aggregated_contradiction_indices'] if i!=last['turn_id']])
                if split=='eval' and count==128:break
            assert count==(64 if split=='fit' else 128)
    root.mkdir(parents=True,exist_ok=False)
    (root/'tasks.json').write_text(json.dumps(tasks));(root/'labels.json').write_text(json.dumps(gold))
    print('prepared',len(tasks),flush=True)


def infer(root, path):
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    start=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True).to('cuda:0').eval()
    assert model.config.id2label[0].upper()=='CONTRADICTION'
    (root/'model.json').write_text(json.dumps(dict(path=str(path),loadSeconds=time.perf_counter()-start,labels=model.config.id2label)))
    with (root/'results.jsonl').open('x') as out:
        for i,t in enumerate(json.loads((root/'tasks.json').read_text())):
            r=dict(id=t['id'],split=t['split'],candidate_count=len(t['candidates']),arms={})
            for arm in (['speaker_context','pairs'] if i%2==0 else ['pairs','speaker_context']):
                premises=['\n'.join(c['text'] for c in t['candidates'])] if arm=='speaker_context' else [c['text'] for c in t['candidates']]
                if not t['candidates']:premises=[]
                encs=[tok(p,t['target']['text'],truncation=False) for p in premises]
                lengths=[len(e['input_ids']) for e in encs]; valid=[j for j,n in enumerate(lengths) if n<=512]
                scores=[None]*len(encs); elapsed=0.; padded=0
                if valid:
                    batch=tok.pad([encs[j] for j in valid],padding=True,return_tensors='pt').to('cuda:0')
                    torch.cuda.synchronize(); start=time.perf_counter()
                    with torch.inference_mode():probs=model(**batch).logits.softmax(-1)[:,0].cpu().tolist()
                    torch.cuda.synchronize();elapsed=(time.perf_counter()-start)*1000
                    padded=int(batch['input_ids'].numel())
                    for j,p in zip(valid,probs):scores[j]=p
                r['arms'][arm]=dict(scores=scores,complete=bool(scores) and all(p is not None for p in scores),
                    inputTokens=sum(lengths[j] for j in valid),paddedTokens=padded,requestedTokens=sum(lengths),
                    forwardBatches=int(bool(valid)),elapsedMs=elapsed,overLimit=len(encs)-len(valid))
            out.write(json.dumps(r)+'\n');out.flush();print(json.dumps(dict(done=i+1,total=192)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','infer']);p.add_argument('root',type=Path)
    p.add_argument('--archive',type=Path);p.add_argument('--old',type=Path);p.add_argument('--model',type=Path);a=p.parse_args()
    if a.mode=='prepare':prepare(a.archive,a.old,a.root)
    else:infer(a.root,a.model)
