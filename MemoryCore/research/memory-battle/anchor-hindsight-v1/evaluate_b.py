"""Offline source-level scoring of native candidates under the unchanged host B judge.

No native fact ID is treated as a raw-source ID. Source overlap does not prove
that a derived assertion is the gold stale assertion, or warrant invalidation.
"""
import argparse
import collections
import json
from pathlib import Path


def source_agreement(candidate, targets, incomplete_ids):
    sources = set(candidate.get('sourceDocumentIds', []))
    if sources & targets:
        return 'source_overlap'
    if not sources or candidate['id'] in incomplete_ids:
        return 'unknown_provenance'
    return 'no_source_overlap'


def evaluate(runtime, gold, directory, predictions, split, arms):
    indexed = {}
    for row in predictions:
        key = (row['id'], row['arm'])
        if key in indexed:
            raise ValueError(f'duplicate output: {key}')
        indexed[key] = row
    counts = {arm: collections.Counter() for arm in arms}
    details = []
    for case in runtime:
        if case['split'] != split:
            continue
        candidate_path = directory / (case['id'] + '.b-candidates.json')
        final_path = directory / (case['id'] + '.json')
        final = json.loads(final_path.read_text()) if final_path.exists() else {}
        candidates = None
        if candidate_path.exists():
            entries = json.loads(candidate_path.read_text())
            if len(entries) != 1 or entries[0]['id'] != case['id']:
                raise ValueError('candidate identity mismatch')
            candidates = {r['id']: r for r in entries[0]['candidates']}
            if len(candidates) != len(entries[0]['candidates']):
                raise ValueError('duplicate native candidate identity')
        incomplete = {r['record_id'] for r in final.get('b_provenance_issues', [])}
        targets = set(gold[case['id']]['target_record_ids'])
        for arm, c in counts.items():
            c['total'] += 1
            c['native_full_success'] += final.get('status') == 'success'
            if final.get('status') != 'success':
                c['native_incomplete'] += 1
            # B recall is saved only after history consolidation passes. A later
            # reflect failure must not erase an otherwise valid B observation.
            if not isinstance(final.get('b_recall'), dict):
                c['history_recall_missing'] += 1
                continue
            if candidates is None:
                c['candidate_missing'] += 1
                continue
            c['candidate_source_retrievable'] += any(
                source_agreement(r, targets, incomplete) == 'source_overlap'
                for r in candidates.values())
            row = indexed.get((case['id'], arm))
            if row is None:
                c['prediction_missing'] += 1
                continue
            c['completed'] += 1
            for field in ('input_tokens', 'output_tokens', 'seconds'):
                c[field] += row[field]
            if row.get('error') or not isinstance(row.get('parsed'), dict):
                c['errors'] += 1
                continue
            selected = row['parsed'].get('target_id')
            if selected is None:
                c['abstained'] += 1
                continue
            if selected not in candidates:
                c['errors'] += 1
                details.append(dict(id=case['id'], arm=arm, error='selected unknown native ID'))
                continue
            c['accepted'] += 1
            verdict = source_agreement(candidates[selected], targets, incomplete)
            c[verdict] += 1
            details.append(dict(id=case['id'], arm=arm, native_id=selected,
                                source_agreement=verdict))
    return dict(split=split, arms={k: dict(v) for k, v in counts.items()}, details=details,
                limitation='Same host B judge on native derived candidates. Source overlap is coarser than raw-record target agreement and is not stale-assertion truth. Unknown provenance is not a negative. Native lifecycle costs must be reported separately from these host-judge costs. Missing/incomplete native cases remain in the full split denominator.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('runtime', type=Path)
    p.add_argument('gold', type=Path)
    p.add_argument('directory', type=Path)
    p.add_argument('predictions', type=Path)
    p.add_argument('report', type=Path)
    p.add_argument('--split', required=True, choices=['development', 'calibration', 'heldout'])
    p.add_argument('--arms', nargs='+', default=['direct', 'nli', 'assertion_nli'])
    a = p.parse_args()
    result = evaluate(json.loads(a.runtime.read_text()), json.loads(a.gold.read_text()),
                      a.directory, [json.loads(s) for s in a.predictions.read_text().splitlines() if s.strip()],
                      a.split, a.arms)
    a.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['arms'], indent=2))


if __name__ == '__main__':
    main()
