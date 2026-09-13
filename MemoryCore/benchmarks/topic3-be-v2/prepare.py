"""Public-schema adapter; privileged labels/known targets are separate files."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def opaque(value):
    return hashlib.sha256(('topic3-v2-source:' + value).encode()).hexdigest()[:20]


def convert(row):
    owner = opaque(row['question_id'])
    messages, sources, support = [], [], []
    sessions = sorted(zip(row['haystack_dates'], row['haystack_session_ids'], row['haystack_sessions']),
                      key=lambda x: datetime.strptime(x[0], '%Y/%m/%d (%a) %H:%M'))
    for si, (date, _, session) in enumerate(sessions):
        for mi, m in enumerate(session):
            if m['role'] not in ('user', 'assistant'):
                continue
            order = len(messages)
            source_id = opaque(f'{owner}:{si}:{mi}')
            public = dict(id=source_id, session=opaque(f'{owner}:{si}'), order=order,
                          role=m['role'], content=m['content'], date=date)
            messages.append(public)
            if m['role'] != 'user':
                continue
            for start in range(0, len(m['content']), 1600):
                sources.append(dict(sourceId=opaque(source_id + ':' + str(start)), parent=source_id,
                                    owner=owner, session=public['session'], order=order, date=date,
                                    content=m['content'][start:start + 1600]))
            if m.get('has_answer'):
                support.append(source_id)
    users = [m for m in messages if m['role'] == 'user']
    supported = [m for m in users if m['id'] in support]
    pair = None
    if supported:
        later = supported[-1]
        prior = [m for m in supported if m['order'] < later['order'] and m['session'] != later['session']]
        if not prior:
            prior = [m for m in users if m['session'] == later['session'] and m['order'] < later['order']]
        if prior:
            pair = dict(old=prior[0], later=later)
    task = dict(id=owner, query=row['question'], messages=messages, sources=sources)
    gold = dict(original_id=row['question_id'], answer=row['answer'], kind=row['question_type'], support=support)
    return task, gold, pair


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--exclude', type=Path)
    a = p.parse_args()
    exclusions = set(json.loads(a.exclude.read_text())) if a.exclude else set()
    rows = json.loads(a.source.read_text())
    selected = []
    for kind in ('knowledge-update', 'single-session-user'):
        eligible = [r for r in rows if r['question_type'] == kind and r['question_id'] not in exclusions]
        selected.extend(sorted(eligible, key=lambda r: hashlib.sha256(('topic3-be-v2:' + r['question_id']).encode()).hexdigest())[:8])
    tasks, gold, privileged = [], {}, []
    for r in selected:
        t, g, pair = convert(r)
        tasks.append(t)
        gold[t['id']] = g
        privileged.append(dict(id=t['id'], query=t['query'], pair=pair))
    a.output.mkdir(parents=True, exist_ok=True)
    for name, content in [('tasks.json', tasks), ('gold.json', gold), ('privileged.json', privileged)]:
        (a.output / name).write_text(json.dumps(content, ensure_ascii=False))
    print(json.dumps(dict(tasks=len(tasks), user_chunks=sum(len(t['sources']) for t in tasks),
                          privileged_pairs=sum(t['pair'] is not None for t in privileged), excluded=sorted(exclusions))))


if __name__ == '__main__':
    main()
