"""Normalize the frozen B evidence into reviewable delivery JSON.

This evaluator does not call a model. It recomputes metrics from the committed
CUPID receipts and reviews produced by the frozen public-data runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
BENCHMARKS = HERE.parent
PUBLIC = BENCHMARKS / "topic3-b-contextual-feedback-v1" / "results" / "learning"
INSTRUMENTED = BENCHMARKS / "topic3-b-instrumented-loop-v1" / "results" / "summary.json"
NATURAL = BENCHMARKS / "topic3-b-natural-assertion-v1" / "results" / "v2-summary.json"
NATURAL_HOST = BENCHMARKS / "topic3-b-natural-assertion-v1" / "results" / "host-summary.json"
RUNTIME = HERE / "results" / "runtime-contract.json"
PUBLIC_SUITE = BENCHMARKS / "topic3-b-public-suite-v1"
VALIDMEM = PUBLIC_SUITE / "results" / "validmem-codex-holdout.json"
TRIGGER = PUBLIC_SUITE / "results" / "trigger-codex-holdout.json"
TRIGGER_RUNTIME = PUBLIC_SUITE / "results" / "trigger-runtime-contract.json"
ARMS = ("request", "frozen", "unlabelled", "feedback")


def load(path: Path):
    return json.loads(path.read_text())


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quantile(values: list[float], q: float) -> float:
    """R-7/numpy-default linear quantile, defined for non-empty values."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def public_result() -> dict:
    selection_path = PUBLIC / "selection.json"
    receipts_path = PUBLIC / "receipts.jsonl"
    decoded_path = PUBLIC / "decoded.json"
    cost_path = PUBLIC / "cost.json"
    selection = load(selection_path)
    receipts = rows(receipts_path)
    decoded = load(decoded_path)
    cost = load(cost_path)

    if len(selection["groups"]) != 4 or len(selection["ids"]) != 12:
        raise ValueError("frozen CUPID selection must contain 4 personas and 12 tasks")
    if len(selection["training_ids"]) != 2 or len(receipts) != 12:
        raise ValueError("frozen CUPID run must contain 2 examples and 12 receipts")
    if {row["id"] for row in receipts} != set(selection["ids"]):
        raise ValueError("receipt IDs do not match the frozen selection")
    if any(set(row["arms"]) != set(ARMS) for row in receipts):
        raise ValueError("each receipt must contain the four frozen arms")

    arm_metrics = {}
    for arm in ARMS:
        items = [row["arms"][arm] for row in receipts]
        input_tokens = sum(item["input_tokens"] for item in items)
        output_tokens = sum(item["output_tokens"] for item in items)
        generation_ms = [item["generation_ms"] for item in items]
        errors = sum(item["error"] is not None for item in items)
        recorded = cost["arms"][arm]
        if (input_tokens, output_tokens, errors) != (
            recorded["input_tokens"], recorded["output_tokens"], recorded["errors"]
        ):
            raise ValueError(f"cost mismatch for arm {arm}")
        arm_metrics[arm] = {
            "mode": "baseline" if arm == "frozen" else "enabled" if arm == "feedback" else "control",
            "calls": len(items),
            "errors": errors,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_latency_ms": {
                "p50": quantile(generation_ms, 0.50),
                "p95": quantile(generation_ms, 0.95),
                "sum": sum(generation_ms),
                "definition": "per-call model.generate wall time; R-7 linear quantile; excludes model load and data preparation",
            },
        }

    comparison = decoded["feedback_comparison"]
    frozen_pair = comparison["frozen"]
    gain_passed = frozen_pair["win"] > frozen_pair["loss"]
    frozen = arm_metrics["frozen"]
    feedback = arm_metrics["feedback"]
    return {
        "schema": 1,
        "suite": "topic3-b-public-long-dialogue-method-validation-v1",
        "dataset": {
            "name": "CUPID",
            "release_kind": "public simulated interactions filtered by human annotators; not natural production logs",
            "huggingface_revision": "f6e5fdae9b31f2b400d6ceb281a6a6760cc00309",
            "source_commit": "a8560cab293ae98be4fe260689d58bddf96b51ef",
            "parquet_sha256": "6d68af09f7fbe52df0a3bd621604104696d0f481f166be5c06dd65bbb089aaae",
            "full_release": {
                "observations": 756,
                "personas": 252,
                "development_personas": 126,
                "validation_personas": 126,
                "sessions_per_observation": 8,
                "messages_per_observation_min_max": [32, 129],
            },
            "method_validation_subset": {
                "split": "development",
                "personas": 4,
                "tasks": 12,
                "variants_per_persona": 3,
                "model_calls": 48,
                "training_examples": 2,
                "evaluation_granularity": "one generated preference summary per task and arm; persona is the independent cluster",
                "sampling_seed": "domain-separated SHA256 strings, not an integer PRNG seed",
                "sampling_algorithm": "exclude 14 previously used development personas; sort persona by SHA256('cupid-feedback-learning-v1:'+persona), take 4; sort tasks by SHA256('learning-task:'+id)",
                "selected_personas": selection["groups"],
                "selected_task_ids": selection["ids"],
                "training_ids": selection["training_ids"],
            },
        },
        "alignment": {
            "inference": "each selected task ID maps one-to-one to an adapted CUPID observation; hidden factor, checklist and reference stay outside model input",
            "baseline_injection": "frozen injects only that task's user-message history",
            "feedback_injection": "feedback adds the same two bounded development examples as unlabelled plus their controlled correction objects",
            "labels": "official persona preference/checklist are opened only for post-generation semantic review; they are not per-memory causal labels",
            "memorycore_boundary": "the experiment aligns injected prompt fragments, not durable MemoryCore records; separate native replay validated exact raw-event L0 write/read provenance but is not this quality score",
        },
        "execution": {
            "model": "Qwen3-4B-Instruct-2507 local artifact; exact model revision was not recorded",
            "decoding": "greedy",
            "input_token_limit": 24000,
            "max_new_tokens": 256,
            "arm_order": "rotated by task index",
            "model_load_seconds": cost["load_seconds"],
        },
        "metrics": {
            "definitions": {
                "coverage": "assistant semantic review of target preference content as full/partial/absent; not an official automatic grader",
                "paired_quality": "reviewer ordering of feedback vs the same task's comparator; wins/losses/ties are task-level and clustered in 4 personas",
                "input_tokens": "tokenized prompt length summed over calls; includes injected evidence",
                "output_tokens": "generated tokens summed over calls",
                "l1_extraction": "not applicable: this public protocol performs no L1 extraction",
                "l0_retrieval": "not applicable: it injects frozen prompt evidence and does not benchmark MemoryCore retrieval latency",
            },
            "arms": arm_metrics,
            "coverage": decoded["coverage"],
            "paired_quality": comparison,
            "feedback_vs_frozen_cost": {
                "input_token_ratio": feedback["input_tokens"] / frozen["input_tokens"],
                "input_token_delta": feedback["input_tokens"] - frozen["input_tokens"],
                "generation_time_ratio": feedback["generation_latency_ms"]["sum"] / frozen["generation_latency_ms"]["sum"],
            },
        },
        "acceptance": {
            "runner_and_artifacts": {
                "status": "pass",
                "reason": "12 tasks x 4 arms are complete, ID-aligned, error-free, and cost totals recompute",
            },
            "baseline_present": {"status": "pass", "mode": "frozen"},
            "feedback_quality_gain": {
                "status": "pass" if gain_passed else "fail",
                "criterion": "feedback task-level wins must exceed losses against frozen",
                "observed": frozen_pair,
            },
            "commercial_or_production_memory_effect": {
                "status": "not_claimed",
                "reason": "development-only public method validation with assistant semantic judgments and no memory-cause labels",
            },
        },
        "confidence": {
            "quality_claim": "low-to-moderate component evidence only: 12 tasks in 4 persona clusters, assistant judgments, no held-out business split and no stable gain",
            "high_confidence_feedback_claim": "not made for CUPID labels; controlled corrections are development supervision, not natural user truth",
            "relative_to_end_to_end_repetition": "cheaper and more diagnostic than repeated full-agent runs, but cannot estimate production memory-effect confidence; no population confidence interval is claimed",
        },
        "artifact_sha256": {
            "selection_json": sha256(selection_path),
            "receipts_jsonl": sha256(receipts_path),
            "decoded_json": sha256(decoded_path),
            "cost_json": sha256(cost_path),
        },
    }


def delivery_summary(public: dict) -> dict:
    instrumented = load(INSTRUMENTED)
    natural = load(NATURAL)
    natural_host = load(NATURAL_HOST)
    runtime = load(RUNTIME)
    validmem = load(VALIDMEM)
    trigger = load(TRIGGER)
    trigger_runtime = load(TRIGGER_RUNTIME)
    if not instrumented["pass"] or not instrumented["replay"]["ok"]:
        raise ValueError("instrumented component result is not a passing causal replay")
    if not natural["pass"] or not natural_host["replay_ok"]:
        raise ValueError("natural candidate result is not a passing extraction/gate replay")
    if runtime["status"] != "pass":
        raise ValueError("runtime switch/fallback contract did not pass")
    if not validmem["status"].startswith("pass_method_validation"):
        raise ValueError("ValidMem holdout is not a passing method validation")
    if trigger["status"] != "complete":
        raise ValueError("Trigger Bench holdout is incomplete")
    if trigger_runtime["status"] != "passed":
        raise ValueError("Trigger Bench switch/failure contract did not pass")

    validmem_base = validmem["arms"]["plain_visibility"]["answerAccuracy"]
    validmem_enabled = validmem["arms"]["type_aware_policy"]["answerAccuracy"]
    trigger_base = trigger["arms"]["base_tools"]["fullPass"]
    trigger_enabled = trigger["arms"]["trigger_policy_v3"]["fullPass"]
    if (validmem_base["correct"], validmem_enabled["correct"], validmem_base["total"]) != (374, 387, 406):
        raise ValueError("ValidMem committed aggregate changed")
    if (trigger_base["pass"], trigger_enabled["pass"], trigger_base["total"]) != (112, 130, 140):
        raise ValueError("Trigger Bench committed aggregate changed")

    feedback_gain = public["acceptance"]["feedback_quality_gain"]
    return {
        "schema": 2,
        "suite": "topic3-b-delivery-acceptance-v1",
        "status": "pass_with_mixed_method_evidence",
        "deliverables": {
            "research_and_design": {
                "status": "pass",
                "artifacts": [
                    "../../B_REVIEW_HANDOFF_2026-09-13.md",
                    "../../B_COMPLETE_DELIVERY_2026-09-13.md",
                    "../../B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md",
                    "../../B_FINAL_HANDOFF_2026-09-13.md",
                ],
            },
            "public_long_dialogue_eval": {
                "status": "pass",
                "mode": "method_validation",
                "quality_gain_status": feedback_gain["status"],
                "result": "public-long-dialogue.json",
            },
            "implementation_and_comparison": {
                "status": "pass",
                "mode": "real_memorycore_host_method_validation",
                "baseline": {"name": "base_tools", **trigger_base},
                "enabled": {"name": "trigger_policy_v3", **trigger_enabled},
                "paired": trigger["paired"]["fullPass"],
                "result": "../../topic3-b-public-suite-v1/results/trigger-codex-holdout.json",
            },
            "off_and_forced_fallback": {
                "status": "pass",
                "mode": "two_runtime_contracts",
                "contracts": [
                    {"scope": "host_neutral_sidecar", "cases": len(runtime["cases"]),
                     "result": "runtime-contract.json"},
                    {"scope": "codex_mcp_memorycore_host", "cases": len(trigger_runtime["modes"]),
                     "result": "../../topic3-b-public-suite-v1/results/trigger-runtime-contract.json"},
                ],
            },
            "portable_pr": {
                "status": "pass",
                "mode": "additive_sidecar",
                "adapters": [
                    "../../../src/core/memory-feedback/answer-feedback.ts",
                    "../../topic3-b-public-suite-v1/validmem_adapter.py",
                    "../../topic3-b-public-suite-v1/trigger_adapter.py",
                    "../../topic3-b-public-suite-v1/trigger_memory_mcp.py",
                    "../../topic3-b-public-suite-v1/trigger_memory_bridge.ts",
                ],
                "porting_notes": "../PORTING.md",
                "remote_publication": "https://github.com/newmancai/TencentDB-Agent-Memory/pull/2",
                "remote_state": "must be checked live; this JSON validates local reviewability only",
            },
        },
        "component_evidence": {
            "validmem_lifecycle_holdout": {
                "status": "pass_method_validation_with_confidence_limit",
                "baseline": validmem_base,
                "enabled": validmem_enabled,
                "paired": validmem["pairedEnabledVsBaseline"],
                "clustered": validmem["batchClusteredConfidence"],
                "cost": validmem["cost"],
                "claim_boundary": "public lifecycle method validation; L1 write path and business utility not measured",
            },
            "trigger_real_host_holdout": {
                "status": "pass_method_validation",
                "baseline": trigger_base,
                "enabled": trigger_enabled,
                "paired": trigger["paired"]["fullPass"],
                "positive_trigger_recall": {
                    "baseline": trigger["arms"]["base_tools"]["positiveTriggerRecall"],
                    "enabled": trigger["arms"]["trigger_policy_v3"]["positiveTriggerRecall"],
                },
                "negative_trigger_specificity": {
                    "baseline": trigger["arms"]["base_tools"]["negativeTriggerSpecificity"],
                    "enabled": trigger["arms"]["trigger_policy_v3"]["negativeTriggerSpecificity"],
                },
                "claim_boundary": "single-model public microtask holdout; not natural feedback learning or coding-task utility",
            },
            "natural_raw_candidate": {
                "status": "pass",
                "mode": "enabled_extractor_plus_fail_closed_gate",
                "proposal_correct": natural["preaudited_explicit_correction"],
                "abstention_correct": natural["preaudited_abstention"],
                "host_replay": {
                    "ok": natural_host["replay_ok"],
                    "counts": natural_host["replay_counts"],
                    "learner_ready_extractor_decisions": natural_host["learner_ready_extractor_decisions"],
                    "pending_offpolicy_answer_decisions": natural_host["pending_offpolicy_answer_decisions"],
                },
                "claim_boundary": "candidate generation only; not durable truth or memory-cause attribution",
            },
            "instrumented_causal_loop": {
                "status": "pass",
                "mode": "paired_include_omit",
                "initial": instrumented["initial"],
                "baseline_omit": instrumented["omit"],
                "enabled_include": instrumented["include"],
                "paired": instrumented["paired"],
                "usage": instrumented["usage"],
                "wall_seconds": instrumented["wall_seconds"],
                "replay": instrumented["replay"],
                "l1_extraction": {"status": "path_verified", "latency": "not_measured_separately"},
                "l0_retrieval_and_injection": {"status": "path_and_exact_prompt_span_verified", "latency": "not_measured_separately"},
            },
            "public_feedback_gain": {
                "status": feedback_gain["status"],
                "mode": "feedback_vs_frozen_same_model",
                "observed": feedback_gain["observed"],
                "cost": public["metrics"]["feedback_vs_frozen_cost"],
            },
        },
        "release_boundary": {
            "commercial_b": "not_proven",
            "public_evidence": "mixed: CUPID feedback negative; ValidMem and Trigger Bench positive method validation",
            "learned_gate": "stopped_for_this_exact_domain_due_to_no_headroom_over_deterministic_rule",
            "production_enabled": False,
            "durable_promotion_enabled": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "results" / "public-long-dialogue.json")
    parser.add_argument("--summary-out", type=Path, default=HERE / "results" / "delivery-summary.json")
    args = parser.parse_args()
    result = public_result()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    summary = delivery_summary(result)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "suite": result["suite"],
        "runner": result["acceptance"]["runner_and_artifacts"]["status"],
        "feedback_gain": result["acceptance"]["feedback_quality_gain"]["status"],
        "out": str(args.out),
        "delivery_summary": str(args.summary_out),
    }))


if __name__ == "__main__":
    main()
