"""One synthetic coding task at native memory capacity, then interrupted-check recovery.

Uses one real Codex call. The seeded constraints are authored fixtures, not learned rules.
This tests integration and recovery, not product quality or incremental memory benefit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', default='gpt-5.6-sol')
    args = parser.parse_args()
    root = args.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    workspace = root / 'workspace'; workspace.mkdir()
    state = root / 'state'; state.mkdir()
    source = workspace / 'src/exporter'; source.mkdir(parents=True)
    (source / '__init__.py').write_text('')
    (source / 'options.py').write_text('def resolve_format(override=None):\n    raise NotImplementedError\n')
    (source / 'render.py').write_text('def render(rows, columns, format=None):\n    raise NotImplementedError\n')
    (workspace / '.gitignore').write_text('__pycache__/\n')
    for command in (['git', 'init', '-q'], ['git', 'add', '.'],
                    ['git', '-c', 'user.name=Integration Test', '-c', 'user.email=test@example.invalid',
                     'commit', '-qm', 'recovery fixture']):
        subprocess.run(command, cwd=workspace, check=True, capture_output=True)
    # Use the real ProjectMemory API to reach its default capacity. No direct DB mutation.
    seed = '''
import { VectorStore } from STORE_MODULE;
import { ProjectMemory } from MEMORY_MODULE;
const store = new VectorStore(DATABASE, 0); store.init();
try {
  const memory = new ProjectMemory(store, 'local-user', 'recovery-smoke');
  const scope = {paths:['src/exporter'], actions:['edit']};
  const old = 'For future edits within src/exporter: the default export format is jsonl. Export bytes must use UTF-8 without a BOM, preserve non-ASCII characters, and use LF line endings with a terminal newline on every nonempty export. Explicit format overrides take priority.';
  const first = await memory.ingest({id:'original-policy',order:1,role:'user',text:old},
    [{key:'export-policy',quote:old,scope}]);
  const update = 'For future edits within src/exporter: the default format is now csv instead of jsonl. All other export rules are unchanged.';
  await memory.ingest({id:'policy-update',order:2,role:'user',text:update},
    [{key:'export-policy',quote:update,scope,supersedes:first.accepted[0].id}]);
  for(let order=3;order<=128;order++)
    await memory.ingest({id:`receipt-${order}`,order,role:'tool',text:'Earlier task completed; checker passed.'},[]);
  const snapshot = await memory.snapshot();
  console.log(JSON.stringify({revision:snapshot.revision,observations:snapshot.observations.length}));
} finally {store.close();}
'''
    for key, value in {
        'STORE_MODULE': (ROOT/'src/core/store/sqlite.ts').as_uri(),
        'MEMORY_MODULE': (ROOT/'src/core/memory-feedback/project-memory.ts').as_uri(),
        'DATABASE': str(state/'memory.sqlite'),
    }.items():
        seed = seed.replace(key, json.dumps(value))
    seeded = subprocess.run(['node','--import','tsx','--input-type=module','-'], input=seed,
                            text=True, capture_output=True, cwd=ROOT)
    (root/'seed.json').write_text(seeded.stdout)
    (root/'seed.stderr.txt').write_text(seeded.stderr)
    if seeded.returncode:
        raise RuntimeError(seeded.stderr)
    checker = root/'checker.py'
    checker.write_text('''import json
from pathlib import Path
import sys
import time
root=Path(__file__).resolve().parent
(root/'checker-entered').write_text('ready')
print('checker ready',flush=True)
while not (root/'allow-check').exists(): time.sleep(0.05)
sys.path.insert(0,'src')
from exporter.options import resolve_format
from exporter.render import render
assert resolve_format() == 'csv'
assert resolve_format('jsonl') == 'jsonl'
rows=[{'name':'上海','count':0}]
assert render(rows,['name','count']) == 'name,count\\n上海,0\\n'.encode('utf-8')
payload=render(rows,['name','count'],format='jsonl')
assert isinstance(payload,bytes) and payload.endswith(b'\\n') and b'\\r' not in payload
assert '上海'.encode('utf-8') in payload and json.loads(payload) == rows[0]
assert render([],['name','count'],format='jsonl') == b''
print('all export checks passed')
''')
    base = ['node',str(ROOT/'bin/memory-agent.mjs'),'--workspace',str(workspace),
            '--state',str(state),'--project','recovery-smoke','--model',args.model,
            '--timeout','180','--instruction-mode','controlled']
    task = ('Implement resolve_format and render in src/exporter across both modules. '
            'Use the earlier user export policy. render returns bytes; accept a list of row dicts '
            'and ordered column names. For CSV include a header in that column order and use CSV escaping; '
            'for jsonl emit one complete row object per line, and empty rows produce empty jsonl bytes. '
            'Honor the optional explicit format argument. Reuse resolve_format in render.')
    with (root/'run.stdout.json').open('w') as out, (root/'run.stderr.txt').open('w') as err:
        process = subprocess.Popen(base+['run',task,'--paths','src/exporter','--check',
                        json.dumps([sys.executable,str(checker)])], stdout=out, stderr=err, cwd=ROOT)
        try:
            deadline=time.monotonic()+210
            while not (root/'checker-entered').exists():
                if process.poll() is not None:
                    raise RuntimeError('coding stage ended before checker; inspect run logs')
                if time.monotonic() > deadline:
                    raise TimeoutError('checker was not reached')
                time.sleep(0.1)
            process.send_signal(signal.SIGINT)
            process.wait(timeout=15)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT); process.wait(timeout=15)
    first=json.loads((root/'run.stdout.json').read_text())
    assert process.returncode == 130 and first['checker_status'] == 'cancelled', first
    assert first['context_mode'] == 'scoped' and not first['task_persisted'], first
    assert 'capacity' in first['memory_error'], first
    context=json.loads((state/'runs'/first['run_id']/'context.json').read_text())
    active=json.loads(context['text'])['scoped_constraints']
    assert len(active)==1 and len(active[0]['predecessorEvidence'])==1
    (root/'allow-check').write_text('ready')
    retry=subprocess.run(base+['check-run',first['run_id']],cwd=ROOT,text=True,capture_output=True)
    (root/'retry.stdout.json').write_text(retry.stdout)
    (root/'retry.stderr.txt').write_text(retry.stderr)
    second=json.loads(retry.stdout)
    history=subprocess.run(base+['history'],cwd=ROOT,text=True,capture_output=True,check=True)
    snapshot=json.loads(history.stdout)
    summary=dict(scope='synthetic integration, not product quality or memory benefit',
                 model_requested=args.model, coding_calls=len(first['calls']),
                 recovery_calls=len(second['calls']), interrupted_exit=process.returncode,
                 recovery_exit=retry.returncode, recovery_checker_pass=second.get('checker_pass'),
                 context_mode=first['context_mode'], context_bytes=first['context_bytes'],
                 memory_error=first['memory_error'], task_persisted=first['task_persisted'],
                 observations_after=len(snapshot['observations']), revision_after=snapshot['revision'],
                 calls=first['calls'], original_run=first['run_id'], recovery_run=second['run_id'])
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    assert retry.returncode==0 and second['checker_pass'] and second['calls']==[]
    assert len(first['calls'])==1 and len(snapshot['observations'])==128 and snapshot['revision']==128


if __name__ == '__main__':
    main()
