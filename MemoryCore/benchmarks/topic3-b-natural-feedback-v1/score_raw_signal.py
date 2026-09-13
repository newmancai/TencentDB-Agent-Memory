import argparse
import json
from pathlib import Path
import numpy as np
from scipy.special import softmax
from sklearn.metrics import roc_auc_score
from run import read, SEED


def main():
    p = argparse.ArgumentParser()
    for key in ['data', 'tasks', 'scores', 'semantic', 'out']:
        p.add_argument('--'+key, type=Path, required=True)
    args = p.parse_args()
    tasks = read(args.tasks); receipts = read(args.scores)
    assert len(receipts) == len(tasks) and len({r['id'] for r in receipts}) == len(receipts)
    assert {r['id'] for r in receipts} == {t['id'] for t in tasks}
    by_id = {t['id']: t for t in tasks}
    labels = {r['id']: r['label'] for r in read(args.data/'labels.jsonl')}
    semantic = {r['id']: r for r in read(args.semantic)}
    rows = []
    for r in receipts:
        if r['error'] is not None: continue
        for arm in r['arms'].values():
            assert len(arm['token_logp']) == r['answer_tokens_scored']
            assert abs(np.mean(arm['token_logp'])-arm['mean_logp']) < 1e-8
        a = {k: v['mean_logp'] for k,v in r['arms'].items()}
        rows.append({'id': r['id'], 'group': by_id[r['id']]['group'],
                     'negative': labels[r['id']].startswith('NEG_'), 'capped': r['answer_capped'],
                     'prior_nll': -a['prior'], 'hindsight_nll': -a['real'],
                     'real_drop': a['prior']-a['real'], 'control_drop': a['prior']-a['control'],
                     'semantic_negative': float(softmax(semantic[r['id']]['logits'])[:4].sum())})
    names = ['prior_nll','hindsight_nll','real_drop','control_drop','semantic_negative']
    result = {'events':len(receipts), 'unknown':len(receipts)-len(rows),
              'capped':sum(r['capped'] for r in rows), 'layers':{}}
    for layer, subset in [('all',rows), ('uncapped',[r for r in rows if not r['capped']])]:
        y = [r['negative'] for r in subset]
        result['layers'][layer] = {'n': len(subset), 'negative':sum(y),
            'auc':{name:float(roc_auc_score(y,[r[name] for r in subset])) for name in names}}
    groups = sorted({r['group'] for r in rows})
    indices = {g:[i for i,r in enumerate(rows) if r['group']==g] for g in groups}
    rng = np.random.default_rng(SEED); deltas = {name:[] for name in ['control_drop','hindsight_nll','semantic_negative']}
    for _ in range(1000):
        sample = [rows[i] for g in rng.choice(groups,len(groups),replace=True) for i in indices[g]]
        y = [r['negative'] for r in sample]
        if len(set(y)) < 2: continue
        real = roc_auc_score(y,[r['real_drop'] for r in sample])
        for name in deltas: deltas[name].append(real-roc_auc_score(y,[r[name] for r in sample]))
    result['descriptive_group_bootstrap_real_auc_minus_95'] = {k:np.quantile(v,[.025,.975]).tolist() for k,v in deltas.items()}
    result['cost'] = {arm:{'forwards':sum(arm in r['arms'] for r in receipts),
        'processed_tokens':sum(r['arms'].get(arm,{}).get('processed_tokens',0) for r in receipts),
        'seconds':sum(r['arms'].get(arm,{}).get('elapsed_ms',0) for r in receipts)/1000}
        for arm in ['prior','real','control']}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.out/'values.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
