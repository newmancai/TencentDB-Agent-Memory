import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from failure_discovery_runner import summarize, validate as validate_runner_manifest
from phase_b_registry import (append_outcome, freeze_episode, load_json, natural_manifest,
                              record_correction, seal_outcome, sha256_bytes,
                              validate_correction, validate_freeze, validate_registry)


EARLY = '2026-09-14T01:00:00Z'
RECORDED = '2026-09-14T01:01:00Z'
LATER = '2026-09-15T02:00:00Z'
FROZEN = '2026-09-15T02:01:00Z'
AUDITED = '2026-09-15T02:02:00Z'
SEALED = '2026-09-15T02:03:00Z'


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


def empty_registry():
    return {
        'schema': 1, 'protocol': 'topic3-be-route-v2-phase-b-natural',
        'status': 'collecting', 'target_sequences': 10, 'minimum_decision_threads': 4,
        'minimum_natural_controls': 3, 'attempts_total': 0, 'invalid_attempts': 0,
        'eligible_sequences': 0, 'decision_threads': 0, 'natural_controls': 0,
        'attempts': [], 'episodes': [],
    }


def completed_case(root: Path, usage=True):
    commit, workspaces, checker = fixture(root)
    evidence = root / 'evidence'
    correction = record_correction(evidence, 'decision-1', 'thread-1', 'message:1',
                                   EARLY, 'Use TypeError.', commit, clock=lambda: RECORDED)
    freeze = freeze_episode(evidence, correction, 'episode-1', 'necessary_update', LATER,
                            'Implement the follow-up.', commit, ['pkg/core.py'],
                            ['python', str(checker.resolve())], workspaces, clock=lambda: FROZEN)
    manifest = natural_manifest(freeze)
    results = root / 'results'; results.mkdir()
    common = {
        'task_id': 'episode-1', 'cluster_id': 'episode-1', 'kind': 'necessary_update',
        'base_commit': commit, 'changes_before': [], 'changes_after': [' M pkg/core.py'],
        'unexpected_changes': [], 'status': 'completed', 'agent_returncode': 0,
        'checker_status': 'completed', 'checker_returncode': 0, 'severe_regression': False,
        'usage': {'input_tokens': 10} if usage else None, 'agent_wall_seconds': 1,
        'checker_wall_seconds': .1, 'total_wall_seconds': 1.1, 'context_bytes': 10,
        'selected_orders': [], 'memory_error': None, 'filesystem_isolated': True,
        'visibility_violations': [], 'evidence': str(results / 'cell'),
    }
    rows = [dict(common, arm='no_history', checker_pass=False, context_mode='off', history_count=0),
            dict(common, arm='raw_full', checker_pass=True, context_mode='raw', history_count=1)]
    (results / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (results / 'receipts.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (results / 'summary.json').write_text(json.dumps(summarize(rows, manifest), indent=2) + '\n')
    freeze_sha = sha256_bytes(freeze.read_bytes())
    audit = root / 'audit.json'
    audit.write_text(json.dumps({
        'schema': 1, 'kind': 'phase_b_patch_audit', 'episode_id': 'episode-1',
        'freeze_sha256': freeze_sha, 'audited_at': AUDITED, 'auditor': 'test-auditor',
        'verdict': 'valid', 'checks': {
            'checker_semantics_complete': True, 'both_patches_reviewed': True,
            'no_cross_arm_contamination': True, 'declared_scope_respected': True,
        }, 'notes': 'synthetic unit-test fixture only',
    }))
    return freeze, results, audit


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
            registry = empty_registry()
            path.write_text(json.dumps(registry))
            self.assertEqual(validate_registry(path)['eligible_sequences'], 0)
            registry['eligible_sequences'] = 1; path.write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                validate_registry(path)

    def test_registry_counts_same_topic_controls_and_rejects_bad_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            row = {'id': 'episode-1', 'decision_thread': 'thread-1',
                   'kind': 'fabricated_control', 'status': 'eligible'}
            registry = empty_registry()
            registry.update({'attempts_total': 1, 'eligible_sequences': 1,
                             'decision_threads': 1, 'natural_controls': 1,
                             'attempts': [row], 'episodes': [row.copy()]})
            path.write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, 'attempt kind'):
                validate_registry(path)

    def test_seals_and_appends_valid_natural_win(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); freeze, results, audit = completed_case(root)
            outcome = seal_outcome(root / 'evidence', freeze, results, audit,
                                   clock=lambda: SEALED)
            self.assertEqual(load_json(outcome)['status'], 'eligible')
            registry = root / 'registry.json'; registry.write_text(json.dumps(empty_registry()))
            updated = append_outcome(registry, outcome)
            self.assertEqual((updated['attempts_total'], updated['eligible_sequences'],
                              updated['decision_threads']), (1, 1, 1))
            self.assertEqual(updated['episodes'][0]['comparison'], 'win')
            with self.assertRaisesRegex(ValueError, 'already registered'):
                append_outcome(registry, outcome)

    def test_missing_usage_is_preserved_as_invalid_attempt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); freeze, results, audit = completed_case(root, usage=False)
            outcome = seal_outcome(root / 'evidence', freeze, results, audit,
                                   clock=lambda: SEALED)
            self.assertEqual(load_json(outcome)['status'], 'invalid')
            registry = root / 'registry.json'; registry.write_text(json.dumps(empty_registry()))
            updated = append_outcome(registry, outcome)
            self.assertEqual((updated['attempts_total'], updated['invalid_attempts'],
                              updated['eligible_sequences']), (1, 1, 0))

    def test_incomplete_execution_is_preserved_as_indeterminate_attempt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); freeze, results, audit = completed_case(root)
            rows = [json.loads((results / 'receipts.jsonl').read_text().splitlines()[0])]
            manifest = load_json(results / 'manifest.json')
            (results / 'receipts.jsonl').write_text(json.dumps(rows[0]) + '\n')
            (results / 'summary.json').write_text(json.dumps(summarize(rows, manifest), indent=2) + '\n')
            (results / 'INVALID_EXECUTION.json').write_text(json.dumps({'arm': 'no_history'}))
            audit_value = load_json(audit)
            audit_value['verdict'] = 'invalid'
            audit_value['checks']['both_patches_reviewed'] = False
            audit.write_text(json.dumps(audit_value))
            outcome = seal_outcome(root / 'evidence', freeze, results, audit,
                                   clock=lambda: SEALED)
            sealed = load_json(outcome)
            self.assertEqual((sealed['status'], sealed['comparison']), ('invalid', 'indeterminate'))
            registry = root / 'registry.json'; registry.write_text(json.dumps(empty_registry()))
            updated = append_outcome(registry, outcome)
            self.assertEqual((updated['attempts_total'], updated['invalid_attempts'],
                              updated['eligible_sequences']), (1, 1, 0))

    def test_rejects_tampered_summary_and_postseal_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); freeze, results, audit = completed_case(root)
            summary = load_json(results / 'summary.json'); summary['decision'] = 'favorable_by_hand'
            (results / 'summary.json').write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, 'does not recompute'):
                seal_outcome(root / 'evidence', freeze, results, audit, clock=lambda: SEALED)
        with TemporaryDirectory() as directory:
            root = Path(directory); freeze, results, audit = completed_case(root)
            outcome = seal_outcome(root / 'evidence', freeze, results, audit,
                                   clock=lambda: SEALED)
            (results / 'extra-after-seal.txt').write_text('changed')
            registry = root / 'registry.json'; registry.write_text(json.dumps(empty_registry()))
            with self.assertRaisesRegex(ValueError, 'result evidence changed'):
                append_outcome(registry, outcome)


if __name__ == '__main__':
    unittest.main()
