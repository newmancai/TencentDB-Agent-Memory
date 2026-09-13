"""Paired Codex oracle-memory intervention with deterministic checking."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


MODEL = "gpt-5.6-sol"
REASONING = "medium"
TASKS = [
    ("atlas", "health_endpoint", "/readyz-a7"),
    ("juniper", "retry_delay_ms", "1375"),
    ("kestrel", "retention_days", "47"),
    ("mica", "artifact_suffix", ".bundle-v3"),
    ("nimbus", "region_failover", "ap-south-2"),
    ("quartz", "batch_limit", "73"),
    ("redwood", "report_timezone", "Pacific/Chatham"),
    ("solace", "routing_header", "X-Solace-Route"),
]


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write_jsonl(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    stream.flush()


def usage(events_path):
    final = None
    event_types = {}
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("type", "unknown")
        event_types[kind] = event_types.get(kind, 0) + 1
        if kind == "turn.completed":
            final = event.get("usage")
    return final, event_types


def decision(record_id, context_id, task_id, candidate_ids, action, selected_ids,
             propensity, decided_at, spans, output_id, policy):
    return {
        "kind": "decision_trace", "schema": 1, "id": record_id,
        "contextId": context_id, "taskId": task_id,
        "contextEventIds": [f"{context_id}:request"],
        "candidateMemoryIds": candidate_ids, "action": action,
        "selectedMemoryIds": selected_ids, "policyVersion": policy,
        "propensity": propensity, "decidedAt": decided_at,
        "promptMemorySpans": spans, "outputIds": [output_id], "toolCallIds": [],
    }


def source_records(project, setting, value):
    context_id = f"{project}:source"
    decision_id = f"{context_id}:decision"
    answer_id = f"{context_id}:answer"
    feedback_id = f"{context_id}:feedback"
    assertion_id = f"{project}:{setting}:assertion"
    return [
        decision(decision_id, context_id, context_id, [f"{project}:{setting}:old"],
                 "include", [f"{project}:{setting}:old"], 1, now(),
                 [{"memoryId": f"{project}:{setting}:old", "start": 0, "end": 1}],
                 answer_id, "scripted-source:v1"),
        {
            "kind": "feedback_claim", "schema": 1, "id": feedback_id,
            "decisionId": decision_id, "observationType": "explicit_correction",
            "targetType": "answer_span", "targetIds": [f"{answer_id}:value"],
            "claimText": f"For {project}, {setting} is {value}.",
            "scope": f"project={project}", "authority": "explicit_user", "confidence": 1,
            "sourceEventIds": [f"{context_id}:user-correction"], "observedAt": now(),
        },
        {
            "kind": "memory_assertion", "schema": 1, "id": assertion_id,
            "subject": project, "predicate": setting, "value": value,
            "scope": f"project={project}", "validFrom": now(), "validTo": None,
            "recordedAt": now(), "supersededAt": None, "status": "verified",
            "authority": "explicit_user", "sourceEventIds": [f"{context_id}:user-correction"],
            "supportedByClaimIds": [feedback_id], "contradictsAssertionIds": [],
        },
        {
            "kind": "outcome", "schema": 1, "id": f"{context_id}:outcome",
            "decisionId": decision_id, "result": "failure", "reward": 0,
            "metrics": {"correctedByUser": True}, "source": "scripted-explicit-correction",
            "observedAt": now(), "delayed": True,
        },
    ]


def prompt(project, setting, assertion, arm):
    memory = ""
    if arm == "include":
        memory = "<memory_assertion>\n" + json.dumps(assertion, ensure_ascii=False) + "\n</memory_assertion>"
    else:
        memory = "<memory_assertion>\nnone supplied\n</memory_assertion>"
    text = f"""Perform one isolated configuration lookup. Do not call tools, browse, inspect files, or execute commands.
Use only the current request and the optional memory assertion. Do not infer an established value from general knowledge.
If no applicable assertion supplies the value, return the literal string \"unknown\" as value.

{memory}

Current request: Return the established value of setting {setting} for project {project}.
Return only JSON matching the supplied schema."""
    return text, memory


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    raw = out / "raw"
    raw.mkdir()
    sandbox = out / "empty-workdir"
    sandbox.mkdir()
    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in ["project", "setting", "value"]},
        "required": ["project", "setting", "value"],
        "additionalProperties": False,
    }
    (out / "output-schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "tasks.jsonl").write_text("".join(json.dumps({
        "id": project, "project": project, "setting": setting, "expected": value,
        "split": "synthetic_development",
    }) + "\n" for project, setting, value in TASKS))

    receipts = []
    with (out / "trace.jsonl").open("x") as trace, (out / "inputs.jsonl").open("x") as inputs, \
            (out / "receipts.jsonl").open("x") as receipt_stream:
        for task_index, (project, setting, expected) in enumerate(TASKS):
            source = source_records(project, setting, expected)
            for row in source:
                write_jsonl(trace, row)
            assertion = source[2]
            order = sorted(["include", "omit"], key=lambda arm: digest(
                f"oracle-attribution-v1:{project}:{arm}"))
            for slot, arm in enumerate(order):
                task_id = f"{project}:future"
                execution_id = f"{task_id}:slot-{slot}:{arm}"
                output_id = f"{execution_id}:output"
                text, memory_block = prompt(project, setting, assertion, arm)
                spans = []
                selected = []
                if arm == "include":
                    start = text.index(memory_block)
                    spans = [{"memoryId": assertion["id"], "start": start, "end": start + len(memory_block)}]
                    selected = [assertion["id"]]
                trace_decision = decision(
                    f"{execution_id}:decision", execution_id, task_id, [assertion["id"]],
                    arm, selected, 0.5, now(), spans, output_id,
                    "oracle-attribution-blocked-random-v1",
                )
                write_jsonl(trace, trace_decision)
                write_jsonl(inputs, {"id": execution_id, "arm": arm, "prompt": text})
                stem = f"{task_index:02d}-{project}-{slot}-{arm}"
                events_path = raw / f"{stem}.events.jsonl"
                message_path = raw / f"{stem}.message.json"
                stderr_path = raw / f"{stem}.stderr.txt"
                command = [
                    "codex", "exec", "--model", MODEL,
                    "-c", f'model_reasoning_effort="{REASONING}"',
                    "--sandbox", "read-only", "-C", str(sandbox.resolve()),
                    "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                    "--output-schema", str((out / "output-schema.json").resolve()),
                    "--json", "--output-last-message", str(message_path.resolve()), "-",
                ]
                started_at = now()
                started = time.perf_counter()
                timed_out = False
                with events_path.open("x") as stdout, stderr_path.open("x") as stderr:
                    try:
                        completed = subprocess.run(command, input=text, text=True, stdout=stdout,
                                                   stderr=stderr, timeout=300, check=False)
                        returncode = completed.returncode
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        returncode = None
                wall_seconds = time.perf_counter() - started
                event_usage, event_types = usage(events_path)
                raw_message = message_path.read_text() if message_path.exists() else ""
                parsed = None
                try:
                    parsed = json.loads(raw_message)
                except (json.JSONDecodeError, TypeError):
                    pass
                success = returncode == 0 and parsed == {
                    "project": project, "setting": setting, "value": expected,
                }
                result = "success" if success else ("unknown" if returncode != 0 or parsed is None else "failure")
                reward = 1 if success else (None if result == "unknown" else 0)
                outcome = {
                    "kind": "outcome", "schema": 1, "id": f"{execution_id}:outcome",
                    "decisionId": trace_decision["id"], "result": result, "reward": reward,
                    "metrics": {"exactMatch": success, "returncode": returncode,
                                "timedOut": timed_out, "parsed": parsed is not None},
                    "source": "deterministic-json-checker", "observedAt": now(), "delayed": False,
                }
                write_jsonl(trace, outcome)
                receipt = {
                    "id": execution_id, "project": project, "setting": setting,
                    "expected": expected, "arm": arm, "slot": slot,
                    "model": MODEL, "reasoning_effort": REASONING,
                    "started_at": started_at, "returncode": returncode,
                    "timed_out": timed_out, "wall_seconds": wall_seconds,
                    "usage": event_usage, "event_types": event_types,
                    "parsed": parsed, "success": success,
                }
                receipts.append(receipt)
                write_jsonl(receipt_stream, receipt)
                print(project, slot, arm, returncode, success, event_usage, flush=True)

    by_task = {project: {} for project, _, _ in TASKS}
    for row in receipts:
        by_task[row["project"]][row["arm"]] = row["success"]
    include_success = sum(row["include"] for row in by_task.values())
    omit_success = sum(row["omit"] for row in by_task.values())
    wins = sum(row["include"] and not row["omit"] for row in by_task.values())
    losses = sum(row["omit"] and not row["include"] for row in by_task.values())
    ties = len(TASKS) - wins - losses
    summary = {
        "protocol": "topic3-b-oracle-attribution-v1",
        "model": MODEL, "reasoning_effort": REASONING,
        "cli_version": subprocess.run(["codex", "--version"], text=True,
                                      capture_output=True, check=True).stdout.strip(),
        "tasks": len(TASKS), "planned_calls": 2 * len(TASKS),
        "completed_calls": sum(row["returncode"] == 0 for row in receipts),
        "include_success": include_success, "omit_success": omit_success,
        "paired": {"wins": wins, "losses": losses, "ties": ties},
        "threshold": {"include_success_required": 7, "paired_net_wins_required": 6},
        "advance_to_scope": include_success >= 7 and wins - losses >= 6,
        "wall_seconds": sum(row["wall_seconds"] for row in receipts),
        "usage": {},
        "scope": "Oracle target/scope/authority and synthetic development tasks. Exact JSON checker; no LLM judge. Not automatic feedback learning or production gain.",
    }
    for key in ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]:
        summary["usage"][key] = sum((row["usage"] or {}).get(key, 0) for row in receipts)
    (out / "execution-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)
