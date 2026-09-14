"""Compare no history, full raw history, and raw BM25 in persistent repository sequences."""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / 'scripts/project-agent'))
sys.path.insert(0, str(HERE.parents[1] / 'topic3-be-agent-product-v1'))
from agent_product_runner import atomic_write, workspace_state
from project_agent import Host

ARMS = ('no_history', 'raw_full', 'raw_top8')
MODES = {'no_history': 'off', 'raw_full': 'raw', 'raw_top8': 'raw_topk'}
TASK_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
COMMIT_ID = re.compile(r'^[0-9a-f]{40}$')


def arms_for(manifest):
    arms = tuple(manifest.get('arms', ARMS))
    if (not arms or len(set(arms)) != len(arms) or not set(arms) <= set(MODES)
            or not {'no_history', 'raw_full'} <= set(arms)):
        raise ValueError('arms must uniquely include no_history and raw_full')
    return arms


def quantile(values, q):
    if not values:
        return None
    values = sorted(values); position = (len(values) - 1) * q
    low, high = int(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def validate(manifest):
    if manifest.get('schema') != 1 or manifest.get('evaluation_mode') not in {'development', 'heldout'}:
        raise ValueError('expected schema=1 and development or heldout evaluation_mode')
    if not isinstance(manifest.get('clusters'), list) or not manifest['clusters']:
        raise ValueError('clusters must be nonempty')
    if not isinstance(manifest.get('enforce_change_paths', False), bool):
        raise ValueError('enforce_change_paths must be boolean')
    arms = arms_for(manifest)
    clusters, tasks, workspaces = set(), set(), set()
    for cluster in manifest['clusters']:
        if not TASK_ID.fullmatch(cluster.get('id', '')) or cluster['id'] in clusters:
            raise ValueError('invalid or duplicate cluster id')
        clusters.add(cluster['id'])
        source = cluster.get('source')
        if (not isinstance(source, dict) or source.get('kind') not in {'github_issue', 'github_pr', 'repository_failure'}
                or not isinstance(source.get('url'), str) or not source['url'].startswith('https://')):
            raise ValueError('each cluster needs a reviewable real source')
        if set(cluster.get('workspaces', {})) != set(arms):
            raise ValueError('each cluster needs one independent workspace per arm')
        forbidden = cluster.get('forbidden_commits')
        if (not isinstance(forbidden, list) or not forbidden
                or not all(isinstance(value, str) and COMMIT_ID.fullmatch(value) for value in forbidden)):
            raise ValueError('each cluster needs known post-base commits to exclude')
        revisions = set()
        for arm in arms:
            path = Path(cluster['workspaces'][arm]).resolve()
            if path in workspaces or not (path / '.agent-benchmark-worktree').is_file():
                raise ValueError('unmarked or shared workspace')
            workspaces.add(path)
            state = workspace_state(path, include_untracked=True)
            if state['changes']:
                raise ValueError('sequence must start from a clean marked workspace')
            revisions.add(state['base_commit'])
            for revision in forbidden:
                visible = subprocess.run(
                    ['git', 'cat-file', '-e', f'{revision}^{{commit}}'], cwd=path,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if visible.returncode == 0:
                    raise ValueError(f'future commit is visible in {cluster["id"]}/{arm}')
        if revisions != {cluster.get('base_commit')}:
            raise ValueError('all arms must use the declared base commit')
        if not isinstance(cluster.get('steps'), list) or len(cluster['steps']) < 2:
            raise ValueError('a sequence needs at least two steps')
        kinds = set()
        for step in cluster['steps']:
            if not TASK_ID.fullmatch(step.get('id', '')) or step['id'] in tasks:
                raise ValueError('invalid or duplicate task id')
            tasks.add(step['id']); kinds.add(step.get('kind'))
            if (step.get('kind') not in {'necessary_update', 'same_topic_control'}
                    or not isinstance(step.get('prompt'), str) or not step['prompt'].strip()
                    or not isinstance(step.get('paths'), list) or not step['paths']
                    or not isinstance(step.get('checker'), list) or not step['checker']
                    or not all(isinstance(value, str) and value for value in step['checker'])
                    or not all(isinstance(value, str) and value.strip() for value in step.get('history', []))):
                raise ValueError('invalid step')
        if kinds != {'necessary_update', 'same_topic_control'}:
            raise ValueError('each cluster needs an update and a same-topic control')
    return manifest


def numeric_usage(rows):
    totals = Counter(); missing = 0
    for row in rows:
        usage = row.get('usage')
        if not usage:
            missing += 1; continue
        for key, value in usage.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += value
    return dict(totals) or None, missing


def quality_comparable(row):
    """A failed or unaudited execution is missing quality data, not a checker loss."""
    return bool(row and row.get('status') == 'completed'
                and row.get('checker_status') == 'completed'
                and row.get('filesystem_isolated') is True
                and not row.get('visibility_violations'))


def unexpected_change_paths(changes, allowed):
    """Return porcelain entries outside exact files or declared directory prefixes."""
    violations = []
    for entry in changes:
        path = entry[3:] if len(entry) >= 4 else entry
        candidates = path.split(' -> ') if ' -> ' in path else [path]
        if any(not any(candidate == root.rstrip('/') or candidate.startswith(root.rstrip('/') + '/')
                       for root in allowed) for candidate in candidates):
            violations.append(entry)
    return violations


def summarize(rows, manifest):
    by_key = {(row['task_id'], row['arm']): row for row in rows}
    task_ids = [step['id'] for cluster in manifest['clusters'] for step in cluster['steps']]
    configured_arms = arms_for(manifest)
    arms = {}
    for arm in configured_arms:
        selected = [row for row in rows if row['arm'] == arm]
        usage, missing = numeric_usage(selected)
        walls = [row['total_wall_seconds'] for row in selected]
        arms[arm] = {'tasks': len(selected), 'checker_pass': sum(row['checker_pass'] for row in selected),
                     'severe_regressions': sum(row['severe_regression'] for row in selected),
                     'execution_failures': sum(row['status'] != 'completed' or row['checker_status'] != 'completed'
                                               for row in selected),
                     'usage': usage, 'usage_missing_tasks': missing,
                     'total_wall_seconds': {'sum': sum(walls), 'p50': quantile(walls, .5),
                                            'p95': quantile(walls, .95)}}
    comparisons = {}
    for candidate, baseline in [('raw_full', 'no_history'), ('raw_top8', 'no_history'),
                                ('raw_top8', 'raw_full')]:
        if candidate not in configured_arms or baseline not in configured_arms:
            continue
        counts = Counter()
        for cluster in manifest['clusters']:
            for step in cluster['steps']:
                left, right = by_key.get((step['id'], candidate)), by_key.get((step['id'], baseline))
                if not left or not right:
                    continue
                outcome = ('indeterminate' if not quality_comparable(left) or not quality_comparable(right) else
                           'win' if left['checker_pass'] and not right['checker_pass'] else
                           'loss' if right['checker_pass'] and not left['checker_pass'] else 'tie')
                counts[outcome] += 1; counts[f"{step['kind']}_{outcome}"] += 1
        comparisons[f'{candidate}_vs_{baseline}'] = dict(counts)
    expected = len(configured_arms) * sum(len(cluster['steps']) for cluster in manifest['clusters'])
    raw_regressions = [task for task in task_ids
                       if quality_comparable(by_key.get((task, 'raw_full')))
                       and quality_comparable(by_key.get((task, 'no_history')))
                       and by_key[(task, 'no_history')]['checker_pass'] is True
                       and by_key[(task, 'raw_full')]['checker_pass'] is False]
    necessary_wins = [step['id'] for cluster in manifest['clusters'] for step in cluster['steps']
                      if step['kind'] == 'necessary_update'
                      and quality_comparable(by_key.get((step['id'], 'raw_full')))
                      and quality_comparable(by_key.get((step['id'], 'no_history')))
                      and by_key[(step['id'], 'raw_full')]['checker_pass'] is True
                      and by_key[(step['id'], 'no_history')]['checker_pass'] is False]
    complete = len(rows) == expected and all(value['execution_failures'] == 0 for value in arms.values())
    decision = ('incomplete_or_execution_invalid' if not complete else
                'raw_full_regression_requires_review' if raw_regressions else
                'phase_a_candidate_pending_patch_audit' if necessary_wins else
                'no_independent_quality_replication')
    return {'schema': 1, 'protocol': 'topic3-be-route-v2-failure-discovery',
            'evaluation_mode': manifest['evaluation_mode'], 'task_source': manifest.get('task_source'),
            'complete': complete,
            'arms': arms, 'paired': comparisons,
            'current_system_failures': [row['task_id'] for row in rows
                                        if row['arm'] == 'raw_full' and quality_comparable(row)
                                        and not row['checker_pass']],
            'execution_failed_tasks': [f"{row['arm']}/{row['task_id']}" for row in rows
                                       if not quality_comparable(row)],
            'memory_dependent_wins': [task for task in task_ids
                                      if quality_comparable(by_key.get((task, 'raw_full')))
                                      and quality_comparable(by_key.get((task, 'no_history')))
                                      and by_key[(task, 'raw_full')]['checker_pass'] is True
                                      and by_key[(task, 'no_history')]['checker_pass'] is False],
            'raw_full_regressions_vs_no_history': raw_regressions,
            'retrieval_misses_vs_raw_full': [task for task in task_ids
                                             if quality_comparable(by_key.get((task, 'raw_full')))
                                             and quality_comparable(by_key.get((task, 'raw_top8')))
                                             and by_key[(task, 'raw_full')]['checker_pass'] is True
                                             and by_key[(task, 'raw_top8')]['checker_pass'] is False],
            'all_arm_passes_no_discrimination': [task for task in task_ids
                                                 if all(quality_comparable(by_key.get((task, arm)))
                                                        and by_key[(task, arm)]['checker_pass'] is True
                                                        for arm in configured_arms)],
            'same_topic_regressions': [row['task_id'] for row in rows
                                       if row['arm'] == 'raw_full' and row['kind'] == 'same_topic_control'
                                       and quality_comparable(row)
                                       and not row['checker_pass']],
            'decision': decision}


def visibility_violations(evidence, workspace, manifest, output):
    event_path = evidence / 'agent' / 'stdout.jsonl'
    if not event_path.is_file():
        return ['missing agent event log']
    text = event_path.read_text(errors='replace')
    violations = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get('item', {}) if isinstance(event, dict) else {}
        if event.get('type') in {'web_search_call', 'web_search'} or item.get('type') == 'web_search':
            violations.append('web_search tool event')
    forbidden = {str(output.resolve()), str(HERE.parents[3])}
    for cluster in manifest['clusters']:
        forbidden.update(str(Path(value).resolve()) for value in cluster['workspaces'].values()
                         if Path(value).resolve() != workspace)
    violations.extend(value for value in forbidden if value in text)
    return sorted(set(violations))


def run(manifest, output):
    validate(manifest); configured_arms = arms_for(manifest); output.mkdir(parents=True, exist_ok=False)
    atomic_write(output / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    rows = []
    for cluster_index, cluster in enumerate(manifest['clusters']):
        for step_index, step in enumerate(cluster['steps']):
            offset = (cluster_index + step_index) % len(configured_arms)
            arms = configured_arms[offset:] + configured_arms[:offset]
            for arm in arms:
                started = time.perf_counter(); workspace = Path(cluster['workspaces'][arm]).resolve()
                evidence = output / cluster['id'] / arm / step['id']; evidence.mkdir(parents=True)
                state = output / 'states' / cluster['id'] / arm
                args = argparse.Namespace(state=state, workspace=workspace, project=cluster['id'], owner=arm,
                    backend=manifest.get('backend', 'codex'), model=manifest.get('model'),
                    effort=manifest.get('effort', 'medium'), timeout=manifest.get('timeout_seconds', 240),
                    instruction_mode=manifest.get('instruction_mode', 'project'), mode=MODES[arm],
                    paths=step['paths'], action='edit', max_bytes=manifest.get('max_context_bytes', 12000),
                    retrieval_k=8, check=json.dumps(step['checker']),
                    agent_isolation_root=HERE.parents[4])
                host = Host(args); history = []
                with (state / 'writer.lock').open('a') as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if arm != 'no_history':
                        for index, text in enumerate(step.get('history', [])):
                            history.append(host.record(text, evidence / f'history-{index}'))
                    before = workspace_state(workspace, include_untracked=True)
                    result = host.run(step['prompt'], evidence)
                call = result['calls'][-1] if result['calls'] else {}
                violations = visibility_violations(evidence, workspace, manifest, output)
                after = workspace_state(workspace, include_untracked=True)
                unexpected = (unexpected_change_paths(after['changes'], step['paths'])
                              if manifest.get('enforce_change_paths', False) else [])
                checker_path = evidence / 'checker.json'
                checker = json.loads(checker_path.read_text()) if checker_path.exists() else {}
                context = json.loads((evidence / 'context.json').read_text())
                row = {'task_id': step['id'], 'kind': step['kind'], 'cluster_id': cluster['id'], 'arm': arm,
                       'base_commit': before['base_commit'], 'changes_before': before['changes'],
                       'changes_after': after['changes'], 'unexpected_changes': unexpected,
                       'status': call.get('status', 'host_error'), 'agent_returncode': call.get('returncode'),
                       'checker_status': checker.get('status', 'not_run'),
                       'checker_returncode': checker.get('returncode'),
                       'checker_pass': (result['checker_pass'] is True and not result['error'] and not unexpected
                                        and call.get('filesystem_isolated') is True and not violations),
                       'severe_regression': checker.get('returncode') == 2 or bool(unexpected),
                       'usage': call.get('usage'), 'agent_wall_seconds': call.get('wall_seconds', 0),
                       'checker_wall_seconds': checker.get('wall_seconds', 0),
                       'total_wall_seconds': time.perf_counter() - started,
                       'context_mode': result['context_mode'], 'context_bytes': result['context_bytes'],
                       'selected_orders': context.get('selected_orders'), 'memory_error': result['memory_error'],
                       'filesystem_isolated': call.get('filesystem_isolated') is True,
                       'visibility_violations': violations,
                       'history_count': len(history), 'evidence': str(evidence)}
                rows.append(row)
                atomic_write(output / 'receipts.jsonl', ''.join(json.dumps(item) + '\n' for item in rows))
                atomic_write(output / 'summary.json', json.dumps(summarize(rows, manifest), indent=2) + '\n')
                print(json.dumps({key: row[key] for key in
                                  ('task_id', 'arm', 'checker_pass', 'severe_regression', 'context_mode')}), flush=True)
                if violations or call.get('filesystem_isolated') is not True:
                    atomic_write(output / 'INVALID_VISIBILITY.json', json.dumps({
                        'task_id': step['id'], 'arm': arm, 'violations': violations,
                        'filesystem_isolated': call.get('filesystem_isolated') is True,
                    }, indent=2) + '\n')
                    raise RuntimeError('agent filesystem isolation audit failed')
                if unexpected:
                    atomic_write(output / 'INVALID_OUTPUT_SCOPE.json', json.dumps({
                        'task_id': step['id'], 'arm': arm, 'unexpected_changes': unexpected,
                    }, indent=2) + '\n')
                    raise RuntimeError('agent changed a path outside the declared output scope')
                if call.get('status') != 'completed' or checker.get('status') != 'completed':
                    atomic_write(output / 'INVALID_EXECUTION.json', json.dumps({
                        'task_id': step['id'], 'arm': arm, 'status': call.get('status'),
                        'checker_status': checker.get('status', 'not_run'),
                    }, indent=2) + '\n')
                    if call.get('status') == 'cancelled':
                        raise KeyboardInterrupt
                    raise RuntimeError('agent or checker execution did not complete')
    return summarize(rows, manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    run(json.loads(arguments.manifest.read_text()), arguments.output.resolve())
