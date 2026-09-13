"""Prepare a smaller fresh-family v6 after v5's execution-invalid matrix."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from prepare_heldout_v3 import NOISE, command, isolated_checkout

ARMS = ('no_history', 'raw_full')
LANES = {'no_history': 'lane-a', 'raw_full': 'lane-b'}

SOURCES = {
    'platformdirs': ('https://github.com/tox-dev/platformdirs.git',
                     'e0847a69cafd0f2534270980a269c4e07f449e1e',
                     ['83918e086451b88d4a88f588c1e22bb9425d4346']),
    'hpack': ('https://github.com/python-hyper/hpack.git',
              '1621490073e4992fe3bf28b547d2574edbd95043',
              ['038618fd72d260bf16db0aeb51f1c4c0b6379b4a']),
    'prettytable': ('https://github.com/prettytable/prettytable.git',
                    '266ff5d02f97354d08557d04606b465933dc78f6',
                    ['889b526974aed7451873358da07b4d097695a116']),
    'importlib-metadata': ('https://github.com/python/importlib_metadata.git',
                           'b9c4be4253250ad604610db66204e5fa70fa2455',
                           ['e4351c226765f53a40316fa6aab50488aee8a90f']),
}

SCENARIOS = {
    'platformdirs': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/tox-dev/platformdirs/pull/540'},
        'paths': ['src/platformdirs/_xdg.py', 'src/platformdirs/unix.py'],
        'history': [
            'The XDG review found that configured paths could violate the base-directory path contract.',
            *NOISE,
            'Accepted platformdirs PR #540 decision: XDG single-directory variables use POSIX absolute-path semantics; trim whitespace and ignore relative, tilde, unexpanded-variable, and Windows-drive values, preserving the platform fallback. For XDG_DATA_DIRS and XDG_CONFIG_DIRS, filter only invalid entries while preserving valid absolute entries and order.',
        ],
        'steps': [
            ('platformdirs-xdg-absolute-boundary', 'necessary_update',
             'Apply the accepted XDG path-validity decision to single-directory and directory-list variables. Preserve existing platform fallbacks.'),
            ('platformdirs-valid-absolute-control', 'same_topic_control',
             'Audit a whitespace-padded absolute XDG_CONFIG_HOME after the validity change. It must still be trimmed, accepted, and receive the application suffix. Fix only if that valid case regressed.'),
        ],
    },
    'hpack': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python-hyper/hpack/pull/287'},
        'paths': ['src/hpack/hpack.py'],
        'history': [
            'The encoder review found a static-table perfect match that was treated as only a name match.',
            *reversed(NOISE),
            'Accepted hpack PR #287 decision: the third HeaderTable.search result is a perfect-match value or None sentinel, so test `perfect is not None`; an empty byte value is still a perfect match and must use indexed representation without a dynamic-table insertion. Non-matching values with the same name remain indexed literals.',
        ],
        'steps': [
            ('hpack-empty-perfect-match', 'necessary_update',
             'Apply the accepted encoder decision for a static-table header whose matching value is empty. Avoid changing ordinary literal insertion.'),
            ('hpack-nonempty-literal-control', 'same_topic_control',
             'Audit a non-empty :authority value after the perfect-match fix. It must remain an indexed literal and enter the dynamic table. Fix only if the match boundary broadened.'),
        ],
    },
    'prettytable': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/prettytable/prettytable/pull/468'},
        'paths': ['src/prettytable/prettytable.py'],
        'history': [
            'The table review found that terminal tab stops made measured and displayed cell widths disagree.',
            *NOISE,
            'Accepted PrettyTable PR #468 decision: expand tabs exactly once on the final string returned by `_format_value`, after any custom formatter, using Python str.expandtabs default width. This gives measurement and rendering the same fixed text; tab-free cells remain unchanged.',
        ],
        'steps': [
            ('prettytable-expand-final-cell', 'necessary_update',
             'Apply the accepted cell-formatting decision so tabbed multiline values keep every rendered table line aligned. Preserve custom formatting.'),
            ('prettytable-custom-tab-control', 'same_topic_control',
             'Audit a custom formatter that itself returns a tabbed string. Its final output must follow the same alignment rule. Fix only if the formatting boundary was placed too early.'),
        ],
    },
    'importlib-metadata': {
        'source': {'kind': 'github_pr', 'url': 'https://github.com/python/importlib_metadata/pull/519'},
        'paths': ['importlib_metadata/__init__.py'],
        'history': [
            'The metadata review found distributions that exist but provide no readable metadata file.',
            *reversed(NOISE),
            'Accepted importlib_metadata PR #519 decision: Distribution.metadata and the public metadata() result are optional and return None when METADATA, PKG-INFO, and the legacy empty-name source are all absent. Continue parsing the first available fallback source; ordinary metadata, name, and version behavior stays unchanged.',
        ],
        'steps': [
            ('importlib-metadata-missing-none', 'necessary_update',
             'Apply the accepted API decision for an existing distribution with no metadata source. Preserve valid metadata parsing.'),
            ('importlib-metadata-pkg-info-control', 'same_topic_control',
             'Audit a distribution with no METADATA but a valid PKG-INFO fallback. It must still return parsed package metadata. Fix only if missing-source handling became too broad.'),
        ],
    },
}


def prepare(root):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name('heldout_v6_checker.py').resolve()
    manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'arms': list(ARMS),
                'backend': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'medium',
                'timeout_seconds': 300, 'instruction_mode': 'controlled',
                'max_context_bytes': 12000,
                'task_source': 'small-task two-arm full-raw replication on four fresh project families',
                'clusters': []}
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
            bounded_prompt = ('Work only in the current repository; do not use the internet or search outside it. '
                              + prompt)
            cluster['steps'].append({'id': task_id, 'kind': kind, 'prompt': bounded_prompt,
                                     'paths': spec['paths'],
                                     'history': spec['history'] if index == 1 else [],
                                     'checker': [sys.executable, str(checker), name, str(index)]})
        baselines = []
        for stage in ('1', '2'):
            baseline = command(sys.executable, str(checker), name, stage,
                               cwd=Path(cluster['workspaces']['no_history']), check=False)
            try:
                observed = json.loads(baseline.stdout)
            except ValueError as error:
                raise RuntimeError(baseline.stderr) from error
            if baseline.returncode != 1 or not observed['compatibility']['pass']:
                raise RuntimeError(f'invalid held-out baseline for {name}/{stage}: '
                                   f'{baseline.stdout} {baseline.stderr}')
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
