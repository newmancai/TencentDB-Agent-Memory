"""Shared real-model loopback endpoint; native templates, no answer or tool-call repair."""
import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Runtime:
    def __init__(self, model_path, receipts, defaults=None):
        import torch
        from transformers import AutoTokenizer, AutoModelForImageTextToText
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForImageTextToText.from_pretrained(model_path, local_files_only=True,
            dtype=torch.bfloat16, device_map='auto', max_memory={0:'21GiB',1:'21GiB'},
            attn_implementation='sdpa').eval()
        self.device = self.model.get_input_embeddings().weight.device
        self.receipts = receipts; receipts.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.defaults = defaults or {}
        self.active = None
        self.stats = dict(calls=0, prompt_tokens=0, completion_tokens=0, generation_seconds=0.)
        from tool_envelope import parse_tool_output
        self.parse_tools = parse_tool_output

    def complete(self, request):
        if request.get('model') != 'Qwen3.5-9B':
            raise ValueError('model must be Qwen3.5-9B')
        if request.get('stream'):
            raise ValueError('streaming unsupported')
        settings = {**self.defaults, **{k: request[k] for k in
            ('temperature','top_p','top_k','presence_penalty','enable_thinking') if k in request}}
        temperature = float(settings.get('temperature', 0))
        thinking = bool(settings.get('enable_thinking', False))
        presence = float(settings.get('presence_penalty', 0))
        if not 0 <= temperature <= 2 or not 0 <= presence <= 2:
            raise ValueError('unsupported temperature/presence penalty')
        if request.get('response_format', {}).get('type') not in (None, 'text'):
            raise ValueError('JSON grammar is unsupported; use documented soft-schema provider mode')
        if request.get('seed', 20260908) != 20260908:
            raise ValueError('seed must be 20260908')
        messages = request.get('messages')
        if not isinstance(messages, list) or not messages:
            raise ValueError('messages required')
        messages = [dict(m) for m in messages]
        for m in messages:
            if isinstance(m.get('content'), list):
                if any(part.get('type') != 'text' for part in m['content']):
                    raise ValueError('text inputs only')
                m['content'] = '\n'.join(part['text'] for part in m['content'])
        maximum = request.get('max_completion_tokens', request.get('max_tokens', 4096))
        if type(maximum) is not int or not 1 <= maximum <= 16384:
            raise ValueError('output budget must be within 1..16384')
        queued = time.perf_counter()
        with self.lock:
            self.torch.manual_seed(20260908)
            tools = request.get('tools') or []
            rendered = self.tokenizer.apply_chat_template(messages, tools=tools or None,
                tokenize=False, add_generation_prompt=True, enable_thinking=thinking)
            encoded = self.tokenizer(rendered, return_tensors='pt', truncation=False).to(self.device)
            n = encoded['input_ids'].shape[1]
            if n > 32768:
                raise ValueError('input exceeds 32768 tokens; no truncation')
            started = time.perf_counter()
            call_id = uuid.uuid4().hex
            self.active = dict(id=call_id, input_tokens=n, maximum=maximum, started_at=time.time())
            print(json.dumps(dict(event='generation_start', **self.active)), flush=True)
            kwargs = dict(max_new_tokens=maximum, do_sample=temperature > 0)
            if temperature > 0:
                kwargs.update(temperature=temperature, top_p=float(settings.get('top_p',1)),
                    top_k=int(settings.get('top_k',0)))
            if presence:
                from transformers import LogitsProcessor, LogitsProcessorList
                torch = self.torch
                class PresencePenalty(LogitsProcessor):
                    def __call__(self, input_ids, scores):
                        for i in range(input_ids.shape[0]):
                            seen=torch.unique(input_ids[i,n:])
                            scores[i,seen] -= presence
                        return scores
                kwargs['logits_processor'] = LogitsProcessorList([PresencePenalty()])
            try:
                with self.torch.inference_mode():
                    generated = self.model.generate(**encoded, **kwargs)
            finally:
                self.active = None
            self.torch.cuda.synchronize()
            seconds = time.perf_counter() - started
            raw = self.tokenizer.decode(generated[0, n:], skip_special_tokens=True).strip()
            output_tokens = int(generated.shape[1] - n)
            record = dict(id=call_id, request=request, effective_generation=settings, raw_output=raw, input_tokens=n,
                output_tokens=output_tokens, generation_seconds=seconds, queue_seconds=started-queued)
            # Save the actual generation even if envelope parsing subsequently fails.
            with self.receipts.open('a') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            self.stats['calls'] += 1; self.stats['prompt_tokens'] += n
            self.stats['completion_tokens'] += output_tokens; self.stats['generation_seconds'] += seconds
            # The native thinking template opens the reasoning segment in the prompt.
            # Do not expose an unfinished reasoning segment as a final answer/tool call.
            final = raw.split('</think>',1)[1].strip() if thinking and '</think>' in raw else ('' if thinking else raw)
            message = self.parse_tools(final, {t['function']['name'] for t in tools}, call_id)
            print(json.dumps(dict(event='generation_end', id=call_id, output_tokens=output_tokens, seconds=seconds)), flush=True)
            reason = 'tool_calls' if message.get('tool_calls') else ('length' if output_tokens >= maximum else 'stop')
            return dict(id='chatcmpl-'+call_id, object='chat.completion', created=int(time.time()),
                model='Qwen3.5-9B', choices=[dict(index=0, message=message, finish_reason=reason)],
                usage=dict(prompt_tokens=n, completion_tokens=output_tokens, total_tokens=n+output_tokens))


def main():
    p = argparse.ArgumentParser(); p.add_argument('--model', type=Path, required=True)
    p.add_argument('--receipts', type=Path, required=True); p.add_argument('--port', type=int, default=18735)
    p.add_argument('--generation-config', type=Path)
    a = p.parse_args(); runtime = Runtime(a.model, a.receipts,
        json.loads(a.generation_config.read_text()) if a.generation_config else None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def send(self, status, body):
            data=json.dumps(body).encode(); self.send_response(status)
            self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            if self.path == '/v1/models':
                self.send(200, dict(object='list', data=[dict(id='Qwen3.5-9B', object='model')]))
            elif self.path == '/stats':
                self.send(200, {**runtime.stats, 'active':runtime.active, 'generation_defaults':runtime.defaults})
            else:
                self.send(404, dict(error='unknown endpoint'))
        def do_POST(self):
            if self.path != '/v1/chat/completions':
                self.send(404, dict(error='unknown endpoint')); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8*1024*1024:
                    raise ValueError('invalid request size')
                request = json.loads(self.rfile.read(size))
                self.send(200, runtime.complete(request))
            except Exception as error:
                self.send(400, dict(error=dict(message=str(error), type=type(error).__name__)))

    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print(json.dumps(dict(ready=True, port=a.port, model='Qwen3.5-9B')), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
