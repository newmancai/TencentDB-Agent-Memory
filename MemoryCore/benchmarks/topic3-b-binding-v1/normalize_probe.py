"""Posthoc presentation-only readout, preserving original diagnostic receipts."""
import json
from pathlib import Path
import re
import sys


def final_anchor(text, allowed, output_tokens):
    m=re.findall(r'(?:^|\n)\s*(?:\*\*)?ANCHOR:\s*(\d+|unknown)(?:\*\*)?\s*$',text)
    value=int(m[0]) if len(m)==1 and m[0].isdigit() else None
    return value if value in allowed and output_tokens<512 else None


def main(root):
    gold=json.loads((root/'labels.json').read_text())
    direct={r['id']:r['arms']['direct']['prediction'] for r in map(json.loads,(root/'results.jsonl').open()) if r['split']=='fit'}
    rows=[]
    for r in map(json.loads,(root/'reasoning-probe.jsonl').open()):
        p=final_anchor(r['text'],range(1,int(r['id'].split(':')[1])+1),r['outputTokens'])
        rows.append({'id':r['id'],'strict_prediction':r['prediction'],'markdown_normalized_prediction':p,
                     'correct':p==gold[r['id']]['anchor'],'direct_correct':direct[r['id']]==gold[r['id']]['anchor']})
    summary={'n':len(rows),'strict_exact':sum(r['strict_prediction']==gold[r['id']]['anchor'] for r in rows),
             'normalized_exact':sum(r['correct'] for r in rows),
             'normalized_unknown':sum(r['markdown_normalized_prediction'] is None for r in rows),
             'wins':sum(r['correct'] and not r['direct_correct'] for r in rows),
             'losses':sum(r['direct_correct'] and not r['correct'] for r in rows),
             'note':'posthoc presentation normalization only; unchanged model receipts and gold; development diagnostic'}
    (root/'reasoning-normalized.json').write_text(json.dumps({'summary':summary,'rows':rows},indent=2)+'\n');print(summary)


if __name__=='__main__':main(Path(sys.argv[1]))
