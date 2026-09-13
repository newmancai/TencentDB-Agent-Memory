"""Materialize bounded reviewed spans. Structural validation is not semantic proof."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    for name in ['state','receipts','review','out']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    state=json.loads(args.state.read_text())
    examples={e['id']:e for e in state['examples']}
    receipts={r['id']:r for r in map(json.loads,args.receipts.read_text().splitlines())}
    reviews=json.loads(args.review.read_text())
    if len(reviews)>2 or len({r['id'] for r in reviews})!=len(reviews):raise ValueError('At most two unique reviewed examples')
    accepted=[]
    for r in reviews:
        if r['decision']!='accept':continue
        e=examples[r['id']];generated=receipts[r['id']]
        if generated['error'] is not None:raise ValueError('Cannot accept failed generation')
        if not r['quote'] or generated['text'][r['start_char']:r['end_char']]!=r['quote']:raise ValueError('Reviewed span is not verbatim generation')
        source={m['evidence_id']:m for s in e['observation']['history'] for m in s['messages']}
        ids=r['supporting_user_message_ids']
        if not ids or len(ids)>8 or len(set(ids))!=len(ids):raise ValueError('Expected bounded distinct source IDs')
        if any(source[i]['role']!='user' for i in ids):raise ValueError('Sources must identify user evidence')
        accepted.append({'id':e['id'],'observation':e['observation'],
            'reviewed_evidence':{'text':r['quote'],'source_ids':ids,
                'limits':r['omissions_and_limits'],'selection_source':r['selection_source']},
            'status':'reviewed_fragment_not_complete_gold'})
    result={'version':1,'capacity':2,'examples':accepted,
        'scope':'Controlled assistant-reviewed training fragments; no automatic semantic certification or new-task evaluation'}
    with args.out.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'accepted_fragments':len(accepted),'capacity':2,'full_demonstrations_certified':0}))


if __name__=='__main__':main()
