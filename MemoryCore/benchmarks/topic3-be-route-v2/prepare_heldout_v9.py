"""Prepare v9 with the corrected porcelain parser and no previously called family."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from prepare_heldout_v3 import NOISE, command, isolated_checkout
from prepare_heldout_v8 import SCENARIOS as V8_SCENARIOS, SOURCES as V8_SOURCES

ARMS = ('no_history', 'raw_full')
LANES = {'no_history': 'lane-a', 'raw_full': 'lane-b'}
SOURCES = {name: V8_SOURCES[name] for name in ('jmespath', 'pluggy', 'zipp')}
SOURCES['typeguard'] = (
    'https://github.com/agronholm/typeguard.git',
    'a42dc4dbace5d1d75ac37ac29356c3b75637f337',
    ['100abcd09c8ab7ab4c2f4661e6d85e180289d255'],
)
SCENARIOS = {name: V8_SCENARIOS[name] for name in ('jmespath', 'pluggy', 'zipp')}
SCENARIOS['typeguard'] = {
    'source': {'kind': 'github_pr', 'url': 'https://github.com/agronholm/typeguard/pull/566'},
    'path': 'src/typeguard/_checkers.py',
    'history': [
        'The Literal review found matching depended on equal bool/int argument order.',
        *reversed(NOISE),
        ('Accepted typeguard PR #566 decision: scan every flattened Literal candidate and require exact '
         'runtime type equality before value equality. An equal int must not hide a later bool match, and '
         'a bool must not match an int-only Literal. Preserve ordinary literals and nested flattening.'),
    ],
    'steps': [
        ('typeguard-literal-order', 'necessary_update',
         'Apply the accepted order-independent Literal matching decision.'),
        ('typeguard-literal-control', 'same_topic_control',
         'Audit ordinary Literal mismatches and bool/int type distinction; edit only if either regressed.'),
    ],
}


def bounded(prompt, path):
    return (f'Work only in the current repository and edit only {path}. Do not use the internet or search outside '
            'the repository. Do not add or change tests, documentation, changelog, configuration, generated files, '
            'or bytecode. Run at most one focused local smoke check, then stop and report. ' + prompt)


def prepare(root):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v9_checker.py').resolve()
    manifest = {
        'schema': 1,
        'evaluation_mode': 'heldout',
        'arms': list(ARMS),
        'backend': 'codex',
        'model': 'gpt-5.6-sol',
        'effort': 'medium',
        'timeout_seconds': 300,
        'instruction_mode': 'controlled',
        'max_context_bytes': 12000,
        'enforce_change_paths': True,
        'task_source': 'porcelain-corrected single-source-file two-arm replication',
        'clusters': [],
    }
    for name, (url, commit, forbidden) in SOURCES.items():
        scenario = SCENARIOS[name]
        cluster = {
            'id': name,
            'source': scenario['source'],
            'source_url': url,
            'base_commit': commit,
            'forbidden_commits': forbidden,
            'workspaces': {},
            'steps': [],
        }
        for arm in ARMS:
            workspace = root / 'workspaces' / name / LANES[arm]
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, forbidden, f'{name} {LANES[arm]}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(scenario['steps'], 1):
            cluster['steps'].append({
                'id': task_id,
                'kind': kind,
                'prompt': bounded(prompt, scenario['path']),
                'paths': [scenario['path']],
                'history': scenario['history'] if index == 1 else [],
                'checker': [sys.executable, str(checker), name, str(index)],
            })
        baselines = []
        for stage in ('1', '2'):
            result = command(sys.executable, str(checker), name, stage,
                             cwd=Path(cluster['workspaces']['no_history']), check=False)
            observed = json.loads(result.stdout)
            if result.returncode != 1 or not observed['compatibility']['pass']:
                raise RuntimeError(f'invalid v9 baseline for {name}/{stage}: {result.stdout} {result.stderr}')
            baselines.append(observed)
        cluster['checker_baseline'] = baselines
        manifest['clusters'].append(cluster)
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.root)
    print(arguments.root.resolve() / 'manifest.json')
