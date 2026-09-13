import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]

def support(r):
    z=r['logits'];m=max(z);return math.exp(z[0]-m)/sum(math.exp(x-m) for x in z)

def main():
    p=argparse.ArgumentParser()
    for n in ['previous','run','out']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();original={r['id']:r for r in read(a.previous/'predictions.jsonl')};labels={r['id']:r for r in read(a.previous/'labels.jsonl')}
    reused=read(a.run/'reused.jsonl');fresh=read(a.run/'new-predictions.jsonl');alternatives={r['id']:r for r in reused+fresh};mapping=read(a.run/'mapping.jsonl')
    assert len(mapping)==len(original) and {r['id'] for r in mapping}==set(original)
    assert len(alternatives)==sum(len(r['candidates']) for r in mapping)
    counts={name:Counter() for name in ['baseline','with_comparison']};paired=Counter();rows=[]
    for m in mapping:
        r=original[m['id']];gold=not labels[m['id']]['positive']
        if r['error']:paired['unknown']+=1;continue
        base=max(range(3),key=lambda i:r['logits'][i])!=0
        valid=[alternatives[c['id']] for c in m['candidates'] if not alternatives[c['id']]['error']]
        better=any(support(v)>support(r) for v in valid);pred=base or better
        for name,value in [('baseline',base),('with_comparison',pred)]:counts[name]['tp' if value and gold else 'fp' if value else 'fn' if gold else 'tn']+=1
        paired['tie' if base==pred else 'win' if pred==gold else 'loss']+=1
        rows.append({'id':r['id'],'gold_review_proxy':gold,'baseline_review':base,'comparison_review':pred,'has_scored_alternative':bool(valid),'baseline_support':support(r),'max_alternative_support':max(map(support,valid)) if valid else None})
    result={'arms':{k:dict(v) for k,v in counts.items()},'paired':dict(paired),'reused_alternatives':len(reused),
        'new_forwards':sum(r['error'] is None for r in fresh),'new_tokens':sum(r['tokens'] for r in fresh if r['error'] is None),'new_seconds':sum(r['elapsed_ms'] for r in fresh)/1000,
        'operational_alternative_forwards':sum(r['error'] is None for r in alternatives.values()),
        'operational_alternative_tokens':sum(r['tokens'] for r in alternatives.values() if r['error'] is None),
        'operational_alternative_seconds':sum(r['elapsed_ms'] for r in alternatives.values())/1000}
    # Offline recoverability audit only; gold counterpart never drives generation/scoring.
    tasks={r['id']:r for r in read(a.previous/'tasks.jsonl')};pairs={};maps={r['id']:r for r in mapping}
    for l in labels.values():pairs.setdefault(l['pair'],{})[l['positive']]=l['id']
    norm=lambda s:' '.join(re.findall(r'\w+',s.casefold()))
    result['candidate_audit']={'pairs':len(pairs),'negative_with_candidate':0,'positive_question_recovered':0}
    for ids in pairs.values():
        q=tasks[ids[True]]['context'].rsplit('\nQuestion: ',1)[1];choices=maps[ids[False]]['candidates']
        result['candidate_audit']['negative_with_candidate']+=bool(choices)
        result['candidate_audit']['positive_question_recovered']+=any(norm(c['question'])==norm(q) for c in choices)
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(a.out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
