"""MemTrace adapter: actual answer inputs only; attribution labels stay offline."""
import ast
import hashlib
import json
import sys
from pathlib import Path


def text_value(node):
    value = node['value']
    if not isinstance(value, str):
        raise ValueError('non-text runtime node')
    try:
        decoded = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value
    return decoded if isinstance(decoded, str) else value


def extract(graph, prediction_id):
    """No annotations, source-evidence IDs or expected answer in this interface."""
    nodes = {n['full_node_id']: n for n in graph['nodes']}
    operations = {o['op_id']: o for o in graph['operations']}
    prediction = nodes[prediction_id]
    edges = [e for e in graph['edges'] if e['target_full_node_id'] == prediction_id
             and operations[e['op_id']]['op_name'] == 'question-answering']
    answer_ops = {e['op_id'] for e in edges}
    if len(answer_ops) != 1:
        raise ValueError('ambiguous answer operation')
    inputs = {e['source_full_node_id']: nodes[e['source_full_node_id']] for e in edges}
    queries = [n for n in inputs.values() if n.get('class_name') == 'query']
    contexts = [n for n in inputs.values() if n['category'] == 'memory_context']
    if len(queries) != 1 or len(contexts) != 1:
        raise ValueError('ambiguous query/context inputs')
    query, context = queries[0], contexts[0]
    for node in (query, context):
        if node['created_at'] > prediction['created_at']:
            raise ValueError('input after prediction checkpoint')
    context_sources = {e['source_full_node_id'] for e in graph['edges']
                       if e['target_full_node_id'] == context['full_node_id']
                       and e['op_id'] in answer_ops}
    retrieve_ops = {e['op_id'] for e in graph['edges']
                    if e['source_full_node_id'] == query['full_node_id']
                    and e['target_full_node_id'] in context_sources
                    and operations[e['op_id']]['op_name'] == 'memory_system.retrieve'
                    and e['created_at'] <= prediction['created_at']}
    if len(retrieve_ops) != 1:
        raise ValueError('ambiguous retrieval operation')
    if any(operations[op]['created_at'] > prediction['created_at'] for op in retrieve_ops | answer_ops):
        raise ValueError('operation after prediction checkpoint')
    # Only remapped, actual operation identity is needed by the host. Model input
    # uses query/context/answer strings, not operation comments or metadata.
    private_map = {'memory': next(iter(retrieve_ops)), 'response': next(iter(answer_ops))}
    return dict(query=text_value(query), context=text_value(context),
                prediction=text_value(prediction)), private_map


def main():
    evidence, output = map(Path, sys.argv[1:])
    tasks, labels, native = [], {}, []
    paths = json.loads((evidence / 'downloaded.json').read_text())
    for spec in paths:
        graph = json.loads(Path(spec['local']).read_text())
        group = spec['path'].split('/')[-1].removesuffix('.json')
        split = 'fit' if group.startswith('locomo_') else 'eval'
        for annotation in graph['data']['annotations']:
            key = hashlib.sha256((group + ':' + annotation['prediction_id']).encode()).hexdigest()[:20]
            task = dict(id=key, group=group, split=split, error=None)
            op_map = {}
            try:
                value, op_map = extract(graph['data'], annotation['prediction_id'])
                task.update(value)
            except (ValueError, KeyError) as exc:
                task['error'] = str(exc)
            tasks.append(task)
            labels[key] = dict(error_type=annotation['final_error_type'],
                               operation=next((role for role, op in op_map.items()
                                               if op == annotation['final_op_id']), None))
            if not task['error']:
                source = dict(id=key, session=group, content=task['context'], date='recorded before prediction')
                native.append(dict(id=key, pair=dict(old=source, later=dict(content=task['query'], date='prediction checkpoint')),
                                   targets=[dict(id='context', text=task['context'], start=0,
                                                 end=len(task['context'].encode('utf-16-le')) // 2)]))
    output.mkdir(parents=True, exist_ok=False)
    feedback = {t['id']: labels[t['id']] for t in tasks if t['split'] == 'fit'}
    reference = {t['id']: labels[t['id']] for t in tasks if t['split'] == 'eval'}
    for name, value in [('tasks', tasks), ('offline', labels), ('feedback', feedback),
                        ('reference', reference), ('native-input', native)]:
        (output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    print(json.dumps(dict(tasks=len(tasks), errors=sum(bool(t['error']) for t in tasks),
                          fit=sum(t['split'] == 'fit' for t in tasks), eval=sum(t['split'] == 'eval' for t in tasks))))


if __name__ == '__main__':
    main()
