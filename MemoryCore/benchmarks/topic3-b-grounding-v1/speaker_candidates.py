"""Visible-speaker substitutions are hypotheses, never asserted corrections."""
import argparse
import json
import re
from pathlib import Path


def candidates(question, messages):
    names=sorted({m['speaker'] for m in messages if isinstance(m.get('speaker'),str) and m['speaker'].strip()})
    if len(names)>8:return [],'speaker_capacity'
    result=[];seen={question}
    for source in names:
        pattern=re.compile(r'(?<!\w)'+re.escape(source)+r'(?!\w)',re.IGNORECASE)
        if not pattern.search(question):continue
        for target in names:
            if target==source:continue
            altered=pattern.sub(lambda _:target,question)
            if altered in seen:continue
            seen.add(altered);result.append({'from':source,'to':target,'question':altered})
            if len(result)>8:return [],'candidate_capacity'
    return result,None


def prepare(run,out):
    tasks=[json.loads(x) for x in (run/'tasks.jsonl').read_text().splitlines()];generated=[];mapping=[]
    for task in tasks:
        context,question=task['context'].rsplit('\nQuestion: ',1)
        messages=[json.loads(x) for x in context.splitlines() if x.startswith('{')]
        choices,error=candidates(question,messages)
        for i,c in enumerate(choices):generated.append({'id':task['id']+'::swap'+str(i),'context':context+'\nQuestion: '+c['question'],'answer':task['answer']})
        mapping.append({'id':task['id'],'error':error,'candidates':[{**c,'id':task['id']+'::swap'+str(i)} for i,c in enumerate(choices)]})
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('tasks',generated),('mapping',mapping)]: (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.run,a.out)
