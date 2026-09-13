"""No-inference feedback representations and exact tokenizer cost accounting."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    for key in ['events','receipts','tokenizer','out']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(a.tokenizer,local_files_only=True)
    with a.events.open() as f:events=[json.loads(l) for l in f if l.strip()]
    with a.receipts.open() as f:receipts={r['id']:r for l in f if l.strip() for r in [json.loads(l)]}
    totals={k:0 for k in ['raw','request_raw','parent_raw','full_prefix','summary']};rows=[];raw_view=[]
    for e in events:
        prefix=e['prefix'];r=receipts[e['id']]
        assert prefix[-1]['evidence_id']==e['feedback_id'] and prefix[-2]['evidence_id']==e['response_id']
        def render(messages):
            return '\n\n'.join(f"[{m['evidence_id']}] {m['role']}: {m['content']}" for m in messages)
        variants={'raw':render(prefix[-1:]),'request_raw':render([prefix[0],prefix[-1]]),
                  'parent_raw':render(prefix[-2:]),'full_prefix':render(prefix),
                  'summary':r['text']}
        counts={k:len(tok.encode(v,add_special_tokens=False)) for k,v in variants.items()}
        for key,value in counts.items():totals[key]+=value
        rows.append({'id':e['id'],'variants':variants,'tokens':counts})
        raw_view.append({'id':e['id'],'feedback':prefix[-1]['content']})
    a.out.mkdir(parents=True,exist_ok=True)
    for name,records in [('packets',rows),('raw-only-review',raw_view)]:
        (a.out/f'{name}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    summary={'mode':'raw_feedback_cost_diagnostic','events':len(events),'payload_tokens':totals,
        'per_event':[{'id':r['id'],'tokens':r['tokens']} for r in rows],
        'scope':'Same available prefix; different returned information and sizes, not equal-budget quality comparison. '
                'Payload tokens exclude transport envelope/chat template. Raw variants perform no model inference. '
                'Prior summary generation cost reported separately, not erased.'}
    (a.out/'raw-cost-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
