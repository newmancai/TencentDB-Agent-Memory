"""Real local embeddings for native hybrid baseline; no gold or target IDs read."""
import argparse
import json
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('runtime', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--split', required=True)
    a = p.parse_args()
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    cases = [c for c in json.loads(a.runtime.read_text()) if c['split'] == a.split]
    documents = sorted({s['content'] for c in cases for s in c['sources']})
    queries = sorted({c['observation']['content'] for c in cases})
    tokenizer = AutoTokenizer.from_pretrained(a.model, local_files_only=True, padding_side='left')
    model = AutoModel.from_pretrained(a.model, local_files_only=True, torch_dtype=torch.bfloat16,
                                       attn_implementation='sdpa').to('cuda:0').eval()
    result = dict(model=str(a.model), split=a.split, dimensions=1024, documents={}, queries={})
    start = time.perf_counter(); tokens = 0
    for kind, texts in [('documents', documents), ('queries', queries)]:
        for offset in range(0, len(texts), 16):
            batch = texts[offset:offset + 16]
            inputs = batch if kind == 'documents' else ['Instruct: Retrieve earlier statements relevant to the new observation.\nQuery:' + s for s in batch]
            encoded = tokenizer(inputs, padding=True, truncation=False, return_tensors='pt').to('cuda:0')
            if encoded['input_ids'].shape[1] > 8192:
                raise ValueError('input exceeds budget; no truncation')
            tokens += int(encoded['attention_mask'].sum())
            with torch.inference_mode():
                vectors = F.normalize(model(**encoded).last_hidden_state[:, -1].float(), p=2, dim=1).cpu().tolist()
            result[kind].update(zip(batch, vectors))
            if offset % 512 == 0:
                print(json.dumps(dict(kind=kind, completed=min(offset + 16, len(texts)), total=len(texts))), flush=True)
    torch.cuda.synchronize()
    result.update(seconds=time.perf_counter() - start, input_tokens=tokens)
    a.output.write_text(json.dumps(result) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('documents', 'queries')}), flush=True)


if __name__ == '__main__':
    main()
