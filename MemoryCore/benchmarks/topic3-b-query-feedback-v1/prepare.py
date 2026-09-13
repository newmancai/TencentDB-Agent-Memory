"""Prepare model-visible vectors separately from evidence labels and batch roles."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    path=Path(__file__).parent.parent/'topic3-b-hindsight-evidence-v1/lexical_probe.py';spec=importlib.util.spec_from_file_location('lexical_adapter',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    sources,tasks,labels,unknown=mod.adapt(a.source)
    ordered=sorted([s['id'] for s in sources],key=lambda s:hashlib.sha256(('query-feedback-source-v1:'+s).encode()).hexdigest());split={s:'feedback' if i<5 else 'validation' for i,s in enumerate(ordered)}
    docs=[{'id':'doc:'+s['id']+':'+str(i),'text':d['text'],'kind':'document'} for s in sources for i,d in enumerate(s['documents'])]
    refs={(s['id'],d['id']):'doc:'+s['id']+':'+str(i) for s in sources for i,d in enumerate(s['documents'])}
    items=docs[:];meta=[]
    for t in tasks:
        qid='q:'+t['id'];items.append({'id':qid,'text':t['question'],'kind':'query'})
        teacher=None
        if split[t['source']]=='feedback':
            teacher='qa:'+t['id'];items.append({'id':teacher,'text':t['question']+'\nAccepted answer: '+t['accepted_answer'],'kind':'query'})
        meta.append({'id':t['id'],'source':t['source'],'split':split[t['source']],'query_id':qid,'teacher_id':teacher,'gold_document_ids':sorted(refs[t['source'],m] for m in labels[t['id']])})
    assert len({r['id'] for r in items})==len(items)
    assert all(m['teacher_id'] is None for m in meta if m['split']=='validation')
    summary={'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'split':split,'documents':len(docs),'feedback_queries':sum(m['split']=='feedback' for m in meta),'validation_queries':sum(m['split']=='validation' for m in meta),'embedding_items':len(items),'alignment_unknown':unknown,'validation_answers_in_embedding_inputs':0}
    a.out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('items.jsonl',items),('evaluation.jsonl',meta)]: (a.out/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
