"""Audit observable follow-up windows, without inventing confirmation labels."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


def audit(path, output):
    groups = defaultdict(list)
    # Iterate physical JSONL lines: public text contains Unicode line separators.
    with path.open() as handle:
        for line in handle:
            event = json.loads(line)
            groups[event['group']].append(event)
    windows = []
    counts = defaultdict(Counter)
    for group, events in groups.items():
        source = events[0]['source']
        counts[source]['conversations'] += 1
        counts[source]['events'] += len(events)
        for index, event in enumerate(events):
            counts[source]['terminal_without_observed_followup'] += index == len(events) - 1
            if index == len(events) - 1:
                continue
            later = events[index + 1]
            previous = event['history'] + [event['incoming']]
            assert later['history'][:len(previous)] == previous, 'non-prefix source'
            assert later['incoming']['id'] not in {m['id'] for m in previous}
            counts[source]['has_later_user_observation'] += 1
            counts[source]['history_at_least_20_messages'] += len(event['history']) >= 20
            windows.append({'group': group, 'source': source,
                            'proposal_event': event['id'], 'later_event': later['id'],
                            'proposal_message': event['incoming']['id'],
                            'later_message': later['incoming']['id'],
                            'history_messages': len(event['history']),
                            'intervening_messages': len(later['history']) - len(previous),
                            'confirmation': None})
    sample = [events[:3] for events in groups.values() if len(events) >= 3][:12]
    report = {'scope': 'observation opportunities, not confirmed feedback',
              'conversations': len(groups), 'windows': len(windows),
              'by_source': {s: dict(c) for s, c in counts.items()},
              'review_selection': [{'group': e[0]['group'],
                                    'proposal_event': e[1]['id'], 'later_event': e[2]['id']}
                                   for e in sample],
              'selection_rule': 'first 12 source-order groups with >=3 events; second to third event',
              'warning': 'Later observations are not truth labels. No memory attribution gold.'}
    output.mkdir(parents=True, exist_ok=True)
    (output/'opportunities.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/'windows.jsonl').write_text(''.join(json.dumps(w)+'\n' for w in windows))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    audit(Path(sys.argv[1]), Path(sys.argv[2]))
