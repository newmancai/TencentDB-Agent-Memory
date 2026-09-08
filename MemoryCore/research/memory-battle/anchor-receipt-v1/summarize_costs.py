"""Observed costs from existing replay and native artifacts; no rerun or E2E claims."""
import argparse
import json
import math
from pathlib import Path


def summary(values):
    values = sorted(values)
    if not values:
        return dict(count=0, total=0, p50=None, p95=None)
    return dict(count=len(values), total=sum(values),
                p50=values[math.ceil(.5 * len(values)) - 1],
                p95=values[math.ceil(.95 * len(values)) - 1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('data', type=Path)
    args = parser.parse_args()
    result = dict(splits={})
    for split in ('development', 'calibration', 'external_domain'):
        rows = [json.loads(line) for line in (args.data / (split + '-feedback.jsonl')).read_text().splitlines()]
        metrics = json.loads((args.data / (split + '-metrics.json')).read_text())
        b_ms = summary([row['b_ms'] for row in rows])
        correct = metrics['counts']['correct']
        result['splits'][split] = dict(B_per_task_ms=b_ms,
            B_ms_per_verified_correct_feedback=b_ms['total'] / correct if correct else None,
            verified_correct_feedback=correct, unverified_feedback=metrics['counts']['unverified'])
    native = [json.loads(line) for line in (args.data / 'external-native-fallback.jsonl').read_text().splitlines()]
    storage = []
    for row in native:
        root = Path(row['root'])
        # Missing actual stores must fail instead of appearing to have zero cost.
        if not (root / 'base.sqlite').is_file() or not (root / 'memory.sqlite').is_file():
            raise FileNotFoundError(root)
        storage.append(dict(task=row['task'], base_sqlite=(root / 'base.sqlite').stat().st_size,
            evolved_sqlite=(root / 'memory.sqlite').stat().st_size,
            head_json=(root / 'view.json').stat().st_size,
            total_artifacts=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())))
    result['native'] = dict(tasks=len(native), verification_per_task_ms=summary([r['ms'] for r in native]),
        storage_bytes={k: summary([r[k] for r in storage]) for k in ('base_sqlite', 'evolved_sqlite', 'head_json', 'total_artifacts')})
    result['limitations'] = [
        'Nearest-rank p50/p95. B CPU time excludes oracle, native I/O and downstream model calls.',
        'Native duration includes construction, reopen, read checks and injected faults; it is verification cost, not online request latency.',
        'Storage is actual on-disk artifacts of the separate base/evolved experiment; no claim of production deployment overhead.',
        'No causal task-failure attribution measured; receipt consistency only. Unknown oracle fields remain unknown.'
    ]
    (args.data / 'cost-metrics.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
