"""Prepare a fresh held-out set after enforcing filesystem isolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'pytest': ('https://github.com/pytest-dev/pytest.git',
               'efa117ad49ce197c5971b12310d53b73ed678d92',
               ['a88e91bacaa98b68fe80e07a138ce40994bd8797',
                '2802b66bb562342be2c0f9bfb3920ed761569ff6']),
    'packaging': ('https://github.com/pypa/packaging.git',
                  '4840c3a6817fbd0831f7e520c9a55367472a4a08',
                  ['db202de8d74ce96d621bb9644ff2c23003712c69']),
    'flask': ('https://github.com/pallets/flask.git',
              '514fc6b3e8402e4c646d5284e97a4f0ab50a7c4b',
              ['de8429ffda8cfb54db175529e2bae72a24e1fa7e',
               '7203feabf723edae0286ae5dc64fec8ac4c91735']),
    'h11': ('https://github.com/python-hyper/h11.git',
            '31e626c64e1e28db3cd73a6aa0ac057f1b915c18',
            ['60782ad107e538b9312aac7e1c119c8358bf797c']),
}

CHECKER_PYTHON = {
    'pytest': sys.executable,
    'packaging': sys.executable,
    'flask': '/opt/anaconda3/bin/python',
    'h11': sys.executable,
}

NOISE = [
    'Separate note: preserve public exception types in focused maintenance.',
    'Separate note: avoid unrelated import sorting.',
    'Separate note: tests must use deterministic local values.',
    'Separate note: keep supported interpreter versions unchanged.',
    'Separate note: do not add a runtime dependency for a local fix.',
    'Separate note: retain existing type annotations unless required.',
    'Separate note: release notes follow the repository section order.',
    'Separate note: do not perform network I/O in unit tests.',
    'Separate note: preserve unrelated command-line defaults.',
    'Separate note: keep the patch scoped to the reviewed behavior.',
]

SCENARIOS = {
    'pytest': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pytest-dev/pytest/pull/14910'},
        'paths': ['src/_pytest/monkeypatch.py'],
        'history': [
            'The MonkeyPatch review found that a failed mutation leaves teardown work which never became valid.',
            *NOISE,
            'Accepted pytest PR #14910 decision: for delattr, setitem, and delitem, capture the old value before mutation but append the undo entry only after the underlying mutation succeeds. Failed mutations must leave no stale undo entry; successful undo and raising=False behavior stay unchanged.',
        ],
        'steps': [
            ('pytest-failed-mutation-undo', 'necessary_update',
             'Apply the accepted MonkeyPatch failure-atomicity decision from the earlier review. Keep successful mutation and undo behavior unchanged.'),
            ('pytest-missing-key-control', 'same_topic_control',
             'Audit MonkeyPatch.delitem missing-key behavior after the atomicity fix. raising=True must still raise and raising=False must remain a no-op. Fix only if that adjacent contract regressed.'),
        ],
    },
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
    'h11': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-hyper/h11/pull/181'},
        'paths': ['h11/_headers.py'],
        'history': [
            'The HTTP framing review found that arbitrarily long digit strings in Content-Length create avoidable integer-conversion work.',
            *reversed(NOISE),
            'Accepted h11 PR #181 decision: reject Content-Length values longer than 20 digits with the existing bad Content-Length LocalProtocolError. Values of 20 digits or fewer remain valid, and Transfer-Encoding validation is unchanged.',
        ],
        'steps': [
            ('h11-content-length-limit', 'necessary_update',
             'Apply the accepted Content-Length resource-limit decision from the earlier review. Reuse the established protocol error and preserve normal framing validation.'),
            ('h11-framing-control', 'same_topic_control',
             'Audit the boundary and neighboring framing behavior after the length limit. A 20-digit Content-Length and chunked Transfer-Encoding must remain accepted. Fix only if the earlier guard broadened.'),
        ],
    },
}


def command(*args, cwd=None, check=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def isolated_checkout(url, workspace, commit, forbidden, label):
    marker = workspace / '.agent-benchmark-worktree'
    if workspace.exists():
        head_result = command('git', 'rev-parse', 'HEAD', cwd=workspace, check=False)
        if not marker.is_file() and (head_result.returncode != 0
                                     or head_result.stdout.strip() != commit):
            command('git', 'fetch', '--depth=1', '--no-tags', url, commit, cwd=workspace)
            command('git', 'checkout', '--detach', commit, cwd=workspace)
            head_result = command('git', 'rev-parse', 'HEAD', cwd=workspace)
        head = head_result.stdout.strip()
        remotes = command('git', 'remote', cwd=workspace).stdout.strip()
        leaked = any(command('git', 'cat-file', '-e', f'{revision}^{{commit}}', cwd=workspace,
                             check=False).returncode == 0 for revision in forbidden)
        if head != commit or remotes or leaked:
            raise RuntimeError(f'existing workspace is not isolated: {label}')
        if not marker.is_file():
            marker.write_text(label + '\n')
        return
    workspace.mkdir(parents=True)
    command('git', 'init', '-q', cwd=workspace)
    command('git', 'fetch', '--depth=1', '--no-tags', url, commit, cwd=workspace)
    command('git', 'checkout', '--detach', commit, cwd=workspace)
    for revision in forbidden:
        if command('git', 'cat-file', '-e', f'{revision}^{{commit}}', cwd=workspace,
                   check=False).returncode == 0:
            raise RuntimeError(f'post-review commit leaked into isolated workspace: {label}')
    marker.write_text(label + '\n')


def prepare(root):
    root = root.resolve(); root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v3_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'backend': 'codex',
                'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
                'instruction_mode': 'controlled', 'max_context_bytes': 12000,
                'task_source': 'filesystem-isolated four-project behavior held-out sequences',
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
            raise RuntimeError(baseline.stderr) from error
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
