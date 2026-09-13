"""Adapt a public MemoryBench corpus and one fixed behavior-policy log.

Gold is offline. Controlled feedback becomes visible only after its answer.
This adapter does not claim that the selected train/test corpora are independent.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import sys


def parse(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return ast.literal_eval(value)


def adapt_log(row, corpus_id, baseline):
    messages = parse(row['dialog_' + baseline])
    feedback = parse(row['implicit_feedback_' + baseline])
    assistant_positions = [i for i, m in enumerate(messages) if m['role'] == 'assistant']
    by_round = {}
    for item in feedback:
        index = item['round']
        assert isinstance(index, int) and 1 <= index <= len(assistant_positions)
        assert index not in by_round, 'duplicate feedback round'
        by_round[index] = item
    key = f'{corpus_id}:{row["test_idx"]}'
    events = []
    for round_index, position in enumerate(assistant_positions, 1):
        receipt = by_round.get(round_index)
        events.append({'id': f'{key}:r{round_index}', 'corpus_id': corpus_id,
                       'query_id': key, 'baseline': baseline,
                       'history': messages[:position + 1],
                       'feedback': receipt,
                       'feedback_status': 'observed_controlled' if receipt else 'not_observed'})
    return events


def main(source, output, corpus_id='Locomo-0', baseline='bm25_dialog'):
    import pyarrow.ipc as ipc
    corpus = parse(parse((source/'corpus.jsonl').read_text())['text'])['conversation']
    memory = []
    sessions = sorted((k for k in corpus if k.startswith('session_') and isinstance(corpus[k], list)),
                      key=lambda k: int(k.split('_')[1]))
    for session in sessions:
        for message in corpus[session]:
            memory.append({'id': message['dia_id'], 'speaker': message['speaker'],
                           'text': message['text'], 'session': session,
                           'session_date': corpus.get(session + '_date_time')})
    lookup = {m['id']: m for m in memory}
    assert len(lookup) == len(memory), 'duplicate source memory ID'
    events, queries, gold, evidence = [], [], [], []
    for split in ['train', 'test']:
        rows = ipc.open_stream(source/f'{split}.arrow').read_all().to_pylist()
        for row in rows:
            key = f'{corpus_id}:{row["test_idx"]}'
            info = parse(row['info'])
            queries.append({'id': key, 'corpus_id': corpus_id, 'split': split,
                            'query': row['origin_question']})
            gold.append({'id': key, 'split': split, 'gold': info})
            for reference in info.get('evidence', []):
                original = lookup.get(reference['dia_id'])
                matched = bool(original and original['text'] == reference['text']
                               and original['speaker'] == reference['speaker'])
                evidence.append({'query_id': key, 'memory_id': reference['dia_id'],
                                 'exact_source_match': matched})
            # Evaluation logs/feedback are never exported into the learning stream.
            if split == 'train':
                events.extend(adapt_log(row, corpus_id, baseline))
    train_ids = {q['id'] for q in queries if q['split'] == 'train'}
    test_ids = {q['id'] for q in queries if q['split'] == 'test'}
    assert not train_ids & test_ids
    summary = {'corpus_id': corpus_id, 'baseline': baseline, 'memory_messages': len(memory),
               'sessions': len(sessions), 'queries': dict(Counter(q['split'] for q in queries)),
               'learning_answer_events': len(events),
               'feedback_status': dict(Counter(e['feedback_status'] for e in events)),
               'actions': dict(Counter(e['feedback']['implicit_action'] for e in events if e['feedback'])),
               'evidence_references': len(evidence),
               'evidence_exact_source_match': sum(e['exact_source_match'] for e in evidence),
               'shared_train_test_corpus': True, 'feedback_origin': 'controlled benchmark feedback',
               'original_log_collection_cost': None}
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in [('memory', memory), ('queries', queries), ('learning-events', events),
                       ('offline-gold', gold), ('offline-evidence-audit', evidence)]:
        (output/f'{name}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
