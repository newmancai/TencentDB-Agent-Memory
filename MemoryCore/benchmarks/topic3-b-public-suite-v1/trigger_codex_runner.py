"""Run paired Codex trigger-policy arms through isolated real MemoryCore stores."""

import argparse
import hashlib
import json
import math
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from amb_failed_approach_runner import MODEL, REASONING, parse_usage, run_bounded
from h6_adapter import sha256, write_json


TASKS_SHA256 = "e15f7be65b2831135478b4dc04a7fde9ef030d02d91595190bd47d957e574c01"
GOLD_SHA256 = "889ea65b524e5ff9f121b47fe32864e4219c1b8d3365f0ef4d971b67f56db6e8"
SPLIT_SEED = "trigger-codex-development-v1"
BOOTSTRAP_SEED = 1309
AVAILABLE_ARMS = ("base_tools", "trigger_policy_v1", "trigger_policy_v2", "trigger_policy_v3")
DEFAULT_ARMS = ("base_tools", "trigger_policy_v3")
DEV_COUNTS = {
    "implicit-write-pos": 4,
    "implicit-write-neg": 4,
    "implicit-read-pos": 4,
    "implicit-read-neg": 4,
    "trap-read-pos": 4,
    "trap-write-neg": 2,
    "trap-read-neg": 2,
}
AGENTS_TEXT = """# Memory tools

Persistent memory is available through the `memorycore` MCP server. Use `memory_search` to retrieve
prior user/project facts and `memory_write` to save durable user/project facts or preferences. Follow
the tool descriptions exactly. Do not inspect the host or parent directories for benchmark material.
"""


def load(adapted: Path) -> tuple[list[dict], dict]:
    tasks_path, gold_path = adapted / "tasks.json", adapted / "gold.json"
    if sha256(tasks_path) != TASKS_SHA256 or sha256(gold_path) != GOLD_SHA256:
        raise ValueError("adapted Trigger Bench snapshot does not match pinned hashes")
    tasks, gold = json.loads(tasks_path.read_text()), json.loads(gold_path.read_text())
    if len(tasks) != 172 or len(gold) != 172 or {task["id"] for task in tasks} != set(gold):
        raise ValueError("invalid adapted Trigger Bench inventory")
    return tasks, gold


def development_ids(tasks: list[dict], gold: dict) -> set[str]:
    selected = set()
    for module, count in DEV_COUNTS.items():
        rows = [task for task in tasks if gold[task["id"]]["module"] == module]
        rows.sort(key=lambda task: hashlib.sha256(
            f"{SPLIT_SEED}:{task['id']}".encode()).digest())
        selected.update(task["id"] for task in rows[:count])
    for expected in (True, False):
        rows = [task for task in tasks if gold[task["id"]]["module"] == "regression"
                and gold[task["id"]]["expect"]["trigger"] is expected]
        rows.sort(key=lambda task: hashlib.sha256(
            f"{SPLIT_SEED}:regression:{expected}:{task['id']}".encode()).digest())
        selected.update(task["id"] for task in rows[:4])
    if len(selected) != 32:
        raise ValueError("development split must contain 32 cases")
    return selected


def select(tasks: list[dict], gold: dict, split: str, case_ids: set[str]) -> list[dict]:
    if case_ids:
        unknown = case_ids - {task["id"] for task in tasks}
        if unknown:
            raise ValueError(f"unknown case IDs: {sorted(unknown)}")
        return [task for task in tasks if task["id"] in case_ids]
    if split == "all":
        return tasks
    dev = development_ids(tasks, gold)
    return [task for task in tasks if (task["id"] in dev) == (split == "development")]


def matches_all(patterns: list[str], text: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) is not None for pattern in patterns)


def matches_none(patterns: list[str], text: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) is None for pattern in patterns)


def score(labels: dict, trace: list[dict], records: list[dict], answer: str,
          returncode: int | None, timed_out: bool) -> dict:
    module, expected = labels["module"], labels["expect"]
    successful = [row for row in trace if row.get("ok")]
    searches = [row for row in successful if row.get("operation") == "search"]
    writes = [row for row in successful if row.get("operation") == "write"]
    actual_trigger = bool(successful)
    expected_trigger = bool(expected["trigger"])
    if not expected_trigger:
        operation_pass = not actual_trigger
    elif "read-pos" in module:
        operation_pass = bool(searches)
    elif "write-pos" in module:
        operation_pass = bool(writes)
    else:
        operation_pass = actual_trigger

    observable = str(expected.get("observable", "")).lower()
    count_pass = not (("exactly one" in observable or "one write" in observable)
                      and "one or multiple" not in observable and len(writes) != 1)
    store_text = "\n".join(str(row.get("content", "")) for row in records)
    store_include = list(expected.get("store_include", []))
    store_exclude = list(expected.get("store_exclude", []))
    answer_include = list(expected.get("answer_include", []))
    answer_exclude = list(expected.get("answer_exclude", []))
    store_pass = matches_all(store_include, store_text) and matches_none(store_exclude, store_text)
    answer_pass = matches_all(answer_include, answer) and matches_none(answer_exclude, answer)
    if (labels.get("category") == "trap-enumeration-recount"
            and re.search(r"\b(?:3|three)\b[^.\n]{0,40}\bservices\b", answer, re.I)
            and matches_none(answer_exclude, answer)):
        # The public regex lists "3 services" but its natural-language rule is
        # count=three; accept the equivalent "3 deployed services" wording.
        answer_pass = True
    acknowledge_pass = not expected.get("acknowledge") or matches_all(store_include, answer)
    notfound_pass = not expected.get("notfound") or bool(re.search(
        r"没有|没(有)?找到|未找到|无记录|not\s+found|no\s+(stored|memory|record)|"
        r"(?:do\s+not|don't|don’t)\s+have[^.\n]{0,80}(?:saved|stored|memory|record)", answer, re.I))
    runtime_pass = returncode == 0 and not timed_out and all(row.get("ok") for row in trace)
    full_pass = all((runtime_pass, operation_pass, count_pass, store_pass,
                     answer_pass, acknowledge_pass, notfound_pass))
    failures = []
    if not runtime_pass:
        failures.append("failed")
    if operation_pass is False:
        failures.append("false-negative" if expected_trigger else "false-positive")
    if not count_pass or not store_pass:
        failures.append("wrong-op")
    if not answer_pass or not acknowledge_pass or not notfound_pass:
        failures.append("wrong-report")
    return {
        "expectedTrigger": expected_trigger,
        "actualTrigger": actual_trigger,
        "triggerDecisionCorrect": expected_trigger == actual_trigger,
        "operationPass": operation_pass,
        "searchCalls": len(searches),
        "writeCalls": len(writes),
        "toolCalls": len(trace),
        "successfulToolCalls": len(successful),
        "countPass": count_pass,
        "storePass": store_pass,
        "answerPass": answer_pass,
        "acknowledgePass": acknowledge_pass,
        "notfoundPass": notfound_pass,
        "runtimePass": runtime_pass,
        "fullPass": full_pass,
        "failureClasses": sorted(set(failures)),
        "finalRecordCount": len(records),
    }


def toml(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def run_case(task: dict, labels: dict, arm: str, run_root: Path, bench: Path,
             tsx: Path, timeout: int, retry_runtime_failure: bool = True) -> dict:
    run_dir = run_root / arm / task["id"]
    run_dir.mkdir(parents=True)
    workspace, store = run_dir / "workspace", run_dir / "store"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(AGENTS_TEXT)
    for item in task["workspaceFiles"]:
        target = (workspace / item["path"]).resolve()
        if workspace.resolve() not in target.parents:
            raise ValueError(f"workspace path escapes root: {item['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])

    seed = subprocess.run(
        [str(tsx), str(bench / "trigger_memory_bridge.ts"), "seed", str(store)],
        input=json.dumps({"memories": task["initialMemory"]}, ensure_ascii=False),
        text=True, capture_output=True, timeout=30,
    )
    if seed.returncode != 0:
        raise RuntimeError(f"seed failed for {task['id']}: {seed.stderr}")
    trace_path = run_dir / "trace.jsonl"
    mcp_args = [
        str(bench / "trigger_memory_mcp.py"),
        "--store", str(store),
        "--trace", str(trace_path),
        "--bridge", str(bench / "trigger_memory_bridge.ts"),
        "--tsx", str(tsx),
        "--policy", arm,
    ]
    answer_path = run_dir / "answer.txt"
    command = [
        "codex", "exec", "--enable", "mcp_2026_07_28",
        "--model", MODEL,
        "-c", f'model_reasoning_effort="{REASONING}"',
        "-c", f"mcp_servers.memorycore.command={toml(sys.executable)}",
        "-c", f"mcp_servers.memorycore.args={toml(mcp_args)}",
        "-c", "mcp_servers.memorycore.startup_timeout_sec=20",
        "-c", 'mcp_servers.memorycore.default_tools_approval_mode="approve"',
        "-c", 'mcp_servers.memorycore.enabled_tools=["memory_search","memory_write"]',
        "-c", "suppress_unstable_features_warning=true",
        "--sandbox", "workspace-write", "-C", str(workspace),
        "--skip-git-repo-check", "--ephemeral", "--ignore-rules",
        "--json", "-o", str(answer_path), "-",
    ]
    started = time.perf_counter()
    returncode, stdout, stderr, timed_out = run_bounded(command, task["prompt"], workspace, timeout)
    latency_ms = (time.perf_counter() - started) * 1000
    (run_dir / "events.jsonl").write_text(stdout)
    (run_dir / "stderr.txt").write_text(stderr)
    answer = answer_path.read_text() if answer_path.exists() else ""
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    dump = subprocess.run(
        [str(tsx), str(bench / "trigger_memory_bridge.ts"), "dump", str(store)],
        text=True, capture_output=True, timeout=30,
    )
    dump_value = json.loads(dump.stdout) if dump.returncode == 0 else {"ok": False, "records": []}
    records = dump_value.get("records", [])
    result = {
        "id": task["id"], "arm": arm, "module": labels["module"],
        "category": labels["category"], "source": labels["source"],
        "language": task["language"],
        "clusterKey": f"{labels['module']}:{labels['category']}:{labels['source']}",
        "returnCode": returncode, "timedOut": timed_out,
        "latencyMs": latency_ms, "usage": parse_usage(stdout),
        "answerSha256": hashlib.sha256(answer.encode()).hexdigest(),
        "seedRecords": len(task["initialMemory"]),
        "newRecords": max(0, len(records) - len(task["initialMemory"])),
        **score(labels, trace, records, answer, returncode, timed_out),
        "attempts": 1,
    }
    write_json(run_dir / "case-result.json", result)
    if retry_runtime_failure and not result["runtimePass"]:
        retried = run_case(task, labels, arm, run_root / "retry-2", bench, tsx, timeout, False)
        retried["attempts"] = 2
        retried["firstAttemptRuntimePass"] = False
        retried["firstAttempt"] = {
            key: result[key] for key in
            ("returnCode", "timedOut", "latencyMs", "usage", "toolCalls", "successfulToolCalls")
        }
        write_json(run_root / "retry-2" / arm / task["id"] / "case-result.json", retried)
        return retried
    return result


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[math.ceil(len(values) * fraction) - 1]


def arm_metrics(rows: list[dict]) -> dict:
    by_module = {}
    for module in sorted({row["module"] for row in rows}):
        selected = [row for row in rows if row["module"] == module]
        by_module[module] = {
            "fullPass": sum(row["fullPass"] for row in selected),
            "triggerDecisionCorrect": sum(row["triggerDecisionCorrect"] for row in selected),
            "total": len(selected),
        }
    positives = [row for row in rows if row["expectedTrigger"]]
    negatives = [row for row in rows if not row["expectedTrigger"]]
    latencies = [row["latencyMs"] for row in rows]
    prior_attempts = [row["firstAttempt"] for row in rows if row.get("firstAttempt")]
    incurred_latencies = latencies + [row["latencyMs"] for row in prior_attempts]
    usage_keys = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
    selected_usage = {key: sum((row.get("usage") or {}).get(key, 0) for row in rows)
                      for key in usage_keys}
    incurred_usage = {key: selected_usage[key] + sum((row.get("usage") or {}).get(key, 0)
                                                     for row in prior_attempts)
                      for key in usage_keys}
    return {
        "fullPass": {"pass": sum(row["fullPass"] for row in rows), "total": len(rows)},
        "triggerAccuracy": {"correct": sum(row["triggerDecisionCorrect"] for row in rows),
                            "total": len(rows)},
        "positiveTriggerRecall": {"triggered": sum(row["actualTrigger"] for row in positives),
                                  "total": len(positives)},
        "negativeTriggerSpecificity": {"silent": sum(not row["actualTrigger"] for row in negatives),
                                       "total": len(negatives)},
        "falsePositives": sum((not row["expectedTrigger"]) and row["actualTrigger"] for row in rows),
        "falseNegatives": sum(row["expectedTrigger"] and not row["actualTrigger"] for row in rows),
        "toolCalls": sum(row["toolCalls"] for row in rows),
        "searchCalls": sum(row["searchCalls"] for row in rows),
        "writeCalls": sum(row["writeCalls"] for row in rows),
        "seedRecords": sum(row["seedRecords"] for row in rows),
        "newRecords": sum(row["newRecords"] for row in rows),
        "byModule": by_module,
        "runtimeAttempts": len(rows) + len(prior_attempts),
        "runtimeRetries": len(prior_attempts),
        "attemptsWithUnavailableUsage": (
            sum(row.get("usage") is None for row in rows)
            + sum(row.get("usage") is None for row in prior_attempts)
        ),
        "usage": selected_usage,
        "incurredUsageKnown": incurred_usage,
        "latencyMs": {"total": sum(latencies), "p50": statistics.median(latencies),
                      "p95": percentile(latencies, .95), "basis": "selected_attempt_per_case"},
        "incurredAttemptLatencyMs": {"total": sum(incurred_latencies),
                                     "p50": statistics.median(incurred_latencies),
                                     "p95": percentile(incurred_latencies, .95),
                                     "basis": "all_attempts_including_runtime_retries"},
    }


def exact_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if not discordant:
        return 1.0
    tail = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(discordant, value) for value in range(tail + 1)) / 2 ** discordant)


def comparison(rows: list[dict], field: str, arms: tuple[str, str]) -> dict:
    by_arm = {arm: {row["id"]: row for row in rows if row["arm"] == arm} for arm in arms}
    ids = sorted(set(by_arm[arms[0]]) & set(by_arm[arms[1]]))
    wins = sum(bool(by_arm[arms[1]][case][field]) and not by_arm[arms[0]][case][field] for case in ids)
    losses = sum(bool(by_arm[arms[0]][case][field]) and not by_arm[arms[1]][case][field] for case in ids)
    deltas = {case: int(bool(by_arm[arms[1]][case][field])) - int(bool(by_arm[arms[0]][case][field]))
              for case in ids}
    clusters = defaultdict(list)
    for case in ids:
        clusters[by_arm[arms[0]][case]["clusterKey"]].append(deltas[case])
    rng = random.Random(BOOTSTRAP_SEED)
    cluster_values = list(clusters.values())
    samples = []
    for _ in range(10_000):
        drawn = [rng.choice(cluster_values) for _ in cluster_values]
        samples.append(100 * sum(map(sum, drawn)) / sum(map(len, drawn)))
    cluster_deltas = [sum(values) for values in cluster_values]
    positive_clusters = sum(value > 0 for value in cluster_deltas)
    negative_clusters = sum(value < 0 for value in cluster_deltas)
    return {
        "candidate": arms[1], "baseline": arms[0], "field": field,
        "wins": wins, "losses": losses, "ties": len(ids) - wins - losses,
        "caseExactTwoSidedP": exact_p(wins, losses),
        "observedDeltaPp": 100 * sum(deltas.values()) / len(ids),
        "clustered": {
            "units": len(cluster_values), "positive": positive_clusters,
            "negative": negative_clusters,
            "tied": len(cluster_values) - positive_clusters - negative_clusters,
            "bootstrap95Pp": [percentile(samples, .025), percentile(samples, .975)],
            "bootstrapReplicates": 10_000, "bootstrapSeed": BOOTSTRAP_SEED,
            "signExactTwoSidedP": exact_p(positive_clusters, negative_clusters),
        },
    }


def summarize(chosen: list[dict], gold: dict, rows: list[dict], split: str,
              arms: tuple[str, ...]) -> dict:
    complete = len(rows) == len(chosen) * len(arms) and all(row["runtimePass"] for row in rows)
    return {
        "schema": 1,
        "protocol": "trigger-memorycore-codex-v1",
        "status": "complete" if complete else "incomplete",
        "source": {
            "dataset": "Agent Memory Trigger Bench",
            "revision": "f64b921474c9d84d073a588ed13568e917275a1c",
            "tasksSha256": TASKS_SHA256,
            "goldSha256": GOLD_SHA256,
        },
        "split": {
            "name": split, "seed": SPLIT_SEED, "cases": len(chosen),
            "caseIdsSha256": hashlib.sha256("\n".join(task["id"] for task in chosen).encode()).hexdigest(),
            "moduleCounts": dict(Counter(gold[task["id"]]["module"] for task in chosen)),
            "positive": sum(gold[task["id"]]["expect"]["trigger"] for task in chosen),
            "negative": sum(not gold[task["id"]]["expect"]["trigger"] for task in chosen),
        },
        "model": MODEL, "reasoningEffort": REASONING,
        "cliVersion": subprocess.run(["codex", "--version"], text=True, capture_output=True,
                                     check=True).stdout.strip(),
        "mcpFeature": "mcp_2026_07_28 (under development in codex-cli 0.153.4)",
        "unit": "one isolated Codex CLI turn plus actual MCP trace and fresh MemoryCore SQLite L1 store",
        "arms": {arm: arm_metrics([row for row in rows if row["arm"] == arm]) for arm in arms},
        "paired": ({field: comparison(rows, field, (arms[0], arms[1]))
                    for field in ("triggerDecisionCorrect", "fullPass")}
                   if len(arms) == 2 else {}),
        "L1": {"path": "writeMemory + executeMemorySearch(FTS) + queryL1Records",
               "perCaseFreshStore": True},
        "L0": "not_measured_trigger_bench_targets_persistent_tool_use",
        "goldVisibleToModel": False,
        "independentBusinessMetric": False,
    }


def run(adapted: Path, output: Path, split: str, case_ids: set[str], execute: bool,
        timeout: int, workers: int, arms: tuple[str, ...], runtime_attempts: int) -> dict:
    adapted = adapted.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"output exists: {output}")
    tasks, gold = load(adapted)
    chosen = select(tasks, gold, split, case_ids)
    output.mkdir(parents=True)
    plan = [(task, gold[task["id"]], arm) for arm in arms for task in chosen]
    if not execute:
        summary = {"schema": 1, "protocol": "trigger-memorycore-codex-v1", "status": "dry_run",
                   "split": split, "cases": len(chosen), "plannedCalls": len(plan)}
        write_json(output / "summary.json", summary)
        return summary

    bench = Path(__file__).resolve().parent
    tsx = bench.parents[1] / "node_modules" / ".bin" / "tsx"
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_case, task, labels, arm, output / "runs", bench, tsx, timeout,
                               runtime_attempts == 2)
                   for task, labels, arm in plan]
        for future in as_completed(futures):
            rows.append(future.result())
            published = sorted(rows, key=lambda row: (row["arm"], row["id"]))
            (output / "cases.jsonl").write_text("".join(json.dumps(row) + "\n" for row in published))
    rows.sort(key=lambda row: (row["arm"], row["id"]))
    summary = summarize(chosen, gold, rows, split, arms)
    write_json(output / "summary.json", summary)
    return summary


def recompute(adapted: Path, output: Path, split: str, case_ids: set[str],
              arms: tuple[str, ...]) -> dict:
    adapted, output = adapted.resolve(), output.resolve()
    tasks, gold = load(adapted)
    chosen = select(tasks, gold, split, case_ids)
    bench = Path(__file__).resolve().parent
    tsx = bench.parents[1] / "node_modules" / ".bin" / "tsx"
    published = {(row["arm"], row["id"]): row for row in
                 map(json.loads, (output / "cases.jsonl").read_text().splitlines())}
    rows = []
    for arm in arms:
        for task in chosen:
            primary = output / "runs" / arm / task["id"]
            run_dir = (output / "runs" / "retry-2" / arm / task["id"]
                       if published[(arm, task["id"])].get("attempts") == 2 else primary)
            if not run_dir.exists():
                run_dir = primary
            prior = json.loads((run_dir / "case-result.json").read_text())
            if published[(arm, task["id"])].get("attempts") == 2:
                first = json.loads((primary / "case-result.json").read_text())
                prior["attempts"] = 2
                prior["firstAttemptRuntimePass"] = False
                prior["firstAttempt"] = {
                    key: first[key] for key in
                    ("returnCode", "timedOut", "latencyMs", "usage", "toolCalls", "successfulToolCalls")
                }
            answer = (run_dir / "answer.txt").read_text() if (run_dir / "answer.txt").exists() else ""
            trace_path = run_dir / "trace.jsonl"
            trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
            dumped = subprocess.run(
                [str(tsx), str(bench / "trigger_memory_bridge.ts"), "dump", str(run_dir / "store")],
                text=True, capture_output=True, check=True, timeout=30,
            )
            records = json.loads(dumped.stdout)["records"]
            prior.update(score(gold[task["id"]], trace, records, answer,
                               prior["returnCode"], prior["timedOut"]))
            write_json(run_dir / "case-result.json", prior)
            rows.append(prior)
    rows.sort(key=lambda row: (row["arm"], row["id"]))
    (output / "cases.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary = summarize(chosen, gold, rows, split, arms)
    write_json(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout", "all"), default="development")
    parser.add_argument("--case-ids", default="")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--runtime-attempts", type=int, choices=(1, 2), default=2)
    parser.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be in 1..8")
    arms = tuple(args.arms.split(","))
    if (not arms or len(set(arms)) != len(arms)
            or any(arm not in AVAILABLE_ARMS for arm in arms)):
        parser.error(f"--arms must be unique values from {','.join(AVAILABLE_ARMS)}")
    ids = {item for item in args.case_ids.split(",") if item}
    result = (recompute(args.adapted, args.output, args.split, ids, arms)
              if args.recompute else
              run(args.adapted, args.output, args.split, ids,
                  args.execute, args.timeout_seconds, args.workers, arms, args.runtime_attempts))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
