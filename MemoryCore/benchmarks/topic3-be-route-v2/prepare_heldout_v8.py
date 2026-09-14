"""Prepare v8 after enforcing declared output paths in the runner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from prepare_heldout_v3 import NOISE, command, isolated_checkout

ARMS = ('no_history', 'raw_full')
LANES = {'no_history': 'lane-a', 'raw_full': 'lane-b'}
SOURCES = {
    'hyperframe': ('https://github.com/python-hyper/hyperframe.git',
                   'b57beaff1cce7d7b7c38ea3514a349cb05a80d3c',
                   ['7b0db7eea110cabe4e1240d1de14fcfc3e22bca3']),
    'jmespath': ('https://github.com/jmespath/jmespath.py.git',
                 '2ad18b0e51ef3c22ef0d4bbeb11506746a39e228',
                 ['4a849225311ce4f894d3fa584ad32a6ddf55b3ef']),
    'pluggy': ('https://github.com/pytest-dev/pluggy.git',
               '6a7f8960eb4009b551f14030233cea7a64ccaf5d',
               ['0eaa5303d198a3337f70b2691bd9ff4d087ae67a']),
    'zipp': ('https://github.com/jaraco/zipp.git',
             'd14b72023b442e0eab42d59a6d849e31c2ab243e',
             ['a43226aba25ed257013d35cd412fcaac07ce8c38']),
}

SCENARIOS = {
    'hyperframe': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-hyper/hyperframe/pull/167'},
        'path': 'src/hyperframe/frame.py',
        'history': ['The SETTINGS review found field-width truncation during serialization.', *NOISE,
            'Accepted hyperframe PR #167 decision: serialize setting identifiers as the full 16-bit field and setting values as the full 32-bit field, masking with 0xFFFF and 0xFFFFFFFF respectively before packing. Preserve ordinary settings and parsing behavior.'],
        'steps': [
            ('hyperframe-settings-widths', 'necessary_update',
             'Apply the accepted SETTINGS serialization field-width decision.'),
            ('hyperframe-ordinary-setting-control', 'same_topic_control',
             'Audit ordinary small setting identifiers and values; edit only if their serialization regressed.'),
        ],
    },
    'jmespath': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/jmespath/jmespath.py/pull/335'},
        'path': 'jmespath/parser.py',
        'history': ['The parser-cache review found random eviction unsafe under concurrent access.', *reversed(NOISE),
            'Accepted jmespath PR #335 decision: use insertion-order FIFO with a 512-entry limit. On a miss at capacity, remove the oldest key before inserting; a cache hit does not refresh order. If concurrent mutation makes removal fail, return the parsed result without inserting so the cache cannot grow beyond the limit.'],
        'steps': [
            ('jmespath-fifo-cache', 'necessary_update',
             'Apply the accepted bounded parser-cache policy and concurrency boundary.'),
            ('jmespath-cache-hit-control', 'same_topic_control',
             'Audit ordinary cache hits and purge after the eviction change; edit only if either behavior regressed.'),
        ],
    },
    'pluggy': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pytest-dev/pluggy/pull/727'},
        'path': 'src/pluggy/_hooks.py',
        'history': ['The hook-call review found missing-argument warnings pointed inside pluggy.', *NOISE,
            'Accepted pluggy PR #727 decision: _verify_all_args_are_provided is one helper below __call__, call_extra, or call_historic, so its missing-argument warning uses stacklevel=3 and points at external hook-calling code. Valid calls remain warning-free.'],
        'steps': [
            ('pluggy-warning-caller', 'necessary_update',
             'Apply the accepted warning-location decision for a hook call missing a required argument.'),
            ('pluggy-call-extra-control', 'same_topic_control',
             'Audit missing-argument warning location through call_extra and preserve warning-free valid calls; edit only if needed.'),
        ],
    },
    'zipp': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/jaraco/zipp/pull/154'},
        'path': 'zipp/__init__.py',
        'history': ['The archive-path review found an inconsistent public exception when listing children of a file.', *reversed(NOISE),
            'Accepted zipp PR #154 decision: Path.iterdir on a non-directory raises NotADirectoryError, consistent with pathlib and zipfile.Path. Keep the existing message and preserve normal archive-root and directory iteration.'],
        'steps': [
            ('zipp-file-iterdir-exception', 'necessary_update',
             'Apply the accepted public exception decision for Path.iterdir on a file.'),
            ('zipp-directory-iterdir-control', 'same_topic_control',
             'Audit ordinary archive-directory iteration; edit only if it regressed.'),
        ],
    },
}


def bounded(prompt, path):
    return (f'Work only in the current repository and edit only {path}. Do not use the internet or search outside '
            'the repository. Do not add or change tests, documentation, changelog, configuration, generated files, '
            'or bytecode. Run at most one focused local smoke check, then stop and report. ' + prompt)


def prepare(root):
    root = root.resolve(); root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v8_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'arms': list(ARMS),
                'backend': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'medium',
                'timeout_seconds': 300, 'instruction_mode': 'controlled',
                'max_context_bytes': 12000, 'enforce_change_paths': True,
                'task_source': 'path-enforced single-source-file two-arm replication', 'clusters': []}
    for name, (url, commit, forbidden) in SOURCES.items():
        spec = SCENARIOS[name]
        cluster = {'id': name, 'source': spec['source'], 'source_url': url,
                   'base_commit': commit, 'forbidden_commits': forbidden,
                   'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / LANES[arm]
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, forbidden, f'{name} {LANES[arm]}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(spec['steps'], 1):
            cluster['steps'].append({'id': task_id, 'kind': kind,
                'prompt': bounded(prompt, spec['path']), 'paths': [spec['path']],
                'history': spec['history'] if index == 1 else [],
                'checker': [sys.executable, str(checker), name, str(index)]})
        baselines = []
        for stage in ('1', '2'):
            result = command(sys.executable, str(checker), name, stage,
                             cwd=Path(cluster['workspaces']['no_history']), check=False)
            observed = json.loads(result.stdout)
            if result.returncode != 1 or not observed['compatibility']['pass']:
                raise RuntimeError(f'invalid v8 baseline for {name}/{stage}: {result.stdout} {result.stderr}')
            baselines.append(observed)
        cluster['checker_baseline'] = baselines
        manifest['clusters'].append(cluster)
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args(); prepare(arguments.root)
    print(arguments.root.resolve() / 'manifest.json')
