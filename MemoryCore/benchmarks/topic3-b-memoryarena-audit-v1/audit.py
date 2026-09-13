"""Pinned source/schema audit; no benchmark answers printed, no agent execution."""
import argparse
import ast
import difflib
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != '6cd9de14b71915e39ac742a20dc33785e14b6aab':
        raise ValueError('Unexpected upstream revision')
    result = {'source_commit': commit, 'dataset_revision': 'da1a37c8b19280e18627ca01cf368195a5e1d92e',
              'mode': 'source_contract_audit_not_benchmark', 'datasets': {}, 'probes': []}
    for path in sorted(args.data.glob('*/data.jsonl')):
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        result['datasets'][path.parent.name] = {
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'rows': len(rows),
            'questions': sum(len(row['questions']) for row in rows),
            'answers': sum(len(row['answers']) for row in rows),
            'question_count_range': [min(len(r['questions']) for r in rows), max(len(r['questions']) for r in rows)],
            'count_mismatches': sum(len(r['questions']) != len(r['answers']) for r in rows)}
    for relative, name in [('env/env_systems/travel_env.py', '_similarity'),
                           ('env/env_systems/travel_planner_env/eval.py', 'similarity')]:
        tree = ast.parse((args.source / relative).read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        namespace = {'difflib': difflib}
        exec(compile(ast.Module(body=[node], type_ignores=[]), relative, 'exec'), namespace)
        scores = [namespace[name](a, b) for a, b in [('A', 'Airport Hotel'), ('Airport Hotel', 'Airport Hotel CLOSED')]]
        assert scores == [1.0, 1.0]
        result['probes'].append({'source': relative, 'line': node.lineno,
                                 'synthetic_prefix_scores': scores, 'passed': True})
    client = ast.parse((args.source / 'env/env_client.py').read_text())
    step = next(n for n in ast.walk(client) if isinstance(n, ast.FunctionDef) and n.name == 'step')
    returned = next(n.value for n in ast.walk(step) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict))
    data = {'observation': {'judge_result': 'incorrect'}, 'reward': 0}
    envelope = eval(compile(ast.Expression(returned), 'upstream_client_return', 'eval'), {'data': data})
    runner = ast.parse((args.source / 'run_math.py').read_text())
    predicate = next(n.test for n in ast.walk(runner) if isinstance(n, ast.If)
                     and 'judge_result_in_memory' in ast.unparse(n.test))
    enabled = eval(compile(ast.Expression(predicate), 'upstream_runner_predicate', 'eval'),
                   {'cfg': {'memory': {'judge_result_in_memory': True}}, 'result': envelope})
    assert not enabled and envelope['observation']['judge_result'] == 'incorrect'
    result['probes'].append({'source': 'run_math.py', 'line': predicate.lineno,
                             'memory_flag_true_branch_taken': enabled,
                             'client_keys': sorted(envelope), 'passed': True})
    # Execute upstream prompt construction with synthetic completed/current tasks.
    from typing import Dict, List
    namespace = {'Dict': Dict, 'List': List}
    root = args.source / 'env/env_systems/web_shopping_env/runtime/runner'
    for filename, name in [('summary_build.py', 'format_feedback'),
                           ('task_files.py', 'build_instruction_for_step')]:
        node = next(n for n in ast.parse((root / filename).read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec'), namespace)
    feedback = namespace['format_feedback'](1, 'BOUGHT', 10.0, 'HIDDEN_TARGET', 'bought item', 'target item')
    prompt = namespace['build_instruction_for_step']('', [
        {'step': 1, 'header': 'Product 1', 'body': 'old requirement'},
        {'step': 2, 'header': 'Product 2', 'body': 'current requirement'}], 2, {1: feedback}, True)
    assert 'HIDDEN_TARGET' in prompt
    result['probes'].append({'source': 'shopping split-history prompt',
                             'synthetic_prior_target_visible': True, 'passed': True})
    # Extract the actual client parser block, using the service URL contract.
    client = ast.parse((args.source / 'env/env_systems/web_shopping_env/webshop_plus_client.py').read_text())
    block = next(n for n in ast.walk(client) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "'/done/' in url")
    namespace = {'url': 'http://local/done/SESSION/PRODUCT/{}', 'asin': None, 'print': lambda *a: None}
    exec(compile(ast.Module(body=[block], type_ignores=[]), 'upstream_purchase_parser', 'exec'), namespace)
    assert namespace['asin'] == 'SESSION'
    result['probes'].append({'source': 'webshop_plus_client.py', 'line': block.lineno,
                             'expected_product': 'PRODUCT', 'parsed_product': namespace['asin'], 'passed': True})
    source = ast.parse((args.source / 'env/env_systems/browsecomp_plus_env.py').read_text())
    final = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'run_final_query')
    flag_reads = sum(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                     and n.id == 'store_eval_in_memory' for n in ast.walk(final))
    assert flag_reads == 0
    result['probes'].append({'source': 'browsecomp_plus_env.py:run_final_query',
                             'store_eval_in_memory_reads': flag_reads, 'passed': True})
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
