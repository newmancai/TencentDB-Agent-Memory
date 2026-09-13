"""Compile bounded assertion updates only after a successful target binding."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


MODEL = "gpt-5.6-sol"
REASONING = "medium"
EXPECTED_VALUES = {
    "atlas-endpoint": "/readyz-a7", "kestrel-retention": "47",
    "mica-suffix": ".bundle-v3", "nimbus-region": "ap-south-2",
    "quartz-batch": "73", "redwood-timezone": "Pacific/Chatham",
    "solace-header": "X-Solace-Route", "python-runtime": "CPython 3.13",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False) + "\n"); stream.flush()


def usage(path):
    value = None
    for line in path.read_text().splitlines():
        if line.strip():
            event = json.loads(line)
            if event.get("type") == "turn.completed": value = event.get("usage")
    return value


def run(target_run, out):
    out.mkdir(parents=True, exist_ok=False)
    raw = out / "raw"; raw.mkdir()
    sandbox = out / "empty-workdir"; sandbox.mkdir()
    cases = {row["id"]: row for row in json.loads((target_run / "cases.private.json").read_text())}
    target_receipts = {json.loads(line)["id"]: json.loads(line)
                       for line in (target_run / "receipts.jsonl").read_text().splitlines() if line.strip()}
    prefix = [json.loads(line) for line in (target_run / "trace.jsonl").read_text().splitlines() if line.strip()]
    assertions = {row["id"]: row for row in prefix if row.get("kind") == "memory_assertion"}
    selected_cases = []
    for case_id, expected_value in EXPECTED_VALUES.items():
        receipt = target_receipts[case_id]
        assert receipt["success"] and len(receipt["predicted"]) == 1
        target_id = receipt["predicted"][0]
        selected_cases.append((case_id, cases[case_id], assertions[target_id], expected_value))
    schema = {"type": "object", "properties": {key: {"type": "string"}
              for key in ["target_id", "value", "scope"]},
              "required": ["target_id", "value", "scope"], "additionalProperties": False}
    (out / "output-schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "trace.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in prefix))
    receipts = []
    with (out / "trace.jsonl").open("a") as trace, (out / "inputs.jsonl").open("x") as inputs, (out / "receipts.jsonl").open("x") as receipt_file:
        for index, (case_id, case, target, expected_value) in enumerate(selected_cases):
            visible = {"answer": case["answer"], "feedback": case["feedback"],
                       "bound_target_assertion": target}
            prompt = f"""Compile one explicit user correction into an updated memory assertion.
Do not call tools, browse, inspect files, or execute commands. The target is already bound; do not choose another target.
Return the same target_id, the corrected value as a string, and the target's scope exactly unchanged.
Do not add preferences, permanence, exclusions, or broader scope not stated in the correction.

<input_json>
{json.dumps(visible, ensure_ascii=False)}
</input_json>

Return only JSON matching the supplied schema."""
            decision_id = f"{case_id}:compiler:decision"; output_id = f"{case_id}:compiler:output"
            write(trace, {"kind": "decision_trace", "schema": 1, "id": decision_id,
                          "contextId": f"{case_id}:compiler", "taskId": f"{case_id}:update",
                          "contextEventIds": [f"{case_id}:feedback"], "candidateMemoryIds": [target["id"]],
                          "action": "verify", "selectedMemoryIds": [target["id"]],
                          "policyVersion": "codex-assertion-update:v1", "propensity": 1,
                          "decidedAt": now(), "promptMemorySpans": [], "outputIds": [output_id], "toolCallIds": []})
            write(inputs, {"id": case_id, "prompt": prompt})
            stem = f"{index:02d}-{case_id}"; events = raw / f"{stem}.events.jsonl"; message = raw / f"{stem}.message.json"; stderr_path = raw / f"{stem}.stderr.txt"
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
            expected = {"target_id": target["id"], "value": expected_value, "scope": target["scope"]}
            success = returncode == 0 and parsed == expected
            if success:
                write(trace, {"kind": "memory_assertion", "schema": 1, "id": f"{case_id}:updated-assertion",
                              "subject": target["subject"], "predicate": target["predicate"], "value": parsed["value"],
                              "scope": parsed["scope"], "validFrom": now(), "validTo": None, "recordedAt": now(),
                              "supersededAt": None, "status": "verified", "authority": "explicit_user",
                              "sourceEventIds": [f"{case_id}:feedback-event"],
                              "supportedByClaimIds": [f"{case_id}:feedback"],
                              "contradictsAssertionIds": [target["id"]]})
            result = "success" if success else ("unknown" if returncode != 0 or parsed is None else "failure")
            write(trace, {"kind": "outcome", "schema": 1, "id": f"{case_id}:compiler:outcome",
                          "decisionId": decision_id, "result": result,
                          "reward": 1 if success else (None if result == "unknown" else 0),
                          "metrics": {"exactTargetValueScope": success}, "source": "deterministic-update-checker",
                          "observedAt": now(), "delayed": False})
            receipt = {"id": case_id, "expected": expected, "parsed": parsed, "success": success,
                       "returncode": returncode, "timed_out": timed_out, "wall_seconds": elapsed, "usage": usage(events)}
            receipts.append(receipt); write(receipt_file, receipt)
            print(case_id, returncode, expected, parsed, success, flush=True)
    correct = sum(row["success"] for row in receipts)
    summary = {"protocol": "topic3-b-assertion-update-v1", "model": MODEL, "reasoning_effort": REASONING,
               "calls": len(receipts), "completed": sum(row["returncode"] == 0 for row in receipts),
               "correct": correct, "threshold": 7, "pass": correct >= 7,
               "wall_seconds": sum(row["wall_seconds"] for row in receipts), "usage": {},
               "scope": "Only target-bound synthetic explicit corrections. Exact target/value/scope checker; rejected target cases do not invoke compiler."}
    for key in ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"]:
        summary["usage"][key] = sum((r["usage"] or {}).get(key, 0) for r in receipts)
    (out / "execution-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--target-run", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); run(args.target_run, args.out)
