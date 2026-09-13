import importlib.util
import json
from pathlib import Path
import sys
from collections import Counter

PREVIOUS = Path(__file__).resolve().parent.parent/'topic3-b-applicability-v1/run.py'
spec = importlib.util.spec_from_file_location('applicability_engine', PREVIOUS)
ENGINE = importlib.util.module_from_spec(spec);spec.loader.exec_module(ENGINE)
PROMPT = (
    'Update the applicable rule set after the current user message. '
    'This is a local diagnostic: the two user messages concern the same topic, '
    'and previous_active is the correct applicable set just before the current message. '
    'Candidates include historical alternatives; preserve previous rules unless the current message '
    'replaces or withdraws them, and apply new requirements expressed in that message. '
    'Only track the supplied candidate rule families. Do not execute the user requests. '
    'Output only ACTIVE: followed by a JSON list of applicable candidate ID strings. '
    'Use ACTIVE: unknown if indeterminate. Do not output explanations.'
)
FAMILIES = {'startwith','endwith','format','countableItems','length','existence','forbidden','case','punctuation'}


def signature(rule):
    return json.dumps([rule['id'],rule['args']],sort_keys=True,ensure_ascii=False)


def allowed(rule):
    return rule['id'] in FAMILIES and not (rule['id']=='length' and rule['args'].get('mode')=='sentence')


def prepare(source,out):
    rows=list(map(json.loads,(source/'dialog_1.jsonl').open()))
    pool={};tasks=[];labels={};previous=None
    for row in rows:
        for r in row['instructions']:
            if allowed(r) and signature(r) not in pool:
                pool[signature(r)]={'id':f'R{len(pool)+1}','family':r['id'],'args':r['args'],
                                    'first_observed_turn':row['turn']}
        if previous is not None and previous['active_topic']==row['active_topic']:
            old=sorted(pool[signature(r)]['id'] for r in previous['instructions'] if allowed(r))
            new=sorted(pool[signature(r)]['id'] for r in row['instructions'] if allowed(r))
            key=f'dialog_1:{row["turn"]}'
            tasks.append({'id':key,'history':[{'turn':x['turn'],'user':x['user_query_verified']} for x in [previous,row]],
                          'previous_active':old,'candidates':list(pool.values())})
            labels[key]={'active':new,'changed':new!=old}
        previous=row
    out.mkdir(parents=True,exist_ok=False)
    (out/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False))
    (out/'labels.json').write_text(json.dumps(labels,indent=2))
    print({'transitions':len(tasks),'changed':sum(v['changed'] for v in labels.values())})


def score(root):
    tasks={t['id']:t for t in json.loads((root/'tasks.json').read_text())}
    gold=json.loads((root/'labels.json').read_text());rows=list(map(json.loads,(root/'predictions.jsonl').open()))
    assert len(rows)==len(gold) and {r['id'] for r in rows}==set(gold)
    arms={a:Counter() for a in ['model','keep','new_family']};strata={};cost=Counter()
    for r in rows:
        t=tasks[r['id']];target=set(gold[r['id']]['active']);old=set(t['previous_active'])
        fresh=[c for c in t['candidates'] if c['first_observed_turn']==t['history'][-1]['turn']]
        families={c['family'] for c in fresh}
        inferred=(old-{c['id'] for c in t['candidates'] if c['family'] in families})|{c['id'] for c in fresh}
        for arm,pred in [('model',None if r['prediction'] is None else set(r['prediction'])),('keep',old),('new_family',inferred)]:
            ok=pred is not None and pred==target;selected=pred or set()
            arms[arm].update(n=1,exact=int(ok),unknown=int(pred is None),tp=len(selected&target),fp=len(selected-target),fn=len(target-selected))
            group=strata.setdefault('changed' if gold[r['id']]['changed'] else 'unchanged',{})
            group.setdefault(arm,Counter()).update(n=1,exact=int(ok))
        for k in ['inputTokens','outputTokens','elapsedMs']:cost[k]+=r[k]
    result={'arms':{a:dict(v) for a,v in arms.items()},'strata':strata,'cost':dict(cost)}
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare(Path(sys.argv[2]),Path(sys.argv[3]))
    elif sys.argv[1]=='infer':
        ENGINE.PROMPT=PROMPT;ENGINE.infer(Path(sys.argv[2]),sys.argv[3])
    else:score(Path(sys.argv[2]))
