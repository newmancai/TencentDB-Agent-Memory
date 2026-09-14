"""Prepare held-out v4 with filesystem and model-tool isolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from failure_discovery_runner import ARMS
from prepare_heldout_v3 import NOISE, command, isolated_checkout

SOURCES = {
    'packaging': ('https://github.com/pypa/packaging.git',
                  '4840c3a6817fbd0831f7e520c9a55367472a4a08',
                  ['db202de8d74ce96d621bb9644ff2c23003712c69']),
    'flask': ('https://github.com/pallets/flask.git',
              '514fc6b3e8402e4c646d5284e97a4f0ab50a7c4b',
              ['de8429ffda8cfb54db175529e2bae72a24e1fa7e',
               '7203feabf723edae0286ae5dc64fec8ac4c91735']),
    'tqdm': ('https://github.com/tqdm/tqdm.git',
             '8d6ff8de5a9066de77d0a9df3e80a022a3dcf146',
             ['2a9e4e82ddba07c5dd6d126e23a4745b76ea49c8',
              '24b9e1e08a097f1c30f2d235b63f9eb25ba47974']),
    'uvicorn': ('https://github.com/Kludex/uvicorn.git',
                '9ce5e2b07839ac5486dc5b91e677e7050a35332e',
                ['07eb61e01c247d37a15ed688245407b8ad7b9947',
                 'b9e62fe55a7f62fc9b762eda01c3a03fb1711d21']),
}

CHECKER_PYTHON = {'packaging': sys.executable, 'flask': '/opt/anaconda3/bin/python',
                  'tqdm': sys.executable, 'uvicorn': sys.executable}

SCENARIOS = {
    'packaging': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pypa/packaging/pull/1392'},
        'paths': ['src/packaging/_ranges.py'],
        'history': [
            'The range-ordering review found two spellings of each unbounded endpoint that compare above one another.',
            *reversed(NOISE),
            'Accepted packaging PR #1392 decision: LowerBound and UpperBound with version=None have one canonical spelling, so force inclusive=False during construction. Equality, hashing, and total ordering must then agree. Preserve inclusive=True for bounded versions.',
        ],
        'steps': [
            ('packaging-unbounded-canonicalization', 'necessary_update',
             'Apply the accepted unbounded range-end decision from the earlier review. Preserve ordering and inclusivity for ordinary versioned bounds.'),
            ('packaging-bounded-control', 'same_topic_control',
             'Audit bounded range endpoints after the unbounded normalization. A concrete version with inclusive=True must remain inclusive and retain existing ordering. Fix only if the earlier change broadened.'),
        ],
    },
    'flask': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pallets/flask/pull/6096'},
        'paths': ['src/flask/app.py', 'src/flask/testing.py'],
        'history': [
            'The Flask review found colon partitioning is not a valid parser for bracketed IPv6 hosts.',
            *NOISE,
            'Accepted Flask PR #6096 decision: parse SERVER_NAME as a URL authority so [::1]:8080 yields host ::1 and integer port 8080, and derive the session cookie host from request.host_url the same way. Preserve IPv4/hostname ports including port zero.',
        ],
        'steps': [
            ('flask-ipv6-authority', 'necessary_update',
             'Apply the accepted IPv6 authority parsing decisions from the earlier review to development-server defaults and test-client session transactions. Keep ordinary hostnames and explicit port zero working.'),
            ('flask-hostname-control', 'same_topic_control',
             'Audit ordinary hostname parsing after the IPv6 fix. localhost:8080 and localhost:0 must retain their existing host and port meaning, and hostname session cookies must still round-trip. Fix only if this scope regressed.'),
        ],
    },
    'tqdm': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/tqdm/tqdm/pull/1830'},
        'paths': ['tqdm/contrib/concurrent.py'],
        'history': [
            'The concurrent-map review found that progress setup crashes when every input iterable has unknown length.',
            *NOISE,
            'Accepted tqdm PR #1830 decision: _min_map_len returns zero when no iterable has a nonnegative length hint, without consuming or materializing generators. If any iterable has a known length, retain the minimum known length.',
        ],
        'steps': [
            ('tqdm-unknown-length', 'necessary_update',
             'Apply the accepted no-length iterable decision to concurrent map progress setup. Do not consume generators and preserve known-length behavior.'),
            ('tqdm-known-length-control', 'same_topic_control',
             'Audit mixed known and unknown length iterables after the fallback. A sized iterable must still determine the minimum known progress total. Fix only if this adjacent contract regressed.'),
        ],
    },
    'uvicorn': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/Kludex/uvicorn/pull/3107'},
        'paths': ['uvicorn/protocols/http/h11_impl.py'],
        'history': [
            'The h11 review reproduced a keep-alive timeout left armed when a buffered second request upgrades to WebSocket.',
            *reversed(NOISE),
            'Accepted Uvicorn PR #3107 decision for h11: clear an armed keep-alive timer as soon as each Request event is consumed, before the WebSocket-upgrade branch. Ordinary pipelined HTTP still has no timer while work is pending and arms one again only when idle.',
        ],
        'steps': [
            ('uvicorn-pipelined-upgrade', 'necessary_update',
             'Apply the accepted h11 keep-alive decision for a pipelined WebSocket upgrade. Preserve ordinary request timing.'),
            ('uvicorn-pipelined-http-control', 'same_topic_control',
             'Audit ordinary h11 pipelining after the upgrade fix. No keep-alive timer may remain while the second response is pending, and one must be armed again when the connection becomes idle. Fix only if that behavior regressed.'),
        ],
    },
}


def prepare(root):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v4_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'backend': 'codex',
                'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
                'instruction_mode': 'controlled', 'max_context_bytes': 12000,
                'task_source': 'web-disabled filesystem-isolated four-project held-out sequences',
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
                                     'checker': [CHECKER_PYTHON[name], str(checker), name, str(index)]})
        baseline = command(CHECKER_PYTHON[name], str(checker), name, '1',
                           cwd=Path(cluster['workspaces']['no_history']), check=False)
        try:
            observed = json.loads(baseline.stdout)
        except ValueError as error:
            raise RuntimeError(
                f'invalid checker output for {name}: stdout={baseline.stdout!r} '
                f'stderr={baseline.stderr!r} returncode={baseline.returncode}'
            ) from error
        if baseline.returncode != 1 or not observed['compatibility']['pass']:
            raise RuntimeError(f'invalid held-out baseline for {name}: {baseline.stdout} {baseline.stderr}')
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
