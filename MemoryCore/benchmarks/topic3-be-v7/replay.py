"""Recompute recorded metrics from public data; does not run native/model paths."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='pinned longmemeval_s_cleaned.json')
    parser.add_argument('output', type=Path, help='fresh replay directory')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    bundle = here / 'results/replay'
    args.output.mkdir(parents=True, exist_ok=False)

    def run(script, *values):
        subprocess.run([sys.executable, str(script), *map(str, values)], check=True)

    prior = args.output / 'prior'
    run(here.parent / 'topic3-be-v6/prepare.py', args.data,
        bundle / 'exclude.json', prior / 'adapted')
    # prepare.py only needs source/target fields here. This reconstructs example
    # inputs, not proof of new native writes; original native receipts stay local.
    (prior / 'native').mkdir()
    shutil.copyfile(prior / 'adapted/pairs.json', prior / 'native/records.json')
    for label in ('source-review.json', 'source-review-second.json'):
        shutil.copyfile(bundle / 'prior' / label, prior / label)
        shutil.copyfile(bundle / 'current' / label, args.output / label)
    run(here / 'prepare.py', args.data, bundle / 'exclude.json',
        prior, args.output / 'adapted')
    for arm in ('model', 'order'):
        shutil.copytree(bundle / arm, args.output / arm)
    shutil.copyfile(bundle / 'logits.jsonl', args.output / 'logits.jsonl')
    for script, result in (('score.py', 'summary.json'),
                           ('score_order.py', 'order-summary.json'),
                           ('score_rank.py', 'rank-summary.json')):
        run(here / script, args.output)
        if json.loads((args.output / result).read_text()) != json.loads((here / 'results' / result).read_text()):
            raise ValueError(f'Replay differs: {result}')
    print('PASS: all three recorded summaries reproduced; no new model/native run')


if __name__ == '__main__':
    main()
