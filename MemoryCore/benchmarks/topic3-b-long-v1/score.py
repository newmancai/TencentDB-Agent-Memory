import json
import math
from pathlib import Path
import statistics
import sys


def main(root,reviews):
    tasks=json.loads((root/'tasks.json').read_text());refs=json.loads((root/'references.json').read_text())
    ns=json.loads((root/'native/results.json').read_text());rs=[json.loads(l) for l in (root/'relations.jsonl').read_text().splitlines()]
    assert len(tasks)==len(ns)==len(rs)==54
    assert {t['id'] for t in tasks}=={r['id'] for r in rs}=={n['id'] for n in ns}
    result=dict(scope='known LME development checkpoints; assistant-silver reference pairs only',writes=sum(n['writes'] for n in ns),tasks=len(tasks),not_applicable=len(json.loads((root/'not-applicable.json').read_text())),arms={},reviews={})
    for arm in ['fts','recent']:
        selected=sum(len(r['pools'][arm]) for r in rs)
        result['arms'][arm]=dict(selected=selected,reference_reached=sum(refs[r['id']]['old']['id'] in r['pools'][arm] for r in rs),thresholds={})
        for threshold in [.5,.7]:
            c=dict(alarms=0,reference_alarms=0,unlabeled_other_alarms=0,unknown=0)
            for r in rs:
                ref=refs[r['id']]['old']['id']
                for key in r['pools'][arm]:
                    p=r['scores'][key]['score']
                    if p is None:c['unknown']+=1
                    elif p>=threshold:
                        c['alarms']+=1;c['reference_alarms']+=key==ref;c['unlabeled_other_alarms']+=key!=ref
            result['arms'][arm]['thresholds'][str(threshold)]=c
    for review in reviews:
        gold={r['id']:r['relation'] for r in json.loads(review.read_text())['rows']}
        report={}
        for relation in ['changed','same','unknown']:
            sub=[r for r in rs if gold[r['id']]==relation];c=dict(n=len(sub))
            for arm in ['fts','recent']:
                c[arm+'_reference_reached']=sum(refs[r['id']]['old']['id'] in r['pools'][arm] for r in sub)
            for threshold in [.5,.7]:
                c['oracle_alarm_'+str(threshold)]=sum(r['scores'][refs[r['id']]['old']['id']]['score'] is not None and r['scores'][refs[r['id']]['old']['id']]['score']>=threshold for r in sub)
                for arm in ['fts','recent']:
                    c[arm+'_reference_alarm_'+str(threshold)]=sum(refs[r['id']]['old']['id'] in r['pools'][arm] and r['scores'][refs[r['id']]['old']['id']]['score'] is not None and r['scores'][refs[r['id']]['old']['id']]['score']>=threshold for r in sub)
            report[relation]=c
        result['reviews'][review.name]=report
    scores=[s for r in rs for s in r['scores'].values()]
    result['costs']={}
    for name,subset in [('online_union',[s for s in scores if not s['oracle_only']]),('oracle_extra',[s for s in scores if s['oracle_only']])]:
        result['costs'][name]=dict(requests=len(subset),executed=sum(s['score'] is not None for s in subset),
            inputTokens=sum(s['inputTokens'] for s in subset if s['score'] is not None),overLimit=sum(s['score'] is None for s in subset),forwardMs=sum(s['elapsedMs'] for s in subset))
    times=sorted(n['fts']['elapsedMs'] for n in ns)
    result['fts_latency']=dict(p50=statistics.median(times),p95=times[math.ceil(.95*len(times))-1],sumMs=sum(times))
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main(Path(sys.argv[1]),list(map(Path,sys.argv[2:])))
