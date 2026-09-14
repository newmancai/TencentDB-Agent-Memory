import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from failure_discovery_runner import validate as validate_runner_manifest
from phase_b_registry import (freeze_episode, load_json, natural_manifest, record_correction,
                              validate_correction, validate_freeze, validate_registry)


EARLY = '2026-09-14T01:00:00Z'
RECORDED = '2026-09-14T01:01:00Z'
LATER = '2026-09-15T02:00:00Z'
FROZEN = '2026-09-15T02:01:00Z'


def git(command, cwd):
    return subprocess.run(['git', *command], cwd=cwd, text=True,
                          capture_output=True, check=True).stdout.strip()


def fixture(root: Path):
    source = root / 'source'; source.mkdir(); (source / 'tracked.txt').write_text('base\n')
    git(['init', '-q'], source); git(['add', '.'], source)
    git(['-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
         'commit', '-qm', 'base'], source)
    commit = git(['rev-parse', 'HEAD'], source)
    workspaces = {}
    for arm in ('no_history', 'raw_full'):
        workspace = root / arm; shutil.copytree(source, workspace)
        (workspace / '.agent-benchmark-worktree').touch()
        workspaces[arm] = workspace
    checker = root / 'checker.py'; checker.write_text('raise SystemExit(0)\n')
    return commit, workspaces, checker


class PhaseBRegistryTest(unittest.TestCase):
    def test_records_verbatim_correction_once_and_detects_tampering(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = record_correction(root, 'decision-1', 'thread-1', 'user-message:42',
                                     EARLY, 'Keep the exact accepted behavior.\n', 'a' * 40,
                                     clock=lambda: RECORDED)
            packet = validate_correction(load_json(path))
            self.assertEqual(packet['verbatim_text'], 'Keep the exact accepted behavior.\n')
            with self.assertRaises(FileExistsError):
                record_correction(root, 'decision-1', 'thread-1', 'user-message:42',
                                  EARLY, 'replacement', 'a' * 40, clock=lambda: RECORDED)
            packet['verbatim_text'] = 'changed later'
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                validate_correction(packet)

    def test_freezes_chronology_clean_same_base_and_distinct_marked_arms(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); commit, workspaces, checker = fixture(root)
            correction = record_correction(root / 'evidence', 'decision-1', 'thread-1',
                                           'user-message:42', EARLY, 'Use TypeError.', commit,
                                           clock=lambda: RECORDED)
            path = freeze_episode(root / 'evidence', correction, 'episode-1',
                                  'necessary_update', LATER, 'Implement the follow-up.', commit,
                                  ['pkg/core.py'], ['python', str(checker.resolve())], workspaces,
                                  clock=lambda: FROZEN)
            packet = validate_freeze(load_json(path))
            self.assertEqual(packet['base_commit'], commit)
            self.assertNotEqual(packet['workspaces']['no_history']['path'],
                                packet['workspaces']['raw_full']['path'])
            manifest = natural_manifest(path)
            validate_runner_manifest(manifest)
            self.assertEqual(len(manifest['clusters'][0]['steps']), 1)
            self.assertEqual(manifest['clusters'][0]['steps'][0]['history'], ['Use TypeError.'])
            checker.write_text('raise SystemExit(1)\n')
            with self.assertRaisesRegex(ValueError, 'checker artifact hash mismatch'):
                validate_freeze(load_json(path))

    def test_rejects_task_that_predates_prospective_record(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); commit, workspaces, checker = fixture(root)
            correction = record_correction(root / 'evidence', 'decision-1', 'thread-1', 'message:1',
                                           EARLY, 'Do this.', commit, clock=lambda: RECORDED)
            with self.assertRaisesRegex(ValueError, 'after the correction was recorded'):
                freeze_episode(root / 'evidence', correction, 'episode-1', 'necessary_update',
                               EARLY, 'Earlier task', commit, ['pkg'], ['python', str(checker)], workspaces,
                               clock=lambda: FROZEN)

    def test_rejects_dirty_unmarked_or_same_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); commit, workspaces, checker = fixture(root)
            correction = record_correction(root / 'evidence', 'decision-1', 'thread-1', 'message:1',
                                           EARLY, 'Do this.', commit, clock=lambda: RECORDED)
            (workspaces['no_history'] / 'tracked.txt').write_text('dirty\n')
            with self.assertRaisesRegex(ValueError, 'not clean'):
                freeze_episode(root / 'evidence', correction, 'episode-dirty', 'same_topic_control',
                               LATER, 'Audit only.', commit, ['pkg'], ['python', str(checker)], workspaces,
                               clock=lambda: FROZEN)
            git(['checkout', '--', 'tracked.txt'], workspaces['no_history'])
            (workspaces['raw_full'] / '.agent-benchmark-worktree').unlink()
            with self.assertRaisesRegex(ValueError, 'unmarked'):
                freeze_episode(root / 'evidence', correction, 'episode-unmarked', 'same_topic_control',
                               LATER, 'Audit only.', commit, ['pkg'], ['python', str(checker)], workspaces,
                               clock=lambda: FROZEN)

    def test_empty_registry_counts_validate_and_drift_fails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            registry = {
                'schema': 1, 'protocol': 'topic3-be-route-v2-phase-b-natural',
                'eligible_sequences': 0, 'decision_threads': 0, 'natural_controls': 0,
                'episodes': [],
            }
            path.write_text(json.dumps(registry))
            self.assertEqual(validate_registry(path)['eligible_sequences'], 0)
            registry['eligible_sequences'] = 1; path.write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                validate_registry(path)

    def test_registry_counts_same_topic_controls_and_rejects_bad_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            registry = {
                'schema': 1, 'protocol': 'topic3-be-route-v2-phase-b-natural',
                'eligible_sequences': 1, 'decision_threads': 1, 'natural_controls': 1,
                'episodes': [{'id': 'episode-1', 'decision_thread': 'thread-1',
                              'kind': 'same_topic_control'}],
            }
            path.write_text(json.dumps(registry))
            self.assertEqual(validate_registry(path)['natural_controls'], 1)
            registry['episodes'][0]['kind'] = 'fabricated_control'; path.write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, 'episode kind'):
                validate_registry(path)


if __name__ == '__main__':
    unittest.main()
