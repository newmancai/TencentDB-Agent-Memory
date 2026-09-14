"""Run ordered tasks against persistent per-project, per-arm state and worktrees."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import sys
import threading
import time

from agent_product_runner import ARMS, TASK_ID, atomic_write, workspace_state, summarize
from project_agent import Host


def validate(manifest):
    if manifest.get('schema') != 2 or not manifest.get('clusters'):
        raise ValueError('expected schema=2 and nonempty clusters')
    seen, workspaces, tasks = set(), set(), set()
    for cluster in manifest['clusters']:
        if not TASK_ID.fullmatch(cluster['id']) or cluster['id'] in seen:
            raise ValueError('invalid or duplicate cluster')
        seen.add(cluster['id']); revisions = set()
        if set(cluster['workspaces']) != set(ARMS):
            raise ValueError('prepare all four independent workspaces')
        for arm, value in cluster['workspaces'].items():
            path = Path(value).resolve()
            if path in workspaces or not (path / '.agent-benchmark-worktree').is_file():
                raise ValueError('unmarked or shared workspace')
            workspaces.add(path)
            state = workspace_state(path, include_untracked=True)
            if state['changes']:
                raise ValueError('sequence must start with a clean workspace')
            revisions.add(state['base_commit'])
        if revisions != {cluster['base_commit']}:
            raise ValueError('sequence arms need the same declared initial base')
        for step in cluster['steps']:
            if not TASK_ID.fullmatch(step['id']) or step['id'] in tasks:
                raise ValueError('invalid or duplicate task id')
            tasks.add(step['id'])
            if step['kind'] not in {'necessary_update','same_topic_control'}:
                raise ValueError('invalid task kind')
            if not step['prompt'].strip() or not step.get('paths') or not step.get('checker'):
                raise ValueError('task needs prompt, paths and checker')
            if not all(isinstance(x,str) and x.strip() for x in step.get('history',[])):
                raise ValueError('history must be raw user text')
    return manifest


def aggregate_calls(calls):
    usage = {}
    for call in calls:
        for key,value in (call.get('usage') or {}).items():
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                usage[key] = usage.get(key,0) + value
    return {'cli_runs':len(calls),'usage':usage or None,
            'wall_seconds':sum(c['wall_seconds'] for c in calls),
            'missing_usage_runs':sum(c.get('usage') is None for c in calls)}


def summary_for(rows, manifest):
    tasks=[{'id':s['id'],'kind':s['kind'],'cluster_id':c['id']}
           for c in manifest['clusters'] for s in c['steps']]
    summary=summarize(rows,{'tasks':tasks,'evaluation_mode':'pilot'})
    summary['context_source']='persistent_project_memory'
    summary['task_source']='authored maintenance scenarios on real repositories; not naturally occurring issues'
    summary['setup']={arm:aggregate_calls([call for r in rows if r['arm']==arm
                                          for event in r['history_results'] for call in event['calls']]) for arm in ARMS}
    summary['end_to_end_wall_seconds']={arm:sum(r['total_wall_seconds'] for r in rows if r['arm']==arm) for arm in ARMS}
    summary['per_cluster']={c['id']:{arm:{'tasks':len(rs),'pass':sum(r['checker_pass'] for r in rs)}
        for arm in ARMS for rs in [[r for r in rows if r['cluster_id']==c['id'] and r['arm']==arm]]}
        for c in manifest['clusters']}
    summary['blocked_backends']=manifest.get('blocked_backends',{})
    return summary


def run(manifest, output, backends, jobs=1):
    validate(manifest)
    output.mkdir(parents=True,exist_ok=False)
    atomic_write(output/'manifest.json',json.dumps(manifest,indent=2)+'\n')
    rows=[]; lock=threading.Lock()
    def cluster_run(cluster):
        for step_index,step in enumerate(cluster['steps']):
            arms=[a for a in ARMS if a.split('_',1)[0] in backends]
            if (step_index + cluster.get('arm_order_offset',0)) % 2: arms.reverse()
            for arm in arms:
                started=time.perf_counter(); backend=arm.split('_',1)[0]
                memory=arm.endswith('_memory'); workspace=Path(cluster['workspaces'][arm])
                evidence=output/cluster['id']/arm/step['id']; evidence.mkdir(parents=True)
                state=output/'states'/cluster['id']/arm
                args=argparse.Namespace(state=state,workspace=workspace,project=cluster['id'],owner=arm,
                    backend=backend,model=manifest.get(f'{backend}_model'),effort=manifest.get('effort','medium'),
                    timeout=manifest.get('timeout_seconds',180),instruction_mode='controlled',
                    mode='scoped' if memory else 'raw', paths=step['paths'],action='edit',max_bytes=12000,
                    check=json.dumps(step['checker']))
                host=Host(args); history=[]
                with (state/'writer.lock').open('a') as handle:
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    for i,text in enumerate(step.get('history',[])):
                        event=(host.remember(text,evidence/f'history-{i}',compile_constraints=True)
                               if memory else host.record(text,evidence/f'history-{i}'))
                        # Host.calls is cumulative; each event must account only for its own CLI runs.
                        event={**event,'calls':list(host.calls)}; history.append(event); host.calls=[]
                        atomic_write(evidence/'history.json',json.dumps(history,indent=2)+'\n')
                    before=workspace_state(workspace,include_untracked=True)
                    result=host.run(step['prompt'],evidence)
                atomic_write(evidence/'result.json',json.dumps(result,indent=2)+'\n')
                call=result['calls'][-1] if result['calls'] else {}
                checker_path=evidence/'checker.json'
                checker=json.loads(checker_path.read_text()) if checker_path.exists() else {}
                row={'task_id':step['id'],'kind':step['kind'],'cluster_id':cluster['id'],'arm':arm,'backend':backend,
                     'base_commit':before['base_commit'],'changes_before':before['changes'],
                     'changes_after':workspace_state(workspace,include_untracked=True)['changes'],
                     'status':call.get('status','host_error'),'agent_returncode':call.get('returncode'),
                     'checker_status':checker.get('status','not_run'),'checker_returncode':checker.get('returncode'),
                     'checker_pass':result['checker_pass'] is True and not result['error'],
                     'severe_regression':checker.get('returncode')==2,
                     'usage':call.get('usage'),'agent_wall_seconds':call.get('wall_seconds',0),
                     'checker_wall_seconds':checker.get('wall_seconds',0),'total_wall_seconds':time.perf_counter()-started,
                     'context_mode':result['context_mode'],'context_bytes':result['context_bytes'],
                     'memory_error':result['memory_error'],'history_results':history,'evidence':str(evidence)}
                with lock:
                    rows.append(row)
                    atomic_write(output/'receipts.jsonl',''.join(json.dumps(r)+'\n' for r in rows))
                    atomic_write(output/'summary.json',json.dumps(summary_for(rows,manifest),indent=2)+'\n')
                    print(json.dumps({key:row[key] for key in ['task_id','arm','checker_pass','severe_regression','context_mode']}),flush=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for _ in pool.map(cluster_run,manifest['clusters']): pass
    return summary_for(rows,manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--backends',nargs='+',choices=['codex','claude'],default=['codex','claude'])
    parser.add_argument('--jobs',type=int,choices=[1,2],default=1)
    args=parser.parse_args()
    run(json.loads(args.manifest.read_text()),args.output.resolve(),args.backends,args.jobs)
