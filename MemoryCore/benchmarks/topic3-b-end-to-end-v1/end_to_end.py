"""Fixed target→update→scope→future-task cascade on synthetic holdout cases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


MODEL = "gpt-5.6-sol"
REASONING = "medium"
CASES = [
    {"id": "tundra", "setting": "metrics_path", "old": "/metrics", "new": "/ops-metrics-t4",
     "answer": "Tundra exports metrics at /metrics.", "feedback": "For Tundra, use /ops-metrics-t4 instead of /metrics.", "target_index": 1,
     "distractors": [("port", "8088"), ("health_path", "/healthz")]},
    {"id": "umbra", "setting": "lock_timeout_ms", "old": "5000", "new": "8750",
     "answer": "Umbra waits 5000 ms for the lock.", "feedback": "The Umbra lock timeout is 8750 ms now.", "target_index": 2,
     "distractors": [("retry_delay_ms", "5000"), ("lease_timeout_ms", "12000")]},
    {"id": "velvet", "setting": "archive_codec", "old": "gzip", "new": "zstd-v5",
     "answer": "Velvet archives are encoded with gzip.", "feedback": "Switch Velvet archive encoding to zstd-v5.", "target_index": 0,
     "distractors": [("archive_suffix", ".tar"), ("transport_codec", "gzip")]},
    {"id": "willow", "setting": "calendar_week_start", "old": "Sunday", "new": "Thursday",
     "answer": "Willow calendars start the week on Sunday.", "feedback": "Willow's established week start is Thursday, not Sunday.", "target_index": 1,
     "distractors": [("report_day", "Thursday"), ("calendar_timezone", "UTC")]},
]


def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def write(stream, row): stream.write(json.dumps(row, ensure_ascii=False) + "\n"); stream.flush()
def digest(value): return hashlib.sha256(value.encode()).hexdigest()


def exact_scope_action(scope, context):
    conflicts = [key for key, value in scope.items() if key in context and context[key] != value]
    missing = [key for key in scope if key not in context]
    if conflicts: return "omit"
    if missing: return "ask"
    return "include"


def parse_usage(path):
    value = None
    for line in path.read_text().splitlines():
        if line.strip():
            event = json.loads(line)
            if event.get("type") == "turn.completed": value = event.get("usage")
    return value


def call_codex(out, sandbox, stage, index, case_id, prompt, schema_path):
    stem = f"{stage}-{index:02d}-{case_id}"; raw = out / "raw"
    events = raw / f"{stem}.events.jsonl"; message = raw / f"{stem}.message.json"; stderr_path = raw / f"{stem}.stderr.txt"
    command = ["codex", "exec", "--model", MODEL, "-c", f'model_reasoning_effort="{REASONING}"', "--sandbox", "read-only", "-C", str(sandbox.resolve()), "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--output-schema", str(schema_path.resolve()), "--json", "--output-last-message", str(message.resolve()), "-"]
    started = time.perf_counter(); timed_out = False
    with events.open("x") as stdout, stderr_path.open("x") as stderr:
        try:
            completed = subprocess.run(command, input=prompt, text=True, stdout=stdout, stderr=stderr, timeout=300, check=False); returncode = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True; returncode = None
    parsed = None
    try: parsed = json.loads(message.read_text()) if message.exists() else None
    except json.JSONDecodeError: pass
    return {"returncode": returncode, "timed_out": timed_out, "wall_seconds": time.perf_counter() - started,
            "usage": parse_usage(events), "parsed": parsed}


def assertion(case, candidate_index, predicate, value):
    return {"kind": "memory_assertion", "schema": 1, "id": f"{case['id']}:candidate-{candidate_index + 1}",
            "subject": case["id"], "predicate": predicate, "value": value,
            "scope": {"project": case["id"]}, "validFrom": None, "validTo": None, "recordedAt": now(),
            "supersededAt": None, "status": "candidate", "authority": "explicit_user",
            "sourceEventIds": [f"{case['id']}:source-{candidate_index + 1}"],
            "supportedByClaimIds": [], "contradictsAssertionIds": []}


def decision(id_, candidates, action, selected, output, policy, propensity=1, spans=None):
    return {"kind": "decision_trace", "schema": 1, "id": id_, "contextId": id_.rsplit(":", 1)[0],
            "taskId": id_.split(":", 1)[0], "contextEventIds": [f"{id_}:input"],
            "candidateMemoryIds": candidates, "action": action, "selectedMemoryIds": selected,
            "policyVersion": policy, "propensity": propensity, "decidedAt": now(),
            "promptMemorySpans": spans or [], "outputIds": [output], "toolCallIds": []}


def target_prompt(case, candidates):
    visible = {"answer": case["answer"], "feedback": case["feedback"], "candidate_memory_assertions": candidates}
    return f"""Bind one user feedback message to the memory assertion(s) it specifically corrects.
Do not call tools, browse, inspect files, or execute commands. Candidate IDs are opaque output labels.
Return only candidate IDs that are uniquely supported as feedback targets by the answer and feedback.
If the feedback is about style, environment/tool failure, or is ambiguous, return an empty list.

<input_json>
{json.dumps(visible, ensure_ascii=False)}
</input_json>

Return only JSON matching the supplied schema."""


def update_prompt(case, target):
    visible = {"answer": case["answer"], "feedback": case["feedback"], "bound_target_assertion": target}
    return f"""Compile one explicit user correction into an updated memory assertion.
Do not call tools, browse, inspect files, or execute commands. The target is already bound; do not choose another target.
Return the same target_id and the corrected value as a string. Scope is preserved by the host and is not yours to rewrite.
Do not add preferences, permanence, exclusions, or broader scope not stated in the correction.

<input_json>
{json.dumps(visible, ensure_ascii=False)}
</input_json>

Return only JSON matching the supplied schema."""


def future_prompt(project, setting, memory_assertion):
    memory = "none supplied" if memory_assertion is None else json.dumps(memory_assertion, ensure_ascii=False)
    return f"""Perform one isolated configuration lookup. Do not call tools, browse, inspect files, or execute commands.
Use only the current request and the optional memory assertion. Do not infer an established value from general knowledge.
If no applicable assertion supplies the value, return the literal string \"unknown\" as value.

<memory_assertion>
{memory}
</memory_assertion>

Current request: Return the established value of setting {setting} for project {project}.
Return only JSON matching the supplied schema."""


def run(out):
    out.mkdir(parents=True, exist_ok=False); (out / "raw").mkdir(); sandbox = out / "empty-workdir"; sandbox.mkdir()
    target_schema = {"type": "object", "properties": {"target_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["target_ids"], "additionalProperties": False}
    update_schema = {"type": "object", "properties": {"target_id": {"type": "string"}, "value": {"type": "string"}}, "required": ["target_id", "value"], "additionalProperties": False}
    answer_schema = {"type": "object", "properties": {key: {"type": "string"} for key in ["project", "setting", "value"]}, "required": ["project", "setting", "value"], "additionalProperties": False}
    for name, schema in [("target", target_schema), ("update", update_schema), ("answer", answer_schema)]:
        (out / f"{name}-schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "cases.private.json").write_text(json.dumps(CASES, indent=2) + "\n")
    calls = []; stage_scores = {"target": [], "update": [], "matched_adaptive": [], "matched_frozen": [], "mismatch_adaptive": []}
    with (out / "trace.jsonl").open("x") as trace, (out / "inputs.jsonl").open("x") as inputs, (out / "receipts.jsonl").open("x") as receipt_file:
        for case_index, case in enumerate(CASES):
            specs = list(case["distractors"]); specs.insert(case["target_index"], (case["setting"], case["old"]))
            candidates = [assertion(case, i, predicate, value) for i, (predicate, value) in enumerate(specs)]
            for row in candidates: write(trace, row)
            candidate_ids = [row["id"] for row in candidates]; expected_target = candidates[case["target_index"]]
            source = decision(f"{case['id']}:source:decision", candidate_ids, "include", candidate_ids, f"{case['id']}:source:answer", "scripted-source:v1")
            write(trace, source)
            claim = {"kind": "feedback_claim", "schema": 1, "id": f"{case['id']}:feedback", "decisionId": source["id"],
                     "observationType": "explicit_correction", "targetType": "answer_span", "targetIds": [f"{case['id']}:source:answer"],
                     "claimText": case["feedback"], "scope": {"project": case["id"]}, "authority": "explicit_user", "confidence": 1,
                     "sourceEventIds": [f"{case['id']}:feedback-event"], "observedAt": now()}
            write(trace, claim)
            write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:source:outcome", "decisionId": source["id"],
                          "result": "failure", "reward": 0, "metrics": {"correctedByUser": True},
                          "source": "scripted-explicit-correction", "observedAt": now(), "delayed": True})

            tp = target_prompt(case, candidates); write(inputs, {"case": case["id"], "stage": "target", "prompt": tp})
            tr = call_codex(out, sandbox, "target", case_index, case["id"], tp, out / "target-schema.json")
            predicted = tr["parsed"].get("target_ids") if isinstance(tr["parsed"], dict) else None
            valid = isinstance(predicted, list) and len(predicted) == len(set(predicted)) and all(x in candidate_ids for x in predicted)
            target_ok = tr["returncode"] == 0 and valid and predicted == [expected_target["id"]]
            binder = decision(f"{case['id']}:binder:decision", candidate_ids, "verify" if valid and predicted else "ask", predicted if valid else [], f"{case['id']}:binder:output", "codex-target-binder:v1")
            write(trace, binder); write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:binder:outcome", "decisionId": binder["id"], "result": "success" if target_ok else "failure", "reward": 1 if target_ok else 0, "metrics": {"exactTargetSet": target_ok}, "source": "deterministic-target-checker", "observedAt": now(), "delayed": False})
            tr.update({"case": case["id"], "stage": "target", "expected": [expected_target["id"]], "success": target_ok}); calls.append(tr); stage_scores["target"].append(target_ok); write(receipt_file, tr)
            print(case["id"], "target", tr["returncode"], target_ok, predicted, flush=True)
            if not target_ok: continue

            up = update_prompt(case, expected_target); write(inputs, {"case": case["id"], "stage": "update", "prompt": up})
            ur = call_codex(out, sandbox, "update", case_index, case["id"], up, out / "update-schema.json")
            expected_update = {"target_id": expected_target["id"], "value": case["new"]}; update_ok = ur["returncode"] == 0 and ur["parsed"] == expected_update
            compiler = decision(f"{case['id']}:compiler:decision", [expected_target["id"]], "verify", [expected_target["id"]], f"{case['id']}:compiler:output", "codex-assertion-update:v2")
            write(trace, compiler); write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:compiler:outcome", "decisionId": compiler["id"], "result": "success" if update_ok else "failure", "reward": 1 if update_ok else 0, "metrics": {"exactTargetValue": update_ok}, "source": "deterministic-update-checker", "observedAt": now(), "delayed": False})
            ur.update({"case": case["id"], "stage": "update", "expected": expected_update, "success": update_ok}); calls.append(ur); stage_scores["update"].append(update_ok); write(receipt_file, ur)
            print(case["id"], "update", ur["returncode"], update_ok, ur["parsed"], flush=True)
            if not update_ok: continue
            updated = {"kind": "memory_assertion", "schema": 1, "id": f"{case['id']}:updated", "subject": case["id"],
                       "predicate": case["setting"], "value": case["new"], "scope": expected_target["scope"],
                       "validFrom": now(), "validTo": None, "recordedAt": now(), "supersededAt": None,
                       "status": "verified", "authority": "explicit_user", "sourceEventIds": [f"{case['id']}:feedback-event"],
                       "supportedByClaimIds": [claim["id"]], "contradictsAssertionIds": [expected_target["id"]]}
            write(trace, updated)

            order = sorted(["adaptive", "frozen"], key=lambda arm: digest(f"end-to-end-v1:{case['id']}:{arm}"))
            pair = {}
            for slot, arm in enumerate(order):
                if arm == "adaptive": assert exact_scope_action(updated["scope"], {"project": case["id"]}) == "include"
                supplied = updated if arm == "adaptive" else None; fp = future_prompt(case["id"], case["setting"], supplied)
                write(inputs, {"case": case["id"], "stage": f"matched_{arm}", "prompt": fp})
                selected = [updated["id"]] if arm == "adaptive" else []; action = "include" if selected else "omit"
                block = json.dumps(updated, ensure_ascii=False) if supplied else ""; start = fp.index(block) if block else -1
                d = decision(f"{case['id']}:matched:{slot}:{arm}:decision", [updated["id"]], action, selected,
                             f"{case['id']}:matched:{slot}:{arm}:output", "end-to-end-blocked-pair:v1", 0.5,
                             [{"memoryId": updated["id"], "start": start, "end": start + len(block)}] if block else [])
                write(trace, d)
                rr = call_codex(out, sandbox, f"matched-{arm}", case_index, case["id"], fp, out / "answer-schema.json")
                expected_answer = {"project": case["id"], "setting": case["setting"], "value": case["new"]}
                ok = rr["returncode"] == 0 and rr["parsed"] == expected_answer; pair[arm] = ok
                write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:matched:{slot}:{arm}:outcome", "decisionId": d["id"], "result": "success" if ok else "failure", "reward": 1 if ok else 0, "metrics": {"exactAnswer": ok}, "source": "deterministic-future-checker", "observedAt": now(), "delayed": False})
                rr.update({"case": case["id"], "stage": f"matched_{arm}", "expected": expected_answer, "success": ok}); calls.append(rr); stage_scores[f"matched_{arm}"].append(ok); write(receipt_file, rr)
                print(case["id"], f"matched_{arm}", rr["returncode"], ok, rr["parsed"], flush=True)

            other = f"{case['id']}-other"; assert exact_scope_action(updated["scope"], {"project": other}) == "omit"
            mismatch_prompt = future_prompt(other, case["setting"], None)
            write(inputs, {"case": case["id"], "stage": "mismatch_adaptive", "scopeGate": "omit_conflict", "prompt": mismatch_prompt})
            md = decision(f"{case['id']}:mismatch:decision", [updated["id"]], "omit", [], f"{case['id']}:mismatch:output", "exact-scope-conjunction:v1")
            write(trace, md)
            mr = call_codex(out, sandbox, "mismatch-adaptive", case_index, case["id"], mismatch_prompt, out / "answer-schema.json")
            mismatch_expected = {"project": other, "setting": case["setting"], "value": "unknown"}; mismatch_ok = mr["returncode"] == 0 and mr["parsed"] == mismatch_expected
            write(trace, {"kind": "outcome", "schema": 1, "id": f"{case['id']}:mismatch:outcome", "decisionId": md["id"], "result": "success" if mismatch_ok else "failure", "reward": 1 if mismatch_ok else 0, "metrics": {"exactUnknown": mismatch_ok, "scopeConflict": True}, "source": "deterministic-scope-safety-checker", "observedAt": now(), "delayed": False})
            mr.update({"case": case["id"], "stage": "mismatch_adaptive", "expected": mismatch_expected, "success": mismatch_ok}); calls.append(mr); stage_scores["mismatch_adaptive"].append(mismatch_ok); write(receipt_file, mr)
            print(case["id"], "mismatch_adaptive", mr["returncode"], mismatch_ok, mr["parsed"], flush=True)

    counts = {key: {"correct": sum(values), "total": len(values)} for key, values in stage_scores.items()}
    pairs = zip(stage_scores["matched_adaptive"], stage_scores["matched_frozen"])
    wins = losses = ties = 0
    for adaptive, frozen in pairs:
        if adaptive and not frozen: wins += 1
        elif frozen and not adaptive: losses += 1
        else: ties += 1
    passed = counts["target"] == {"correct": 4, "total": 4} and counts["update"] == {"correct": 4, "total": 4} and counts["matched_adaptive"] == {"correct": 4, "total": 4} and wins - losses >= 3 and counts["mismatch_adaptive"] == {"correct": 4, "total": 4}
    summary = {"protocol": "topic3-b-end-to-end-v1", "model": MODEL, "reasoning_effort": REASONING,
               "holdout_cases": len(CASES), "calls": len(calls), "completed": sum(c["returncode"] == 0 for c in calls),
               "stages": counts, "matched_pair": {"wins": wins, "losses": losses, "ties": ties}, "pass": passed,
               "wall_seconds": sum(c["wall_seconds"] for c in calls), "usage": {},
               "scope": "Synthetic holdout with oracle candidate construction, explicit corrections, deterministic scope and exact checkers. Not natural or production B."}
    for key in ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]:
        summary["usage"][key] = sum((c["usage"] or {}).get(key, 0) for c in calls)
    (out / "execution-summary.json").write_text(json.dumps(summary, indent=2) + "\n"); print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True); run(parser.parse_args().out)
