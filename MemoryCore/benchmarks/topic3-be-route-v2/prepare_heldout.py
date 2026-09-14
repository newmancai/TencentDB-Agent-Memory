"""Prepare the frozen four-project held-out B+E route evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'click': (
        'https://github.com/pallets/click.git',
        'c7e493d6f8c79f2022a803ddf302e3ae14281985',
        'e39679ab8d0cf0a8ce203a881c5ae7f44fadaebc',
    ),
    'httpcore': (
        'https://github.com/encode/httpcore.git',
        '65b530f28920c044af9efe78c48460c055acb097',
        'a3a80c9fdfe7b8cd974c2eeccf2eb31b2e29a9c6',
    ),
    'attrs': (
        'https://github.com/python-attrs/attrs.git',
        '48b8611c27779811d161200e17de8da24aae7feb',
        '5cd0fac89fd4d8a45d3328124f0a581252eae688',
    ),
    'markupsafe': (
        'https://github.com/pallets/markupsafe.git',
        '5c1e0ba949068dda2e4d76ade644df1729e1fb0e',
        'f0b96109c3b39e93275d4f9ec2771de51cbb311b',
    ),
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
    'click': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pallets/click/pull/3451',
                   'grounding': 'The base is the review commit before the accepted public-style type-alias name.'},
        'paths': ['src/click/testing.py'],
        'history': [
            'The testing-module typing review remains open on whether its exception tuple alias is private.',
            *NOISE,
            'Accepted Click PR #3451 decision: follow the other aliases and name this type alias ExceptionInfo without a leading underscore. Update every annotation that refers to it; do not alter runtime capture behavior.',
        ],
        'steps': [
            ('click-exception-alias', 'necessary_update',
             'Apply the accepted exception type-alias naming decision from the earlier project review. Keep the change focused in src/click/testing.py and preserve runtime behavior.'),
            ('click-private-alias-override', 'same_topic_control',
             'A later API review explicitly reverses the visibility choice: this alias must now be private. Rename it to _ExceptionInfo and update all references, without changing runtime capture behavior.'),
        ],
    },
    'httpcore': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/encode/httpcore/pull/1030',
                   'grounding': 'The base is the contributor commit using 3.x before the maintainer chose an explicit version.'},
        'paths': ['.github/workflows/test-suite.yml'],
        'history': [
            'The CI review remains open on whether the matrix should track Python 3.x automatically.',
            *reversed(NOISE),
            'Accepted HTTP Core PR #1030 decision: list Python 3.13 explicitly instead of 3.x, while retaining 3.14 and every older supported version. Minor Python releases are infrequent and explicit coverage is clearer.',
        ],
        'steps': [
            ('httpcore-explicit-matrix', 'necessary_update',
             'Apply the accepted Python matrix policy from the earlier project review. Change only the relevant matrix entry and preserve every other supported version and workflow behavior.'),
            ('httpcore-floating-matrix-override', 'same_topic_control',
             'The CI policy has now explicitly changed to track the latest stable Python automatically. Replace the 3.13 entry with 3.x while retaining 3.14 and all older supported versions.'),
        ],
    },
    'attrs': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-attrs/attrs/pull/1530',
                   'grounding': 'The base predates the accepted handling of the Python 3.15 regex error-message change.'},
        'paths': ['tests/test_validators.py'],
        'history': [
            'The validator test review must decide how much pre-release Python compatibility to retain.',
            *NOISE,
            'Accepted attrs PR #1530 decision: do not special-case old Python 3.15 alpha releases. For sys.version_info >= (3, 15), the invalid matches_re function message expects prefixmatch instead of match; older Python keeps match.',
        ],
        'steps': [
            ('attrs-python315-message', 'necessary_update',
             'Apply the accepted Python 3.15 validator-test compatibility decision from the earlier project review. Make the smallest focused test change and keep older Python expectations intact.'),
            ('attrs-alpha7-override', 'same_topic_control',
             "Pre-release support has now been explicitly expanded. Use the prefixmatch expectation only for sys.version_info >= (3, 15, 0, 'alpha', 7); Python 3.15 alpha 6 and earlier must retain the old match expectation."),
        ],
    },
    'markupsafe': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/pallets/markupsafe/pull/507',
                   'grounding': 'The base is the intermediate commit with a Beta classifier before the accepted classifier removal.'},
        'paths': ['pyproject.toml'],
        'history': [
            'The free-threading test work is complete, but its packaging maturity claim remains under review.',
            *reversed(NOISE),
            'Accepted MarkupSafe PR #507 decision: remove the Python Free Threading Beta classifier rather than claiming Beta, Stable, or Resilient maturity. Keep the parallel test setup and every unrelated classifier unchanged.',
        ],
        'steps': [
            ('markupsafe-remove-classifier', 'necessary_update',
             'Apply the accepted free-threading classifier decision from the earlier project review. Preserve the parallel test configuration and every unrelated project classifier.'),
            ('markupsafe-stable-override', 'same_topic_control',
             'A later packaging review now explicitly approves Stable maturity. Add exactly Programming Language :: Python :: Free Threading :: 3 - Stable, with no Beta classifier, and preserve all unrelated metadata.'),
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
    checker = Path(__file__).with_name('heldout_checker.py').resolve()
    manifest = {
        'schema': 1,
        'evaluation_mode': 'heldout',
        'backend': 'codex',
        'model': 'gpt-5.6-sol',
        'effort': 'medium',
        'timeout_seconds': 300,
        'instruction_mode': 'controlled',
        'max_context_bytes': 12000,
        'task_source': 'four unseen real PR review sequences with explicit same-topic overrides',
        'clusters': [],
    }
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
        observed = json.loads(baseline.stdout)
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
