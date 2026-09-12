"""First frozen-model error per negative class, LMSYS only; no resampling."""
import argparse
import json
from pathlib import Path

from run import LABELS, read, visible_input


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--scores', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    labels = {r['id']: r.get('label') for r in read(args.data / 'labels.jsonl')}
    receipts = {r['id']: r for r in read(args.scores)}
    selected, blind, full = set(), [], []
    for observation in read(args.data / 'observations.jsonl'):
        label = labels[observation['id']]
        if observation['source'] != 'lmsys' or label not in LABELS[:4] or label in selected:
            continue
        receipt = receipts[observation['id']]
        assert receipt['error'] is None
        prediction = LABELS[max(range(len(LABELS)), key=lambda i: receipt['logits'][i])]
        if prediction == label:
            continue
        selected.add(label)
        case = 'case' + str(len(blind) + 1)
        blind.append({'case': case, 'visible': visible_input(observation)[0]})
        full.append({'case': case, 'observation': observation,
                     'gold': label, 'prediction': prediction})
    assert len(blind) == 4
    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in [('blind', blind), ('full', full)]:
        (args.out / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print('Four development errors prepared; original conversation text is local only.')


if __name__ == '__main__':
    main()
