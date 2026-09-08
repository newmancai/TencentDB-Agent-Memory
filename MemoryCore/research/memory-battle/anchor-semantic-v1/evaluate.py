"""Offline localization scoring; benchmark agreement is not semantic truth."""
import argparse
import json
from pathlib import Path


def evaluate(candidates, gold, outputs):
    indexed = {}
    for row in outputs:
        key = (row['id'], row['arm'])
        if key in indexed:
            raise ValueError(f'duplicate output: {key}')
        indexed[key] = row
    results = []
    arms = sorted({row['arm'] for row in outputs}) or ['direct', 'relations']
    for split in ('development', 'calibration', 'heldout'):
        cases = [c for c in candidates if c['split'] == split]
        for arm in arms:
            counts = dict(total=len(cases), completed=0, missing=0, errors=0,
                          truncated=0,
                          retrievable=0, accepted=0, localized=0, off_target=0,
                          abstained=0, input_tokens=0, output_tokens=0, seconds=0.)
            scores = []
            for case in cases:
                target_ids = set(gold[case['id']]['target_record_ids'])
                counts['retrievable'] += bool(target_ids & {c['id'] for c in case['candidates']})
                row = indexed.get((case['id'], arm))
                if row is None:
                    counts['missing'] += 1
                    continue
                counts['completed'] += 1
                counts['truncated'] += row.get('finish_reason') == 'length'
                for field in ('input_tokens', 'output_tokens', 'seconds'):
                    counts[field] += row[field]
                if row['error'] or not isinstance(row.get('parsed'), dict):
                    counts['errors'] += 1
                    continue
                selected = row['parsed'].get('target_id')
                if selected is None:
                    counts['abstained'] += 1
                    continue
                counts['accepted'] += 1
                hit = selected in target_ids
                counts['localized' if hit else 'off_target'] += 1
                scores.append(dict(id=case['id'], score=row['parsed']['confidence'],
                                   benchmark_target_agreement=hit))
            results.append(dict(split=split, arm=arm, **counts,
                                accepted_scores=scores,
                                semantic_false_invalidation_rate=None,
                                limitation='Positive-only, non-exhaustive target labels; off-target is not necessarily semantically false. Missing outputs are not abstentions.'))
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument('candidates', type=Path)
    p.add_argument('gold', type=Path)
    p.add_argument('outputs', type=Path)
    p.add_argument('report', type=Path)
    args = p.parse_args()
    outputs = [json.loads(line) for line in args.outputs.read_text().splitlines() if line.strip()]
    report = evaluate(json.loads(args.candidates.read_text()), json.loads(args.gold.read_text()), outputs)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps([{k: v for k, v in r.items() if k not in ('accepted_scores', 'limitation')} for r in report], indent=2))


if __name__ == '__main__':
    main()
