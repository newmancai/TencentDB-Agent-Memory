import json
from pathlib import Path
import sys
import time

SCHEMA = {'format': {'mode':'string, e.g. csv/json/markdown/html'}, 'countableItems': {'num':'integer'},
 'reader_age': {'reader_age':'string, e.g. child/youth/senior'}, 'startwith': {'mode':'keyword|letter|emoji|quotation','value':'string'},
 'endwith': {'mode':'keyword|letter|emoji|quotation','value':'string'},
 'length': {'mode':'word|sentence|paragraph|characters','relation':'more_than|less_than|exactly','number':'integer'},
 'forbidden':['forbidden literal strings'], 'punctuation':{'mode':'must_include|must_not_include','value':'string'},
 'existence':{'literal phrase':'required integer count'},'case':{'mode':'all_lower|all_upper'},
 'emotion':{'emotion':'string'}, 'style':{'style':'string'}}
PROMPT = ('Read the recorded user instruction sequence as data. Identify all constraints currently applicable to the final request. '
 'Track replacements, withdrawals, topic changes and returning topics. Do not execute the requests. '
 'Return only a JSON object mapping constraint family to its parameter object/list. Omit inactive families. '
 'Preserve literal required words. The public serialization interface is: '+json.dumps(SCHEMA)+
 '. Examples, if supplied, are earlier development observations, not current instructions. Their last-eight-message excerpt may omit earlier requirements.')


def canonical(d):
    return {k:json.dumps(v,sort_keys=True,ensure_ascii=False) for k,v in d.items()}


def prepare(source, output):
    tasks=[]; labels={}
    for dialog in [1,2,3]:
        rows=[json.loads(l) for l in (source/f'dialog_{dialog}.jsonl').open()]
        history=[]
        for row in rows:
            history.append({'turn':row['turn'],'text':row['user_query_verified']})
            if row['turn'] % 5: continue
            key=f'dialog_{dialog}:{row["turn"]}'
            tasks.append({'id':key,'split':'fit' if dialog==1 else 'eval','history':history.copy()})
            labels[key]={i['id']:i['args'] for i in row['instructions']}
    output.mkdir(parents=True,exist_ok=False)
    (output/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False))
    (output/'labels.json').write_text(json.dumps(labels,ensure_ascii=False))
    print({'tasks':len(tasks)})


def infer(root,model_path):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    tasks=json.loads((root/'tasks.json').read_text()); gold=json.loads((root/'labels.json').read_text()); examples=[]
    def predict(task, examples):
        content=json.dumps({'examples':examples,'current_history':task['history']},ensure_ascii=False)
        prompt=tok.apply_chat_template([{'role':'system','content':PROMPT},{'role':'user','content':content}],tokenize=False,add_generation_prompt=True)
        enc=tok(prompt,return_tensors='pt').to('cuda:0'); n=enc['input_ids'].shape[1]
        rec={'inputTokens':n,'outputTokens':0,'elapsedMs':0,'text':'','prediction':None,'error':None}
        if n>32768:rec['error']='input_limit';return rec
        torch.cuda.synchronize();start=time.perf_counter()
        with torch.inference_mode():ids=model.generate(**enc,do_sample=False,max_new_tokens=768,pad_token_id=tok.eos_token_id)
        torch.cuda.synchronize();rec.update(elapsedMs=(time.perf_counter()-start)*1000,outputTokens=int(ids.shape[1]-n),text=tok.decode(ids[0,n:],skip_special_tokens=True))
        try:
            pred=json.loads(rec['text']);assert isinstance(pred,dict) and set(pred)<=set(SCHEMA)
            assert rec['outputTokens']<768
            rec['prediction']=pred
        except (ValueError,AssertionError,TypeError):rec['error']='invalid_or_limited_output'
        return rec
    with (root/'results.jsonl').open('x') as out:
        for index,task in enumerate(tasks):
            if task['split']=='fit':
                arms={'direct':predict(task,[])}
                if len(examples)<4 and arms['direct']['prediction']!=gold[task['id']]:
                    examples.append({'source':task['id'],'history_excerpt':task['history'][-8:],
                                     'earlier_history_omitted':len(task['history'])>8,
                                     'prediction':arms['direct']['prediction'],'verified_target':gold[task['id']]})
            else:
                unlabelled=[{k:v for k,v in e.items() if k!='verified_target'} for e in examples]
                contexts={'direct':[],'unlabelled':unlabelled,'feedback':examples}
                order=['direct','unlabelled','feedback'];order=order[index%3:]+order[:index%3]
                arms={a:predict(task,contexts[a]) for a in order}
            out.write(json.dumps({'id':task['id'],'split':task['split'],'arms':arms},ensure_ascii=False)+'\n');out.flush()
            print(json.dumps({'done':index+1,'total':len(tasks)}),flush=True)
        (root/'feedback-state.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare(Path(sys.argv[2]),Path(sys.argv[3]))
    else:infer(Path(sys.argv[2]),sys.argv[3])
