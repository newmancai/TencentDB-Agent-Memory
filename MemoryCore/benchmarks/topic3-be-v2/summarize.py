"""Offline scorer. Exact match is deliberately not a semantic verifier."""
import argparse
import json
import re
from pathlib import Path


def exact(a, b):
    norm = lambda s: re.sub(r'\s+', ' ', str(s).strip().lower().rstrip('.'))
    return norm(a) == norm(b)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    a = p.parse_args(); r = a.root
    gold = json.loads((r / 'adapted/gold.json').read_text())
    tasks = {t['id']: t for t in json.loads((r / 'adapted/tasks.json').read_text())}
    native = json.loads((r / 'native/results.json').read_text())
    reach = []
    for t in native:
        support = set(gold[t['id']]['support'])
        messages = {m['id']: m for m in tasks[t['id']]['messages']}
        opportunities = []
        for source in sorted(support):
            prior = {s for s in support if messages[s]['order'] < messages[source]['order']
                     and messages[s]['session'] != messages[source]['session']}
            if not prior:
                continue
            candidates = {c['parent'] for e in t['events'] if e['parent'] == source for c in e['candidates']}
            opportunities.append(dict(source=source, targets=len(prior), hit=len(prior & candidates)))
        reach.append(dict(id=t['id'], events=len(t['events']), l0=t['l0'],
                          nonempty=sum(bool(e['candidates']) for e in t['events']), opportunities=opportunities,
                          support_turns=len(support), final_support_hit=len(support & {s['parent'] for s in t['native']}),
                          retrieval_ms=sum(e['elapsedMs'] for e in t['events']), native_wall_ms=t['elapsedMs']))
    summary = dict(protocol='topic3-incoming-qualification-v2', scope='development reuse, no policy learning', reach=reach, experiments={})
    for name in ['model', 'order']:
        path = r / name / 'results.jsonl'
        if not path.exists():
            continue
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        arms = {}
        for row in rows:
            for arm, receipt in row['readers'].items():
                aggregate = arms.setdefault(arm, dict(tasks=0, strict_exact=0, errors=0, inputTokens=0, outputTokens=0, serviceMs=0))
                aggregate['tasks'] += 1
                aggregate['strict_exact'] += int(not receipt.get('error') and exact(receipt.get('text'), gold[row['id']]['answer']))
                aggregate['errors'] += int(bool(receipt.get('error')))
                for key in ['inputTokens', 'outputTokens']:
                    aggregate[key] += receipt.get(key, 0)
                aggregate['serviceMs'] += receipt.get('elapsedMs', 0)
        summary['experiments'][name] = arms
    raw = [json.loads(x)['result'] for x in (r / 'model-calls.jsonl').read_text().splitlines()]
    summary['actual_model'] = dict(calls=len(raw), inputTokens=sum(x['inputTokens'] for x in raw),
                                   outputTokens=sum(x['outputTokens'] for x in raw), serviceMs=sum(x['elapsedMs'] for x in raw))
    (r / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != 'reach'}, indent=2))


if __name__ == '__main__':
    main()
