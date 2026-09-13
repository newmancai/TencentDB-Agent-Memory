import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from failure_discovery_runner import ARMS, run, summarize, visibility_violations


class FakeHost:
    def __init__(self, args):
        self.args = args; self.state = args.state; self.state.mkdir(parents=True, exist_ok=True); self.calls = []
    def record(self, text, evidence):
        with (self.state / 'raw.txt').open('a') as handle: handle.write(text + '\n')
        return {'observation': {'text': text}, 'calls': []}
    def run(self, text, evidence):
        progress = self.args.workspace / 'progress.txt'
        old = int(progress.read_text()) if progress.exists() else 0
        progress.write_text(str(old + 1))
        expected = {'no_history': 'off', 'raw_full': 'raw', 'raw_top8': 'raw_topk'}[self.args.owner]
        assert self.args.mode == expected and self.args.retrieval_k == 8
        if self.args.owner != 'no_history': assert (self.state / 'raw.txt').exists()
        self.calls.append({'usage': {'input_tokens': 10}, 'wall_seconds': 1,
                           'status': 'completed', 'returncode': 0, 'filesystem_isolated': True})
        agent = evidence / 'agent'; agent.mkdir()
        (agent / 'stdout.jsonl').write_text('{}\n')
        (evidence / 'context.json').write_text(json.dumps({'mode': expected, 'selected_orders': [1]}))
        (evidence / 'checker.json').write_text(json.dumps({'status': 'completed', 'returncode': 0,
                                                          'wall_seconds': .1}))
        return {'calls': self.calls, 'checker_pass': True, 'error': None, 'context_mode': expected,
                'context_bytes': 10, 'memory_error': None}


def fixture_manifest(root, source, arms=ARMS):
    for command in (['git', 'init', '-q'], ['git', 'add', '.'],
                    ['git', '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                     'commit', '-qm', 'base']):
        subprocess.run(command, cwd=source, check=True, capture_output=True)
    base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    workspaces = {}
    for arm in arms:
        path = root / arm
        shutil.copytree(source, path)
        (path / '.agent-benchmark-worktree').touch()
        workspaces[arm] = str(path)
    return {'schema': 1, 'evaluation_mode': 'heldout', 'task_source': 'test',
            'arms': list(arms), 'clusters': [{
                'id': 'repo', 'base_commit': base, 'workspaces': workspaces,
                'forbidden_commits': ['0' * 40],
                'source': {'kind': 'github_issue', 'url': 'https://example.invalid/issue/1'},
                'steps': [
                    {'id': 'update', 'kind': 'necessary_update', 'prompt': 'one', 'paths': ['a'],
                     'history': ['old', 'correction'], 'checker': ['true']},
                    {'id': 'control', 'kind': 'same_topic_control', 'prompt': 'two', 'paths': ['a'],
                     'history': [], 'checker': ['true']},
                ],
            }]}


class FailureDiscoveryRunnerTest(unittest.TestCase):
    def test_execution_failure_is_indeterminate_not_a_memory_win(self):
        manifest = {'schema': 1, 'evaluation_mode': 'heldout', 'task_source': 'test',
                    'arms': ['no_history', 'raw_full'], 'clusters': [{
                        'id': 'repo', 'steps': [
                            {'id': 'update', 'kind': 'necessary_update'},
                            {'id': 'control', 'kind': 'same_topic_control'},
                        ]}]}
        common = {'severe_regression': False, 'usage': None, 'total_wall_seconds': 1,
                  'filesystem_isolated': True, 'visibility_violations': []}
        rows = [
            dict(common, task_id='update', kind='necessary_update', arm='no_history',
                 status='timeout', checker_status='not_run', checker_pass=False),
            dict(common, task_id='update', kind='necessary_update', arm='raw_full',
                 status='completed', checker_status='completed', checker_pass=True),
            dict(common, task_id='control', kind='same_topic_control', arm='no_history',
                 status='completed', checker_status='completed', checker_pass=False),
            dict(common, task_id='control', kind='same_topic_control', arm='raw_full',
                 status='completed', checker_status='completed', checker_pass=True),
        ]
        summary = summarize(rows, manifest)
        self.assertEqual(summary['paired']['raw_full_vs_no_history'], {
            'indeterminate': 1, 'necessary_update_indeterminate': 1,
            'win': 1, 'same_topic_control_win': 1,
        })
        self.assertEqual(summary['execution_failed_tasks'], ['update'])
        self.assertEqual(summary['memory_dependent_wins'], ['control'])

    def test_two_arm_replication_omits_closed_retrieval_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; source.mkdir(); (source / 'a').write_text('base')
            manifest = fixture_manifest(root, source, ('no_history', 'raw_full'))
            with patch('failure_discovery_runner.Host', FakeHost), contextlib.redirect_stdout(io.StringIO()):
                summary = run(manifest, root / 'out')
            self.assertTrue(summary['complete'])
            self.assertEqual(set(summary['arms']), {'no_history', 'raw_full'})
            self.assertEqual(len((root / 'out' / 'receipts.jsonl').read_text().splitlines()), 4)
            self.assertEqual(set(summary['paired']), {'raw_full_vs_no_history'})

    def test_web_search_event_is_a_visibility_violation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); workspace = root / 'workspace'; output = root / 'output'
            evidence = root / 'evidence'; agent = evidence / 'agent'; agent.mkdir(parents=True)
            workspace.mkdir(); output.mkdir()
            (agent / 'stdout.jsonl').write_text(json.dumps({
                'type': 'item.completed', 'item': {'type': 'web_search'},
            }) + '\n')
            manifest = {'clusters': [{'workspaces': {'no_history': str(workspace)}}]}
            self.assertIn('web_search tool event',
                          visibility_violations(evidence, workspace, manifest, output))

    def test_three_lossless_baselines_are_separate_and_sequential(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; source.mkdir(); (source / 'a').write_text('base')
            for command in (['git', 'init', '-q'], ['git', 'add', '.'],
                            ['git', '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                             'commit', '-qm', 'base']):
                subprocess.run(command, cwd=source, check=True, capture_output=True)
            base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
            workspaces = {}
            for arm in ARMS:
                path = root / arm; shutil.copytree(source, path); (path / '.agent-benchmark-worktree').touch()
                workspaces[arm] = str(path)
            manifest = {'schema': 1, 'evaluation_mode': 'development', 'task_source': 'test',
                        'clusters': [{'id': 'repo', 'base_commit': base, 'workspaces': workspaces,
                          'forbidden_commits': ['0' * 40],
                          'source': {'kind': 'github_issue', 'url': 'https://example.invalid/issue/1'}, 'steps': [
                            {'id': 'update', 'kind': 'necessary_update', 'prompt': 'one', 'paths': ['a'],
                             'history': ['old', 'correction'], 'checker': ['true']},
                            {'id': 'control', 'kind': 'same_topic_control', 'prompt': 'two', 'paths': ['a'],
                             'history': [], 'checker': ['true']}] }]}
            with patch('failure_discovery_runner.Host', FakeHost), contextlib.redirect_stdout(io.StringIO()):
                summary = run(manifest, root / 'results')
            self.assertTrue(summary['complete'])
            self.assertEqual(summary['arms']['raw_full']['checker_pass'], 2)
            self.assertEqual(summary['arms']['raw_top8']['usage']['input_tokens'], 20)
            self.assertEqual((root / 'no_history' / 'progress.txt').read_text(), '2')
            self.assertFalse((root / 'results' / 'states' / 'repo' / 'no_history' / 'raw.txt').exists())
            self.assertEqual((root / 'results' / 'states' / 'repo' / 'raw_full' / 'raw.txt').read_text(),
                             'old\ncorrection\n')


if __name__ == '__main__': unittest.main()
