"""Feedback-updated bounded retrieval sidecar. Controlled batches, no natural timeline."""
import argparse
from collections import defaultdict,Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from lexical_probe import adapt,words,retrieve,percentile


def index(texts):
    db=sqlite3.connect(':memory:');db.execute("CREATE VIRTUAL TABLE docs USING fts5(text, tokenize='unicode61')")
    db.executemany('INSERT INTO docs(text) VALUES (?)',[(t,) for t in texts]);return db


def fuse(base,side):
    score=defaultdict(float);order={v:i for i,v in enumerate(dict.fromkeys(base+side))}
    for ranking in (base,side):
        for rank,mid in enumerate(dict.fromkeys(ranking),1):score[mid]+=1/(60+rank)
    return sorted(score,key=lambda mid:(-score[mid],order[mid]))[:10]


class Sidecar:
    def __init__(self,state,allowed):
        self.db=None;self.entries=[];self.error=None
        try:
            if not isinstance(state,list) or len(state)>64:raise ValueError('invalid_state')
            if any(not isinstance(e,dict) or set(e)!={'text','message_id'} or not isinstance(e['text'],str) or e['message_id'] not in allowed for e in state):raise ValueError('invalid_state')
            self.entries=state;self.db=index([e['text'] for e in state])
        except (ValueError,TypeError,sqlite3.Error):self.error='invalid_state'

    def select(self,q,base,enabled=True):
        if not enabled:return list(base),{'fallback':'disabled','query_ms':0,'side_hits':0}
        if self.error:return list(base),{'fallback':self.error,'query_ms':0,'side_hits':0}
        try:
            rows,ms=retrieve(self.db,q);side=list(dict.fromkeys(self.entries[i-1]['message_id'] for i,_ in rows))
            return (fuse(base,side) if side else list(base)),{'fallback':None if side else 'no_side_hit','query_ms':ms,'side_hits':len(side)}
        except sqlite3.Error:return list(base),{'fallback':'read_failed','query_ms':0,'side_hits':0}

    def close(self):
        if self.db:self.db.close()


def split(tasks,source):
    groups=defaultdict(list)
    for t in tasks:groups[' '.join(words(t['question']))].append(t)
    keys=sorted(groups,key=lambda q:hashlib.sha256(('transfer-feedback-v1:'+source+':'+q).encode()).hexdigest())
    selected=set(keys[:min(64,len(keys)//2)])
    return [groups[k][0] for k in keys if k in selected],[t for k in keys if k not in selected for t in groups[k]],[t['id'] for k in selected for t in groups[k][1:]]


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sources,tasks,labels,unknown=adapt(a.source);states={};results=[];splits={};cost=Counter();fits=[]
    for source in sources:
        sid=source['id'];docs=source['documents'];byid={d['id']:d['text'] for d in docs}
        start=time.perf_counter();db=index([d['text'] for d in docs]);cost['base_index_ms']+=(time.perf_counter()-start)*1000
        feedback,validation,dropped=split([t for t in tasks if t['source']==sid],sid)
        assert {' '.join(words(t['question'])) for t in feedback}.isdisjoint({' '.join(words(t['question'])) for t in validation})
        splits[sid]={'feedback':[t['id'] for t in feedback],'validation':[t['id'] for t in validation],'duplicate_feedback_group_excluded':dropped}
        state={arm:[] for arm in ('no_answer','direct_cache','feedback_alias')}
        for t in feedback:
            q=t['question'];qa=q+' '+t['accepted_answer'];qrows,qms=retrieve(db,q,1);arows,ams=retrieve(db,qa,1)
            cost['feedback_binding_queries']+=2;cost['feedback_binding_ms']+=qms+ams
            for arm,rows,text in [('no_answer',qrows,q),('direct_cache',arows,qa),('feedback_alias',arows,q)]:
                if rows:state[arm].append({'text':text,'message_id':docs[rows[0][0]-1]['id']})
            fits.append({'id':t['id'],'source':sid,'q_bound':docs[qrows[0][0]-1]['id'] if qrows else None,'qa_bound':docs[arows[0][0]-1]['id'] if arows else None})
        states[sid]=state;start=time.perf_counter();sidecars={arm:Sidecar(entries,set(byid)) for arm,entries in state.items()};cost['side_index_ms']+=(time.perf_counter()-start)*1000
        for t in validation:
            # Only the question, never this task's accepted_answer, enters evaluation.
            rows,ms=retrieve(db,t['question']);base=[docs[i-1]['id'] for i,_ in rows];cost['base_eval_queries']+=1;cost['base_eval_ms']+=ms
            outputs={'base':base};logs={'base':{'query_ms':ms,'fallback':None}}
            for arm,side in sidecars.items():outputs[arm],logs[arm]=side.select(t['question'],base)
            results.append({'id':t['id'],'source':sid,'outputs':outputs,'logs':logs,'words':{arm:sum(len(words(byid[i])) for i in ids) for arm,ids in outputs.items()}})
        for side in sidecars.values():side.close()
        db.close()
    # Evaluation evidence labels, loaded by adapt, are consumed here after rankings are fixed.
    summary={'mode':'controlled_feedback_transfer_v1','sqlite_version':sqlite3.sqlite_version,'feedback_tasks':len(fits),'validation_tasks':len(results),'unknown':unknown,'cost':dict(cost),'arms':{},'paired':{},'by_source':{}}
    for arm in ('base','no_answer','direct_cache','feedback_alias'):
        hits=[set(r['outputs'][arm])&labels[r['id']] for r in results];times=[r['logs'][arm]['query_ms'] for r in results]
        summary['arms'][arm]={'any':sum(bool(h) for h in hits),'all':sum(h==labels[r['id']] for r,h in zip(results,hits)),'macro_recall':sum(len(h)/len(labels[r['id']]) for r,h in zip(results,hits))/len(results),'words':sum(r['words'][arm] for r in results),'query_ms':sum(times),'p50_ms':percentile(times,.5),'p95_ms':percentile(times,.95),'fallbacks':dict(Counter(r['logs'][arm]['fallback'] for r in results if r['logs'][arm]['fallback']))}
    for arm,baseline in [('direct_cache','base'),('feedback_alias','base'),('feedback_alias','direct_cache'),('feedback_alias','no_answer')]:
        c=Counter()
        for r in results:
            gold=labels[r['id']];x=gold<=set(r['outputs'][arm]);y=gold<=set(r['outputs'][baseline]);c['tie' if x==y else 'win' if x else 'loss']+=1
        summary['paired'][arm+'_vs_'+baseline]=dict(c)
    for sid in states:
        subset=[r for r in results if r['source']==sid];summary['by_source'][sid]={'n':len(subset),**{arm:sum(labels[r['id']]<=set(r['outputs'][arm]) for r in subset) for arm in summary['arms']}}
    a.out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('summary.json',summary),('states.json',states),('split.json',splits)]: (a.out/name).write_text(json.dumps(obj,indent=2)+'\n')
    for name,rs in [('rankings.jsonl',results),('bindings.jsonl',fits)]: (a.out/name).write_text(''.join(json.dumps(r)+'\n' for r in rs))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
