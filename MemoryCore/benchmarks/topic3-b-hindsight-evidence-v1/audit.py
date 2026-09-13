"""Audit positive evidence alignment; do not infer negative labels or feedback turns."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def audit(locomo, longmem):
    lc=json.loads(locomo.read_text()); lm=json.loads(longmem.read_text())
    counts=Counter(); unresolved=[]; usages=Counter()
    for row in lc:
        messages={m['dia_id']:m for k,v in row['conversation'].items() if k.startswith('session_') and isinstance(v,list) for m in v}
        for i,q in enumerate(row['qa']):
            if q['category'] not in (1,2,4):
                counts['excluded_category_'+str(q['category'])]+=1; continue
            counts['eligible_qa']+=1
            refs=q.get('evidence',[])
            if not refs or any(r not in messages for r in refs):
                counts['alignment_unknown']+=1
                unresolved.append({'source':row['sample_id'],'question_index':i,'references':refs});continue
            counts['aligned_qa']+=1
            counts['aligned_positive_references']+=len(set(refs))
            for r in set(refs):usages[(row['sample_id'],r)]+=1
    mc=Counter(); mismatch=[]; turnkeys=Counter()
    for row in lm:
        mc['questions']+=1
        ids=row['haystack_session_ids']; sessions=row['haystack_sessions']
        assert len(ids)==len(sessions)==len(row['haystack_dates'])
        duplicate_ids={sid for sid,n in Counter(ids).items() if n>1}
        mc['questions_with_duplicate_session_ids']+=bool(duplicate_ids)
        mc['duplicate_session_id_instances']+=len(ids)-len(set(ids))
        targets=set(row['answer_session_ids']); missing=targets-set(ids)
        mc['missing_target_session_ids']+=len(missing)
        marked=set()
        for sid,turns in zip(ids,sessions):
            mc['session_instances']+=1
            for t in turns:
                turnkeys.update(t.keys());mc['turn_instances']+=1
                if t.get('has_answer'):
                    marked.add(sid);mc['positive_turn_instances']+=1
                    mc['positive_role_'+t['role']]+=1
                    if sid not in targets:mc['marked_turn_outside_target_session']+=1
        mc['target_session_instances']+=len(targets)
        mc['target_sessions_without_marked_turn']+=len(targets-marked)
        kind='abstention' if row['question_id'].endswith('_abs') else 'answerable'
        mc[kind+'_target_sessions_without_marked_turn']+=len(targets-marked)
        if missing or marked-targets or duplicate_ids:
            mismatch.append({'question_id':row['question_id'],'duplicate_session_ids':sorted(duplicate_ids),'missing_session_ids':sorted(missing),'marked_outside_target':sorted(marked-targets)})
    return {'mode':'source_contract_audit','locomo':dict(counts),'locomo_unique_positive_messages':len(usages),'locomo_messages_referenced_by_multiple_eligible_qa':sum(n>1 for n in usages.values()),'locomo_unresolved':unresolved,'longmemeval':dict(mc),'longmemeval_turn_keys':dict(turnkeys),'longmemeval_alignment_exceptions':mismatch,'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (locomo,longmem)},'interpretation':{'unlisted_evidence':'unlabeled, not negative','accepted_answer':'controlled oracle observation, not natural feedback','qa_order':'not a timestamped user feedback stream','longmemeval_ids_and_has_answer':'label-bearing; replace IDs and remove markers before model input'}}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--locomo',type=Path,required=True);p.add_argument('--longmemeval',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=audit(a.locomo,a.longmemeval);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
