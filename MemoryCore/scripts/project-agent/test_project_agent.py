import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from project_agent import Host, final_text, retain_project_instructions, command_for


class ProjectAgentTest(unittest.TestCase):
    def test_normal_product_use_retains_project_guidance(self):
        original=command_for('codex_memory',Path('/tmp'),'task',{})
        normal=retain_project_instructions(original,'codex')
        self.assertNotIn('project_doc_max_bytes=0',normal)
        self.assertNotIn('--ignore-user-config',normal)
        self.assertIn('--sandbox',normal)
        self.assertIn('workspace-write',normal)
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
            snapshot={'observations':[observation],'constraints':[], 'retractions':[], 'revision':1}
            host.store=Mock(side_effect=[snapshot,{'status':'selected','omittedForBudget':1}])
            result=host.context('scoped',['src/api'],'edit',1)
            self.assertEqual(result['mode'],'raw_fallback')
            self.assertEqual(json.loads(result['text']),observation)

    def test_failed_extraction_persists_raw_observation_only(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); host=self.host(root)
            host.store=Mock(side_effect=[{'observations':[],'constraints':[]}, {'accepted':[]}])
            host.call=Mock(side_effect=RuntimeError('backend 502'))
            result=host.remember('Keep existing worker behavior.',root)
            self.assertEqual(result['extraction_error'],'backend 502')
            self.assertEqual(host.store.call_args.kwargs['proposals'],[])
            self.assertEqual(host.store.call_args.kwargs['observation']['text'],'Keep existing worker behavior.')

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


if __name__ == '__main__':
    unittest.main()
