"""Prepare replacement held-out projects after the first checker was invalidated."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'urllib3': ('https://github.com/urllib3/urllib3.git',
                '52dfb19e055baacc4ebc432a2e6012b6d489e4b6',
                '2a53e62f6e4bd547f4478d93844d154494dc5ca2'),
    'starlette': ('https://github.com/Kludex/starlette.git',
                  'bda8fcdb08bd97837988788a88d85f5e07a540e5',
                  '27b1f6cefcdd88635394ab46debc1c5b7bfb0df5'),
    'anyio': ('https://github.com/agronholm/anyio.git',
              'd3132e10aa690b87d1ed788352aea726691cb632',
              '4d8114e08eb00edd07ac7d949ad4edb555d5261e'),
    'trio': ('https://github.com/python-trio/trio.git',
             'd77bc763d49737431c1621c3feebfea2d71feb83',
             'af5100446675ee6947064ec2a6b7ad4d48b4b141'),
}

NOISE = [
    'Separate note: keep supported Python versions unchanged in focused patches.',
    'Separate note: public imports require a deprecation path before removal.',
    'Separate note: generated documentation follows the repository line length.',
    'Separate note: avoid adding a runtime dependency for a local change.',
    'Separate note: release notes use the existing section order.',
    'Separate note: tests should not require external network access.',
    'Separate note: preserve exception chaining in unrelated error paths.',
    'Separate note: type annotations must not change runtime semantics.',
    'Separate note: use deterministic values in unit tests.',
    'Separate note: do not reformat unrelated files.',
]

SCENARIOS = {
    'urllib3': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/urllib3/urllib3/pull/5161',
                   'grounding': 'The base predates the accepted HTTP 303 body-framing cleanup.'},
        'paths': ['src/urllib3/_collections.py', 'src/urllib3/connectionpool.py', 'src/urllib3/poolmanager.py'],
        'history': [
            'The redirect review found that a 303 switches to GET but some state describing the discarded body survives.',
            *NOISE,
            'Accepted urllib3 PR #5161 decision: when 303 changes the method and discards the body, reset chunked and body_pos in both connection-pool paths and remove Transfer-Encoding in HTTPHeaderDict._prepare_for_method_change. Preserve unrelated request headers.',
        ],
        'steps': [
            ('urllib3-303-framing', 'necessary_update',
             'Apply the accepted HTTP 303 body-framing decisions from the earlier project review. Keep body-preserving redirects and unrelated headers unchanged, and make the smallest focused fix.'),
            ('urllib3-header-scope-control', 'same_topic_control',
             'Audit the method-change helper after the framing fix. Transfer-Encoding and content framing must be removed, but Authorization and X-Request-ID are unrelated and must remain. Fix only if this scope is violated.'),
        ],
    },
    'starlette': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/Kludex/starlette/pull/3544',
                   'grounding': 'The base has append_query_params but predates the accepted preservation fix.'},
        'paths': ['starlette/datastructures.py'],
        'history': [
            'The URL append API review found that parsing and re-encoding the existing query changes valid noncanonical bytes.',
            *reversed(NOISE),
            'Accepted Starlette PR #3544 decision: URL.append_query_params must preserve the existing query serialization byte-for-byte, append only the newly encoded parameters, and return the existing URL unchanged for an empty append. replace_query_params still replaces and canonicalizes normally.',
        ],
        'steps': [
            ('starlette-query-preservation', 'necessary_update',
             'Apply the accepted URL append serialization decisions from the earlier project review. Keep replace_query_params semantics and unrelated URL behavior unchanged.'),
            ('starlette-replace-scope-control', 'same_topic_control',
             'Audit the sibling replace_query_params behavior. The append path preserves old serialization, but replace must still discard the old query and encode only the replacement values. Fix only if the earlier append change leaked into replace.'),
        ],
    },
    'anyio': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/agronholm/anyio/pull/1318',
                   'grounding': 'The base shields file close but predates the accepted pending-cancellation checkpoint.'},
        'paths': ['src/anyio/streams/file.py'],
        'history': [
            'File stream cleanup is shielded now, but the review still needs cancellation to be delivered after close completes.',
            *NOISE,
            'Accepted AnyIO PR #1318 decision: FileReadStream and FileWriteStream aclose must close inside a shielded CancelScope and then await checkpoint_if_cancelled after leaving the shield. Do not add that checkpoint to ordinary receive or send operations.',
        ],
        'steps': [
            ('anyio-close-checkpoint', 'necessary_update',
             'Apply the accepted file-stream cancellation decision from the earlier project review. Preserve shielded cleanup and make the same focused behavior apply to both read and write file streams.'),
            ('anyio-io-scope-control', 'same_topic_control',
             'Audit ordinary FileReadStream.receive and FileWriteStream.send after the close fix. The post-shield cancellation checkpoint belongs to aclose only and must not be added to normal I/O. Fix only if that scope was broadened.'),
        ],
    },
    'trio': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-trio/trio/pull/3456',
                   'grounding': 'The base predates the accepted final Python 3.15 test adjustments.'},
        'paths': ['test-requirements.in', 'pyproject.toml', 'src/trio/_core/_tests/test_thread_cache.py'],
        'history': [
            'The Python 3.15 test-support review has a temporary coverage warning workaround that should now be removed.',
            *reversed(NOISE),
            'Accepted Trio PR #3456 decision: raise the test coverage floor to 7.15.0, remove the Module globals loader DeprecationWarning filter, and apply warnings.simplefilter("default") in test_thread_cache only when sys.version_info is below 3.15. Do not change the pytest floor.',
        ],
        'steps': [
            ('trio-python315-tests', 'necessary_update',
             'Apply the accepted final Python 3.15 test-support decisions from the earlier project review. Keep the change limited to the named test dependencies, warning configuration, and thread-cache test.'),
            ('trio-pytest-floor-control', 'same_topic_control',
             'Audit the neighboring pytest test dependency after the coverage update. The accepted decision raised coverage only; pytest must remain at >=8.4. Fix only if that unrelated floor changed.'),
        ],
    },
}


def command(*args, cwd=None, check=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def isolated_checkout(url, workspace, commit, forbidden, label):
    marker = workspace / '.agent-benchmark-worktree'
    if workspace.exists():
        head = command('git', 'rev-parse', 'HEAD', cwd=workspace).stdout.strip()
        remotes = command('git', 'remote', cwd=workspace).stdout.strip()
        leaked = command('git', 'cat-file', '-e', f'{forbidden}^{{commit}}', cwd=workspace, check=False)
        if head != commit or remotes or leaked.returncode == 0 or not marker.is_file():
            raise RuntimeError(f'existing workspace is not isolated: {label}')
        return
    workspace.mkdir(parents=True)
    command('git', 'init', '-q', cwd=workspace)
    command('git', 'fetch', '--depth=1', '--no-tags', url, commit, cwd=workspace)
    command('git', 'checkout', '--detach', commit, cwd=workspace)
    if command('git', 'cat-file', '-e', f'{forbidden}^{{commit}}', cwd=workspace, check=False).returncode == 0:
        raise RuntimeError(f'post-review commit leaked into isolated workspace: {label}')
    marker.write_text(label + '\n')


def prepare(root):
    root = root.resolve(); root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v2_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'backend': 'codex',
                'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
                'instruction_mode': 'controlled', 'max_context_bytes': 12000,
                'task_source': 'replacement four-project behavior-oriented held-out sequences',
                'clusters': []}
    for name, (url, commit, post_review) in SOURCES.items():
        spec = SCENARIOS[name]
        cluster = {'id': name, 'source': spec['source'], 'source_url': url,
                   'base_commit': commit, 'forbidden_commits': [post_review],
                   'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / arm
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, post_review, f'{name} {arm}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(spec['steps'], 1):
            cluster['steps'].append({'id': task_id, 'kind': kind, 'prompt': prompt,
                                     'paths': spec['paths'], 'history': spec['history'] if index == 1 else [],
                                     'checker': [sys.executable, str(checker), name, str(index)]})
        baseline = command(sys.executable, str(checker), name, '1',
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
    args = parser.parse_args()
    prepare(args.root)
    print(args.root.resolve() / 'manifest.json')
