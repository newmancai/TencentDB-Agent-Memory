"""Only adapters know public dataset schemas. Answers never enter runtime tasks."""
import argparse
import ast
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def task(task_id, owner, query, messages, options=None, split="evaluation"):
    sources = []
    for index, message in enumerate(messages):
        if message["role"] != "user":
            continue
        for start in range(0, len(message["content"]), 1600):
            sources.append(dict(sourceId=f"m{index}p{start}", owner=owner, order=index,
                                content=message["content"][start:start + 1600]))
    return dict(id=task_id, owner=owner, query=query, options=options or [], split=split,
                messages=messages, sources=sources)


def persona(root):
    rows = list(csv.DictReader((root / "persona_v1_questions_32k.csv").open()))
    contexts = {}
    for line in (root / "persona_v1_shared_contexts_32k.jsonl").read_text().splitlines():
        contexts.update(json.loads(line))
    owners = sorted({x["persona_id"] for x in rows} - {"0", "1"}, key=lambda x: digest("topic3-be-v1:" + x))
    tasks, gold = [], {}
    for i, owner in enumerate(owners):
        for kind in ("track_full_preference_evolution", "recall_user_shared_facts"):
            selected = sorted((x for x in rows if x["persona_id"] == owner and x["question_type"] == kind),
                              key=lambda x: digest("topic3-be-v1:" + x["question_id"]))
            if not selected:
                continue
            row = selected[0]
            messages = [{"role": m["role"], "content": m["content"]} for m in
                        contexts[row["shared_context_id"]][:int(row["end_index_in_shared_context"])]
                        if m["role"] in ("user", "assistant")]
            tasks.append(task(row["question_id"], "persona-" + owner, row["user_question_or_message"], messages,
                              ast.literal_eval(row["all_options"]), "development" if i < 6 else "evaluation"))
            gold[row["question_id"]] = {"answer": row["correct_answer"], "kind": kind}
    return tasks, gold


def longmemeval(path):
    tasks, gold = [], {}
    for row in json.loads(path.read_text()):
        sessions = sorted(zip(row["haystack_dates"], row["haystack_sessions"]),
                          key=lambda x: datetime.strptime(x[0], "%Y/%m/%d (%a) %H:%M"))
        messages = [{"role": m["role"], "content": m["content"]} for _, session in sessions for m in session]
        tasks.append(task(row["question_id"], row["question_id"], row["question"], messages))
        gold[row["question_id"]] = {"answer": row["answer"], "kind": row["question_type"]}
    return tasks, gold


def neutral(path):
    rows = json.loads(path.read_text())
    return [task(r["id"], r["owner"], r["query"], r["messages"], r.get("options"), r.get("split", "evaluation"))
            for r in rows], {r["id"]: {"answer": r["answer"]} for r in rows if "answer" in r}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=["persona", "longmemeval", "neutral"], required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tasks, gold = globals()[args.adapter](args.source)
    args.output.mkdir(parents=True, exist_ok=True)
    training = {t["owner"] for t in tasks if t["split"] == "development"}
    evaluation = {t["owner"] for t in tasks if t["split"] == "evaluation"}
    assert not training & evaluation
    chunks = {split: {digest(s["content"]) for t in tasks if t["split"] == split for s in t["sources"]}
              for split in ("development", "evaluation")}
    manifest = dict(adapter=args.adapter, protocol="topic3-be-v1", selection_seed="topic3-be-v1",
                    tasks=[dict(id=t["id"], owner=t["owner"], split=t["split"], messages=len(t["messages"]),
                                source_characters=sum(len(m["content"]) for m in t["messages"])) for t in tasks],
                    owners_overlap=sorted(training & evaluation),
                    shared_user_chunks=len(chunks["development"] & chunks["evaluation"]))
    for name, data in (("tasks.json", tasks), ("gold.json", gold), ("manifest.json", manifest)):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"tasks": len(tasks), "development_owners": len(training), "evaluation_owners": len(evaluation),
                      "shared_user_chunks": manifest["shared_user_chunks"]}))


if __name__ == "__main__":
    main()
