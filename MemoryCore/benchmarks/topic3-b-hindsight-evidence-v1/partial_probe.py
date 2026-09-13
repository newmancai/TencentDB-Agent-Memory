"""Compare ordinary review with answer-span feedback; research only."""
import argparse
import hashlib
import json
from pathlib import Path
import time

COMMON='''Check the candidate answer to the question using only the provided messages. The question and candidate answer are targets to verify, not evidence. Respect the named people, objects, events and temporal qualifiers. Unmentioned is not false. Do not use outside facts. Return JSON only.'''
ORDINARY=COMMON+''' Return {"relation":"supported|insufficient|conflict","evidence_ids":["ID"],"explanation":"brief reason"}. You may identify any useful partial support and missing links in the explanation. Cite at most 3 provided IDs.'''
PARTS=COMMON+''' Return {"supported_parts":[{"answer_span":"exact nonempty substring of candidate answer","evidence_ids":["ID"]}],"missing_relations":["brief missing link"]}. Include at most 3 supported parts and 3 missing links. Include a part only if the evidence establishes its association with the person/object/event asked about; support for the question's background alone is not answer support. Preserve an empty supported_parts list when no answer component is established. A part is not approval of the whole answer. Cite at most 3 provided IDs per part.'''


def prepare(source,receipts,previous,out):
    used={r['task_id'] for r in json.loads(previous.read_text())};rs=[json.loads(r) for r in receipts.read_text().splitlines()];tasks=[]
    for src in json.loads(source.read_text()):
        pool=[r for r in rs if r['source']==src['sample_id'] and r['id'] not in used and set(r['arms']['qa']['ids'])-set(r['arms']['q']['ids'])]
        chosen=sorted(pool,key=lambda r:hashlib.sha256(('partial-feedback-v1:'+r['id']).encode()).hexdigest())[:2]
        for r in chosen:
            mid=next(i for i in r['arms']['qa']['ids'] if i not in r['arms']['q']['ids']);q=src['qa'][int(r['id'].rsplit(':',1)[1])]
            for key,session in src['conversation'].items():
                if not isinstance(session,list):continue
                for i,m in enumerate(session):
                    if m['dia_id']==mid:
                        evidence=[{k:n[k] for k in ('speaker','dia_id','text')} for n in session[max(0,i-1):i+2]]
                        tasks.append({'id':r['id'],'question':q['question'],'candidate':str(q['answer']),'focus_id':mid,'timestamp':src['conversation'].get(key+'_date_time'),'evidence':evidence})
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(r)+'\n' for r in tasks));print({'tasks':len(tasks),'overlap_previous_audit':len({r['id'] for r in tasks}&used)})


def parse(text,t,arm):
    try:r=json.loads(text)
    except ValueError:return None
    allowed={m['dia_id'] for m in t['evidence']}
    def ids(v):return isinstance(v,list) and len(v)<=3 and all(isinstance(x,str) and x in allowed for x in v) and len(v)==len(set(v))
    if not isinstance(r,dict):return None
    if arm=='ordinary':
        return r if set(r)=={'relation','evidence_ids','explanation'} and r['relation'] in ('supported','insufficient','conflict') and ids(r['evidence_ids']) and isinstance(r['explanation'],str) else None
    if set(r)!={'supported_parts','missing_relations'} or not isinstance(r['supported_parts'],list) or len(r['supported_parts'])>3 or not isinstance(r['missing_relations'],list) or len(r['missing_relations'])>3 or any(not isinstance(x,str) for x in r['missing_relations']):return None
    for part in r['supported_parts']:
        if not isinstance(part,dict) or set(part)!={'answer_span','evidence_ids'}:return None
        span=part['answer_span']
        if not isinstance(span,str) or not span.strip() or span not in t['candidate'] or not ids(part['evidence_ids']) or not part['evidence_ids']:return None
    return r


def infer(tasks,path,out):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True);model=AutoModelForCausalLM.from_pretrained(path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    with out.open('x') as stream:
        for i,t in enumerate(json.loads(x) for x in tasks.read_text().splitlines()):
            arms={}
            for arm in (['ordinary','parts'] if i%2==0 else ['parts','ordinary']):
                prompt=tok.apply_chat_template([{'role':'system','content':ORDINARY if arm=='ordinary' else PARTS},{'role':'user','content':json.dumps({k:v for k,v in t.items() if k!='id'})}],tokenize=False,add_generation_prompt=True)
                enc=tok(prompt,return_tensors='pt').to('cuda:0');n=enc['input_ids'].shape[1];r={'input_tokens':n,'output_tokens':0,'elapsed_ms':0,'text':'','parsed':None,'error':None}
                if n>4096:r['error']='input_limit'
                else:
                    torch.cuda.synchronize();start=time.perf_counter()
                    with torch.inference_mode():y=model.generate(**enc,do_sample=False,max_new_tokens=256,pad_token_id=tok.eos_token_id)
                    torch.cuda.synchronize();r['elapsed_ms']=(time.perf_counter()-start)*1000;r['output_tokens']=int(y.shape[1]-n);r['text']=tok.decode(y[0,n:],skip_special_tokens=True)
                    r['parsed']=parse(r['text'],t,arm) if r['output_tokens']<256 else None
                    if r['parsed'] is None:r['error']='output_limit' if r['output_tokens']>=256 else 'invalid_output'
                arms[arm]=r
            stream.write(json.dumps({'id':t['id'],'arms':arms})+'\n');stream.flush();print(i+1,t['id'],{k:v['error'] for k,v in arms.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','infer'])
    for name in ('source','receipts','previous','tasks','model','out'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':prepare(a.source,a.receipts,a.previous,a.out)
    else:infer(a.tasks,a.model,a.out)
