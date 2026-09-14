"""Create and validate prospective Phase B correction and task-freeze packets.

The real registry remains outcome-only.  These local packets prove that a user
correction existed before a later task and that the paired workspaces and audit
boundary were frozen before either arm ran.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from typing import Callable


ARMS = ('no_history', 'raw_full')
MARKER = '.agent-benchmark-worktree'
IDENTIFIER = re.compile(r'^[a-z0-9][a-z0-9._-]{0,79}$')
GIT_COMMIT = re.compile(r'^[0-9a-f]{40}$')


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f'timestamp must be a string: {value!r}')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(f'invalid ISO-8601 timestamp: {value}') from error
    if parsed.tzinfo is None:
        raise ValueError('timestamp must include a UTC offset')
    return parsed.astimezone(timezone.utc)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def require_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f'invalid {label}: {value!r}')


def require_commit(value: str) -> None:
    if not isinstance(value, str) or not GIT_COMMIT.fullmatch(value):
        raise ValueError(f'base commit must be a full lowercase Git SHA: {value!r}')


def write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(canonical_bytes(value))


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f'expected JSON object: {path}')
    return value


def validate_correction(packet: dict) -> dict:
    if packet.get('schema') != 1 or packet.get('kind') != 'phase_b_user_correction':
        raise ValueError('not a Phase B correction packet')
    require_identifier(packet.get('id', ''), 'correction id')
    require_identifier(packet.get('decision_thread', ''), 'decision thread')
    require_commit(packet.get('project_head_at_recording', ''))
    observed = parse_timestamp(packet.get('observed_at', ''))
    recorded = parse_timestamp(packet.get('recorded_at', ''))
    if observed > recorded:
        raise ValueError('correction observed_at must not be later than recorded_at')
    text = packet.get('verbatim_text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('verbatim correction text must be non-empty')
    if sha256_bytes(text.encode()) != packet.get('verbatim_sha256'):
        raise ValueError('verbatim correction hash mismatch')
    source_ref = packet.get('source_ref')
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError('source_ref must be non-empty')
    return packet


def record_correction(root: Path, correction_id: str, decision_thread: str,
                      source_ref: str, observed_at: str, text: str,
                      project_head: str, clock: Callable[[], str] = utc_now) -> Path:
    require_identifier(correction_id, 'correction id')
    require_identifier(decision_thread, 'decision thread')
    require_commit(project_head)
    parse_timestamp(observed_at)
    recorded_at = clock()
    parse_timestamp(recorded_at)
    if not text.strip():
        raise ValueError('verbatim correction text must be non-empty')
    packet = {
        'schema': 1,
        'kind': 'phase_b_user_correction',
        'id': correction_id,
        'decision_thread': decision_thread,
        'source_ref': source_ref,
        'observed_at': observed_at,
        'recorded_at': recorded_at,
        'project_head_at_recording': project_head,
        'verbatim_sha256': sha256_bytes(text.encode()),
        'verbatim_text': text,
    }
    validate_correction(packet)
    path = root.resolve() / 'corrections' / f'{correction_id}.json'
    write_exclusive(path, packet)
    return path


def git_output(workspace: Path, *arguments: str) -> str:
    result = subprocess.run(['git', *arguments], cwd=workspace, text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f'git {" ".join(arguments)} failed in {workspace}: {result.stderr.strip()}')
    return result.stdout.rstrip('\r\n')


def workspace_snapshot(workspace: Path, expected_commit: str) -> dict:
    workspace = workspace.resolve()
    if not workspace.is_dir() or not (workspace / MARKER).is_file():
        raise ValueError(f'unmarked Phase B workspace: {workspace}')
    actual_commit = git_output(workspace, 'rev-parse', 'HEAD')
    if actual_commit != expected_commit:
        raise ValueError(f'workspace HEAD mismatch: {workspace}: {actual_commit}')
    status = git_output(workspace, 'status', '--porcelain=v1', '--untracked-files=all')
    changes = [line for line in status.splitlines()
               if line != f'?? {MARKER}']
    if changes:
        raise ValueError(f'workspace is not clean: {workspace}: {changes}')
    return {
        'path': str(workspace),
        'base_commit': actual_commit,
        'marker': MARKER,
        'porcelain': status.splitlines(),
    }


def validate_relative_paths(paths: list[str]) -> None:
    if not isinstance(paths, list) or not paths:
        raise ValueError('allowed_paths must not be empty')
    if not all(isinstance(value, str) for value in paths):
        raise ValueError('allowed_paths must contain strings')
    if len(paths) != len(set(paths)):
        raise ValueError('allowed_paths must not contain duplicates')
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or '..' in path.parts or value in ('', '.'):
            raise ValueError(f'unsafe allowed path: {value!r}')


def validate_freeze(packet: dict) -> dict:
    if packet.get('schema') != 1 or packet.get('kind') != 'phase_b_task_freeze':
        raise ValueError('not a Phase B task-freeze packet')
    require_identifier(packet.get('id', ''), 'episode id')
    require_identifier(packet.get('decision_thread', ''), 'decision thread')
    require_commit(packet.get('base_commit', ''))
    if packet.get('episode_kind') not in ('necessary_update', 'same_topic_control'):
        raise ValueError('invalid episode_kind')
    correction_recorded = parse_timestamp(packet.get('correction_recorded_at', ''))
    task_received = parse_timestamp(packet.get('task_received_at', ''))
    frozen = parse_timestamp(packet.get('frozen_at', ''))
    if not correction_recorded < task_received <= frozen:
        raise ValueError('required chronology is correction_recorded < task_received <= frozen')
    task_text = packet.get('task_text')
    if not isinstance(task_text, str) or not task_text.strip():
        raise ValueError('task text must be non-empty')
    if sha256_bytes(task_text.encode()) != packet.get('task_sha256'):
        raise ValueError('task text hash mismatch')
    correction_path_value = packet.get('correction_path')
    if not isinstance(correction_path_value, str):
        raise ValueError('correction_path must be a string')
    correction_path = Path(correction_path_value)
    if not correction_path.is_file():
        raise ValueError('referenced correction packet is missing')
    correction_raw = correction_path.read_bytes()
    if sha256_bytes(correction_raw) != packet.get('correction_packet_sha256'):
        raise ValueError('referenced correction packet hash mismatch')
    correction = validate_correction(json.loads(correction_raw))
    if (correction['id'] != packet.get('correction_id')
            or correction['decision_thread'] != packet['decision_thread']
            or correction['recorded_at'] != packet['correction_recorded_at']):
        raise ValueError('referenced correction metadata mismatch')
    validate_relative_paths(packet.get('allowed_paths', []))
    checker = packet.get('checker')
    if not isinstance(checker, list) or not checker or not all(
            isinstance(item, str) and item for item in checker):
        raise ValueError('checker must be a non-empty argv list')
    checker_artifacts = packet.get('checker_artifacts')
    if not isinstance(checker_artifacts, list) or not checker_artifacts:
        raise ValueError('at least one external checker artifact must be frozen')
    for artifact in checker_artifacts:
        if not isinstance(artifact, dict):
            raise ValueError('checker artifact must be an object')
        path_value = artifact.get('path')
        if not isinstance(path_value, str):
            raise ValueError('checker artifact path must be a string')
        path = Path(path_value)
        if not path.is_absolute() or not path.is_file():
            raise ValueError(f'frozen checker artifact is missing: {path}')
        if sha256_bytes(path.read_bytes()) != artifact.get('sha256'):
            raise ValueError(f'frozen checker artifact hash mismatch: {path}')
    execution = packet.get('execution')
    if (not isinstance(execution, dict) or execution.get('backend') != 'codex'
            or not isinstance(execution.get('model'), str) or not execution['model'].strip()
            or execution.get('effort') not in ('low', 'medium', 'high', 'xhigh')
            or not isinstance(execution.get('timeout_seconds'), int)
            or isinstance(execution.get('timeout_seconds'), bool)
            or execution['timeout_seconds'] <= 0):
        raise ValueError('invalid frozen execution configuration')
    snapshots = packet.get('workspaces', {})
    if not isinstance(snapshots, dict):
        raise ValueError('workspaces must be an object')
    if set(snapshots) != set(ARMS):
        raise ValueError(f'workspaces must contain exactly {ARMS}')
    if not all(isinstance(snapshots[arm], dict) for arm in ARMS):
        raise ValueError('workspace snapshots must be objects')
    if len({snapshots[arm].get('path') for arm in ARMS}) != len(ARMS):
        raise ValueError('arm workspaces must be distinct')
    if any(snapshots[arm].get('base_commit') != packet['base_commit'] for arm in ARMS):
        raise ValueError('arm base commits must match the frozen base')
    return packet


def freeze_episode(root: Path, correction_path: Path, episode_id: str,
                   episode_kind: str, task_received_at: str, task_text: str,
                   base_commit: str, allowed_paths: list[str], checker: list[str],
                   workspaces: dict[str, Path], model: str = 'gpt-5.6-sol',
                   effort: str = 'medium', timeout_seconds: int = 300,
                   clock: Callable[[], str] = utc_now) -> Path:
    correction_raw = correction_path.resolve().read_bytes()
    correction = validate_correction(json.loads(correction_raw))
    require_identifier(episode_id, 'episode id')
    require_commit(base_commit)
    validate_relative_paths(allowed_paths)
    if (not isinstance(checker, list) or not checker
            or not all(isinstance(item, str) and item for item in checker)):
        raise ValueError('checker must be a non-empty argv list')
    if episode_kind not in ('necessary_update', 'same_topic_control'):
        raise ValueError('invalid episode_kind')
    received = parse_timestamp(task_received_at)
    if received <= parse_timestamp(correction['recorded_at']):
        raise ValueError('later task must arrive after the correction was recorded')
    if set(workspaces) != set(ARMS):
        raise ValueError(f'workspaces must contain exactly {ARMS}')
    snapshots = {arm: workspace_snapshot(workspaces[arm], base_commit) for arm in ARMS}
    if len({item['path'] for item in snapshots.values()}) != len(ARMS):
        raise ValueError('arm workspaces must be distinct')
    frozen_at = clock()
    if parse_timestamp(frozen_at) < received:
        raise ValueError('freeze timestamp precedes task receipt')
    workspace_roots = [Path(item['path']) for item in snapshots.values()]
    checker_artifacts = []
    for value in checker[1:]:
        candidate = Path(value)
        if not candidate.is_absolute() or not candidate.is_file():
            continue
        candidate = candidate.resolve()
        if any(candidate == workspace or workspace in candidate.parents for workspace in workspace_roots):
            raise ValueError('checker artifacts must remain outside both agent workspaces')
        checker_artifacts.append({'path': str(candidate),
                                  'sha256': sha256_bytes(candidate.read_bytes())})
    if not checker_artifacts:
        raise ValueError('checker argv must name an absolute external checker file after argv[0]')
    packet = {
        'schema': 1,
        'kind': 'phase_b_task_freeze',
        'id': episode_id,
        'episode_kind': episode_kind,
        'decision_thread': correction['decision_thread'],
        'correction_id': correction['id'],
        'correction_path': str(correction_path.resolve()),
        'correction_packet_sha256': sha256_bytes(correction_raw),
        'correction_recorded_at': correction['recorded_at'],
        'task_received_at': task_received_at,
        'frozen_at': frozen_at,
        'task_text': task_text,
        'task_sha256': sha256_bytes(task_text.encode()),
        'base_commit': base_commit,
        'allowed_paths': allowed_paths,
        'checker': checker,
        'checker_artifacts': checker_artifacts,
        'execution': {'backend': 'codex', 'model': model, 'effort': effort,
                      'timeout_seconds': timeout_seconds},
        'workspaces': snapshots,
    }
    validate_freeze(packet)
    path = root.resolve() / 'freezes' / f'{episode_id}.json'
    write_exclusive(path, packet)
    return path


def natural_manifest(freeze_path: Path) -> dict:
    freeze_raw = freeze_path.resolve().read_bytes()
    freeze = validate_freeze(json.loads(freeze_raw))
    correction = validate_correction(load_json(Path(freeze['correction_path'])))
    if sha256_bytes(Path(freeze['correction_path']).read_bytes()) != freeze['correction_packet_sha256']:
        raise ValueError('correction changed after the task was frozen')
    execution = freeze['execution']
    manifest = {
        'schema': 1,
        'evaluation_mode': 'natural',
        'task_source': 'prospective natural user task',
        'arms': list(ARMS),
        'backend': execution['backend'],
        'model': execution['model'],
        'effort': execution['effort'],
        'timeout_seconds': execution['timeout_seconds'],
        'instruction_mode': 'project',
        'max_context_bytes': 12000,
        'enforce_change_paths': True,
        'phase_b_freeze_path': str(freeze_path.resolve()),
        'phase_b_freeze_sha256': sha256_bytes(freeze_raw),
        'clusters': [{
            'id': freeze['id'],
            'source': {
                'kind': 'user_correction',
                'ref': correction['source_ref'],
                'packet_sha256': freeze['correction_packet_sha256'],
            },
            'base_commit': freeze['base_commit'],
            'forbidden_commits': [],
            'workspaces': {arm: freeze['workspaces'][arm]['path'] for arm in ARMS},
            'steps': [{
                'id': freeze['id'],
                'kind': freeze['episode_kind'],
                'prompt': freeze['task_text'],
                'paths': freeze['allowed_paths'],
                'history': [correction['verbatim_text']],
                'checker': freeze['checker'],
            }],
        }],
    }
    return manifest


def evidence_tree(root: Path) -> list[dict]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f'result directory is missing: {root}')
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'symlink is not allowed in sealed evidence: {path}')
        if path.is_file():
            raw = path.read_bytes()
            files.append({'path': path.relative_to(root).as_posix(), 'bytes': len(raw),
                          'sha256': sha256_bytes(raw)})
    if not files:
        raise ValueError('result directory contains no evidence files')
    return files


def validate_patch_audit(audit: dict, episode_id: str, freeze_sha256: str,
                         frozen_at: str) -> dict:
    if audit.get('schema') != 1 or audit.get('kind') != 'phase_b_patch_audit':
        raise ValueError('not a Phase B patch-audit packet')
    if audit.get('episode_id') != episode_id or audit.get('freeze_sha256') != freeze_sha256:
        raise ValueError('patch audit does not bind the frozen episode')
    if parse_timestamp(audit.get('audited_at', '')) < parse_timestamp(frozen_at):
        raise ValueError('patch audit predates task freeze')
    if not isinstance(audit.get('auditor'), str) or not audit['auditor'].strip():
        raise ValueError('patch audit needs an auditor identifier')
    if audit.get('verdict') not in ('valid', 'invalid'):
        raise ValueError('patch audit verdict must be valid or invalid')
    checks = audit.get('checks')
    required = ('checker_semantics_complete', 'both_patches_reviewed',
                'no_cross_arm_contamination', 'declared_scope_respected')
    if not isinstance(checks, dict) or any(not isinstance(checks.get(key), bool) for key in required):
        raise ValueError(f'patch audit needs boolean checks: {required}')
    if audit['verdict'] == 'valid' and not all(checks[key] for key in required):
        raise ValueError('a valid patch audit requires every audit check to pass')
    if not isinstance(audit.get('notes'), str):
        raise ValueError('patch audit notes must be a string')
    return audit


def validate_natural_results(freeze_path: Path, results: Path) -> tuple[dict, list[dict], dict]:
    expected_manifest = natural_manifest(freeze_path)
    actual_manifest = load_json(results / 'manifest.json')
    if actual_manifest != expected_manifest:
        raise ValueError('result manifest differs from the frozen natural manifest')
    receipt_path = results / 'receipts.jsonl'
    try:
        rows = [json.loads(line) for line in receipt_path.read_text().splitlines() if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError('natural result receipts are missing or malformed') from error
    freeze = validate_freeze(load_json(freeze_path))
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError('every natural receipt must be an object')
    observed_arms = [row.get('arm') for row in rows]
    if (not rows or len(rows) > len(ARMS) or len(observed_arms) != len(set(observed_arms))
            or not set(observed_arms) <= set(ARMS)):
        raise ValueError('natural results need at most one receipt for each known arm')
    for row in rows:
        arm = row['arm']
        if (row.get('task_id') != freeze['id'] or row.get('cluster_id') != freeze['id']
                or row.get('kind') != freeze['episode_kind']
                or row.get('base_commit') != freeze['base_commit']
                or row.get('changes_before') != []
                or row.get('context_mode') != ('off' if arm == 'no_history' else 'raw')
                or row.get('history_count') != (0 if arm == 'no_history' else 1)):
            raise ValueError(f'natural receipt does not match freeze for {arm}')
        if (not isinstance(row.get('checker_pass'), bool)
                or not isinstance(row.get('severe_regression'), bool)
                or not isinstance(row.get('filesystem_isolated'), bool)
                or not isinstance(row.get('unexpected_changes'), list)
                or not isinstance(row.get('visibility_violations'), list)
                or row.get('usage') is not None and not isinstance(row.get('usage'), dict)):
            raise ValueError(f'natural receipt has malformed audit fields for {arm}')
    from failure_discovery_runner import summarize
    expected_summary = summarize(rows, expected_manifest)
    actual_summary = load_json(results / 'summary.json')
    if actual_summary != expected_summary:
        raise ValueError('natural result summary does not recompute from raw receipts')
    return freeze, rows, actual_summary


def outcome_fields(freeze: dict, rows: list[dict], summary: dict,
                   results: Path, audit: dict) -> dict:
    invalid_files = sorted(path.name for path in results.iterdir()
                           if path.name.startswith('INVALID_') and path.is_file())
    mechanically_valid = (len(rows) == len(ARMS) and {row['arm'] for row in rows} == set(ARMS)
                          and summary.get('complete') is True and not invalid_files
                          and all(row.get('status') == 'completed'
                                  and row.get('checker_status') == 'completed'
                                  and row.get('filesystem_isolated') is True
                                  and not row.get('visibility_violations')
                                  and not row.get('unexpected_changes')
                                  and isinstance(row.get('usage'), dict) and bool(row['usage'])
                                  for row in rows))
    by_arm = {row['arm']: row for row in rows}
    quality_comparable = (set(by_arm) == set(ARMS)
                          and all(row.get('status') == 'completed'
                                  and row.get('checker_status') == 'completed'
                                  and row.get('filesystem_isolated') is True
                                  and not row.get('visibility_violations')
                                  and not row.get('unexpected_changes') for row in rows))
    if quality_comparable:
        no_history = by_arm['no_history']['checker_pass'] is True
        raw_full = by_arm['raw_full']['checker_pass'] is True
        comparison = ('win' if raw_full and not no_history else
                      'loss' if no_history and not raw_full else 'tie')
    else:
        comparison = 'indeterminate'
    return {
        'id': freeze['id'],
        'decision_thread': freeze['decision_thread'],
        'episode_kind': freeze['episode_kind'],
        'status': 'eligible' if mechanically_valid and audit['verdict'] == 'valid' else 'invalid',
        'comparison': comparison,
        'checker_pass': {arm: (by_arm[arm].get('checker_pass') is True if arm in by_arm else None)
                         for arm in ARMS},
        'severe_regression': any(row.get('severe_regression') is True for row in rows),
        'invalid_files': invalid_files,
    }


def seal_outcome(root: Path, freeze_path: Path, results: Path, audit_path: Path,
                 clock: Callable[[], str] = utc_now) -> Path:
    freeze_raw = freeze_path.resolve().read_bytes()
    freeze_sha = sha256_bytes(freeze_raw)
    freeze, rows, summary = validate_natural_results(freeze_path.resolve(), results.resolve())
    audit_raw = audit_path.resolve().read_bytes()
    audit = validate_patch_audit(json.loads(audit_raw), freeze['id'], freeze_sha,
                                 freeze['frozen_at'])
    fields = outcome_fields(freeze, rows, summary, results, audit)
    packet = {
        'schema': 1,
        'kind': 'phase_b_sealed_outcome',
        **fields,
        'freeze_path': str(freeze_path.resolve()),
        'freeze_sha256': freeze_sha,
        'results_path': str(results.resolve()),
        'results_files': evidence_tree(results),
        'audit_path': str(audit_path.resolve()),
        'audit_sha256': sha256_bytes(audit_raw),
        'sealed_at': clock(),
    }
    if parse_timestamp(packet['sealed_at']) < parse_timestamp(audit['audited_at']):
        raise ValueError('outcome seal predates patch audit')
    path = root.resolve() / 'outcomes' / f"{freeze['id']}.json"
    write_exclusive(path, packet)
    return path


def validate_sealed_outcome(outcome: dict) -> dict:
    if outcome.get('schema') != 1 or outcome.get('kind') != 'phase_b_sealed_outcome':
        raise ValueError('not a sealed Phase B outcome')
    require_identifier(outcome.get('id', ''), 'outcome id')
    path_values = {key: outcome.get(key) for key in ('freeze_path', 'results_path', 'audit_path')}
    if not all(isinstance(value, str) and value for value in path_values.values()):
        raise ValueError('sealed outcome evidence paths must be non-empty strings')
    freeze_path = Path(path_values['freeze_path'])
    results_path = Path(path_values['results_path'])
    audit_path = Path(path_values['audit_path'])
    if not freeze_path.is_file() or sha256_bytes(freeze_path.read_bytes()) != outcome.get('freeze_sha256'):
        raise ValueError('sealed outcome freeze evidence is missing or changed')
    if not audit_path.is_file() or sha256_bytes(audit_path.read_bytes()) != outcome.get('audit_sha256'):
        raise ValueError('sealed outcome audit evidence is missing or changed')
    freeze, rows, summary = validate_natural_results(freeze_path, results_path)
    audit = validate_patch_audit(load_json(audit_path), freeze['id'], outcome['freeze_sha256'],
                                 freeze['frozen_at'])
    if outcome.get('results_files') != evidence_tree(results_path):
        raise ValueError('sealed outcome result evidence changed')
    expected = outcome_fields(freeze, rows, summary, results_path, audit)
    for key, value in expected.items():
        if outcome.get(key) != value:
            raise ValueError(f'sealed outcome field mismatch for {key}')
    if parse_timestamp(outcome.get('sealed_at', '')) < parse_timestamp(audit['audited_at']):
        raise ValueError('outcome seal predates patch audit')
    return outcome


def append_outcome(registry_path: Path, outcome_path: Path) -> dict:
    outcome_raw = outcome_path.resolve().read_bytes()
    outcome = validate_sealed_outcome(json.loads(outcome_raw))
    lock_path = registry_path.resolve().with_suffix(registry_path.suffix + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        registry = validate_registry(registry_path.resolve())
        if any(item['id'] == outcome['id'] for item in registry['attempts']):
            raise ValueError(f'outcome already registered: {outcome["id"]}')
        row = {
            'id': outcome['id'],
            'decision_thread': outcome['decision_thread'],
            'kind': outcome['episode_kind'],
            'status': outcome['status'],
            'comparison': outcome['comparison'],
            'severe_regression': outcome['severe_regression'],
            'outcome_path': str(outcome_path.resolve()),
            'outcome_sha256': sha256_bytes(outcome_raw),
        }
        registry['attempts'].append(row)
        if outcome['status'] == 'eligible':
            registry['episodes'].append(row.copy())
        registry['attempts_total'] = len(registry['attempts'])
        registry['invalid_attempts'] = sum(item['status'] == 'invalid' for item in registry['attempts'])
        registry['eligible_sequences'] = len(registry['episodes'])
        registry['decision_threads'] = len({item['decision_thread'] for item in registry['episodes']})
        registry['natural_controls'] = sum(item['kind'] == 'same_topic_control'
                                           for item in registry['episodes'])
        if (registry['eligible_sequences'] >= registry['target_sequences']
                and registry['decision_threads'] >= registry['minimum_decision_threads']
                and registry['natural_controls'] >= registry['minimum_natural_controls']):
            registry['status'] = 'ready_for_decision'
        validate_registry_value(registry)
        with tempfile.NamedTemporaryFile('wb', dir=registry_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(registry, ensure_ascii=False, indent=2).encode() + b'\n')
        os.replace(temporary, registry_path)
        return registry


def validate_registry_value(registry: dict) -> dict:
    if registry.get('schema') != 1 or registry.get('protocol') != 'topic3-be-route-v2-phase-b-natural':
        raise ValueError('unexpected Phase B registry schema or protocol')
    attempts = registry.get('attempts')
    episodes = registry.get('episodes')
    if not isinstance(attempts, list) or not isinstance(episodes, list):
        raise ValueError('attempts and episodes must be lists')
    for item in attempts:
        if not isinstance(item, dict):
            raise ValueError('registry attempt must be an object')
        require_identifier(item.get('id', ''), 'attempt id')
        require_identifier(item.get('decision_thread', ''), 'decision thread')
        if item.get('kind') not in ('necessary_update', 'same_topic_control'):
            raise ValueError('invalid registry attempt kind')
        if item.get('status') not in ('eligible', 'invalid'):
            raise ValueError('invalid registry attempt status')
        if item.get('comparison') not in ('win', 'loss', 'tie', 'indeterminate'):
            raise ValueError('invalid registry attempt comparison')
        if not isinstance(item.get('severe_regression'), bool):
            raise ValueError('registry severe_regression must be boolean')
        outcome_path_value = item.get('outcome_path')
        outcome_sha = item.get('outcome_sha256')
        if (not isinstance(outcome_path_value, str) or not Path(outcome_path_value).is_absolute()
                or not isinstance(outcome_sha, str) or len(outcome_sha) != 64):
            raise ValueError('registry attempt needs an absolute outcome path and SHA-256')
        outcome_path = Path(outcome_path_value)
        if not outcome_path.is_file() or sha256_bytes(outcome_path.read_bytes()) != outcome_sha:
            raise ValueError(f'registered outcome evidence is missing or changed: {outcome_path}')
        sealed = validate_sealed_outcome(load_json(outcome_path))
        bound = {
            'id': sealed['id'], 'decision_thread': sealed['decision_thread'],
            'kind': sealed['episode_kind'], 'status': sealed['status'],
            'comparison': sealed['comparison'], 'severe_regression': sealed['severe_regression'],
            'outcome_path': str(outcome_path), 'outcome_sha256': outcome_sha,
        }
        if item != bound:
            raise ValueError('registry attempt differs from its sealed outcome')
    attempt_ids = [item['id'] for item in attempts]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ValueError('duplicate attempt id')
    eligible_attempts = [item for item in attempts if item['status'] == 'eligible']
    if episodes != eligible_attempts:
        raise ValueError('episodes must exactly equal eligible attempts in append order')
    threads = {episode['decision_thread'] for episode in episodes}
    controls = sum(episode['kind'] == 'same_topic_control' for episode in episodes)
    expected = {
        'attempts_total': len(attempts),
        'invalid_attempts': len(attempts) - len(eligible_attempts),
        'eligible_sequences': len(episodes),
        'decision_threads': len(threads),
        'natural_controls': controls,
    }
    for key, value in expected.items():
        if registry.get(key) != value:
            raise ValueError(f'derived registry count mismatch for {key}: {registry.get(key)} != {value}')
    for key in ('target_sequences', 'minimum_decision_threads', 'minimum_natural_controls'):
        if (not isinstance(registry.get(key), int) or isinstance(registry.get(key), bool)
                or registry[key] <= 0):
            raise ValueError(f'invalid registry threshold: {key}')
    ready = (len(episodes) >= registry['target_sequences']
             and len(threads) >= registry['minimum_decision_threads']
             and controls >= registry['minimum_natural_controls'])
    expected_status = 'ready_for_decision' if ready else 'collecting'
    if registry.get('status') != expected_status:
        raise ValueError(f'registry status mismatch: {registry.get("status")} != {expected_status}')
    return registry


def validate_registry(path: Path) -> dict:
    registry = load_json(path)
    return validate_registry_value(registry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='action', required=True)
    record = subparsers.add_parser('record-correction')
    record.add_argument('--root', type=Path, required=True)
    record.add_argument('--id', required=True)
    record.add_argument('--decision-thread', required=True)
    record.add_argument('--source-ref', required=True)
    record.add_argument('--observed-at', required=True)
    record.add_argument('--text-file', type=Path, required=True)
    record.add_argument('--project-head', required=True)
    record.add_argument('--project-root', type=Path, default=Path.cwd())
    freeze = subparsers.add_parser('freeze-task')
    freeze.add_argument('--root', type=Path, required=True)
    freeze.add_argument('--correction', type=Path, required=True)
    freeze.add_argument('--id', required=True)
    freeze.add_argument('--episode-kind', choices=('necessary_update', 'same_topic_control'), required=True)
    freeze.add_argument('--task-received-at', required=True)
    freeze.add_argument('--task-file', type=Path, required=True)
    freeze.add_argument('--base-commit', required=True)
    freeze.add_argument('--allowed-path', action='append', required=True)
    freeze.add_argument('--checker-json', type=Path, required=True)
    freeze.add_argument('--no-history-workspace', type=Path, required=True)
    freeze.add_argument('--raw-full-workspace', type=Path, required=True)
    freeze.add_argument('--model', required=True)
    freeze.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh'), required=True)
    freeze.add_argument('--timeout-seconds', type=int, default=300)
    manifest = subparsers.add_parser('build-manifest')
    manifest.add_argument('--freeze', type=Path, required=True)
    manifest.add_argument('--output', type=Path, required=True)
    seal = subparsers.add_parser('seal-outcome')
    seal.add_argument('--root', type=Path, required=True)
    seal.add_argument('--freeze', type=Path, required=True)
    seal.add_argument('--results', type=Path, required=True)
    seal.add_argument('--audit', type=Path, required=True)
    append = subparsers.add_parser('append-outcome')
    append.add_argument('--registry', type=Path, required=True)
    append.add_argument('--outcome', type=Path, required=True)
    validate = subparsers.add_parser('validate')
    validate.add_argument('path', type=Path)
    arguments = parser.parse_args()
    if arguments.action == 'record-correction':
        actual_head = git_output(arguments.project_root.resolve(), 'rev-parse', 'HEAD')
        if actual_head != arguments.project_head:
            raise ValueError(f'project-head is not current HEAD: {arguments.project_head} != {actual_head}')
        output = record_correction(arguments.root, arguments.id, arguments.decision_thread,
                                   arguments.source_ref, arguments.observed_at,
                                   arguments.text_file.read_bytes().decode('utf-8'), arguments.project_head)
        print(output)
    elif arguments.action == 'freeze-task':
        checker = json.loads(arguments.checker_json.read_text())
        output = freeze_episode(
            arguments.root, arguments.correction, arguments.id, arguments.episode_kind,
            arguments.task_received_at, arguments.task_file.read_bytes().decode('utf-8'),
            arguments.base_commit, arguments.allowed_path, checker,
            {'no_history': arguments.no_history_workspace,
             'raw_full': arguments.raw_full_workspace},
            model=arguments.model, effort=arguments.effort,
            timeout_seconds=arguments.timeout_seconds,
        )
        print(output)
    elif arguments.action == 'build-manifest':
        write_exclusive(arguments.output.resolve(), natural_manifest(arguments.freeze))
        print(arguments.output.resolve())
    elif arguments.action == 'seal-outcome':
        print(seal_outcome(arguments.root, arguments.freeze, arguments.results,
                           arguments.audit))
    elif arguments.action == 'append-outcome':
        value = append_outcome(arguments.registry, arguments.outcome)
        print(json.dumps({key: value[key] for key in
                          ('status', 'attempts_total', 'invalid_attempts', 'eligible_sequences',
                           'decision_threads', 'natural_controls')}))
    else:
        value = load_json(arguments.path)
        kind = value.get('kind')
        if kind == 'phase_b_user_correction':
            validate_correction(value)
        elif kind == 'phase_b_task_freeze':
            validate_freeze(value)
        elif kind == 'phase_b_sealed_outcome':
            validate_sealed_outcome(value)
        else:
            validate_registry(arguments.path)
        print(arguments.path.resolve())


if __name__ == '__main__':
    main()
