"""Prepare the two-arm v5 replication after the first valid held-out signal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from prepare_heldout_v3 import NOISE, command, isolated_checkout

ARMS = ('no_history', 'raw_full')

SOURCES = {
    'websockets': ('https://github.com/python-websockets/websockets.git',
                   'ad8d970e7678f0c1d676f988d9e0072c7f3626a5',
                   ['ef56ca556848a9c2c72d52f49b7bdbd968f8c0f8']),
    'jsonschema': ('https://github.com/python-jsonschema/jsonschema.git',
                   '6b12cf853912d8eaff6e029053510e0892c983af',
                   ['88ec636d345a4f02c554c18e73539a7226245235']),
    'scrapy': ('https://github.com/scrapy/scrapy.git',
               'ebfb04912d8cafa2307ec0fb43a7f7f144921a63',
               ['0116cd81633c6a29f2cde6e34709e342cabd75f0']),
    'wsproto': ('https://github.com/python-hyper/wsproto.git',
                'b2239f4dbdf837836bfe88f88c831b8aae6934e5',
                ['541752c6b8c697b6c07b34db098498dfe42fdf2e']),
}

SCENARIOS = {
    'websockets': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-websockets/websockets/pull/1758'},
        'paths': ['src/websockets/legacy/http.py'],
        'history': [
            'The legacy HTTP parser review found that valid obs-text bytes were rejected after raw validation.',
            *NOISE,
            'Accepted Websockets PR #1758 decision: validate header values as raw HTTP bytes, decode them as ASCII with surrogateescape, then insert with Headers.set_insecure so string-level ASCII validation is not repeated. Invalid names and control bytes must still be rejected.',
        ],
        'steps': [
            ('websockets-obs-text-header', 'necessary_update',
             'Apply the accepted legacy parser decision for a non-ASCII HTTP header value. Preserve the existing raw header security validation.'),
            ('websockets-control-byte-control', 'same_topic_control',
             'Audit invalid legacy header bytes after the obs-text fix. NUL and other disallowed controls must still raise rather than enter Headers. Fix only if that boundary regressed.'),
        ],
    },
    'jsonschema': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-jsonschema/jsonschema/pull/1300'},
        'paths': ['jsonschema/exceptions.py'],
        'history': [
            'The best-match review found that sibling path order could select a deep but less useful failure from one branch.',
            *reversed(NOISE),
            'Accepted jsonschema PR #1300 decision: remove sibling path order from the relevance key. While descending anyOf or oneOf, first retain the most relevant error in each separate subschema, then choose the least relevant/deepest among those representatives. If representatives tie, keep the parent combination error.',
        ],
        'steps': [
            ('jsonschema-subschema-relevance', 'necessary_update',
             'Apply the accepted best-match decision for nested anyOf and oneOf failures. Preserve ordinary top-level relevance.'),
            ('jsonschema-tied-subschema-control', 'same_topic_control',
             'Audit equally relevant failures in separate anyOf branches after the traversal change. A true tie must keep the parent anyOf error. Fix only if that decision broadened.'),
        ],
    },
    'scrapy': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/scrapy/scrapy/pull/8113'},
        'paths': ['scrapy/utils/datatypes.py'],
        'history': [
            'The LocalCache review found that updating an existing key at capacity evicted an unrelated oldest key.',
            *NOISE,
            'Accepted Scrapy PR #8113 decision: capacity eviction runs only when the assigned key is new. Updating an existing key preserves both entries and their existing order; a later new key still evicts the oldest entry.',
        ],
        'steps': [
            ('scrapy-existing-key-update', 'necessary_update',
             'Apply the accepted LocalCache decision for updating an existing key at capacity. Preserve bounded insertion behavior.'),
            ('scrapy-new-key-eviction-control', 'same_topic_control',
             'Audit the next new-key insertion after an existing-key update. It must still evict exactly the oldest entry and keep the configured bound. Fix only if that behavior regressed.'),
        ],
    },
    'wsproto': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-hyper/wsproto/pull/202'},
        'paths': ['src/wsproto/utilities.py'],
        'history': [
            'The remote protocol-error review found that a missing close-event hint left callers without a required wire response.',
            *reversed(NOISE),
            'Accepted wsproto PR #202 decision for version 1.4: RemoteProtocolError.event_hint is a required constructor argument with no None default. This is an intentional breaking API change; explicit CloseConnection hints and LocalProtocolError remain unchanged.',
        ],
        'steps': [
            ('wsproto-required-event-hint', 'necessary_update',
             'Apply the accepted remote protocol-error hint API decision. Preserve explicit-hint behavior and local errors.'),
            ('wsproto-explicit-hint-control', 'same_topic_control',
             'Audit explicit RemoteProtocolError hints after making the argument required. The supplied CloseConnection object must remain available unchanged. Fix only if that behavior regressed.'),
        ],
    },
}


def prepare(root):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v5_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'arms': list(ARMS),
                'backend': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'medium',
                'timeout_seconds': 300, 'instruction_mode': 'controlled',
                'max_context_bytes': 12000,
                'task_source': 'two-arm lossless-history replication on four new project families',
                'clusters': []}
    for name, (url, commit, forbidden) in SOURCES.items():
        spec = SCENARIOS[name]
        cluster = {'id': name, 'source': spec['source'], 'source_url': url,
                   'base_commit': commit, 'forbidden_commits': forbidden,
                   'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / arm
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, forbidden, f'{name} {arm}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(spec['steps'], 1):
            cluster['steps'].append({'id': task_id, 'kind': kind, 'prompt': prompt,
                                     'paths': spec['paths'],
                                     'history': spec['history'] if index == 1 else [],
                                     'checker': [sys.executable, str(checker), name, str(index)]})
        baseline = command(sys.executable, str(checker), name, '1',
                           cwd=Path(cluster['workspaces']['no_history']), check=False)
        try:
            observed = json.loads(baseline.stdout)
        except ValueError as error:
            raise RuntimeError(
                f'invalid checker output for {name}: stdout={baseline.stdout!r} '
                f'stderr={baseline.stderr!r} returncode={baseline.returncode}'
            ) from error
        if baseline.returncode != 1 or not observed['compatibility']['pass']:
            raise RuntimeError(f'invalid replication baseline for {name}: {baseline.stdout} {baseline.stderr}')
        cluster['checker_baseline'] = observed
        manifest['clusters'].append(cluster)
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.root)
    print(arguments.root.resolve() / 'manifest.json')
