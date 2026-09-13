"""Offline metrics. Only this process reads answer labels or the source audit."""
import argparse
import json
import math
import re
from pathlib import Path


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def letter(s):
    match = re.fullmatch(r"\s*\(([a-z])\)\s*", s or "", re.I)
    return match[1].lower() if match else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--audit", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = [json.loads(s) for s in (args.run / "results.jsonl").read_text().splitlines()]
    actual = [json.loads(s) for s in (args.run / "calls.jsonl").read_text().splitlines()]
    receipt_index = {(c["task"], c["phase"]): c for c in actual}
    gold = json.loads(args.gold.read_text())
    audit = {r["id"]: r for r in json.loads(args.audit.read_text())} if args.audit else {}
    result = {"protocol": "topic3-be-v1", "splits": {}, "per_task": []}
    for split in ("development", "evaluation"):
        tasks = [r for r in rows if r["split"] == split]
        arms = {}
        for arm in ("base", "fixed", "adaptive"):
            service_times, tokens_in, tokens_out, calls, updates, errors, correct = [], 0, 0, 0, 0, 0, 0
            wrong_annotations = ambiguous_annotations = 0
            b_ms = e_ms = reader_ms = nli_tokens = 0
            for r in tasks:
                a = r["arms"][arm]; answer = a["answer"]
                # Recover actual failed/truncated generations in older receipts;
                # keep their failure status and charge all consumed tokens/time.
                if answer.get("error"):
                    answer = {**receipt_index.get((r["id"], f"reader:{arm}"), {}), **answer}
                ok = not answer.get("error") and letter(answer.get("text")) == letter(gold[r["id"]]["answer"]) and letter(answer.get("text")) is not None
                correct += ok; errors += bool(answer.get("error"))
                reader_ms += answer.get("elapsedMs", 0)
                tokens_in += answer.get("inputTokens", 0); tokens_out += answer.get("outputTokens", 0)
                service = answer.get("elapsedMs", 0) + a["read"]["elapsedMs"]
                if arm != "base":
                    for c in r["checks"]:
                        # Fixed checks all candidates; NLI is only adaptive B's selection cost.
                        if arm == "adaptive":
                            ms = c["score"].get("elapsedMs", 0); b_ms += ms; service += ms
                            tokens_in += c["score"].get("inputTokens", 0)
                            nli_tokens += c["score"].get("inputTokens", 0)
                        selected = arm == "fixed" or split == "development" or c["decision"]["verify"]
                        if selected:
                            calls += 1
                            receipt = c.get("receipt") or {}
                            ms = receipt.get("elapsedMs", 0); e_ms += ms; service += ms
                            tokens_in += receipt.get("inputTokens", 0); tokens_out += receipt.get("outputTokens", 0)
                            errors += bool(c["verification"]["error"])
                        changed = c["actions"].get(arm) in ("published", "duplicate")
                        updates += changed
                        label = audit.get(c["id"], {}).get("relation")
                        wrong_annotations += changed and label == "same"
                        ambiguous_annotations += changed and label == "unknown"
                service_times.append(service)
                result["per_task"].append({"id": r["id"], "owner": r["owner"], "split": split,
                    "mode": arm, "status": "pass" if ok else "fail", "answer": answer.get("text"),
                    "fallback": a["read"]["fallback"]})
            arms[arm] = dict(tasks=len(tasks), correct=correct, accuracy=correct / len(tasks) if tasks else None,
                e_calls=calls, annotations=updates, source_audit_unsupported_annotations=wrong_annotations if audit else None,
                source_audit_ambiguous_annotations=ambiguous_annotations if audit else None, errors=errors,
                input_tokens_including_nli=tokens_in, output_tokens=tokens_out,
                nli_input_tokens=nli_tokens, generative_input_tokens=tokens_in-nli_tokens,
                nli_service_ms=b_ms, e_service_ms=e_ms, reader_service_ms=reader_ms,
                component_service_p50_ms=percentile(service_times, .5), component_service_p95_ms=percentile(service_times, .95))
        checks = [c for r in tasks for c in r["checks"]]
        paired = {}
        for a, b in (("fixed", "base"), ("adaptive", "base"), ("adaptive", "fixed")):
            wins = losses = ties = 0
            for r in tasks:
                wanted = letter(gold[r["id"]]["answer"])
                x = not r["arms"][a]["answer"].get("error") and letter(r["arms"][a]["answer"].get("text")) == wanted
                y = not r["arms"][b]["answer"].get("error") and letter(r["arms"][b]["answer"].get("text")) == wanted
                wins += x and not y; losses += y and not x; ties += x == y
            paired[f"{a}_vs_{b}"] = dict(wins=wins, losses=losses, ties=ties)
        result["splits"][split] = dict(arms=arms, paired=paired,
            candidate_pairs=len(checks), e_relations={k: sum((c["verification"]["result"] or {}).get("relation") == k for c in checks)
                for k in ("changed", "same", "unknown")},
            adaptive_skipped_e_changed=sum(not c["decision"]["verify"] and (c["verification"]["result"] or {}).get("relation") == "changed"
                for c in checks) if split == "evaluation" else 0,
            fallback_checks=sum(len(r["failures"]) for r in tasks),
            fallback_pass=sum(c["fallback"] and c["exactBase"] for r in tasks for c in r["failures"]),
            original_history_preserved=sum(r["originalsPreserved"] for r in tasks),
            l0_message_range=[min(r["l0Count"] for r in tasks), max(r["l0Count"] for r in tasks)])
    result["actual_model"] = dict(calls=len(actual), input_tokens=sum(c.get("inputTokens", 0) for c in actual),
        output_tokens=sum(c.get("outputTokens", 0) for c in actual), generation_ms=sum(c.get("elapsedMs", 0) for c in actual))
    result["limitations"] = ["NLI score and E reviewer are fallible; no calibrated semantic confidence claim",
        "candidate coverage is conditional; global stale-memory recall is unknown",
        "source audit is single-pass assistant judgement, not independent human gold",
        "component service quantiles are sums of measured stages, not deployed wall latency",
        "identical deterministic E and reader outputs are reused across arms; logical arm costs are separately charged",
        "L0 text is stored via L1 episodic writer; no learned extraction comparison or coding-business claim"]
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "per_task"}, indent=2))


if __name__ == "__main__":
    main()
