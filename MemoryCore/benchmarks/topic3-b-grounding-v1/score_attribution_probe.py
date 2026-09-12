import argparse
from collections import Counter
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    labels={r['id']:r for r in read(a.run/'labels.jsonl')};rows=read(a.run/'predictions.jsonl')
    assert len(rows)==len(labels) and {r['id'] for r in rows}==set(labels)
    result={'arms':{},'paired':dict(win=0,loss=0,tie=0,unknown=0)}
    for arm in ['direct','attribution']:
        records=[r['arms'][arm] for r in rows];covered=[r for r in rows if r['arms'][arm]['parsed'] is not None]
        tp=fp=fn=tn=0
        for r in covered:
            pred=r['arms'][arm]['parsed']['relation']!='supported';gold=labels[r['id']]['unsupported_proxy']
            tp+=pred and gold;fp+=pred and not gold;fn+=not pred and gold;tn+=not pred and not gold
        result['arms'][arm]={'total':len(rows),'covered':len(covered),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'balanced_accuracy':.5*(tp/(tp+fn)+tn/(tn+fp)) if tp+fn and tn+fp else None,
            'relations':dict(Counter(r['parsed']['relation'] for r in records if r['parsed'])),
            'errors':dict(Counter(r['error'] for r in records if r['error'])),
            'outputs_with_citations':sum(bool(r['parsed']['evidence_ids']) for r in records if r['parsed']),
            'generations':sum(r['error']!='input_limit' for r in records),
            'input_tokens':sum(r['input_tokens'] for r in records if r['error']!='input_limit'),
            'output_tokens':sum(r['output_tokens'] for r in records),'seconds':sum(r['elapsed_ms'] for r in records)/1000}
    for r in rows:
        x,y=[r['arms'][k]['parsed'] for k in ['direct','attribution']]
        if x is None or y is None:result['paired']['unknown']+=1;continue
        cx=(x['relation']!='supported')==labels[r['id']]['unsupported_proxy'];cy=(y['relation']!='supported')==labels[r['id']]['unsupported_proxy']
        result['paired']['tie' if cx==cy else 'win' if cy else 'loss']+=1
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
