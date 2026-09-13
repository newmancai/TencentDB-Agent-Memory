import json
import math
import statistics
import sys
from pathlib import Path
from policy import fit as fit_policy, choose


def metrics(rows, labels, arm):
    tp=fp=fn=tn=abstain=exact=located=evidence_known=raw_correct=any_hit=0
    for r in rows:
        d, g = r['arms'][arm], labels[r['id']]
        p, y = d['contradiction'], g['contradiction']
        if p is None: abstain += 1
        elif p and y: tp += 1
        elif p: fp += 1
        elif y: fn += 1
        else: tn += 1
        # human-bot provides binary labels but empty evidence even for positives.
        # Missing annotation is not an empty gold evidence set.
        known = not y or bool(g['evidence'])
        evidence_known += known
        if known and p is not None and p == y and set(d['evidence']) == set(g['evidence']): exact += 1
        if y and g['evidence'] and p and set(d['evidence']) == set(g['evidence']): located += 1
        if y and g['evidence'] and p and set(d['evidence']) & set(g['evidence']): any_hit += 1
        try:
            raw=json.loads(d['receipt']['text']).get('contradiction')
            raw_correct += type(raw) is bool and raw == y
        except (ValueError,AttributeError):pass
    positive = sum(labels[r['id']]['contradiction'] for r in rows)
    receipts = [r['arms'][arm]['receipt'] for r in rows]
    times = sorted(x['elapsedMs'] for x in receipts if 'elapsedMs' in x)
    return dict(n=len(rows), positive=positive, correct=tp+tn, tp=tp,fp=fp,fn=fn,tn=tn,abstain=abstain,
                precision=tp/(tp+fp) if tp+fp else None, recall=tp/positive if positive else None,
                raw_binary_correct=raw_correct,
                joint_exact_known=exact, joint_evidence_denominator=evidence_known,
                positive_evidence_exact=located if any(labels[r['id']]['contradiction'] and labels[r['id']]['evidence'] for r in rows) else None,
                positive_evidence_denominator=sum(bool(labels[r['id']]['contradiction'] and labels[r['id']]['evidence']) for r in rows),
                true_positive_evidence_any_hit=any_hit if any(labels[r['id']]['contradiction'] and labels[r['id']]['evidence'] for r in rows) else None,
                cost=dict(inputTokens=sum(x['inputTokens'] for x in receipts), outputTokens=sum(x['outputTokens'] for x in receipts),
                          serviceMs=sum(times), p50Ms=statistics.median(times) if times else None,
                          p95Ms=times[max(0,math.ceil(len(times)*.95)-1)] if times else None))


def main(root):
    rows = [json.loads(s) for s in (root/'results.jsonl').read_text().splitlines()]
    tasks = json.loads((root/'tasks.json').read_text())
    assert len(rows)==len(tasks)==192
    assert {r['id'] for r in rows}=={r['id'] for r in tasks}
    labels = json.loads((root/'labels.json').read_text())
    fit = [r for r in rows if r['split']=='fit']
    policy=fit_policy([dict(label=labels[r['id']]['contradiction'], direct=r['arms']['direct']['contradiction'],
                           local=r['arms']['local']['contradiction']) for r in fit])
    selected = choose(policy)['arm']
    (root/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    summary=dict(protocol='v1.1-missing-evidence-correction', scope='DECODE component signal/grounding; not lifecycle or long-conversation validation',policy=policy,splits={})
    for split in ('fit','eval'):
        subset=[r for r in rows if r['split']==split]
        m={a:metrics(subset,labels,a) for a in ('direct','local')}
        wins=losses=ties=0
        for r in subset:
            g=labels[r['id']]['contradiction']
            a=r['arms']['direct']['contradiction']==g
            b=r['arms']['local']['contradiction']==g
            if b and not a:wins+=1
            elif a and not b:losses+=1
            else:ties+=1
        discordant=wins+losses
        pvalue=min(1.,2*sum(math.comb(discordant,k) for k in range(min(wins,losses)+1))/2**discordant) if discordant else 1.
        summary['splits'][split]=dict(arms=m,local_vs_direct=dict(wins=wins,losses=losses,ties=ties,
                                                               paired_exact_two_sided_p=pvalue),selected_arm=selected)
    summary['learning_cost_note']='Both arms must be collected on fit; arm selection adds no eval calls. Fixed-arm comparison must count this cold-start cost.'
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main(Path(sys.argv[1]))
