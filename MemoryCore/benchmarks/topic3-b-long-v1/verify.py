"""Check actual persisted prefixes and reference/online separation, read-only."""
import json
from pathlib import Path
import sqlite3
import sys


def main(root):
    tasks=json.loads((root/'tasks.json').read_text());native={r['id']:r for r in json.loads((root/'native/results.json').read_text())}
    relations={r['id']:r for r in map(json.loads,(root/'relations.jsonl').read_text().splitlines())}
    checked=0
    for t in tasks:
        db=sqlite3.connect(f"file:{root/'native'/t['id']/'base.sqlite'}?mode=ro",uri=True)
        try:stored=db.execute('SELECT record_id,message_text,role,timestamp FROM l0_conversations').fetchall()
        finally:db.close()
        expected={m['id']:(m['content'],'user',1700000000000+m['order']) for m in t['messages']}
        assert {r[0]:tuple(r[1:]) for r in stored}==expected
        assert all(m['order']<t['incoming']['order'] for m in t['messages'])
        assert t['incoming']['id'] not in expected
        r=relations[t['id']];union=set()
        for arm in ['fts','recent']:
            items=native[t['id']][arm]['results']
            assert r['pools'][arm]==[m['id'] for m in items]
            assert all(expected[m['id']][0]==m['content'] for m in items)
            assert len(items)<=8
            union.update(r['pools'][arm])
        assert all(s['oracle_only']==(key not in union) for key,s in r['scores'].items())
        checked+=len(stored)
    summary=dict(tasks=len(tasks),persisted_messages_checked=checked,prefix_and_readback='pass',oracle_pool_separation='pass')
    (root/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
