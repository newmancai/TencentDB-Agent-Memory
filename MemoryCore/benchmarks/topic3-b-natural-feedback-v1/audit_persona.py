"""Check local public PersonaMem source contracts, without running an agent."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--v1-manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with (args.source / 'persona_v1_questions_32k.csv').open() as stream:
        v1 = list(csv.DictReader(stream))
    path = args.source / 'persona_benchmark.csv'
    with path.open() as stream:
        v2 = list(csv.DictReader(stream))
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual_hash == '95f2a8a324aab7baf2af937feae12731369e2abf7cad5ab3e170594cb25a3e52'
    manifest = json.loads(args.v1_manifest.read_text())
    old_owners = {t['owner'].removeprefix('persona-') for t in manifest['tasks']}
    # The prior protocol separately documents personas 0 and 1 as used prototypes.
    prototype_owners = {'0', '1'}
    v1_owners = {r['persona_id'] for r in v1}
    preferences = Counter((r['persona_id'], r['preference']) for r in v2)
    result = {
        'v1': {'rows': len(v1), 'owners': sorted(v1_owners),
               'manifest_owners': sorted(old_owners), 'manifest_tasks': len(manifest['tasks']),
               'previous_prototype_owners_per_protocol': sorted(prototype_owners),
               'owners_remaining_after_known_exposure': sorted(v1_owners-old_owners-prototype_owners)},
        'v2': {'rows': len(v2), 'owners': len({r['persona_id'] for r in v2}),
               'revision': 'ed956dea41521fc4499acbc63f966e0fd3c053ba',
               'sha256': actual_hash, 'fields': list(v2[0]),
               'history_32k_links': len({r['chat_history_32k_link'] for r in v2}),
               'who_updated': dict(Counter(r['who']+'/'+r['updated'] for r in v2)),
               'exact_persona_preference_groups': len(preferences),
               'rows_in_singleton_exact_preference_groups': sum(n for n in preferences.values() if n == 1),
               'rows_in_repeated_exact_preference_groups': sum(n for n in preferences.values() if n > 1),
               'duplicate_persona_query_rows': sum(n-1 for n in Counter((r['persona_id'], r['user_query']) for r in v2).values()),
               'feedback_action_named_columns': [k for k in v2[0] if any(t in k for t in ['feedback','action','propensity','response'])],
               'freshness': 'Not certified; this audit does not exhaust all historical source exposure.',
               'causal_contract': 'QA labels and source snippets exist; no executed memory action, action probability, or response-specific follow-up in benchmark rows.'},
        'scope': 'Metadata and source-contract audit only. Exact preference strings are not semantic preference identities. No runtime/gold relabeling.'}
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
