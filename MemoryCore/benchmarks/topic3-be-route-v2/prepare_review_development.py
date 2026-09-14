"""Prepare PR-intermediate revisions where accepted review decisions are not in local code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'cachetools': ('https://github.com/tkem/cachetools.git',
                   '4dd976de71a0cb488f03719c2788b438e2f5ce1c', 'pull/408/head',
                   'b0ea1a4a0b38e1d3c60e802d171d776795c7a81b'),
    'httpx': ('https://github.com/encode/httpx.git',
              '424beb3d0f31e795ea9081e5c3171b97f17b789e', 'pull/2278/head',
              '74de49482f0fdf49fb112d118bf580d764d18ccd'),
}

NOISE = [
    'Separate review note: retain the existing minimum Python version.',
    'Separate review note: documentation should use semantic line breaks.',
    'Separate review note: do not add a dependency for a parser this small.',
    'Separate review note: keep the public import surface stable.',
    'Separate review note: preserve exception chaining in unrelated validation.',
    'Separate review note: use deterministic data in unit tests.',
    'Separate review note: keep benchmark fixtures out of the distributed wheel.',
    'Separate review note: avoid platform-specific path assertions.',
    'Separate review note: public examples should not rely on network access.',
    'Separate review note: preserve the existing copyright header.',
]

SCENARIOS = {
    'cachetools': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/tkem/cachetools/pull/408',
                   'issue': 'https://github.com/tkem/cachetools/issues/405',
                   'grounding': 'The base is the contributor commit before maintainer review was applied.'},
        'paths': ['src/cachetools/__init__.py', 'tests/__init__.py', 'CHANGELOG.rst'],
        'history': [
            'Review context: the current branch fixes Cache.__setitem__ over-eviction when a sized value grows, but review is still unresolved.',
            *NOISE,
            'Accepted maintainer review for PR #408: do not add CHANGELOG entries in ordinary PRs. Split Cache.__setitem__ into an insert branch with a fixed diffsize and a replacement branch that rechecks whether popitem removed the replaced key. In tests, numeric keys normally match values; use a different value only for replacement, and cover grow, same-size, and shrink replacements.',
        ],
        'steps': [
            ('cachetools-apply-review', 'necessary_update',
             'Apply the accepted Cache.__setitem__ review decisions from the earlier project discussion to this pending branch. Preserve the actual over-eviction fix and old cache behavior. Keep the change local and run focused checks available in the repository.'),
            ('cachetools-release-note-exception', 'same_topic_control',
             'This is now a release-preparation task, not an ordinary pull request. Add an Unreleased CHANGELOG entry for the Cache.__setitem__ over-eviction fix even though the earlier PR-time policy normally omitted it. Do not alter the reviewed cache implementation.'),
        ],
    },
    'httpx': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/encode/httpx/pull/2278',
                   'issue': 'https://github.com/encode/httpx/issues/2235',
                   'grounding': 'The base is an intermediate PR commit before final boundary-parser review.'},
        'paths': ['httpx/_multipart.py'],
        'history': [
            'Review context: explicit multipart boundaries from Content-Type are implemented, but the boundary parser still has unresolved edge-case choices.',
            *reversed(NOISE),
            'Accepted final review for PR #2278: boundary parameter names are matched case-insensitively and parsing removes only the boundary= prefix, so boundary= inside the value is preserved. Strip double quotes only; single quotes are not valid MIME quoting and remain part of the value. Use the simpler implementation: do not validate all boundary characters or implement quoted-pair unescaping. Case-insensitive matching applies to the parameter name, never to returned boundary bytes.',
        ],
        'steps': [
            ('httpx-boundary-review', 'necessary_update',
             'Apply the accepted multipart boundary parser decisions from the earlier review discussion. Make the smallest local change in httpx/_multipart.py and preserve existing multipart behavior.'),
            ('httpx-boundary-value-case', 'same_topic_control',
             'Check the same parser for mixed-case boundary values. Parameter-name matching is case-insensitive, but boundary value bytes are case-sensitive and must be returned unchanged. Fix only if that scope distinction is currently violated.'),
        ],
    },
}


def command(*args, cwd=None, check=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def isolated_checkout(url, workspace, commit, forbidden, label):
    """Fetch exactly the pre-review commit into a standalone shallow repository."""
    workspace.mkdir(parents=True)
    command('git', 'init', '-q', cwd=workspace)
    command('git', 'fetch', '--depth=1', '--no-tags', url, commit, cwd=workspace)
    command('git', 'checkout', '--detach', commit, cwd=workspace)
    if command('git', 'cat-file', '-e', f'{forbidden}^{{commit}}', cwd=workspace, check=False).returncode == 0:
        raise RuntimeError(f'post-review commit leaked into isolated workspace: {label}')
    (workspace / '.agent-benchmark-worktree').write_text(label + '\n')


def prepare(root):
    root = root.resolve(); root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('review_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'development', 'backend': 'codex',
                'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
                'instruction_mode': 'controlled', 'max_context_bytes': 12000,
                'task_source': 'two real PR intermediate revisions and accepted maintainer review decisions',
                'clusters': []}
    for name, (url, commit, pull_ref, post_review) in SOURCES.items():
        spec = SCENARIOS[name]
        cluster = {'id': name, 'source': spec['source'], 'source_url': url,
                   'base_commit': commit, 'forbidden_commits': [post_review],
                   'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / arm; workspace.parent.mkdir(parents=True, exist_ok=True)
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
            raise RuntimeError(f'invalid review baseline for {name}: {baseline.stdout} {baseline.stderr}')
        cluster['checker_baseline'] = observed; manifest['clusters'].append(cluster)
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); prepare(args.root); print(args.root.resolve() / 'manifest.json')
