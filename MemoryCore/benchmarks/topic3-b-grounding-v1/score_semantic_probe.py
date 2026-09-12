import argparse
import json
from pathlib import Path


def read(p):return [json.loads(x) for x in p.read_text().splitlines()]


def detectors(previous,run):
    rows=[]
    for p in read(previous/'predictions.jsonl'):
        if p['id'].endswith('::ordinary'):rows.append({**p,'id':p['id'].replace('::ordinary','::linked')})
    return rows+read(run/'detector-predictions.jsonl')


def metrics(rows):
    c=[r for r in rows if r['prediction'] is not None]
    tp=sum(r['prediction'] and r['gold'] for r in c);fp=sum(r['prediction'] and not r['gold'] for r in c)
    fn=sum(not r['prediction'] and r['gold'] for r in c);tn=sum(not r['prediction'] and not r['gold'] for r in c)
    return {'total':len(rows),'covered':len(c),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'balanced_accuracy':(tp/(tp+fn)+tn/(tn+fp))/2 if tp+fn and tn+fp else None}


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['allow','score'])
    for n in ['previous','run','out']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();det=detectors(a.previous,a.run);labels={r['id']:r for r in read(a.run/'labels.jsonl')}
    assert len(det)==len(labels) and {r['id'] for r in det}==set(labels)
    if a.mode=='allow':a.out.write_text(json.dumps([r['id'] for r in det if r['error'] is None])+'\n');return
    sem=read(a.run/'semantic-predictions.jsonl');assert len(sem)==len(labels) and {r['id'] for r in sem}==set(labels)
    rows=[]
    for name,records in [('detector',det),('semantic',sem)]:
        for r in records:
            l=labels[r['id']]
            pred=None if r['error'] else (any(t['pred']==1 for t in r['answer_tokens']) if name=='detector' else max(range(3),key=lambda i:r['logits'][i])!=0)
            rows.append({'id':r['id'],'pair':l['pair'],'category':l['category'],'scope':l['scope'],'model':name,'gold':l['unsupported_proxy'],'prediction':pred})
    common=set(r['pair'] for r in rows)-set(r['pair'] for r in rows if r['prediction'] is None)
    result={'four_arm_common_pairs':len(common),'arms':{},'common_arms':{},'scope_common_arms':{},'cost':{}}
    for model in ['detector','semantic']:
        for scope in ['linked','sessions']:
            selected=[r for r in rows if r['model']==model and r['scope']==scope];key=model+'_'+scope
            result['arms'][key]=metrics(selected);result['common_arms'][key]=metrics([r for r in selected if r['pair'] in common])
            scope_unknown={r['pair'] for r in rows if r['scope']==scope and r['prediction'] is None}
            result['scope_common_arms'][key]=metrics([r for r in selected if r['pair'] not in scope_unknown])
            result['arms'][key]['categories']={str(c):metrics([r for r in selected if r['category']==c]) for c in [1,2,4,5]}
            records=[r for r in (det if model=='detector' else sem) if labels[r['id']]['scope']==scope]
            result['cost'][key]={'reused_from_previous_run':model=='detector' and scope=='linked','forwards':sum(r['error'] is None for r in records),'tokens':sum(r['tokens'] for r in records if r['error'] is None),'seconds':sum(r['elapsed_ms'] for r in records)/1000}
    result['paired']={}
    for scope in ['linked','sessions']:
        mapping={(r['pair'],r['model']):r for r in rows if r['scope']==scope};win=loss=tie=0
        for pair in {r['pair'] for r in rows}:
            x,y=[mapping[pair,m] for m in ['detector','semantic']]
            if x['prediction'] is None or y['prediction'] is None:continue
            cx=x['prediction']==x['gold'];cy=y['prediction']==y['gold']
            win+=cy and not cx;loss+=cx and not cy;tie+=cx==cy
        result['paired'][scope]={'semantic_win':win,'semantic_loss':loss,'tie':tie}
    masses=sorted(r['letter_mass'] for r in sem if r['letter_mass'] is not None)
    result['semantic_letter_mass']={'min':min(masses),'median':masses[len(masses)//2],'max':max(masses)}
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(a.out/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps({k:v for k,v in result.items() if k!='arms'},indent=2))


if __name__=='__main__':main()
