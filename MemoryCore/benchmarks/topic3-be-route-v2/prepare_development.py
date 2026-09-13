"""Prepare two issue-grounded development sequences in fresh independent worktrees."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from failure_discovery_runner import ARMS

SOURCES = {
    'tenacity': ('https://github.com/jd/tenacity.git',
                 'fd7842774cc10d41e68e6bc64afe7d9f83221aa0'),
    'cattrs': ('https://github.com/python-attrs/cattrs.git',
               '44aba28bd02388e0dc2c7d1539f7688b76c365cc'),
}

NOISE = [
    'Unrelated project note: documentation examples should remain executable and short.',
    'Unrelated project note: do not change the supported Python version in a bug fix.',
    'Unrelated project note: changelog entries use the existing repository style.',
    'Unrelated project note: public imports should remain backward compatible.',
    'Unrelated project note: avoid adding a runtime dependency for a local implementation fix.',
    'Unrelated project note: type annotations must not alter runtime behavior.',
    'Unrelated project note: tests should use deterministic inputs.',
    'Unrelated project note: preserve exception chaining in parser errors.',
]


SCENARIOS = {
    'tenacity': {
        'source': {'kind': 'github_issue', 'url': 'https://github.com/jd/tenacity/issues/233',
                   'related_pr': 'https://github.com/jd/tenacity/pull/278',
                   'grounding': 'Step 1 reproduces the issue; Step 2 is an authored explicit-override control.'},
        'paths': ['tenacity/__init__.py'],
        'history': [
            'Earlier assumption for Retrying.copy: preserve common retry settings, but reset specialized retry error handling on a copy.',
            *NOISE,
            'Correction after issue #233 review: retry_error_cls and retry_error_callback are behavioral state. Retrying.copy and retry_with must preserve both when the caller omits them. An explicitly supplied replacement, including callback=None, still wins over the preserved value.',
        ],
        'steps': [
            ('tenacity-copy-state', 'necessary_update',
             'Resolve the Retrying.copy and retry_with compatibility defect described in the earlier project discussion. Make the smallest backward-compatible implementation change in tenacity/__init__.py. Do not add dependencies or copy an external patch.'),
            ('tenacity-explicit-clear', 'same_topic_control',
             'Check the copy behavior for an explicitly supplied retry_error_callback=None. If needed, make a local fix so explicit None clears the callback while omitted values remain inherited. Preserve retry_error_cls unless it is explicitly replaced and keep other retry settings unchanged.'),
        ],
    },
    'cattrs': {
        'source': {'kind': 'github_issue', 'url': 'https://github.com/python-attrs/cattrs/issues/190',
                   'grounding': 'Step 1 reproduces the issue; Step 2 is an authored structure-vs-unstructure scope control.'},
        'paths': ['src/cattr/gen.py'],
        'history': [
            'Earlier assumption for generated structure functions: forbid_extra_keys may derive allowed input names directly from attrs field names because rename only affects value extraction.',
            *reversed(NOISE),
            'Correction after issue #190 review: when make_dict_structure_fn uses override(rename=...), forbid_extra_keys must allow the effective renamed input key, not the original attrs field name. Truly unknown keys and the replaced original name remain forbidden. This correction is for generated structuring; existing unstructuring rename behavior must not be changed.',
        ],
        'steps': [
            ('cattrs-renamed-input', 'necessary_update',
             'Resolve the generated-dict forbid_extra_keys defect described in the earlier project discussion. Make the smallest compatible change in src/cattr/gen.py. Keep normal unrenamed structuring and existing unstructuring behavior intact.'),
            ('cattrs-no-alias-broadening', 'same_topic_control',
             'Check that a structure-field rename remains a replacement, not an alias: the renamed input is accepted, while the old field name, both names together, and unrelated keys are rejected under forbid_extra_keys. Do not change unstructure rename behavior. Make a local fix only if the current implementation violates this.'),
        ],
    },
}


def command(*args, cwd=None, check=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def prepare(root):
    root = root.resolve(); sources = root / 'sources'; sources.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('development_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'development', 'backend': 'codex',
                'model': 'gpt-5.6-sol', 'effort': 'medium', 'timeout_seconds': 300,
                'instruction_mode': 'controlled', 'max_context_bytes': 12000,
                'task_source': 'two previously unused GitHub issues plus explicitly labeled authored controls',
                'clusters': []}
    for name, (url, commit) in SOURCES.items():
        source = sources / name
        if not source.exists(): command('git', 'clone', '--filter=blob:none', url, str(source))
        command('git', 'fetch', 'origin', commit, cwd=source)
        actual = command('git', 'rev-parse', f'{commit}^{{commit}}', cwd=source).stdout.strip()
        if actual != commit: raise RuntimeError(f'wrong source revision for {name}')
        spec = SCENARIOS[name]
        cluster = {'id': name, 'source': spec['source'], 'source_url': url,
                   'base_commit': commit, 'workspaces': {}, 'steps': []}
        for arm in ARMS:
            workspace = root / 'workspaces' / name / arm; workspace.parent.mkdir(parents=True, exist_ok=True)
            command('git', 'worktree', 'add', '--detach', str(workspace), commit, cwd=source)
            (workspace / '.agent-benchmark-worktree').write_text(f'{name} {arm}\n')
            cluster['workspaces'][arm] = str(workspace)
        for index, (task_id, kind, prompt) in enumerate(spec['steps'], 1):
            cluster['steps'].append({'id': task_id, 'kind': kind, 'prompt': prompt,
                                     'paths': spec['paths'], 'history': spec['history'] if index == 1 else [],
                                     'checker': [sys.executable, str(checker), name, str(index)]})
        # The source checkout may be on a newer default branch; prove the checker
        # against the declared pre-fix revision in a prepared worktree.
        baseline = command(sys.executable, str(checker), name, '1',
                           cwd=Path(cluster['workspaces']['no_history']), check=False)
        try: observed = json.loads(baseline.stdout)
        except ValueError as error: raise RuntimeError(baseline.stderr) from error
        if baseline.returncode != 1 or not observed['compatibility']['pass']:
            raise RuntimeError(f'invalid pre-fix checker for {name}: {baseline.stdout} {baseline.stderr}')
        cluster['checker_baseline'] = observed; manifest['clusters'].append(cluster)
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); prepare(args.root); print(args.root.resolve() / 'manifest.json')
