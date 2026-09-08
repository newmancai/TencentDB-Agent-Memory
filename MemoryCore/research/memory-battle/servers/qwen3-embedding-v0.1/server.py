#!/usr/bin/env python3
"""Small loopback-only OpenAI embeddings server for the frozen system battle.

The server intentionally exposes only the endpoint needed by Hindsight's
``OpenAIEmbeddings`` client.  It is not a general inference service and never
reads detector gold.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def normalize_inputs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("input must be a string or an array of strings")


@dataclass
class RequestStats:
    requests: int = 0
    successful_requests: int = 0
    items: int = 0
    input_characters: int = 0
    input_tokens: int = 0
    failures: int = 0
    inference_milliseconds: float = 0.0
    queue_milliseconds: float = 0.0


class EmbeddingRuntime:
    def __init__(self, model_path: Path, device: str, batch_size: int, max_sequence_length: int):
        from sentence_transformers import SentenceTransformer

        self.model_path = model_path.resolve()
        self.model_id = self.model_path.name
        self.device = device
        self.batch_size = batch_size
        self.model = SentenceTransformer(
            str(self.model_path),
            device=device,
            trust_remote_code=False,
            model_kwargs={"low_cpu_mem_usage": False},
        )
        self.model.max_seq_length = max_sequence_length
        dimension = self.model.get_sentence_embedding_dimension()
        if not isinstance(dimension, int) or dimension <= 0:
            raise RuntimeError("embedding model did not expose a positive dimension")
        self.dimension = dimension
        self.max_sequence_length = max_sequence_length
        self.lock = threading.Lock()
        self.stats_lock = threading.Lock()
        self.stats = RequestStats()

    def request_received(self) -> None:
        """Count every valid endpoint attempt, including malformed/failed ones."""
        with self.stats_lock:
            self.stats.requests += 1

    def encode(self, texts: list[str]) -> tuple[list[list[float]], int, float]:
        queued_at = time.perf_counter()
        with self.lock:
            started = time.perf_counter()
            queue_ms = (started - queued_at) * 1000.0
            vectors = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            tokenized = self.model.tokenizer(
                texts,
                truncation=True,
                max_length=self.max_sequence_length,
                add_special_tokens=True,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
        token_count = sum(len(ids) for ids in tokenized["input_ids"])
        rows = vectors.astype(float).tolist()
        with self.stats_lock:
            self.stats.successful_requests += 1
            self.stats.items += len(texts)
            self.stats.input_characters += sum(len(text) for text in texts)
            self.stats.input_tokens += token_count
            self.stats.inference_milliseconds += elapsed_ms
            self.stats.queue_milliseconds += queue_ms
        return rows, token_count, elapsed_ms

    def failure(self) -> None:
        with self.stats_lock:
            self.stats.failures += 1

    def snapshot(self) -> dict[str, Any]:
        with self.stats_lock:
            stats = asdict(self.stats)
        return {
            "schemaVersion": "local-embedding-server-stats.v0.2",
            "modelId": self.model_id,
            "modelPath": str(self.model_path),
            "device": self.device,
            "dimension": self.dimension,
            "maxSequenceLength": self.max_sequence_length,
            **stats,
        }


def handler_for(runtime: EmbeddingRuntime):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TDAI-QwenEmbeddingBattle/0.2"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            route = urlparse(self.path).path
            if route == "/health":
                self._json(200, {"status": "ok", "model": runtime.model_id})
                return
            if route == "/stats":
                self._json(200, runtime.snapshot())
                return
            self._json(404, {"error": {"message": "not found", "type": "not_found"}})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            route = urlparse(self.path).path.rstrip("/")
            if route != "/v1/embeddings":
                self._json(404, {"error": {"message": "not found", "type": "not_found"}})
                return
            runtime.request_received()
            try:
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    raise ValueError("Content-Length is required")
                body = json.loads(self.rfile.read(int(raw_length)))
                texts = normalize_inputs(body.get("input"))
                if not texts:
                    raise ValueError("input cannot be empty")
                vectors, token_count, _ = runtime.encode(texts)
                model = body.get("model") if isinstance(body.get("model"), str) else runtime.model_id
            except Exception as error:  # keep OpenAI-compatible error envelope
                runtime.failure()
                self._json(
                    400,
                    {"error": {"message": str(error), "type": type(error).__name__}},
                )
                return
            self._json(
                200,
                {
                    "object": "list",
                    "model": model,
                    "data": [
                        {"object": "embedding", "index": index, "embedding": vector}
                        for index, vector in enumerate(vectors)
                    ],
                    "usage": {"prompt_tokens": token_count, "total_tokens": token_count},
                },
            )

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-sequence-length", type=int, default=8192)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("battle server must bind to loopback")
    if args.batch_size < 1 or args.max_sequence_length < 128:
        raise SystemExit("invalid embedding budget")
    runtime = EmbeddingRuntime(args.model, args.device, args.batch_size, args.max_sequence_length)
    server = ThreadingHTTPServer((args.host, args.port), handler_for(runtime))
    print(
        json.dumps(
            {
                "status": "ready",
                "url": f"http://{args.host}:{args.port}/v1",
                "model": runtime.model_id,
                "dimension": runtime.dimension,
                "device": args.device,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
