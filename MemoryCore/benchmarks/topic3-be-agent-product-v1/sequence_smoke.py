"""Three paired sequential coding tasks; SYNTHETIC integration smoke, never product quality evidence."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'scripts/project-agent/project_agent.py'


def invoke(root, state, workspace, command):
    argv = [sys.executable, str(HOST), '--state', str(state), '--workspace', str(workspace),
            '--project', 'sequence-smoke', '--model', 'gpt-5.6-sol', '--timeout', '180',
            '--instruction-mode', 'controlled', *command]
    result = subprocess.run(argv, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); root = args.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    seed = root / 'seed'; seed.mkdir()
    for package in ('api', 'workers'):
        folder = seed / 'src' / package; folder.mkdir(parents=True)
        (folder / '__init__.py').write_text('')
        (folder / 'settings.py').write_text('"""Retry settings. Overrides may be zero."""\n\ndef effective_attempts(override=None):\n    raise NotImplementedError\n')
    (seed / 'src/api/budget.py').write_text('"""Retry budgeting."""\n\ndef total_attempts(requests, override=None):\n    raise NotImplementedError\n')
    (seed / 'README.md').write_text('Python retry configuration example. Source code is in src.\n')
    for command in (['git','init','-q'], ['git','add','.'],
                    ['git','-c','user.name=Integration Test','-c','user.email=test@example.invalid','commit','-qm','fixture base']):
        subprocess.run(command,cwd=seed,check=True,capture_output=True)
    seed_state = root / 'seed-state'
    setup = []
    for message in (
        'Within src/api, future edit tasks must use 2 as the default retry attempts. Within src/workers, future edit tasks must use 5 as the default retry attempts.',
        'Correction for future edit tasks within src/api: use 0 as the default retry attempts, replacing the previous default of 2. This change does not apply to src/workers.',
    ):
        setup.append(invoke(root,seed_state,seed,['remember',message,'--compile']))
    (root / 'setup.json').write_text(json.dumps(setup,indent=2)+'\n')
    # The checker values are outside the coding workspaces and are never serialized into agent prompts.
    assertions = [
        'from api.settings import effective_attempts as api\nassert api() == 0\nassert api(0) == 0\nassert api(7) == 7\n',
        'from workers.settings import effective_attempts as worker\nassert worker() == 5\nassert worker(0) == 0\nassert worker(9) == 9\n',
        'from api.budget import total_attempts\nassert total_attempts(3) == 0\nassert total_attempts(3, 4) == 12\nassert total_attempts(3, 0) == 0\n',
    ]
    tasks = [
        ('api-update', 'src/api/settings.py', 'Implement effective_attempts in src/api/settings.py using the project default from prior user instructions. Preserve explicit overrides, including zero. Do not edit the worker module.'),
        ('worker-control', 'src/workers/settings.py', 'Implement effective_attempts in src/workers/settings.py using the project default from prior user instructions. Preserve explicit overrides, including zero. Preserve the completed API behavior.'),
        ('api-followup', 'src/api/budget.py', 'Implement total_attempts in src/api/budget.py. It should return requests multiplied by effective_attempts for the API. Reuse the existing API settings function and preserve both settings modules.'),
    ]
    for i in range(3):
        (root / f'checker-{i}.py').write_text('import sys\nsys.path.insert(0,"src")\n'+''.join(assertions[:i+1]))
    states, workspaces = {}, {}
    for mode in ('raw','scoped'):
        states[mode] = root / f'{mode}-state'; workspaces[mode] = root / f'{mode}-workspace'
        shutil.copytree(seed_state,states[mode]); shutil.copytree(seed,workspaces[mode])
    results = []
    for i,(task,path,prompt) in enumerate(tasks):
        for mode in (('raw','scoped') if i % 2 == 0 else ('scoped','raw')):
            result = invoke(root,states[mode],workspaces[mode],['run',prompt,'--paths',path,'--mode',mode,
                              '--check',json.dumps([sys.executable,str(root / f'checker-{i}.py')])])
            results.append(dict(task=task,mode=mode,**result))
            (root / 'results.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps({'task':task,'mode':mode,'checker_pass':result['checker_pass'],
                              'context_mode':result['context_mode'],'context_bytes':result['context_bytes']}),flush=True)
    summary = {'scope':'synthetic sequence integration smoke, not a product benchmark', 'product_pass':False,
               'setup':{'extraction_calls':sum(len(x['calls']) for x in setup),
                        'accepted_constraints':[len(x['accepted']['accepted']) for x in setup],
                        'errors':[x['extraction_error'] for x in setup]},
               'paired':{},'results':results}
    for mode in ('raw','scoped'):
        rows=[r for r in results if r['mode']==mode]
        summary['paired'][mode]={'checker_pass':sum(r['checker_pass'] is True for r in rows),
                                 'tasks':len(rows),'context_bytes':sum(r['context_bytes'] for r in rows)}
    (root / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))


if __name__ == '__main__':
    main()
