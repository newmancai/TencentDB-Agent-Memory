"""Controlled hindsight information baseline, using SQLite's native FTS5."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time


def words(text):
    return re.findall(r'\w+', text.casefold())


def query(text):
    return ' OR '.join('"'+w.replace('"','""')+'"' for w in dict.fromkeys(words(text)))


def retrieve(db, text, k=10):
    expression=query(text)
    start=time.perf_counter()
    rows=db.execute('SELECT rowid, bm25(docs) FROM docs WHERE docs MATCH ? ORDER BY bm25(docs), rowid LIMIT ?', (expression,k)).fetchall() if expression else []
    return rows, (time.perf_counter()-start)*1000


def adapt(path):
    sources=[]; labels={}; tasks=[]; unknown=[]
    for row in json.loads(path.read_text()):
        docs=[{'id':m['dia_id'],'text':m['speaker']+': '+m['text']} for k,v in row['conversation'].items() if k.startswith('session_') and isinstance(v,list) for m in v]
        ids={d['id'] for d in docs}
        assert len(ids)==len(docs)
        sources.append({'id':row['sample_id'],'documents':docs})
        for i,q in enumerate(row['qa']):
            if q['category'] not in (1,2,4):continue
            tid=row['sample_id']+':'+str(i); refs=q.get('evidence',[])
            if not refs or any(r not in ids for r in refs):
                unknown.append({'id':tid,'reason':'alignment_unknown'});continue
            tasks.append({'id':tid,'source':row['sample_id'],'question':q['question'],'accepted_answer':str(q['answer'])})
            labels[tid]=set(refs)
    return sources,tasks,labels,unknown


def percentile(values,p):
    s=sorted(values);x=(len(s)-1)*p;lo=int(x);hi=min(lo+1,len(s)-1)
    return s[lo]+(s[hi]-s[lo])*(x-lo)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sources,tasks,labels,unknown=adapt(a.source)
    controls={}
    for t in tasks:
        n=len(words(t['accepted_answer']))
        pool=[u for u in tasks if u['source']!=t['source'] and u['accepted_answer']!=t['accepted_answer']]
        controls[t['id']]=min(pool,key=lambda u:(abs(len(words(u['accepted_answer']))-n),hashlib.sha256(('hindsight-control-v1:'+t['id']+':'+u['id']).encode()).hexdigest()))
    receipts=[];index_ms=0
    for source in sources:
        docs=source['documents'];db=sqlite3.connect(':memory:');start=time.perf_counter()
        db.execute("CREATE VIRTUAL TABLE docs USING fts5(text, tokenize='unicode61')")
        db.executemany('INSERT INTO docs(text) VALUES (?)',[(d['text'],) for d in docs]);index_ms+=(time.perf_counter()-start)*1000
        for t in tasks:
            if t['source']!=source['id']:continue
            c=controls[t['id']]
            texts={'q':t['question'],'a':t['accepted_answer'],'qa':t['question']+' '+t['accepted_answer'],'control':t['question']+' '+c['accepted_answer']}
            arms={}
            for arm,text in texts.items():
                hits,ms=retrieve(db,text)
                arms[arm]={'ids':[docs[i-1]['id'] for i,_ in hits],'scores':[s for _,s in hits],'query_ms':ms,'characters':[len(docs[i-1]['text']) for i,_ in hits],'words':[len(words(docs[i-1]['text'])) for i,_ in hits]}
            receipts.append({'id':t['id'],'source':t['source'],'control_id':c['id'],'control_length_delta':len(words(c['accepted_answer']))-len(words(t['accepted_answer'])),'arms':arms})
        db.close()
    # Evidence-ID labels do not enter retrieval. Gold answers are explicitly revealed in A arms.
    summary={'mode':'controlled_hindsight_fts5_v1','sqlite_version':sqlite3.sqlite_version,'tasks':len(tasks),'unknown':unknown,'index_ms':index_ms,'arms':{},'qa_vs_q':{},'by_source':{}}
    scored=[]
    for r in receipts:
        gold=labels[r['id']];entry={'id':r['id'],'source':r['source'],'gold_ids':sorted(gold),'arms':{}}
        for arm,res in r['arms'].items():
            entry['arms'][arm]={str(k):{'any':bool(gold&set(res['ids'][:k])),'all':gold<=set(res['ids'][:k]),'recall':len(gold&set(res['ids'][:k]))/len(gold)} for k in (1,5,10)}
        scored.append(entry)
    for arm in ('q','a','qa','control'):
        times=[r['arms'][arm]['query_ms'] for r in receipts]
        summary['arms'][arm]={'query_ms_p50':percentile(times,.5),'query_ms_p95':percentile(times,.95),'total_query_ms':sum(times),'at_k':{}}
        for k in (1,5,10):
            summary['arms'][arm]['at_k'][str(k)]={metric:sum(r['arms'][arm][str(k)][metric] for r in scored)/len(scored) for metric in ('any','all','recall')}
            summary['arms'][arm]['at_k'][str(k)].update({'returned':sum(len(r['arms'][arm]['ids'][:k]) for r in receipts),'characters':sum(sum(r['arms'][arm]['characters'][:k]) for r in receipts),'words':sum(sum(r['arms'][arm]['words'][:k]) for r in receipts)})
    for k in (1,5,10):
        c=Counter()
        for r,s in zip(receipts,scored):
            gold=labels[r['id']];before=set(r['arms']['q']['ids'][:k]);after=set(r['arms']['qa']['ids'][:k])
            c['new_reference_hits']+=len((after-before)&gold);c['lost_reference_hits']+=len((before-after)&gold)
            for metric in ('any','all'):
                old=s['arms']['q'][str(k)][metric];new=s['arms']['qa'][str(k)][metric]
                c[metric+('_tie' if old==new else '_win' if new else '_loss')]+=1
        summary['qa_vs_q'][str(k)]=dict(c)
    for source in sources:
        subset=[r for r in scored if r['source']==source['id']]
        summary['by_source'][source['id']]={'n':len(subset),**{arm:sum(r['arms'][arm]['10']['all'] for r in subset) for arm in ('q','a','qa','control')}}
    a.out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('receipts.jsonl',receipts),('scored.jsonl',scored)]:
        (a.out/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
