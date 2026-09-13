"""Read-only label-contract audit; never manufactures negative span labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def locomo(path):
    data=json.loads(path.read_text());summary=Counter();categories=Counter();lengths=[];invalid=[];evidence_by_category={}
    for record in data:
        turns=[t for name,session in record['conversation'].items() if name.startswith('session_') and isinstance(session,list) for t in session]
        ids=[t['dia_id'] for t in turns];index=set(ids);lengths.append(len(turns))
        summary['duplicate_dialog_ids']+=len(ids)-len(index)
        for i,qa in enumerate(record['qa']):
            summary['questions']+=1;categories[str(qa['category'])]+=1
            evidence=qa.get('evidence',[])
            bucket=evidence_by_category.setdefault(str(qa['category']),Counter())
            bucket['questions']+=1;bucket['with_evidence']+=bool(evidence)
            bucket['with_answer_field']+=('answer' in qa)
            bucket['with_adversarial_answer_field']+=('adversarial_answer' in qa)
            summary['with_evidence']+=bool(evidence);summary['without_evidence']+=not bool(evidence)
            summary['references']+=len(evidence)
            missing=[e for e in evidence if e not in index]
            summary['exact_resolved_references']+=len(evidence)-len(missing)
            summary['questions_with_unresolved_reference']+=bool(missing)
            if missing:invalid.append({'sample_id':record['sample_id'],'question_index':i,'unresolved':missing})
    return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'conversations':len(data),
        'turns_per_conversation':lengths,'counts':dict(summary),'categories':dict(categories),
        'evidence_by_category':{k:dict(v) for k,v in evidence_by_category.items()},
        'unresolved':invalid,'negative_label_contract':'unlisted messages are unlabeled, not unsupported or refuted',
        'span_labels_available':False,
        'category_warning':'category 5 evidence is not support for adversarial_answer; category 3 allows open-domain inference'}


def dialfact(directory):
    result={};groups={};contexts={}
    for split in ['valid','test']:
        path=directory/(split+'_split.jsonl');rows=[json.loads(x) for x in path.read_text().splitlines()]
        groups[split]={r['context_id'] for r in rows}
        contexts[split]={json.dumps(r['context'],ensure_ascii=False) for r in rows}
        turns=Counter(len(r['context']) for r in rows)
        result[split]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(rows),
            'contexts':len(groups[split]),'history_turn_counts':dict(sorted(turns.items())),
            'response_labels':dict(Counter(r['response_label'] for r in rows)),
            'type_labels':dict(Counter(r['type_label'] for r in rows)),
            'empty_evidence':sum(not r['evidence_list'] for r in rows),
            'evidence_with_extra_metadata':sum(len(e)>4 for r in rows for e in r['evidence_list'])}
    result['context_id_overlap']=len(groups['valid']&groups['test'])
    result['exact_context_text_overlap']=len(contexts['valid']&contexts['test'])
    result['span_labels_available']=False
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--locomo',type=Path,required=True)
    p.add_argument('--dialfact',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result={'locomo':locomo(a.locomo),'dialfact':dialfact(a.dialfact)}
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
