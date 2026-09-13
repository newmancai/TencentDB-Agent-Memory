"""CUPID adapter: dialogue-only observations, separate privileged annotations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--parquet', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    rows = pq.read_table(args.parquet).to_pylist()
    personas = sorted({r['persona_id'] for r in rows}, key=lambda x: digest('cupid-b-v1:' + x))
    development = set(personas[:len(personas)//2])
    seen, observations, annotations = set(), [], []
    session_owners = {}
    roles = Counter()
    for row in rows:
        group = row['persona_id']
        identifier = digest(group + ':' + row['instance_type'])[:24]
        if identifier in seen:
            raise ValueError('Duplicate persona/type')
        seen.add(identifier)
        history = []
        for session_index, session in enumerate(row['prior_interactions']):
            dialogue = []
            for turn, message in enumerate(session['dialogue']):
                role, content = message['role'], message['content']
                if role not in {'user', 'assistant'} or not isinstance(content, str):
                    raise ValueError('Unknown role/content')
                roles[role] += 1
                dialogue.append({'role': role, 'content': content,
                                 'evidence_id': f's{session_index+1}:t{turn+1}'})
            history.append({'session_id': f's{session_index+1}', 'messages': dialogue})
            fingerprint = digest(json.dumps([(m['role'], m['content']) for m in dialogue], ensure_ascii=False))
            session_owners.setdefault(fingerprint, set()).add(group)
        observations.append({'id': identifier, 'source': 'cupid', 'group': group,
            'split': 'development' if group in development else 'validation',
            'current_request': row['current_request'], 'history': history})
        annotations.append({'id': identifier, 'instance_type': row['instance_type'],
            'current_context_factor': row['current_context_factor'],
            'preference': row['current_contextual_preference'], 'checklist': row['current_checklist'],
            'prior_annotations': [{'session_id': f's{i+1}', 'context_factor': s['context_factor'],
                                   'preference': s['contextual_preference']}
                                  for i, s in enumerate(row['prior_interactions'])]})
    cross = sum(bool(owners & development) and bool(owners-development) for owners in session_owners.values())
    if cross:
        raise ValueError('Identical sessions cross persona split; revise grouping before evaluation')
    args.out.mkdir(parents=True, exist_ok=True)
    for name, records in [('observations', observations), ('labels', annotations)]:
        with (args.out / f'{name}.jsonl').open('w') as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False)+'\n')
    lengths = [sum(len(s['messages']) for s in o['history']) for o in observations]
    summary = {'protocol': 'cupid-contextual-feedback-v1-preparation',
        'dataset_revision': 'f6e5fdae9b31f2b400d6ceb281a6a6760cc00309',
        'source_commit': 'a8560cab293ae98be4fe260689d58bddf96b51ef',
        'parquet_sha256': hashlib.sha256(args.parquet.read_bytes()).hexdigest(),
        'rows': len(rows), 'personas': len(personas), 'instance_types': dict(Counter(r['instance_type'] for r in rows)),
        'split_events': dict(Counter(o['split'] for o in observations)),
        'development_personas': len(development), 'validation_personas': len(personas)-len(development),
        'sessions_per_observation': dict(Counter(len(o['history']) for o in observations)),
        'message_count_min_max': [min(lengths),max(lengths)], 'message_roles_including_variant_reuse': dict(roles),
        'unique_session_contents': len(session_owners), 'cross_split_identical_sessions': cross,
        'smoke_development_ids': [o['id'] for o in observations if o['group'] in set(personas[:2])],
        'scope': 'Official public simulated/human-curated data; no model run, B quality or learning result.'}
    (args.out / 'preparation-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
