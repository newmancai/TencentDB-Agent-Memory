"""Same-evidence ordering control, no answer-label input."""
import argparse
import json
import time
import urllib.request
from pathlib import Path
from qualify import READER


def main():
    p = argparse.ArgumentParser()
    p.add_argument('privileged', type=Path)
    p.add_argument('native', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--endpoint', default='http://127.0.0.1:18781')
    a = p.parse_args()
    # Only query/id are consumed; privileged pair is not used in this control.
    tasks = json.loads(a.privileged.read_text())
    native = {t['id']: t for t in json.loads(a.native.read_text())}
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / 'results.jsonl').open('x') as output:
        for i, t in enumerate(tasks):
            result = dict(id=t['id'], readers={})
            for arm in (['oldest_first', 'newest_first'] if i % 2 == 0 else ['newest_first', 'oldest_first']):
                sources = sorted(native[t['id']]['native'], key=lambda s: s['order'], reverse=arm == 'newest_first')
                inp = dict(question=t['query'], ordering=arm,
                           evidence=[dict(content=s['content'], date=s['date']) for s in sources])
                req = dict(messages=[dict(role='system', content=READER +
                    ' Evidence order is stated in ordering. Use dates, factual timing and scope; do not assume the first or last item is correct.'),
                    dict(role='user', content=json.dumps(inp, ensure_ascii=False))], maxTokens=96)
                start = time.perf_counter()
                try:
                    request = urllib.request.Request(a.endpoint, json.dumps(req).encode(), {'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request, timeout=180) as response:
                        body = json.load(response)
                    if body.get('truncated'):
                        body['error'] = 'truncated'
                except Exception as e:
                    body = dict(error=str(e))
                result['readers'][arm] = dict(body, wallMs=(time.perf_counter() - start) * 1000, request=req)
            output.write(json.dumps(result, ensure_ascii=False) + '\n'); output.flush()
            print(json.dumps(dict(id=t['id'], answers={k: v.get('text') for k, v in result['readers'].items()})), flush=True)


if __name__ == '__main__':
    main()
