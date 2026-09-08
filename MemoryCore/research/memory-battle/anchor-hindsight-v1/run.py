"""Real Hindsight concise retention + observations, using only public runtime input.

Run with the existing hindsight-battle-0.9.2 environment. This is a configured
local-model baseline, not the vendor's leaderboard or default cloud deployment.
"""
import argparse
import asyncio
import importlib.util
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import build_opener, ProxyHandler


def configure(profile='greedy'):
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        os.environ.pop(key, None)
    settings = {
        'LLM_PROVIDER': 'lmstudio', 'LLM_API_KEY': 'local-experiment',
        'LLM_MODEL': 'Qwen3.5-9B', 'LLM_BASE_URL': 'http://127.0.0.1:18735/v1',
        'LLM_TEMPERATURE': '0', 'LLM_MAX_CONCURRENT': '1', 'LLM_TIMEOUT': '600',
        'LLM_STRICT_SCHEMA': 'false', 'RETAIN_EXTRACTION_MODE': 'concise',
        'ENABLE_OBSERVATIONS': 'true', 'ENABLE_AUTO_CONSOLIDATION': 'false',
        'WORKER_ENABLED': 'false', 'STORE_DOCUMENT_TEXT': 'true',
        'RETAIN_MAX_COMPLETION_TOKENS': '16384',
        'CONSOLIDATION_MAX_COMPLETION_TOKENS': '16384',
        'REFLECT_MAX_COMPLETION_TOKENS': '4096', 'REFLECT_MAX_CONTEXT_TOKENS': '24000',
        'REFLECT_MAX_ITERATIONS': '10', 'RERANKER_PROVIDER': 'rrf',
        'EMBEDDINGS_PROVIDER': 'openai', 'EMBEDDINGS_OPENAI_API_KEY': 'local-experiment',
        'EMBEDDINGS_OPENAI_BASE_URL': 'http://127.0.0.1:18736/v1',
        'EMBEDDINGS_OPENAI_MODEL': 'Qwen3-Embedding-0.6B',
        'EMBEDDINGS_OPENAI_DIMENSIONS': '1024',
    }
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'true'
    if profile == 'thinking-v5':settings['LLM_TEMPERATURE'] = '1'
    settings['LLM_EXTRA_BODY'] = json.dumps(dict(enable_thinking=profile=='thinking-v5',
        presence_penalty=1.5 if profile=='thinking-v5' else 0,
        top_p=.95 if profile=='thinking-v5' else 1, top_k=20 if profile=='thinking-v5' else 0))
    for key, value in settings.items():
        os.environ['HINDSIGHT_API_' + key] = value
    return settings


def timestamp(text):
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def document(source):
    return dict(content=source['content'], document_id=source['id'],
        event_date=timestamp(source['observedAt']), context='User conversation statement',
        metadata={'public_source_id': source['id'], 'observed_at': source['observedAt']})


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


async def run(args):
    settings = configure(args.generation_profile)
    from hindsight_api.engine.memory_engine import MemoryEngine
    from hindsight_api.engine.embeddings import OpenAIEmbeddings
    from hindsight_api.engine.cross_encoder import RRFPassthroughCrossEncoder
    from hindsight_api.engine.task_backend import SyncTaskBackend
    from hindsight_api.models import RequestContext
    adapter_path = Path(__file__).resolve().parent.parent / 'competitors/hindsight/adapter.py'
    spec = importlib.util.spec_from_file_location('hindsight_native_adapter', adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    # Dataclasses in the existing adapter require registration during import.
    import sys
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
    opener = build_opener(ProxyHandler({}))

    def counters():
        result = {}
        for name, port in [('llm', 18735), ('embedding', 18736)]:
            with opener.open(f'http://127.0.0.1:{port}/stats', timeout=30) as response:
                result[name] = json.load(response)
        return result

    cases = [case for case in json.loads(args.runtime.read_text()) if case['split'] == args.split]
    if args.limit:
        cases = cases[:args.limit]  # Prefix for compatibility only; not a new score subset.
    args.output.mkdir(parents=True, exist_ok=True)
    if args.resume_interrupted:
        old_settings=json.loads((args.output/'configuration.json').read_text())
        for key in ('LLM_MODEL','LLM_TEMPERATURE','RETAIN_EXTRACTION_MODE','ENABLE_OBSERVATIONS'):
            if old_settings[key]!=settings[key]:raise ValueError('cannot resume bank under changed model/policy')
    dump(args.output / 'configuration.json', settings)
    engine = MemoryEngine(db_url='postgresql://hindsight:hindsight@127.0.0.1:65438/hindsight',
        memory_llm_provider='lmstudio', memory_llm_api_key='local-experiment',
        memory_llm_model='Qwen3.5-9B', memory_llm_base_url='http://127.0.0.1:18735/v1',
        embeddings=OpenAIEmbeddings(api_key='local-experiment', model='Qwen3-Embedding-0.6B',
            base_url='http://127.0.0.1:18736/v1', dimensions=1024, batch_size=16, max_retries=0,
            query_prefix='Instruct: Retrieve earlier statements relevant to the new observation.\nQuery:',
            passage_prefix=''), cross_encoder=RRFPassthroughCrossEncoder(),
        task_backend=SyncTaskBackend(), skip_llm_verification=False)
    ctx = RequestContext(internal=True)
    initial = counters()
    expected_thinking = args.generation_profile == 'thinking-v5'
    effective={**initial['llm'].get('generation_defaults',{}),**json.loads(settings['LLM_EXTRA_BODY'])}
    if bool(effective.get('enable_thinking',False)) != expected_thinking:
        raise ValueError('shared endpoint generation profile mismatch')
    await engine.initialize()
    dump(args.output / 'initialization.json', {'before': initial, 'after': counters()})
    try:
        for case in cases:
            path = args.output / (case['id'] + '.json')
            previous=None
            if path.exists():
                previous=json.loads(path.read_text())
                if not args.resume_interrupted or previous['status']!='interrupted':continue
                if previous['phases']:raise ValueError('only history-retain interruption is supported; avoid future observation leakage')
                archive=path.with_suffix('.interrupted-attempt.json')
                with archive.open('x') as f:json.dump(previous,f,ensure_ascii=False,indent=2)
            bank = previous['bank_id'] if previous else 'anchor-semantic-' + uuid.uuid4().hex
            row = dict(id=case['id'], split=case['split'], bank_id=bank,
                status='running', before=counters(), phases=[])
            if previous:row['resumed_attempt']=str(archive)
            started = time.perf_counter()
            try:
                for phase, sources in [('history', case['sources']), ('update', [case['observation']])]:
                    phase_start = time.perf_counter()
                    ids, usage = await engine.retain_batch_async(bank_id=bank,
                        contents=[document(source) for source in sources], request_context=ctx, return_usage=True)
                    consolidation = await engine.run_consolidation(bank, request_context=ctx)
                    stats = await engine.get_bank_stats(bank, request_context=ctx, force_refresh=True)
                    row['phases'].append(dict(phase=phase, native_ids=ids,
                        usage=usage.to_dict() if hasattr(usage, 'to_dict') else str(usage),
                        consolidation=consolidation, bank_stats=stats,
                        seconds=time.perf_counter()-phase_start, counters=counters()))
                    dump(args.output / (case['id'] + '.progress.json'), row)
                    if stats.get('pending_consolidation', 0) or stats.get('failed_consolidation', 0):
                        raise RuntimeError('native consolidation incomplete; not a semantic failure')
                    if phase == 'history':
                        # Same new observation, before retention; no probe query or gold.
                        prior = await engine.recall_async(bank_id=bank,
                            query=case['observation']['content'], max_tokens=4096,
                            enable_trace=True, fact_type=['world', 'experience', 'observation'],
                            question_date=timestamp(case['observation']['observedAt']),
                            include_source_facts=True, request_context=ctx, reranking='rrf')
                        prior_payload = prior.model_dump(mode='json')
                        records, issues = adapter.normalize_system_retrieved_records(prior_payload, top_k=8)
                        row['b_recall'] = prior_payload
                        row['b_provenance_issues'] = issues
                        dump(args.output / (case['id']+'.b-candidates.json'), [dict(
                            id=case['id'], split=case['split'], observation=case['observation'],
                            candidates=[dict(id=record['nativeRecordId'], content=record['content'],
                                sourceDocumentIds=record['sourceDocumentIds']) for record in records])])
                        row['b_diagnostic_counters_after'] = counters()
                recall = await engine.recall_async(bank_id=bank, query=case['query'],
                    max_tokens=4096, enable_trace=True, fact_type=['world', 'experience', 'observation'],
                    question_date=timestamp(case['observation']['observedAt']),
                    include_source_facts=True, request_context=ctx, reranking='rrf')
                payload = recall.model_dump(mode='json')
                normalized, issues = adapter.normalize_system_retrieved_records(payload, top_k=8)
                row['recall'] = payload
                row['normalized_recall'] = normalized
                row['provenance_issues'] = issues
                answer = await engine.reflect_async(bank_id=bank, query=case['query'],
                    context='Answer as of '+case['observation']['observedAt']+'.', request_context=ctx)
                row['reflect'] = answer.model_dump(mode='json')
                row['status'] = 'success'
            except Exception as error:
                row['status'] = 'error'
                row['error'] = f'{type(error).__name__}: {error}'
            except BaseException as error:
                row['status'] = 'interrupted'
                row['error'] = type(error).__name__
                raise
            finally:
                row['seconds'] = time.perf_counter()-started
                row['after'] = counters()
                dump(path, row)
            print(json.dumps({'id': case['id'], 'status': row['status'], 'error': row.get('error')}), flush=True)
            if row['status'] == 'error':
                break  # Diagnose compatibility before spending on additional public cases.
    finally:
        await engine.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--split', required=True, choices=['development', 'calibration', 'heldout'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--generation-profile', choices=['greedy','thinking-v5'], default='greedy')
    parser.add_argument('--resume-interrupted', action='store_true')
    asyncio.run(run(parser.parse_args()))
