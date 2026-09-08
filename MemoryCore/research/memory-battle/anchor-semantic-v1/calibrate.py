"""Fixed calibration rule for benchmark target agreement, never production confidence."""
import argparse
import json
from pathlib import Path

THRESHOLDS = (0., .5, .7, .8, .9, .95, 1.)


def select(report, arms=('direct', 'relations')):
    selected = {}
    for arm in arms:
        rows = [r for r in report if r['split'] == 'calibration' and r['arm'] == arm]
        if len(rows) != 1 or rows[0]['missing'] or rows[0]['total'] != 16:
            raise ValueError('require complete fixed calibration split')
        candidates = []
        for threshold in THRESHOLDS:
            accepted = [s for s in rows[0]['accepted_scores'] if s['score'] >= threshold]
            hits = sum(s['benchmark_target_agreement'] for s in accepted)
            candidates.append(dict(threshold=threshold, accepted=len(accepted), localized=hits,
                                   eligible=len(accepted) >= 5 and hits / len(accepted) >= .9))
        eligible = [r for r in candidates if r['eligible']]
        selected[arm] = dict(threshold=eligible[0]['threshold'] if eligible else None,
                             search=candidates)
    return dict(arms=selected, permits_semantic_invalidation=False,
                meaning='Calibrates public target-localization agreement only; model scores and dataset labels do not establish commercial validity.')


def score_heldout(report, policy):
    results = []
    for row in report:
        if row['split'] != 'heldout':
            continue
        if row['missing'] or row['total'] != 16:
            raise ValueError('require complete fixed heldout split')
        threshold = policy['arms'][row['arm']]['threshold']
        accepted = [s for s in row['accepted_scores'] if threshold is not None and s['score'] >= threshold]
        results.append(dict(arm=row['arm'], total=row['total'], threshold=threshold,
                            accepted=len(accepted), localized=sum(s['benchmark_target_agreement'] for s in accepted),
                            errors=row['errors'], input_tokens=row['input_tokens'],
                            output_tokens=row['output_tokens'], seconds=row['seconds']))
    return dict(results=results, permits_semantic_invalidation=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['select', 'heldout'])
    parser.add_argument('report', type=Path)
    parser.add_argument('policy', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--arms', nargs='+', default=['direct','relations'])
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if args.mode == 'select':
        # Refuse to choose thresholds after this output file has been created.
        with args.policy.open('x') as out:
            json.dump(select(report, args.arms), out, indent=2)
    else:
        if args.output is None:
            parser.error('--output required for heldout')
        args.output.write_text(json.dumps(score_heldout(report, json.loads(args.policy.read_text())), indent=2) + '\n')


if __name__ == '__main__':
    main()
