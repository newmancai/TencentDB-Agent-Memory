#!/usr/bin/env python3
"""Run frozen MemoryCode packets with one local Hugging Face causal LM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


ARMS = ("full_history", "memorycore_l0", "latest_guidelines_oracle")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("".join(json.dumps(row) + "\n" for row in rows))
    temp.replace(path)


def run(args: argparse.Namespace) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    packets = _read_jsonl(args.packets)
    selected = [(index, packet) for index, packet in enumerate(packets)
                if index % args.shard_count == args.shard_index]
    existing = _read_jsonl(args.output) if args.resume and args.output.exists() else []
    done = {(row["task_id"], row["arm"]) for row in existing}
    if args.output.exists() and not args.resume:
        raise ValueError(f"output exists: {args.output}")

    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).to("cuda:0").eval()
    load_seconds = time.perf_counter() - load_started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = list(existing)

    for global_index, packet in selected:
        arm_order = ARMS[global_index % len(ARMS):] + ARMS[:global_index % len(ARMS)]
        for arm in arm_order:
            if (packet["task_id"], arm) in done:
                continue
            item = packet["arms"][arm]
            messages = [
                {"role": "system", "content": item["system"]},
                {"role": "user", "content": item["user"]},
            ]
            input_ids = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt"
            )
            input_tokens = int(input_ids.shape[-1])
            receipt: dict[str, Any] = {
                "schema": 1,
                "protocol": "topic3-be-memorycode-model-v1",
                "task_id": packet["task_id"],
                "dialogue_id": packet["dialogue_id"],
                "session_count": packet["session_count"],
                "history_class": packet["history_class"],
                "target_status": packet["target_status"],
                "arm": arm,
                "mode": item["mode"],
                "model": "Qwen/Qwen3-4B-Instruct-2507",
                "decoding": "greedy",
                "input_tokens": input_tokens,
                "max_input_tokens": args.max_input_tokens,
                "max_new_tokens": args.max_new_tokens,
                "prompt_sha256": hashlib.sha256(
                    (item["system"] + "\0" + item["user"]).encode()
                ).hexdigest(),
                "source_session_ids": item["source_session_ids"],
                "status": "failed",
                "error": None,
                "output_tokens": 0,
                "output_truncated": False,
                "generation_seconds": 0.0,
                "output": "",
                "shard": args.shard_index,
                "load_seconds": load_seconds,
            }
            if input_tokens > args.max_input_tokens:
                receipt["error"] = "input_limit_exceeded"
            else:
                try:
                    input_ids = input_ids.to("cuda:0")
                    torch.cuda.synchronize()
                    started = time.perf_counter()
                    with torch.inference_mode():
                        generated = model.generate(
                            input_ids,
                            max_new_tokens=args.max_new_tokens,
                            do_sample=False,
                            temperature=None,
                            top_p=None,
                            pad_token_id=tokenizer.eos_token_id,
                        )
                    torch.cuda.synchronize()
                    receipt["generation_seconds"] = time.perf_counter() - started
                    output_ids = generated[0, input_tokens:]
                    receipt["output_tokens"] = int(output_ids.shape[-1])
                    receipt["output_truncated"] = receipt["output_tokens"] == args.max_new_tokens
                    receipt["output"] = tokenizer.decode(output_ids, skip_special_tokens=True)
                    receipt["status"] = "passed"
                except Exception as error:
                    receipt["error"] = f"{type(error).__name__}: {error}"
                    torch.cuda.empty_cache()
            rows.append(receipt)
            done.add((packet["task_id"], arm))
            _write_atomic(args.output, rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--max-input-tokens", type=int, default=65536)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    run(args)


if __name__ == "__main__":
    main()
