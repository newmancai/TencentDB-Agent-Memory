"""Prepare real review decisions whose exact policy is not determined by source code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'httpcore': (
        'https://github.com/encode/httpcore.git',
        '0ea254006acc1dd7cecf1dbf613e93ff140472ea',
        '9c8fa1d0411e9a38e74aa1c677d3049e41522214',
    ),
    'werkzeug': (
        'https://github.com/pallets/werkzeug.git',
        'b70b7838af4d1446ee718dd71763b36e5d62a1cb',
        'ff1b12a6629b37f5d8372b9e53f02de9d1322e19',
    ),
}

NOISE = [
    'Separate project note: keep public imports stable in patch releases.',
    'Separate project note: generated documentation uses the repository line length.',
    'Separate project note: avoid adding a dependency for a one-line transformation.',
    'Separate project note: focused tests should use deterministic byte strings.',
    'Separate project note: preserve exception chaining in unrelated parsers.',
    'Separate project note: CI changes must keep all currently supported Python versions.',
    'Separate project note: release notes use the existing section order.',
    'Separate project note: do not convert unrelated functions during a focused fix.',
    'Separate project note: type annotations must not change runtime semantics.',
    'Separate project note: avoid platform-dependent assertions.',
]

SCENARIOS = {
    'httpcore': {
        'source': {
            'kind': 'github_pr',
            'url': 'https://github.com/encode/httpcore/pull/1008',
            'grounding': 'The base is the intermediate dependency commit after removing the upper bound but before the maintainer-selected security floor.',
        },
        'paths': ['pyproject.toml'],
        'history': [
            'Dependency review is still open: removing the h11 upper bound is not enough to select a safe minimum.',
            *NOISE,
            'Accepted maintainer decision for HTTP Core PR #1008: the h11 requirement must be exactly h11>=0.16. The lower bound itself prevents resolving to versions affected by GHSA-vqfr-h8mv-ghfj; do not keep the old >=0.13 floor and do not restore an upper bound.',
        ],
        'steps': [
            (
                'httpcore-h11-floor',
                'necessary_update',
                'Apply the accepted h11 dependency policy from the earlier project review to this pending branch. Change only the relevant dependency declaration and preserve the rest of the project metadata.',
            ),
            (
                'httpcore-vendored-exception',
                'same_topic_control',
                'A downstream release now explicitly vendors the security patch on h11 0.15.1 and cannot install 0.16. Override the earlier general floor for this branch: set the requirement exactly to h11>=0.15.1 with no upper bound. Do not alter other dependencies.',
            ),
        ],
    },
    'werkzeug': {
        'source': {
            'kind': 'github_pr',
            'url': 'https://github.com/pallets/werkzeug/pull/3166',
            'grounding': 'The base is the reviewed intermediate commit that already switched ETags to Base64 but still retained padding.',
        },
        'paths': ['src/werkzeug/http.py'],
        'history': [
            'ETag review is still open: the branch has switched SHA3-256 output from hex to Base64, but its wire representation is not final.',
            *reversed(NOISE),
            'Accepted maintainer decision for Werkzeug PR #3166: strip Base64 = padding from generate_etag because decoding is unnecessary and the padding is ugly. Return the 43-character unpadded digest and update its versionchanged length; do not change hashing or other header behavior.',
        ],
        'steps': [
            (
                'werkzeug-etag-padding',
                'necessary_update',
                'Apply the accepted ETag representation decision from the earlier project review to this pending branch. Keep the SHA3-256 and Base64 choices and make the smallest focused implementation and documentation change.',
            ),
            (
                'werkzeug-padded-rollout',
                'same_topic_control',
                'The deployment contract has now explicitly changed to fixed-width 44-character Base64 ETags. Restore standard = padding in generate_etag and update the versionchanged length to 44. Keep SHA3-256 and all unrelated header behavior unchanged.',
            ),
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
        leaked = command(
            'git', 'cat-file', '-e', f'{forbidden}^{{commit}}', cwd=workspace, check=False
        ).returncode == 0
        if head != commit or remotes or leaked or not marker.is_file():
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
    checker = Path(__file__).with_name('policy_checker.py').resolve()
    manifest = {
        'schema': 1,
        'evaluation_mode': 'development',
        'backend': 'codex',
        'model': 'gpt-5.6-sol',
        'effort': 'medium',
        'timeout_seconds': 300,
        'instruction_mode': 'controlled',
        'max_context_bytes': 12000,
        'task_source': 'two real maintainer-selected PR policy decisions plus explicit later overrides',
        'clusters': [],
    }
    for name, (url, commit, post_review) in SOURCES.items():
        spec = SCENARIOS[name]
        cluster = {
            'id': name,
            'source': spec['source'],
            'source_url': url,
            'base_commit': commit,
            'forbidden_commits': [post_review],
            'workspaces': {},
            'steps': [],
        }
        for arm in ARMS:
            workspace = root / 'workspaces' / name / arm
            workspace.parent.mkdir(parents=True, exist_ok=True)
            isolated_checkout(url, workspace, commit, post_review, f'{name} {arm}')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(spec['steps'], 1):
            cluster['steps'].append({
                'id': task_id,
                'kind': kind,
                'prompt': prompt,
                'paths': spec['paths'],
                'history': spec['history'] if index == 1 else [],
                'checker': [sys.executable, str(checker), name, str(index)],
            })
        baseline = command(
            sys.executable,
            str(checker),
            name,
            '1',
            cwd=Path(cluster['workspaces']['no_history']),
            check=False,
        )
        observed = json.loads(baseline.stdout)
        if baseline.returncode != 1 or not observed['compatibility']['pass']:
            raise RuntimeError(f'invalid policy baseline for {name}: {baseline.stdout} {baseline.stderr}')
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
