import argparse
import json
from pathlib import Path
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tasks', type=Path, required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0').eval()
    with args.out.open('x') as output, args.tasks.open() as source:
        for line in source:
            task = json.loads(line)
            completion = tok.encode(task['answer']['text'].rstrip()+tok.eos_token, add_special_tokens=False)
            original_length = len(completion)
            completion = completion[:4096]
            histories = {}
            for arm, field in [('prior', None), ('real', 'followup'), ('control', 'control_followup')]:
                history = [{'role': m['role'], 'content': m['text']} for m in task['history']]
                if field:
                    history.append({'role': 'assistant', 'content':
                        '=== HINDSIGHT CONTEXT ===\n'
                        '[The following is a future user message. Use this to guide your answer to the user prompt.]\n'
                        +task[field]['text'].strip()})
                prompt = tok.apply_chat_template(history, tokenize=False, add_generation_prompt=True,
                                                  enable_thinking=False)
                histories[arm] = tok.encode(prompt, add_special_tokens=False)
            record = {'id': task['id'], 'answer_tokens_original': original_length,
                      'answer_tokens_scored': len(completion), 'answer_capped': original_length > 4096,
                      'error': None, 'arms': {}}
            if max(len(x) for x in histories.values())+len(completion)>32768:
                record['error'] = 'input_limit'
            else:
                for arm, prefix in histories.items():
                    inputs = torch.tensor([prefix+completion], device='cuda:0')
                    targets = torch.tensor(completion, device='cuda:0')
                    torch.cuda.synchronize(); started = time.perf_counter()
                    with torch.inference_mode():
                        logits = model(input_ids=inputs, use_cache=False,
                                       logits_to_keep=len(completion)+1).logits[0, :-1]
                        assert logits.shape[0] == len(completion)
                        values = []
                        for start in range(0, len(completion), 128):
                            values.extend((-torch.nn.functional.cross_entropy(
                                logits[start:start+128].float(), targets[start:start+128],
                                reduction='none')).cpu().tolist())
                        del logits
                    torch.cuda.synchronize()
                    record['arms'][arm] = {'mean_logp': sum(values)/len(values),
                        'token_logp': values, 'prefix_tokens': len(prefix),
                        'processed_tokens': len(prefix)+len(completion),
                        'elapsed_ms': (time.perf_counter()-started)*1000}
            output.write(json.dumps(record)+'\n'); output.flush()
            print(task['id'], record['error'], len(completion), flush=True)


if __name__ == '__main__':
    main()
