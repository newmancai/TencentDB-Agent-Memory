"""RAGTruth adapter: original context/answer separate from human feedback spans."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def read(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    source_rows = read(args.source/'source_info.jsonl')
    answers = read(args.source/'response.jsonl')
    sources = {r['source_id']: r for r in source_rows}
    assert len(sources) == len(source_rows)
    assert len({r['id'] for r in answers}) == len(answers)
    counts, types, flags = Counter(), Counter(), Counter()
    groups = {'train': set(), 'test': set()}
    fingerprints = {'train': set(), 'test': set()}
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out/'observations.jsonl').open('w') as observations, \
         (args.out/'labels.jsonl').open('w') as labels, \
         (args.out/'excluded.jsonl').open('w') as excluded:
        for row in answers:
            source = sources[row['source_id']]
            assert row['split'] in groups
            for span in row['labels']:
                assert 0 <= span['start'] < span['end'] <= len(row['response'])
                assert row['response'][span['start']:span['end']] == span['text']
                types[span['label_type']] += 1
                for flag in ['implicit_true', 'due_to_null']:
                    flags[flag+':'+str(span.get(flag, 'missing'))] += 1
            counts[row['split']+'/'+row['quality']] += 1
            if row['quality'] != 'good':
                excluded.write(json.dumps({'id': row['id'], 'group': row['source_id'],
                    'split': row['split'], 'quality': row['quality'],
                    'status': 'excluded_by_official_quality_protocol'})+'\n')
                continue
            groups[row['split']].add(row['source_id'])
            canonical = json.dumps(source['source_info'], ensure_ascii=False, sort_keys=True)
            fingerprints[row['split']].add(hashlib.sha256(re.sub(r'\s+', ' ', canonical).encode()).hexdigest())
            observations.write(json.dumps({'id': row['id'], 'group': row['source_id'],
                'split': row['split'], 'context': source['prompt'], 'answer': row['response'],
                'source_kind': source['task_type']}, ensure_ascii=False)+'\n')
            labels.write(json.dumps({'id': row['id'], 'spans': row['labels'],
                'authority': 'human_source_grounding_annotation',
                'is_factual_truth_label': False, 'is_memory_fault_label': False},
                ensure_ascii=False)+'\n')
    summary = {'source_revision': 'c103204b9ce28d6bbad859304bf30de72b8ed8fe',
        'source_records': len(sources), 'answer_records': len(answers),
        'task_counts': dict(Counter(r['task_type'] for r in source_rows)),
        'split_quality': dict(counts), 'all_span_types': dict(types), 'all_span_flags': dict(flags),
        'all_spans_exact': sum(types.values()),
        'eligible_answers': sum(n for k,n in counts.items() if k.endswith('/good')),
        'excluded_answers': sum(n for k,n in counts.items() if not k.endswith('/good')),
        'eligible_source_groups': {k: len(v) for k,v in groups.items()},
        'source_id_overlap': len(groups['train'] & groups['test']),
        'normalized_exact_source_content_overlap': len(fingerprints['train'] & fingerprints['test']),
        'scope': 'Standalone RAG source-grounding supervision, not long-dialogue memory attribution or downstream improvement.'}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':main()
