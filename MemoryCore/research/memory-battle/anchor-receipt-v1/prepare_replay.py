"""Replay public TRAIN actions in the unmodified upstream environment.

The runtime file contains observable results only. Independent state snapshots
go to a separate offline oracle file, never the feedback detector.
"""
import argparse,copy,importlib,json,sys,subprocess,collections
from pathlib import Path

REV='5644b1838d96bc4483da29642d058ecaa6f80f7f'
DOMAINS={'customer_support':('CSEnvironmentData','CustomerSupportEnvironment','development'),
         'travel':('EnvironmentData','TravelEnvironment','calibration'),
         'shopping_assistant':('SAEnvironmentData','ShoppingAssistantEnvironment','external_domain')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.upstream,text=True).strip()!=REV:raise ValueError('upstream revision mismatch')
    sys.path.insert(0,str(a.upstream));a.output.mkdir(parents=True,exist_ok=True)
    counts=collections.Counter()
    with (a.output/'runtime.jsonl').open('w') as runtime,(a.output/'oracle.jsonl').open('w') as oracle:
        for domain,(schema_name,env_name,split) in DOMAINS.items():
            schema=getattr(importlib.import_module(f'state_bench.domains.{domain}.schemas'),schema_name)
            env_class=getattr(importlib.import_module(f'state_bench.domains.{domain}.environment'),env_name)
            for file in sorted((a.upstream/'datasets/train_task_trajectories'/domain).glob('*.json')):
                task=json.loads((a.upstream/f'state_bench/domains/{domain}/tasks/{file.name}').read_text())
                env=schema.from_dict(json.loads((a.upstream/task['task_env_path']).read_text()))
                environment=env_class(env,task['now']);tid=f'{domain}/{file.stem}';events=[];truth=[]
                for turn,message in enumerate(json.loads(file.read_text())['conversation']):
                    for index,call in enumerate(message.get('tool_calls') or []):
                        eid=f'{tid}/{turn}/{index}';before=copy.deepcopy(environment.get_full_snapshot())
                        try:result=environment.tool_handlers[call['name']](copy.deepcopy(call.get('arguments') or {}))
                        except Exception as e:result={'error':f'{type(e).__name__}: {e}'};counts['execution_exception']+=1
                        after=copy.deepcopy(environment.get_full_snapshot())
                        events.append(dict(id=eid,scope=tid,order=len(events),tool=call['name'],arguments=call.get('arguments') or {},result=result))
                        truth.append(dict(id=eid,before=before,after=after,original_result_matches=result==call.get('result')))
                        counts['events']+=1;counts['original_result_mismatch']+=result!=call.get('result')
                runtime.write(json.dumps(dict(id=tid,domain=domain,split=split,events=events),ensure_ascii=False)+'\n')
                oracle.write(json.dumps(dict(id=tid,events=truth),ensure_ascii=False)+'\n');counts['tasks']+=1
    (a.output/'manifest.json').write_text(json.dumps(dict(revision=REV,counts=dict(counts),splits={k:v[2] for k,v in DOMAINS.items()},
        protocol='Fixed public action replay, not a new agent E2E run or official leaderboard result. New tool responses are from executable upstream code; original mismatches are disclosed.'),indent=2)+'\n')
    print(dict(counts))

if __name__=='__main__':main()
