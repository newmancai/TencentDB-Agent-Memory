import argparse
import json
from pathlib import Path
import numpy as np


def read(path):
    with path.open() as f:return [json.loads(x) for x in f]


def spans(tokens):
    result=[];current=None
    for t in tokens:
        if t['pred']==1:
            if current is None:current=[t['start'],t['end']]
            else:current[1]=t['end']
        elif current is not None:result.append(current);current=None
    if current is not None:result.append(current)
    return result


def metrics(tp,fp,fn):
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else 0,
            'recall':tp/(tp+fn) if tp+fn else 0,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0}


def main():
    p=argparse.ArgumentParser()
    for name in ['tasks','labels','predictions','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();tasks={r['id']:r for r in read(a.tasks)};gold={r['id']:r for r in read(a.labels)}
    predictions=read(a.predictions)
    assert len(predictions)==len(tasks) and len({r['id'] for r in predictions})==len(predictions)
    assert {r['id'] for r in predictions}==set(tasks)
    rows=[]
    for r in predictions:
        target={i for s in gold[r['id']]['spans'] for i in range(s['start'],s['end'])}
        chosen=spans(r['answer_tokens']) if r['error'] is None else []
        predicted={i for start,end in chosen for i in range(start,end)}
        rows.append({'id':r['id'],'source_kind':r['source_kind'],'unknown':r['error'] is not None,
            'gold_positive':bool(target),'predicted_positive':bool(chosen),
            'spans':chosen,'char_tp':len(target&predicted),'char_fp':len(predicted-target),
            'char_fn':len(target-predicted),'gold_characters':len(target)})
    result={'groups':len({r['group'] for r in predictions}),'layers':{}}
    for kind in ['all']+sorted({r['source_kind'] for r in rows}):
        selected=[r for r in rows if kind=='all' or r['source_kind']==kind];covered=[r for r in selected if not r['unknown']]
        result['layers'][kind]={'total':len(selected),'covered':len(covered),
            'unknown_positive':sum(r['gold_positive'] for r in selected if r['unknown']),
            'response_covered':metrics(sum(r['gold_positive'] and r['predicted_positive'] for r in covered),
                sum(not r['gold_positive'] and r['predicted_positive'] for r in covered),
                sum(r['gold_positive'] and not r['predicted_positive'] for r in covered)),
            'character_covered':metrics(*(sum(r[k] for r in covered) for k in ['char_tp','char_fp','char_fn'])),
            'gold_character_coverage_all_queue':sum(r['char_tp'] for r in selected)/max(1,sum(r['gold_characters'] for r in selected))}
    elapsed=[r['elapsed_ms'] for r in predictions if r['error'] is None]
    result['cost']={'forwards':len(elapsed),'processed_tokens':sum(r['tokens'] for r in predictions if r['error'] is None),
        'seconds':sum(elapsed)/1000,'forward_ms_p50_p95':np.quantile(elapsed,[.5,.95]).tolist()}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'rows.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
