"""Next development cohort; same v2 adapter, no new gold construction."""
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('v2_adapter', Path(__file__).resolve().parent.parent / 'topic3-be-v2/prepare.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
source, exclude, output = map(Path, sys.argv[1:])
rows = json.loads(source.read_text())
excluded = set(json.loads(exclude.read_text()))
selected = []
for kind in ('knowledge-update', 'single-session-user'):
    eligible = [r for r in rows if r['question_type'] == kind and r['question_id'] not in excluded]
    selected += sorted(eligible, key=lambda r: hashlib.sha256(('topic3-be-v2:' + r['question_id']).encode()).hexdigest())[8:16]
runtime, gold = [], {}
for row in selected:
    task, label, pair = adapter.convert(row)
    runtime.append(dict(id=task['id'], pair=pair))
    gold[task['id']] = label
output.mkdir(parents=True, exist_ok=False)
(output / 'pairs.json').write_text(json.dumps(runtime, ensure_ascii=False))
(output / 'offline.json').write_text(json.dumps(gold, ensure_ascii=False))
print(json.dumps(dict(tasks=len(runtime), pairs=sum(r['pair'] is not None for r in runtime))))
