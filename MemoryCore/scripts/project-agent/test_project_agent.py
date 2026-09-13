import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import sys

from project_agent import Host, final_text, lexical_observations, retain_project_instructions, command_for


class ProjectAgentTest(unittest.TestCase):
    def test_normal_product_use_retains_project_guidance(self):
        original=command_for('codex_memory',Path('/tmp'),'task',{})
        normal=retain_project_instructions(original,'codex')
        self.assertNotIn('project_doc_max_bytes=0',normal)
        self.assertNotIn('--ignore-user-config',normal)
        self.assertIn('--sandbox',normal)
        self.assertIn('workspace-write',normal)
        self.assertIn('web_search="disabled"', normal)
        self.assertIn('project_doc_max_bytes=0',original)
    def host(self, root, mode='scoped'):
        args = argparse.Namespace(state=root/'state', workspace=root, owner='u', project='p',
            backend='codex', model='example', effort='medium', timeout=2,
            mode=mode, paths=['src/api'], action='edit', max_bytes=12000, check=None)
        return Host(args)

    def test_off_and_store_failure_still_run_ordinary_agent(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for mode in ('off','scoped'):
                host=self.host(root,mode)
                host.store=Mock(side_effect=RuntimeError('unavailable'))
                host.call=Mock(return_value='edited')
                result=host.run('Implement the function.',root)
                self.assertEqual(result['final'],'edited')
                self.assertIsNone(result['error'])
                if mode=='off':
                    host.store.assert_not_called()
                    self.assertEqual(result['context_mode'],'off')
                else:
                    self.assertEqual(result['context_mode'],'off_fallback')
                    self.assertIn('unavailable',result['memory_error'])

    def test_budget_overflow_retains_exact_raw_sources(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            observation={'id':'u1','order':1,'role':'user','text':'Keep the zero override.'}
            snapshot={'observations':[observation],'constraints':[{'sourceId':'u1','quote':observation['text']}], 'retractions':[], 'revision':1}
            host.store=Mock(side_effect=[snapshot,{'status':'selected','omittedForBudget':1}])
            result=host.context('scoped',['src/api'],'edit',1)
            self.assertEqual(result['mode'],'raw_fallback')
            self.assertEqual(json.loads(result['text']),observation)

    def test_failed_extraction_persists_raw_observation_only(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            host.store=Mock(side_effect=[{'observations':[],'constraints':[]}, {'accepted':[]}])
            host.call=Mock(side_effect=RuntimeError('backend 502'))
            result=host.remember('Keep existing worker behavior.',root,compile_constraints=True)
            self.assertEqual(result['extraction_error'],'backend 502')
            self.assertEqual(host.store.call_args.kwargs['proposals'],[])
            self.assertEqual(host.store.call_args.kwargs['observation']['text'],'Keep existing worker behavior.')

    def test_remember_defaults_to_lossless_raw_storage_without_model_calls(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);host=self.host(root)
            host.store=Mock(side_effect=[{'observations':[]}, {'revision':1,'accepted':[]}])
            host.call=Mock(side_effect=AssertionError('must not invoke a model'))
            result=host.remember('Keep the exact instruction.',root)
            host.call.assert_not_called()
            self.assertEqual(result['observation']['text'],'Keep the exact instruction.')
            self.assertEqual(result['calls'],[])
            source=result['observation']
            host.store=Mock(return_value={'observations':[source],'constraints':[],'revision':1})
            context=host.context('scoped',['.'],'edit',12000)
            self.assertEqual(context['mode'],'raw')
            self.assertEqual(json.loads(context['text']),source)

    def test_raw_topk_is_lossless_lexical_retrieval_with_recent_tie_break(self):
        observations = [
            {'id':'old','order':1,'role':'user','text':'The cache backend in src/cache.py is memory.'},
            {'id':'noise','order':2,'role':'user','text':'Keep the documentation examples short.'},
            {'id':'new','order':3,'role':'user','text':'Correction: the cache backend is redis now.'},
            {'id':'tool','order':4,'role':'tool','text':'cache backend checker failed'},
        ]
        selected, omitted = lexical_observations(observations,'edit src/cache.py cache backend',2,12000)
        self.assertEqual([item['id'] for item in selected],['old','new'])
        self.assertEqual(omitted,1)
        with TemporaryDirectory() as directory:
            host=self.host(Path(directory),'raw_topk');host.args.retrieval_k=2
            host.store=Mock(return_value={'observations':observations,'constraints':[],'revision':4})
            context=host.context('raw_topk',['src/cache.py'],'edit',12000,query='Change cache backend')
            self.assertEqual([json.loads(line)['id'] for line in context['text'].splitlines()],['old','new'])
            self.assertEqual(context['selected_orders'],[1,3])
            self.assertEqual(context['retrieval'],'bm25_raw_user_observations')

    def test_raw_topk_tokenizes_chinese_queries(self):
        observations = [
            {'id':'noise','order':1,'role':'user','text':'文档示例保持简短。'},
            {'id':'retry','order':2,'role':'user','text':'纠正：客户端重试次数改为零。'},
        ]
        selected, omitted = lexical_observations(observations,'修改客户端重试逻辑',1,12000)
        self.assertEqual([item['id'] for item in selected],['retry'])
        self.assertEqual(omitted,1)

    def test_partial_compilation_does_not_drop_other_user_requirements(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            source={'id':'u1','order':1,'role':'user','text':'Use zero retries. Keep cancellation support.'}
            snapshot={'observations':[source], 'constraints':[{'sourceId':'u1','quote':'Use zero retries.'}],
                      'retractions':[], 'revision':1}
            host.store=Mock(side_effect=[snapshot,{'status':'selected','omittedForBudget':0,'text':'{}'}])
            result=host.context('scoped',['src/api'],'edit',12000)
            self.assertEqual(json.loads(result['text'])['uncompiled_user_observations'],[source])

    def test_extraction_does_not_turn_tool_output_into_user_memory(self):
        stdout='\n'.join(json.dumps(e) for e in [
            {'type':'item.completed','item':{'type':'command_execution','aggregated_output':'bad JSON'}},
            {'type':'item.completed','item':{'type':'agent_message','text':'{"proposals":[]}'}}])
        self.assertEqual(json.loads(final_text('codex',stdout)),{'proposals':[]})

    def test_full_store_retains_loaded_context_and_marks_unsaved_task(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            snapshot={'observations':[{'id':'policy','order':128,'role':'user',
                       'text':'Explicit zero must be preserved.'}], 'constraints':[], 'revision':128}
            host.store=Mock(side_effect=[snapshot,snapshot,ValueError('capacity exceeded')])
            host.call=Mock(return_value='edited')
            result=host.run('Fix the retry default.',root)
            self.assertEqual(result['context_mode'],'raw')
            self.assertIn('Explicit zero must be preserved.',host.call.call_args.args[0])
            self.assertFalse(result['task_persisted'])
            self.assertFalse(result['receipt_persisted'])
            self.assertIn('capacity',result['memory_error'])
            self.assertEqual(json.loads((root/'task.json').read_text())['text'],'Fix the retry default.')

    def test_invalid_checker_fails_before_memory_or_model(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            host.store=Mock();host.call=Mock()
            for invalid in ('{','[]','[""]','["python", 3]','["python", "\\u0000"]'):
                host.args.check=invalid
                with self.assertRaises(ValueError):host.run('Edit code.',root)
            host.store.assert_not_called();host.call.assert_not_called()

    def test_checker_recovery_uses_current_files_without_model_or_memory_calls(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);host=self.host(root,'off')
            original=host.state/'runs'/'original';original.mkdir(parents=True)
            host.args.check=json.dumps([sys.executable,'-c',
                'from pathlib import Path; assert Path("answer").read_text()=="fixed"'])
            host.call=Mock(return_value='coding done')
            host.store=Mock(side_effect=AssertionError('no memory in off/recheck'))
            # A checker failure must leave a completed coding checkpoint.
            first=host.run('Implement answer.',original)
            self.assertFalse(first['checker_pass'])
            (root/'answer').write_text('fixed')
            host.args.check=None
            evidence=host.state/'runs'/'retry';evidence.mkdir()
            result=host.check_run('original',evidence)
            self.assertTrue(result['checker_pass'])
            self.assertEqual(result['calls'],[])
            host.call.assert_called_once();host.store.assert_not_called()
            self.assertEqual(json.loads((original/'checker.json').read_text())['returncode'],1)
            self.assertEqual(json.loads((evidence/'checker.json').read_text())['returncode'],0)

    def test_recovery_refuses_unknown_completion_and_different_workspace(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);host=self.host(root,'off')
            original=host.state/'runs'/'original';original.mkdir(parents=True)
            host.call=Mock(side_effect=RuntimeError('interrupted model'))
            host.run('Edit code.',original)
            with patch('project_agent.run_command') as execute:
                with self.assertRaisesRegex(ValueError,'completion is unconfirmed'):
                    host.check_run('original',root)
                task=json.loads((original/'task.json').read_text());task['workspace']='/different'
                (original/'task.json').write_text(json.dumps(task))
                with self.assertRaisesRegex(ValueError,'must match'):
                    host.check_run('original',root)
                with self.assertRaises(ValueError):host.check_run('../original',root)
                execute.assert_not_called()

    def test_coding_checkpoint_survives_host_interruption_before_check(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);host=self.host(root,'off')
            original=host.state/'runs'/'original';original.mkdir(parents=True)
            host.args.check=json.dumps([sys.executable,'-c','print("checked")'])
            host.call=Mock(return_value='complete')
            with patch.object(host,'check',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):host.run('Edit code.',original)
            self.assertTrue((original/'agent-result.json').exists())
            evidence=host.state/'runs'/'retry';evidence.mkdir()
            self.assertTrue(host.check_run('original',evidence)['checker_pass'])
            host.call.assert_called_once()


if __name__ == '__main__':
    unittest.main()
