"""Run a paired Codex lifecycle-policy evaluation on adapted ValidMem."""

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

from amb_failed_approach_runner import MODEL, REASONING, parse_usage, run_bounded
from h6_adapter import sha256, write_json


TASKS_SHA256 = "cef3fe3e7ab7fb2b48ff330722c8b203d16746595f0fa7b6e7a4842c10c93dc3"
GOLD_SHA256 = "8b70d72b776f4a32b946e480d96cc618beab66a9165e997a24570304ceceb726"
SPLIT_SEED = "validmem-codex-dev-v1"
BOOTSTRAP_SEED = 1309
ARMS = ("plain_visibility", "lifecycle_policy", "type_aware_policy")


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "choiceId": {"type": "string"},
                    "selectedMemoryIds": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "choiceId", "selectedMemoryIds"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answers"],
    "additionalProperties": False,
}


def load(adapted: Path) -> tuple[list[dict], dict]:
    tasks_path, gold_path = adapted / "tasks.json", adapted / "gold.json"
    if sha256(tasks_path) != TASKS_SHA256 or sha256(gold_path) != GOLD_SHA256:
        raise ValueError("adapted ValidMem snapshot does not match the pinned hashes")
    tasks, gold = json.loads(tasks_path.read_text()), json.loads(gold_path.read_text())
    if len(tasks) != 466 or len(gold) != 466 or {task["id"] for task in tasks} != set(gold):
        raise ValueError("invalid adapted ValidMem inventory")
    return tasks, gold


def select(tasks: list[dict], gold: dict, split: str) -> list[dict]:
    if split == "all":
        return tasks
    development = set()
    for part in "ABC":
        rows = [task for task in tasks if gold[task["id"]]["part"] == part]
        rows.sort(key=lambda task: hashlib.sha256(
            f"{SPLIT_SEED}:{task['id']}".encode()
        ).digest())
        development.update(task["id"] for task in rows[:20])
    return [task for task in tasks if (task["id"] in development) == (split == "development")]


def prompt_for(tasks: list[dict], arm: str) -> str:
    policy = {
        "plain_visibility": (
            "Treat each supplied store as the complete visible memory. Use the question, record contents, "
            "recorded days, explicit expiry metadata, and answer choices to make the best decision. A stored "
            "record is not automatically current."
        ),
        "lifecycle_policy": (
            "Apply this lifecycle policy before answering: first classify the question as current-state or "
            "historical. A record is expired only when expiresDay is non-null and currentDay is greater than "
            "expiresDay (it is still active on the boundary day). For current-state questions, exclude expired "
            "records and older records contradicted or replaced by later records about the same entity and "
            "attribute. For historical questions, keep superseded records when the requested time refers to "
            "them, but still exclude records already expired at that requested/current time. Never transfer a "
            "fact between different entities."
        ),
        "type_aware_policy": (
            "Apply the lifecycle policy before answering. First classify the question as current-state or "
            "historical. A record is explicitly expired only when expiresDay is non-null and currentDay is "
            "greater than expiresDay; it remains active on the boundary day. A project-status record without "
            "an explicit expiresDay is short-lived and expires when currentDay-createdDay is greater than 14; "
            "do not invent that implicit TTL for feedback, user, reference, or project-context records. For "
            "current-state questions also exclude older records contradicted or replaced by later records "
            "about the same entity and attribute. Historical questions may use superseded records for the "
            "requested past time, but not records expired at that time. Never transfer facts between entities."
        ),
    }[arm]
    cases = []
    for task in tasks:
        memories = "\n".join(
            f"- {item['memoryId']} | recordedDay={item['createdDay']} | "
            f"expiresDay={item['expiresDay'] if item['expiresDay'] is not None else 'null'} | "
            f"type={item['type']} | {item['description']}"
            for item in task["memoryStore"]
        )
        choices = "\n".join(f"- {item['id']}: {item['text']}" for item in task["choices"])
        cases.append(
            f"CASE {task['id']}\ncurrentDay={task['currentDay']}\nMEMORY STORE\n{memories}\n"
            f"QUESTION\n{task['query']}\nCHOICES\n{choices}"
        )
    return (
        "Solve the independent memory cases below. Use only the supplied fields; do not use tools, files, "
        "outside knowledge, or cross-case information. " + policy + "\nFor every case return exactly one "
        "choiceId and selectedMemoryIds containing only the memory IDs actually selected as answer evidence; "
        "use an empty list when no memory remains valid. Return only the requested JSON object.\n\n"
        + "\n\n".join(cases)
    )


def parse_answers(text: str, expected_ids: set[str]) -> dict[str, dict]:
    value = json.loads(text)
    answers = value.get("answers")
    if not isinstance(answers, list):
        raise ValueError("response has no answers array")
    mapped = {}
    for answer in answers:
        case_id = answer.get("id") if isinstance(answer, dict) else None
        memory_ids = answer.get("selectedMemoryIds") if isinstance(answer, dict) else None
        if (case_id not in expected_ids or case_id in mapped
                or not isinstance(answer.get("choiceId"), str)
                or not isinstance(memory_ids, list)
                or not all(isinstance(item, str) for item in memory_ids)):
            raise ValueError("invalid, duplicate, or unexpected answer")
        mapped[case_id] = answer
    if set(mapped) != expected_ids:
        raise ValueError("response case IDs do not match the batch")
    return mapped


def score(task: dict, labels: dict, answer: dict | None) -> dict:
    visible_ids = {item["memoryId"] for item in task["memoryStore"]}
    predicted = answer.get("choiceId") if answer else None
    selected = answer.get("selectedMemoryIds", []) if answer else []
    valid_selection = len(selected) == len(set(selected)) and set(selected) <= visible_ids
    correct = predicted == labels["correctChoiceId"] and valid_selection
    selected_set = set(selected) if valid_selection else visible_ids
    return {
        "prediction": predicted,
        "selectedMemoryIds": selected,
        "validSelection": valid_selection,
        "correct": correct,
        "crrPass": correct and not (selected_set & set(labels["supersededDecoys"])),
        "earPass": correct and not (selected_set & set(labels["expiredDecoys"])),
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def metrics(rows: list[dict], arm: str) -> dict:
    selected = [row for row in rows if row["arm"] == arm]
    by_part = {}
    for part in "ABC":
        part_rows = [row for row in selected if row["part"] == part]
        by_part[part] = {"correct": sum(row["correct"] for row in part_rows), "total": len(part_rows)}
    a_rows = [row for row in selected if row["part"] == "A"]
    b_rows = [row for row in selected if row["part"] == "B"]
    return {
        "answerAccuracy": {"correct": sum(row["correct"] for row in selected), "total": len(selected)},
        "byPart": by_part,
        "CRR_partA": {"pass": sum(row["crrPass"] for row in a_rows), "total": len(a_rows)},
        "EAR_partB": {"pass": sum(row["earPass"] for row in b_rows), "total": len(b_rows)},
        "invalidSelections": sum(not row["validSelection"] for row in selected),
    }


def paired(rows: list[dict], candidate: str) -> dict:
    by_case = {arm: {row["id"]: row for row in rows if row["arm"] == arm}
               for arm in (ARMS[0], candidate)}
    wins = sum(by_case[candidate][case_id]["correct"] and not row["correct"]
               for case_id, row in by_case[ARMS[0]].items())
    losses = sum(row["correct"] and not by_case[candidate][case_id]["correct"]
                 for case_id, row in by_case[ARMS[0]].items())
    ties = len(by_case[ARMS[0]]) - wins - losses
    discordant = wins + losses
    p_value = 1.0 if not discordant else min(1.0, 2 * sum(
        math.comb(discordant, value) for value in range(min(wins, losses) + 1)
    ) / (2 ** discordant))
    return {"wins": wins, "losses": losses, "ties": ties, "mcnemarExactTwoSidedP": p_value}


def cost(call_rows: list[dict], arm: str) -> dict:
    rows = [row for row in call_rows if row["arm"] == arm]
    latencies = [row["latencyMs"] for row in rows]
    return {
        "calls": len(rows),
        "usage": {key: sum((row.get("usage") or {}).get(key, 0) for row in rows)
                  for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")},
        "promptCharacters": sum(row["promptCharacters"] for row in rows),
        "latencyMs": {"total": sum(latencies), "p50": statistics.median(latencies),
                      "p95": percentile(latencies, .95)},
    }


def clustered_comparison(case_rows: list[dict], call_rows: list[dict], candidate: str) -> dict:
    by_arm = {arm: {row["id"]: row for row in case_rows if row["arm"] == arm}
              for arm in (ARMS[0], candidate)}
    candidate_cases = {case_id for row in call_rows if row["arm"] == candidate
                       for case_id in row["caseIds"]}
    batches = []
    for call in call_rows:
        if call["arm"] != ARMS[0]:
            continue
        case_ids = call["caseIds"]
        if not set(case_ids) <= candidate_cases:
            raise ValueError("candidate arm does not match baseline batch cases")
        deltas = [int(by_arm[candidate][case_id]["correct"])
                  - int(by_arm[ARMS[0]][case_id]["correct"]) for case_id in case_ids]
        batches.append(deltas)
    if not batches:
        raise ValueError("no baseline batches for clustered comparison")
    rng = random.Random(BOOTSTRAP_SEED)
    samples = []
    for _ in range(10_000):
        drawn = [rng.choice(batches) for _ in batches]
        samples.append(100 * sum(map(sum, drawn)) / sum(map(len, drawn)))
    batch_deltas = [sum(values) for values in batches]
    discordant = sum(value != 0 for value in batch_deltas)
    positive = sum(value > 0 for value in batch_deltas)
    tail = min(positive, discordant - positive)
    p_value = 1.0 if not discordant else min(1.0, 2 * sum(
        math.comb(discordant, value) for value in range(tail + 1)
    ) / (2 ** discordant))
    return {
        "batchUnits": len(batches),
        "positiveBatches": positive,
        "negativeBatches": sum(value < 0 for value in batch_deltas),
        "tiedBatches": sum(value == 0 for value in batch_deltas),
        "observedAccuracyDeltaPp": 100 * sum(batch_deltas) / sum(map(len, batches)),
        "clusterBootstrap95Pp": [percentile(samples, .025), percentile(samples, .975)],
        "bootstrapReplicates": 10_000,
        "bootstrapSeed": BOOTSTRAP_SEED,
        "batchSignExactTwoSidedP": p_value,
    }


def summarize(chosen: list[dict], gold: dict, case_rows: list[dict], call_rows: list[dict],
              split: str, batch_size: int, arms: tuple[str, ...] = ARMS) -> dict:
    latencies = [row["latencyMs"] for row in call_rows]
    usage = {key: sum((row.get("usage") or {}).get(key, 0) for row in call_rows)
             for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
    complete = (len(case_rows) == len(arms) * len(chosen)
                and all(row["parseError"] is None and row["returnCode"] == 0 for row in call_rows))
    comparisons = ({arm: paired(case_rows, arm) for arm in arms if arm != ARMS[0]}
                   if ARMS[0] in arms else {})
    single_choice_ids = {task["id"] for task in chosen if len(task["choices"]) == 1}
    sensitivity_rows = [row for row in case_rows if row["id"] not in single_choice_ids]
    return {
        "schema": 1, "protocol": "validmem-codex-v1",
        "status": "complete" if complete else "incomplete",
        "source": {"dataset": "ValidMem-v1.1", "tasksSha256": TASKS_SHA256,
                   "goldSha256": GOLD_SHA256},
        "split": {"name": split, "seed": SPLIT_SEED, "cases": len(chosen),
                  "caseIdsSha256": hashlib.sha256("\n".join(task["id"] for task in chosen).encode()).hexdigest(),
                  "partCounts": dict(Counter(gold[task["id"]]["part"] for task in chosen))},
        "model": MODEL, "reasoningEffort": REASONING,
        "cliVersion": subprocess.run(["codex", "--version"], capture_output=True, text=True, check=True).stdout.strip(),
        "arms": {arm: metrics(case_rows, arm) for arm in arms},
        "pairedAgainstPlain": comparisons,
        "pairedByPartAgainstPlain": {
            arm: {part: paired([row for row in case_rows if row["part"] == part], arm)
                  for part in "ABC"}
            for arm in arms if arm != ARMS[0]
        } if ARMS[0] in arms else {},
        "batchClusteredAgainstPlain": {
            arm: clustered_comparison(case_rows, call_rows, arm)
            for arm in arms if arm != ARMS[0]
        } if ARMS[0] in arms else {},
        "singleChoiceSensitivity": {
            "excludedCaseIds": sorted(single_choice_ids),
            "arms": {arm: metrics(sensitivity_rows, arm) for arm in arms},
            "pairedAgainstPlain": ({arm: paired(sensitivity_rows, arm)
                                    for arm in arms if arm != ARMS[0]}
                                   if single_choice_ids and ARMS[0] in arms else comparisons),
        },
        "calls": len(call_rows), "batchSize": batch_size, "usage": usage,
        "costByArm": {arm: cost(call_rows, arm) for arm in arms},
        "latencyMs": {"total": sum(latencies), "p50": statistics.median(latencies),
                      "p95": percentile(latencies, .95)},
        "L1": "not_measured_prebuilt_public_store",
        "L0": {"injectedMemoryRecordsPerArm": sum(len(task["memoryStore"]) for task in chosen),
               "sameVisibleRecordsAcrossArms": True},
        "independentBusinessMetric": False,
    }


def recompute(adapted: Path, output: Path, split: str, batch_size: int) -> dict:
    tasks, gold = load(adapted)
    chosen = select(tasks, gold, split)
    call_rows = [json.loads(line) for line in (output / "calls.jsonl").read_text().splitlines()]
    case_rows = [json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()]
    arms = tuple(arm for arm in ARMS if any(row["arm"] == arm for row in call_rows))
    summary = summarize(chosen, gold, case_rows, call_rows, split, batch_size, arms)
    write_json(output / "summary.json", summary)
    return summary


def run(adapted: Path, output: Path, split: str, execute: bool, batch_size: int,
        timeout: int, arms: tuple[str, ...] = ARMS) -> dict:
    if output.exists():
        raise ValueError(f"output exists: {output}")
    tasks, gold = load(adapted)
    chosen = select(tasks, gold, split)
    output.mkdir(parents=True)
    write_json(output / "output-schema.json", OUTPUT_SCHEMA)
    case_rows, call_rows = [], []
    with tempfile.TemporaryDirectory(prefix="validmem-codex-") as temporary:
        workspace = Path(temporary)
        for arm in arms:
            for start in range(0, len(chosen), batch_size):
                batch = chosen[start:start + batch_size]
                batch_id = f"{arm}-{start // batch_size + 1:03d}"
                prompt = prompt_for(batch, arm)
                prompt_path = output / f"{batch_id}.prompt.txt"
                events_path = output / f"{batch_id}.events.jsonl"
                stderr_path = output / f"{batch_id}.stderr.txt"
                answer_path = output / f"{batch_id}.answer.json"
                prompt_path.write_text(prompt)
                command = [
                    "codex", "exec", "--model", MODEL,
                    "-c", f'model_reasoning_effort="{REASONING}"', "--sandbox", "read-only",
                    "-C", str(workspace), "--skip-git-repo-check", "--ephemeral",
                    "--ignore-user-config", "--ignore-rules", "--output-schema",
                    str((output / "output-schema.json").resolve()), "-o", str(answer_path.resolve()),
                    "--json", "-",
                ]
                if not execute:
                    call_rows.append({"batchId": batch_id, "arm": arm, "caseIds": [x["id"] for x in batch],
                                      "status": "dry_run", "promptCharacters": len(prompt)})
                    continue
                started = time.perf_counter()
                returncode, stdout, stderr, timed_out = run_bounded(command, prompt, workspace, timeout)
                latency = (time.perf_counter() - started) * 1000
                events_path.write_text(stdout)
                stderr_path.write_text(stderr)
                parse_error, answers = None, {}
                try:
                    answers = parse_answers(answer_path.read_text(), {task["id"] for task in batch})
                except Exception as error:
                    parse_error = f"{type(error).__name__}: {error}"
                usage = parse_usage(stdout)
                call_rows.append({
                    "batchId": batch_id, "arm": arm, "caseIds": [x["id"] for x in batch],
                    "status": "timeout" if timed_out else "failed" if returncode else "completed",
                    "returnCode": returncode, "parseError": parse_error, "usage": usage,
                    "latencyMs": latency, "promptCharacters": len(prompt),
                })
                for task in batch:
                    result = score(task, gold[task["id"]], answers.get(task["id"]))
                    case_rows.append({
                        "id": task["id"], "arm": arm, "part": gold[task["id"]]["part"],
                        "subcategory": gold[task["id"]]["subcategory"],
                        "memoryCount": len(task["memoryStore"]), "choiceCount": len(task["choices"]),
                        **result,
                    })
                (output / "calls.jsonl").write_text("".join(json.dumps(row) + "\n" for row in call_rows))
                (output / "cases.jsonl").write_text("".join(json.dumps(row) + "\n" for row in case_rows))

    if not execute:
        summary = {"schema": 1, "protocol": "validmem-codex-v1", "status": "dry_run",
                   "split": split, "cases": len(chosen), "plannedCalls": len(call_rows)}
    else:
        summary = summarize(chosen, gold, case_rows, call_rows, split, batch_size, arms)
    write_json(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout", "all"), default="development")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 16:
        parser.error("--batch-size must be in 1..16")
    arms = tuple(args.arms.split(","))
    if not arms or len(set(arms)) != len(arms) or any(arm not in ARMS for arm in arms):
        parser.error(f"--arms must be unique values from {','.join(ARMS)}")
    result = (recompute(args.adapted, args.output, args.split, args.batch_size)
              if args.recompute else
              run(args.adapted, args.output, args.split, args.execute,
                  args.batch_size, args.timeout_seconds, arms))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
