"""Pinned local model adapters. Neither mode opens public answer/audit labels."""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["score", "serve"])
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--port", type=int, default=18779)
    a = p.parse_args()
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification
    tokenizer = AutoTokenizer.from_pretrained(a.model, local_files_only=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    if a.mode == "score":
        model = AutoModelForSequenceClassification.from_pretrained(a.model, local_files_only=True).to(a.device).eval()
        labels = [model.config.id2label[i] for i in range(3)]
        assert labels == ["contradiction", "entailment", "neutral"]
        output = {}
        for t in json.loads(a.input.read_text()):
            for c in t["candidates"]:
                start = time.perf_counter()
                encoded = tokenizer(c["newQuote"], c["oldQuote"], return_tensors="pt", truncation=False)
                n = int(encoded["attention_mask"].sum())
                if n > 512:
                    output[c["id"]] = dict(score=1, error="pair exceeds 512 tokens", inputTokens=n, elapsedMs=0)
                    continue
                with torch.inference_mode():
                    probs = model(**encoded.to(a.device)).logits.softmax(-1)[0].cpu().tolist()
                output[c["id"]] = dict(score=probs[0], probabilities=dict(zip(labels, probs)), inputTokens=n,
                                       elapsedMs=(time.perf_counter() - start) * 1000)
        a.output.write_text(json.dumps(output, indent=2))
        print(json.dumps({"scored": len(output)}), flush=True)
        return

    model = AutoModelForCausalLM.from_pretrained(a.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(a.device).eval()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"ready":true}')

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 1024 * 1024:
                    raise ValueError("invalid request size")
                req = json.loads(self.rfile.read(size))
                maximum = req["maxTokens"]
                if not isinstance(maximum, int) or not 1 <= maximum <= 256:
                    raise ValueError("invalid output budget")
                with lock:
                    text = tokenizer.apply_chat_template(req["messages"], tokenize=False, add_generation_prompt=True)
                    encoded = tokenizer(text, return_tensors="pt", truncation=False).to(a.device)
                    n = int(encoded["attention_mask"].sum())
                    if n > 16384:
                        raise ValueError("input exceeds 16384 tokens; no truncation")
                    torch.manual_seed(20260912)
                    start = time.perf_counter()
                    with torch.inference_mode():
                        out = model.generate(**encoded, do_sample=False, max_new_tokens=maximum,
                                             pad_token_id=tokenizer.eos_token_id)
                    torch.cuda.synchronize()
                    result = dict(text=tokenizer.decode(out[0, n:], skip_special_tokens=True).strip(),
                                  inputTokens=n, outputTokens=int(out.shape[1] - n),
                                  elapsedMs=(time.perf_counter() - start) * 1000,
                                  truncated=int(out.shape[1] - n) >= maximum)
                    with a.output.open("a") as f:
                        f.write(json.dumps({"request": req, "result": result}, ensure_ascii=False) + "\n")
                status = 200
            except Exception as e:
                status, result = 400, {"error": str(e)}
            data = json.dumps(result).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(json.dumps({"ready": True, "port": a.port}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
