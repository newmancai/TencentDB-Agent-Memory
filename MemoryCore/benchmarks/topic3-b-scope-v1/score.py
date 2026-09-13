import json
from pathlib import Path
import sys
from collections import Counter


def items(value):
    return {(k,json.dumps(v,sort_keys=True,ensure_ascii=False)) for k,v in (value or {}).items()}


def main(root):
    labels=json.loads((root/'labels.json').read_text())
    rows=[json.loads(l) for l in (root/'results.jsonl').open()]
    assert len(rows)==30 and len({r['id'] for r in rows})==30
    result={'scope':'effective-constraint extraction component; not violation detection or task improvement','arms':{},'paired':{}}
    for split in ['fit','eval']:
        sub=[r for r in rows if r['split']==split]
        for arm in ['direct'] if split=='fit' else ['direct','unlabelled','feedback']:
            c=Counter();by_dialog={}
            for r in sub:
                p=r['arms'][arm];g=labels[r['id']];a=items(p['prediction']);b=items(g)
                exact=p['prediction'] is not None and p['prediction']==g
                c.update(n=1,exact=int(exact),family_exact=int(p['prediction'] is not None and set(p['prediction'])==set(g)),
                         tp=len(a&b),fp=len(a-b),fn=len(b-a),invalid=int(p['error'] is not None),
                         inputTokens=p['inputTokens'],outputTokens=p['outputTokens'],elapsedMs=p['elapsedMs'])
                pf=set(p['prediction'] or {});gf=set(g)
                c.update(family_tp=len(pf&gf),family_fp=len(pf-gf),family_fn=len(gf-pf))
                d=by_dialog.setdefault(r['id'].split(':')[0],{'n':0,'exact':0});d['n']+=1;d['exact']+=exact
            c=dict(c);c['precision']=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None
            c['recall']=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None
            c['family_precision']=c['family_tp']/(c['family_tp']+c['family_fp']) if c['family_tp']+c['family_fp'] else None
            c['family_recall']=c['family_tp']/(c['family_tp']+c['family_fn']) if c['family_tp']+c['family_fn'] else None
            c['by_dialog']=by_dialog;result['arms'][f'{split}/{arm}']=c
    for baseline in ['direct','unlabelled']:
        c=Counter(win=0,loss=0,tie=0)
        for r in rows:
            if r['split']!='eval':continue
            left=r['arms'][baseline]['prediction']==labels[r['id']]
            right=r['arms']['feedback']['prediction']==labels[r['id']]
            c['win' if right and not left else 'loss' if left and not right else 'tie']+=1
        result['paired'][f'feedback_vs_{baseline}']=dict(c)
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main(Path(sys.argv[1]))
