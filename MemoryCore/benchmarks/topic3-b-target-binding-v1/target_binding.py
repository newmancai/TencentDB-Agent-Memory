"""One-pass Codex target binder on fixed synthetic development cases."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


MODEL = "gpt-5.6-sol"
REASONING = "medium"


def c(id_, subject, predicate, value, scope):
    return {"id": id_, "subject": subject, "predicate": predicate, "value": value, "scope": scope}


CASES = [
    {"id": "atlas-endpoint", "kind": "identifiable",
     "candidates": [c("atlas-health", "atlas", "health_endpoint", "/health", "project=atlas"), c("atlas-port", "atlas", "port", 8080, "project=atlas"), c("juniper-health", "juniper", "health_endpoint", "/healthz", "project=juniper")],
     "answer": "Atlas uses /health for readiness.", "feedback": "For Atlas, readiness must use /readyz-a7, not /health.", "expected": ["atlas-health"]},
    {"id": "kestrel-retention", "kind": "identifiable",
     "candidates": [c("kestrel-retention", "kestrel", "retention_days", 30, "project=kestrel"), c("kestrel-timeout", "kestrel", "timeout_seconds", 30, "project=kestrel"), c("mica-retention", "mica", "retention_days", 90, "project=mica")],
     "answer": "Kestrel retains logs for 30 days.", "feedback": "Change Kestrel log retention to 47 days.", "expected": ["kestrel-retention"]},
    {"id": "mica-suffix", "kind": "identifiable",
     "candidates": [c("mica-suffix", "mica", "artifact_suffix", ".zip", "project=mica"), c("mica-prefix", "mica", "artifact_prefix", "rel-", "project=mica"), c("quartz-suffix", "quartz", "artifact_suffix", ".tar", "project=quartz")],
     "answer": "The Mica artifact is release.zip.", "feedback": "Mica packages should end in .bundle-v3 instead.", "expected": ["mica-suffix"]},
    {"id": "nimbus-region", "kind": "identifiable",
     "candidates": [c("nimbus-primary", "nimbus", "primary_region", "eu-west-1", "project=nimbus"), c("nimbus-failover", "nimbus", "region_failover", "us-east-2", "project=nimbus"), c("atlas-failover", "atlas", "region_failover", "us-west-1", "project=atlas")],
     "answer": "Nimbus fails over to us-east-2.", "feedback": "Our Nimbus failover region is ap-south-2 now.", "expected": ["nimbus-failover"]},
    {"id": "quartz-batch", "kind": "identifiable",
     "candidates": [c("quartz-batch", "quartz", "batch_limit", 50, "project=quartz"), c("quartz-retries", "quartz", "retry_count", 5, "project=quartz"), c("solace-batch", "solace", "batch_limit", 100, "project=solace")],
     "answer": "Quartz processes 50 items per batch.", "feedback": "Set the Quartz batch limit to 73.", "expected": ["quartz-batch"]},
    {"id": "redwood-timezone", "kind": "identifiable",
     "candidates": [c("redwood-timezone", "redwood", "report_timezone", "UTC", "project=redwood"), c("redwood-locale", "redwood", "report_locale", "en-US", "project=redwood"), c("atlas-timezone", "atlas", "report_timezone", "Asia/Tokyo", "project=atlas")],
     "answer": "Redwood reports are scheduled in UTC.", "feedback": "Please use Pacific/Chatham for Redwood reports.", "expected": ["redwood-timezone"]},
    {"id": "solace-header", "kind": "identifiable",
     "candidates": [c("solace-header", "solace", "routing_header", "X-Route", "project=solace"), c("solace-token", "solace", "token_header", "Authorization", "project=solace"), c("nimbus-header", "nimbus", "routing_header", "X-Nimbus", "project=nimbus")],
     "answer": "Send Solace routing in X-Route.", "feedback": "The Solace routing header should be X-Solace-Route.", "expected": ["solace-header"]},
    {"id": "python-runtime", "kind": "identifiable",
     "candidates": [c("python-runtime", "sdk", "python_runtime", "3.11", "language=python"), c("python-linter", "sdk", "python_linter", "ruff", "language=python"), c("node-runtime", "sdk", "node_runtime", "22", "language=node")],
     "answer": "Use Python 3.11 for this SDK.", "feedback": "This SDK has moved to CPython 3.13.", "expected": ["python-runtime"]},
    {"id": "vague-retry", "kind": "reject",
     "candidates": [c("vague-endpoint", "atlas", "health_endpoint", "/health", "project=atlas"), c("vague-port", "atlas", "port", 8080, "project=atlas"), c("vague-timeout", "atlas", "timeout", 30, "project=atlas")],
     "answer": "Atlas uses /health on port 8080 with a 30 second timeout.", "feedback": "This is still wrong. Try again.", "expected": []},
    {"id": "environment-failure", "kind": "reject",
     "candidates": [c("env-region", "nimbus", "region", "eu-west-1", "project=nimbus"), c("env-retries", "nimbus", "retry_count", 3, "project=nimbus"), c("env-timeout", "nimbus", "timeout", 20, "project=nimbus")],
     "answer": "Deploy Nimbus to eu-west-1 with three retries.", "feedback": "Deployment failed because the temporary credentials expired.", "expected": []},
    {"id": "style-only", "kind": "reject",
     "candidates": [c("style-port", "mica", "port", 7000, "project=mica"), c("style-region", "mica", "region", "us-west-2", "project=mica"), c("style-owner", "mica", "owner", "platform", "project=mica")],
     "answer": "Mica uses port 7000 in us-west-2 and is owned by platform.", "feedback": "Make the explanation friendlier and less abrupt.", "expected": []},
    {"id": "ambiguous-number", "kind": "reject",
     "candidates": [c("ambiguous-timeout", "quartz", "timeout", 30, "project=quartz"), c("ambiguous-retention", "quartz", "retention_days", 30, "project=quartz"), c("ambiguous-batch", "quartz", "batch_limit", 50, "project=quartz")],
     "answer": "Quartz uses 30 seconds, keeps records for 30 days, and batches 50 items.", "feedback": "Use 60 instead.", "expected": []},
]


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    stream.flush()


def parse_usage(path):
    final = None
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "turn.completed":
            final = event.get("usage")
    return final


def assertion_record(case_id, item, index):
    return {"kind": "memory_assertion", "schema": 1, "id": f"{case_id}:candidate-{index + 1}",
            "subject": item["subject"], "predicate": item["predicate"], "value": item["value"],
            "scope": item["scope"], "validFrom": None, "validTo": None, "recordedAt": now(),
            "supersededAt": None, "status": "candidate", "authority": "explicit_user",
            "sourceEventIds": [f"{case_id}:{item['id']}:source"],
            "supportedByClaimIds": [], "contradictsAssertionIds": []}


def decision(id_, candidates, action, selected, output):
    return {"kind": "decision_trace", "schema": 1, "id": id_, "contextId": id_.rsplit(":", 1)[0],
            "taskId": id_.split(":", 1)[0], "contextEventIds": [f"{id_}:input"],
            "candidateMemoryIds": candidates, "action": action, "selectedMemoryIds": selected,
            "policyVersion": "codex-target-binder:v1", "propensity": 1, "decidedAt": now(),
            "promptMemorySpans": [], "outputIds": [output], "toolCallIds": []}


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    raw = out / "raw"; raw.mkdir()
    sandbox = out / "empty-workdir"; sandbox.mkdir()
    schema = {"type": "object", "properties": {"target_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["target_ids"], "additionalProperties": False}
    (out / "output-schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "cases.private.json").write_text(json.dumps(CASES, indent=2) + "\n")
    receipts = []
    with (out / "inputs.jsonl").open("x") as inputs, (out / "receipts.jsonl").open("x") as receipt_file, (out / "trace.jsonl").open("x") as trace:
        for index, case in enumerate(CASES):
            assertions = [assertion_record(case["id"], item, item_index)
                          for item_index, item in enumerate(case["candidates"])]
            expected_lookup = {item["id"]: assertion["id"]
                               for item, assertion in zip(case["candidates"], assertions)}
            for row in assertions: write(trace, row)
            candidate_ids = [row["id"] for row in assertions]
            source_decision = decision(f"{case['id']}:source:decision", candidate_ids, "include", candidate_ids, f"{case['id']}:answer")
            write(trace, source_decision)
            claim = {"kind": "feedback_claim", "schema": 1, "id": f"{case['id']}:feedback",
                     "decisionId": source_decision["id"], "observationType": "explicit_correction",
                     "targetType": "answer_span", "targetIds": [f"{case['id']}:answer"],
                     "claimText": case["feedback"], "scope": "current interaction",
                     "authority": "explicit_user", "confidence": 1,
                     "sourceEventIds": [f"{case['id']}:feedback-event"], "observedAt": now()}
            write(trace, claim)
            visible = {"answer": case["answer"], "feedback": case["feedback"],
                       "candidate_memory_assertions": assertions}
            prompt = f"""Bind one user feedback message to the memory assertion(s) it specifically corrects.
Do not call tools, browse, inspect files, or execute commands. Candidate IDs are opaque output labels.
Return only candidate IDs that are uniquely supported as feedback targets by the answer and feedback.
If the feedback is about style, environment/tool failure, or is ambiguous, return an empty list.

<input_json>
{json.dumps(visible, ensure_ascii=False)}
</input_json>

Return only JSON matching the supplied schema."""
            binder_id = f"{case['id']}:binder:decision"
            output_id = f"{case['id']}:binder:output"
            write(inputs, {"id": case["id"], "prompt": prompt})
            stem = f"{index:02d}-{case['id']}"
            events = raw / f"{stem}.events.jsonl"; message = raw / f"{stem}.message.json"; stderr_path = raw / f"{stem}.stderr.txt"
            command = ["codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"', "--sandbox", "read-only", "-C", str(sandbox.resolve()), "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--output-schema", str((out / "output-schema.json").resolve()), "--json", "--output-last-message", str(message.resolve()), "-"]
            started = time.perf_counter(); timed_out = False
            with events.open("x") as stdout, stderr_path.open("x") as stderr:
                try:
                    completed = subprocess.run(command, input=prompt, text=True, stdout=stdout, stderr=stderr, timeout=300, check=False)
                    returncode = completed.returncode
                except subprocess.TimeoutExpired:
                    timed_out = True; returncode = None
            elapsed = time.perf_counter() - started
            parsed = None
            try: parsed = json.loads(message.read_text()) if message.exists() else None
            except json.JSONDecodeError: pass
            predicted_raw = parsed.get("target_ids") if isinstance(parsed, dict) else None
            predicted = sorted(predicted_raw) if isinstance(predicted_raw, list) and all(isinstance(x, str) for x in predicted_raw) else None
            expected = sorted(expected_lookup[value] for value in case["expected"])
            valid = predicted is not None and len(predicted) == len(set(predicted)) and all(x in candidate_ids for x in predicted)
            success = returncode == 0 and valid and predicted == expected
            selected = predicted if valid else []
            binder = decision(binder_id, candidate_ids, "verify" if selected else "ask", selected, output_id)
            write(trace, binder)
            result = "success" if success else ("unknown" if returncode != 0 or predicted is None else "failure")
            write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:binder:outcome",
                          "decisionId": binder_id, "result": result, "reward": 1 if success else (None if result == "unknown" else 0),
                          "metrics": {"exactTargetSet": success, "validCandidateSet": valid},
                          "source": "deterministic-target-checker", "observedAt": now(), "delayed": False})
            receipt = {"id": case["id"], "kind": case["kind"], "expected": expected, "predicted": predicted,
                       "valid": valid, "success": success, "returncode": returncode, "timed_out": timed_out,
                       "wall_seconds": elapsed, "usage": parse_usage(events)}
            receipts.append(receipt); write(receipt_file, receipt)
            print(case["id"], returncode, expected, predicted, success, flush=True)
    identifiable = [r for r in receipts if r["kind"] == "identifiable"]
    rejected = [r for r in receipts if r["kind"] == "reject"]
    overall = sum(r["success"] for r in receipts); ident_ok = sum(r["success"] for r in identifiable); reject_ok = sum(r["success"] for r in rejected)
    summary = {"protocol": "topic3-b-target-binding-v1", "model": MODEL, "reasoning_effort": REASONING,
               "calls": len(receipts), "completed": sum(r["returncode"] == 0 for r in receipts),
               "overall": {"correct": overall, "total": len(receipts)},
               "identifiable": {"correct": ident_ok, "total": len(identifiable)},
               "reject": {"correct": reject_ok, "total": len(rejected)},
               "threshold": {"overall": 10, "identifiable": 7, "reject": 3},
               "pass": overall >= 10 and ident_ok >= 7 and reject_ok >= 3,
               "wall_seconds": sum(r["wall_seconds"] for r in receipts), "usage": {},
               "scope": "Synthetic development target binding with oracle candidate sets and deterministic labels; not natural feedback learning or memory-cause proof."}
    for key in ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]:
        summary["usage"][key] = sum((r["usage"] or {}).get(key, 0) for r in receipts)
    (out / "execution-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)
