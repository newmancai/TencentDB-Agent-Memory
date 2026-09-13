"""Generate common answers without exposing construction labels to the model."""
import json
from pathlib import Path
import sys
import time


def prepare(source, out, dialog=1):
    rows = [json.loads(line) for line in (source / f'dialog_{dialog}.jsonl').open()]
    assert [r['turn'] for r in rows] == list(range(1, 51))
    tasks = [{'turn': r['turn'], 'user': r['user_query_verified']} for r in rows]
    assert all(isinstance(r['user'], str) and r['user'].strip() for r in tasks)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'messages.json').write_text(json.dumps(tasks, ensure_ascii=False))
    (out / 'selection.json').write_text(json.dumps({'dataset': 'KikiNLP/EvolIF',
        'revision': '47115ae2af4830948f3f15697221a1acca6078a7',
        'dialog': dialog, 'split': 'development_reuse' if dialog == 1 else 'evaluation',
        'turns': len(tasks)}, indent=2))


def generate(root, model_path):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tasks = json.loads((root / 'messages.json').read_text())
    tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0').eval()
    history = []
    records = []
    with (root / 'answers.jsonl').open('x') as output:
        for task in tasks:
            history.append({'role': 'user', 'content': task['user']})
            prompt = tok.apply_chat_template(history, tokenize=False, add_generation_prompt=True)
            enc = tok(prompt, return_tensors='pt').to('cuda:0')
            n = enc['input_ids'].shape[1]
            r = {'turn': task['turn'], 'inputTokens': n, 'outputTokens': 0,
                 'elapsedMs': 0, 'text': '', 'error': None}
            if n > 32768:
                r['error'] = 'input_limit'
            else:
                torch.cuda.synchronize()
                start = time.perf_counter()
                with torch.inference_mode():
                    ids = model.generate(**enc, do_sample=False, max_new_tokens=512,
                                         pad_token_id=tok.eos_token_id)
                torch.cuda.synchronize()
                r.update(elapsedMs=(time.perf_counter()-start)*1000,
                         outputTokens=int(ids.shape[1]-n),
                         text=tok.decode(ids[0, n:], skip_special_tokens=True))
                if r['outputTokens'] >= 512:
                    r['error'] = 'output_limit'
            output.write(json.dumps(r, ensure_ascii=False)+'\n')
            output.flush()
            records.append(r)
            print(json.dumps({'turn': task['turn'], 'error': r['error']}), flush=True)
            if r['error'] == 'input_limit':
                break
            history.append({'role': 'assistant', 'content': r['text']})
    summary = {'requested': len(tasks), 'observed': len(records),
               'unobserved': len(tasks)-len(records),
               'capped': sum(r['error']=='output_limit' for r in records),
               'input_limit': sum(r['error']=='input_limit' for r in records)}
    for k in ['inputTokens', 'outputTokens', 'elapsedMs']:
        summary[k] = sum(r[k] for r in records)
    (root / 'generation-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv)>4 else 1)
    else:
        generate(Path(sys.argv[2]), sys.argv[3])
