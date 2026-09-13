"""Bounded in-context correction memory; fixed candidate history, four controls."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from compare_views import SYSTEM


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def visible(row):
    return {'current_request': row['current_request'], 'history': [
        {'session_id': s['session_id'], 'messages': [m for m in s['messages'] if m['role']=='user']}
        for s in row['history']]}


def prepare(root, out):
    observations=rows(root/'adapted/observations.jsonl')
    labels={r['id']:r for r in rows(root/'adapted/labels.jsonl')}
    smoke=json.loads((root/'adapted/preparation-summary.json').read_text())['smoke_development_ids']
    used={r['group'] for r in observations if r['id'] in smoke}
    used|={r['group'] for r in rows(root/'events/audit-inputs.jsonl')}
    used|=set(json.loads((root/'views/selection.json').read_text())['groups'])
    used|=set(json.loads((root/'scope-audit/selection.json').read_text())['groups'])
    key=lambda s:hashlib.sha256(s.encode()).hexdigest()
    groups=sorted({r['group'] for r in observations if r['split']=='development'}-used,key=lambda g:key('cupid-feedback-learning-v1:'+g))[:4]
    tasks=sorted([r for r in observations if r['group'] in groups],key=lambda r:key('learning-task:'+r['id']))
    train=rows(root/'views/tasks.jsonl'); receipts={r['id']:r for r in rows(root/'views/run/view-receipts.jsonl')}
    reviews={r['id']:r for r in json.loads((root/'views/independent-review.json').read_text())}
    mapping=json.loads((root/'views/review-map.json').read_text())
    examples=[]
    for group in sorted({r['group'] for r in train}):
        r=min([r for r in train if r['group']==group],key=lambda r:key('cupid-feedback-example-v1:'+r['id']))
        arm=next(k for k,v in mapping[r['id']].items() if v=='users')
        examples.append({'id':r['id'],'observation':visible(r),'draft':receipts[r['id']]['arms']['users']['text'],
            'feedback':{'source':'controlled offline reference and independent assistant review, not natural user truth',
                'reference_requirement':labels[r['id']]['preference'],'review':reviews[r['id']][arm]}})
    assert len(tasks)==12 and not (set(groups)&{r['group'] for r in train})
    out.mkdir(parents=True,exist_ok=False)
    (out/'tasks.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in tasks))
    (out/'reference.jsonl').write_text(''.join(json.dumps(labels[r['id']],ensure_ascii=False)+'\n' for r in tasks))
    (out/'state.json').write_text(json.dumps({'version':1,'capacity':2,'examples':examples},ensure_ascii=False,indent=2)+'\n')
    (out/'selection.json').write_text(json.dumps({'groups':groups,'excluded_personas':len(used),'ids':[r['id'] for r in tasks],
        'training_ids':[e['id'] for e in examples],'scope':'new development personas, validation not used'},indent=2)+'\n')


def context(state, arm):
    if arm in {'request','frozen'}:return []
    if arm=='reviewed':
        return [{'observation':e['observation'],'reviewed_requirement_fragment':e['reviewed_evidence']}
                for e in state['reviewed_examples']]
    examples=[]
    for e in state['examples']:
        item={'observation':e['observation'],'prior_draft':e['draft']}
        if arm=='feedback':item['controlled_correction']=e['feedback']
        examples.append(item)
    return examples


def run(folder, model_path, *, reviewed=False, arms_override=None, shard_gpus=False, protocol=None):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    state=json.loads((folder/'state.json').read_text())
    assert state['version']==1 and len(state['examples'])<=state['capacity']==2
    tasks=rows(folder/'tasks.jsonl'); output=folder/'receipts.jsonl'
    if output.exists():raise FileExistsError(output)
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    t=time.perf_counter()
    placement={'device_map':'auto','max_memory':{i:'20GiB' for i in range(torch.cuda.device_count())}} if shard_gpus else {}
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa',**placement)
    if not shard_gpus:model=model.to('cuda:0')
    model.eval()
    device_map=getattr(model,'hf_device_map',{'':'cuda:0'})
    if shard_gpus and any(str(d) in {'cpu','disk'} for d in device_map.values()):
        raise RuntimeError('GPU-only baseline does not permit silent CPU/disk offload')
    input_device=model.get_input_embeddings().weight.device
    def synchronize():
        for i in range(torch.cuda.device_count() if shard_gpus else 1):torch.cuda.synchronize(i)
    synchronize(); load=time.perf_counter()-t
    arms=['frozen','unlabelled','feedback','reviewed'] if reviewed else ['request','frozen','unlabelled','feedback']
    if arms_override is not None:
        if not arms_override or not set(arms_override)<=set(arms):raise ValueError('Invalid diagnostic arms')
        arms=list(arms_override)
    if reviewed:
        assert len(state['reviewed_examples'])==2
        assert {e['id'] for e in state['reviewed_examples']}=={e['id'] for e in state['examples']}
    costs={a:{'input_tokens':0,'output_tokens':0,'generation_ms':0,'errors':0} for a in arms}
    with output.open('x') as stream,(folder/'inputs.jsonl').open('x') as inputs:
        for i,row in enumerate(tasks):
            result={}
            for arm in arms[i%len(arms):]+arms[:i%len(arms)]:
                observation=visible(row)
                if arm=='request':observation['history']=[]
                examples=context(state,arm)
                messages=[{'role':'system','content':SYSTEM}]
                if examples:
                    messages.append({'role':'user','content':'Previous development observations and drafts, with controlled corrections when available. Use them as experience for interpreting new history; do not copy their task-specific preferences.\n'+json.dumps(examples,ensure_ascii=False)})
                    messages.append({'role':'assistant','content':'I will infer preferences for the new request from its own evidence.'})
                messages.append({'role':'user','content':json.dumps(observation,ensure_ascii=False)})
                prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
                inputs.write(json.dumps({'id':row['id'],'arm':arm,'prompt':prompt},ensure_ascii=False)+'\n');inputs.flush()
                enc=tok(prompt,return_tensors='pt').to(input_device);n=enc['input_ids'].shape[1]
                receipt={'input_tokens':n,'output_tokens':0,'generation_ms':0,'text':'','error':None}
                if n>24000:receipt['error']='input_limit'
                else:
                    synchronize();start=time.perf_counter()
                    with torch.inference_mode():generated=model.generate(**enc,do_sample=False,max_new_tokens=256,pad_token_id=tok.eos_token_id)
                    synchronize();receipt['generation_ms']=(time.perf_counter()-start)*1000
                    answer=generated[0,n:];receipt['output_tokens']=len(answer);receipt['text']=tok.decode(answer,skip_special_tokens=True)
                    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
                    if len(answer)==256 and int(answer[-1]) not in (eos or []):receipt['error']='output_limit'
                for k in ['input_tokens','output_tokens','generation_ms']:costs[arm][k]+=receipt[k]
                costs[arm]['errors']+=int(receipt['error'] is not None);result[arm]=receipt
                print(row['id'],arm,n,receipt['output_tokens'],receipt['error'],flush=True)
            stream.write(json.dumps({'id':row['id'],'arms':result},ensure_ascii=False)+'\n');stream.flush()
    (folder/'cost.json').write_text(json.dumps({'protocol':protocol or ('cupid-reviewed-fragments-v1' if reviewed else 'cupid-feedback-learning-v1'),'examples':len(tasks),'load_seconds':load,'model_path':str(model_path),'device_map':device_map,'arms':costs},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--root',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',type=Path)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.out)
    else:run(a.out,a.model)
