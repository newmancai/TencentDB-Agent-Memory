"""Independent pretrained NLI baseline; same candidates, no gold or retraining."""
import argparse
import json
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('candidates',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--split',required=True)
    p.add_argument('--witnesses',type=Path)
    p.add_argument('--device',default='cuda:3')
    a=p.parse_args()
    import torch
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    tokenizer=AutoTokenizer.from_pretrained(a.model,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(a.model,local_files_only=True).to(a.device).eval()
    # Official model card order; do not infer label IDs from arbitrary score order.
    labels=['contradiction','entailment','neutral']
    if [model.config.id2label[i] for i in range(3)]!=labels:raise ValueError('unexpected NLI label mapping')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    completed={json.loads(s)['id'] for s in a.output.read_text().splitlines()} if a.output.exists() else set()
    witnesses={r['id']:r for r in map(json.loads,a.witnesses.read_text().splitlines()) if r['arm']=='assertions'} if a.witnesses else {}
    for case in json.loads(a.candidates.read_text()):
        if case['split']!=a.split or case['id'] in completed:continue
        started=time.perf_counter();scores=[];tokens=0;error=None;selected=None;upstream={}
        try:
            candidates=case['candidates'];premise=case['observation']['content']
            if a.witnesses:
                from infer import align_quote
                upstream=witnesses[case['id']];proposal=upstream.get('parsed')
                if not isinstance(proposal,dict):raise ValueError('upstream output missing or unparsable')
                target=proposal.get('target_id')
                if target is None:
                    candidates=[]
                else:
                    old=next(c['content'] for c in candidates if c['id']==target)
                    if proposal.get('signal_type')!='fact_transition':raise ValueError('not a fact proposal')
                    if not align_quote(proposal.get('old_assertion'),old,True) or not align_quote(proposal.get('new_assertion'),premise,True):raise ValueError('unaligned assertion witness')
                    premise=proposal['new_assertion']
                    candidates=[dict(id=target,content=proposal['old_assertion'])]
            encoded=tokenizer([premise]*len(candidates),
                [r['content'] for r in candidates],padding=True,truncation=False,return_tensors='pt') if candidates else None
            if encoded is None:
                parsed=dict(target_id=None,confidence=0,reason='upstream abstained')
            else:
                tokens=int(encoded['attention_mask'].sum())
                if encoded['input_ids'].shape[1]>512:raise ValueError('NLI pair exceeds 512 tokens; no truncation')
                with torch.inference_mode():probs=model(**encoded.to(a.device)).logits.softmax(-1).cpu().tolist()
                if str(a.device).startswith('cuda'):torch.cuda.synchronize(a.device)
                scores=[dict(id=r['id'],**dict(zip(labels,values))) for r,values in zip(candidates,probs)]
                winner=max(scores,key=lambda r:r['contradiction'])
                if winner['contradiction']>max(winner['entailment'],winner['neutral']):selected=winner['id']
                parsed=dict(target_id=selected,confidence=winner['contradiction'],reason='pretrained three-way NLI argmax')
        except Exception as e:
            error=f'{type(e).__name__}: {e}';parsed=None
        row=dict(id=case['id'],split=case['split'],arm='assertion_nli' if a.witnesses else 'nli',parsed=parsed,error=error,
            scores=scores,input_tokens=tokens+upstream.get('input_tokens',0),output_tokens=upstream.get('output_tokens',0),seconds=time.perf_counter()-started+upstream.get('seconds',0),
            nli_input_tokens=tokens,nli_seconds=time.perf_counter()-started,
            timing='local_pair_classifier',model=str(a.model))
        with a.output.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({'id':row['id'],'parsed':parsed,'error':error}),flush=True)


if __name__=='__main__':main()
