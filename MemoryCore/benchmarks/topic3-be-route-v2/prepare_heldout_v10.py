"""Prepare v10 with reviewed, equivalent, and semantic near-miss preflight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from prepare_heldout_v3 import NOISE, command, isolated_checkout

ARMS = ('no_history', 'raw_full')
LANES = {'no_history': 'lane-a', 'raw_full': 'lane-b'}
SOURCES = {
    'h2': ('https://github.com/python-hyper/h2.git',
           '1cd9ce0c1c9862df948318b12c3b75d72537abd4',
           ['9c6780cc58bf021e37703d00e51794b2ac7e7d17']),
    'pycodestyle': ('https://github.com/PyCQA/pycodestyle.git',
                    '16f212741b5cba7495ad45f448cbc5361ae9e5bd',
                    ['875e20fb8ed37322b39ce536fbcf369e3672984b']),
    'path': ('https://github.com/jaraco/path.git',
             'efa71fcb34e5a9d34b34474326af67d082ad9b4a',
             ['797fa31a138e7cdc9ae34b30dbfe524de51871ce']),
    'importlib_resources': ('https://github.com/python/importlib_resources.git',
                            'c6773a1534416cbb0ca274de99959c04bee99277',
                            ['d80822a9018c1a2438fe0cfe5b526c81a3705267']),
}

SCENARIOS = {
    'h2': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-hyper/h2/pull/1317'},
        'path': 'src/h2/stream.py',
        'history': ['The content-length review found that the first duplicate silently won.', *NOISE,
            ('Accepted h2 PR #1317 decision: accept repeated content-length fields only when every parsed '
             'decimal value is equal; raise ProtocolError when any later value conflicts, even with unrelated '
             'headers between them. Preserve absent, single, equal-duplicate, and invalid-value behavior.')],
        'steps': [
            ('h2-content-length-conflict', 'necessary_update',
             'Apply the accepted duplicate content-length decision.'),
            ('h2-content-length-control', 'same_topic_control',
             'Audit absent, single, equal repeated, and invalid content lengths; edit only if one regressed.'),
        ],
    },
    'pycodestyle': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/PyCQA/pycodestyle/pull/1323'},
        'path': 'pycodestyle.py',
        'history': ['The configuration review found a lexical prefix was treated as a shared directory.',
            *reversed(NOISE),
            ('Accepted pycodestyle PR #1323 decision: begin project-config discovery from the actual common '
             'filesystem path of all input arguments, not their character prefix. Sibling names such as aaa, '
             'aaabbb, and aaaccc share only their real parent. Preserve single-file local config discovery.')],
        'steps': [
            ('pycodestyle-common-config-path', 'necessary_update',
             'Apply the accepted project configuration discovery boundary.'),
            ('pycodestyle-single-config-control', 'same_topic_control',
             'Audit single-file local project configuration discovery; edit only if it regressed.'),
        ],
    },
    'path': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/jaraco/path/pull/237'},
        'path': 'path/__init__.py',
        'history': ['The TempDir review found construction arguments succeeded in __new__ then failed in __init__.',
            *NOISE,
            ('Accepted path PR #237 decision: TempDir accepts and ignores all positional and keyword initializer '
             'arguments already consumed by tempfile.mkdtemp in __new__. Preserve no-argument construction, '
             'prefix/suffix/dir, context-manager cleanup, and explicit removal.')],
        'steps': [
            ('path-tempdir-constructor', 'necessary_update',
             'Apply the accepted TempDir constructor argument decision.'),
            ('path-tempdir-cleanup-control', 'same_topic_control',
             'Audit no-argument, context-manager, and explicit TempDir removal; edit only if one regressed.'),
        ],
    },
    'importlib_resources': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python/importlib_resources/pull/331'},
        'path': 'importlib_resources/_common.py',
        'history': ['The resources review found an opaque failure for modules whose import spec is absent.',
            *reversed(NOISE),
            ('Accepted importlib_resources PR #331 decision: before adapting a package, if and only if its '
             '__spec__ is None, raise TypeError naming the module and explaining that it is not importable because '
             '__spec__ is None. Preserve ordinary package resource access.')],
        'steps': [
            ('resources-none-spec-error', 'necessary_update',
             'Apply the accepted missing-module-spec error decision.'),
            ('resources-package-control', 'same_topic_control',
             'Audit ordinary package resources and a second missing-spec module name; edit only if one regressed.'),
        ],
    },
}


def bounded(prompt, path):
    return (f'Work only in the current repository and edit only {path}. Do not use the internet or search outside '
            'the repository. Do not add or change tests, documentation, changelog, configuration, generated files, '
            'or bytecode. Run at most one focused local smoke check, then stop and report. ' + prompt)


def prepare(root):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v10_checker.py').resolve()
    manifest = {
        'schema': 1, 'evaluation_mode': 'heldout', 'arms': list(ARMS), 'backend': 'codex',
        'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
        'instruction_mode': 'controlled', 'max_context_bytes': 12000, 'enforce_change_paths': True,
        'task_source': 'near-miss-preflight single-source-file two-arm replication', 'clusters': [],
    }
    for name, (url, commit, forbidden) in SOURCES.items():
        scenario = SCENARIOS[name]
        cluster = {'id': name, 'source': scenario['source'], 'source_url': url,
                   'base_commit': commit, 'forbidden_commits': forbidden,
                   'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / LANES[arm]
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, forbidden, f'{name} {LANES[arm]}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(scenario['steps'], 1):
            cluster['steps'].append({'id': task_id, 'kind': kind,
                'prompt': bounded(prompt, scenario['path']), 'paths': [scenario['path']],
                'history': scenario['history'] if index == 1 else [],
                'checker': [sys.executable, str(checker), name, str(index)]})
        baselines = []
        for stage in ('1', '2'):
            result = command(sys.executable, str(checker), name, stage,
                             cwd=Path(cluster['workspaces']['no_history']), check=False)
            observed = json.loads(result.stdout)
            if result.returncode != 1 or not observed['compatibility']['pass']:
                raise RuntimeError(f'invalid v10 baseline for {name}/{stage}: {result.stdout} {result.stderr}')
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
