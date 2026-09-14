import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from agent_product_runner import ARMS
from sequence_runner import run


class FakeHost:
    def __init__(self,args):
        self.args=args;self.state=args.state;self.state.mkdir(parents=True,exist_ok=True);self.calls=[]
    def record(self,text,evidence):
        with (self.state/'raw.txt').open('a') as f:f.write(text+'\n')
        return {'calls':[]}
    def remember(self,text,evidence,*,compile_constraints=False):
        assert compile_constraints
        assert self.args.mode=='scoped'
        self.record(text,evidence)
        self.calls.append({'usage':{'input_tokens':2},'wall_seconds':.5})
        return {'calls':self.calls}
    def run(self,text,evidence):
        counter=self.args.workspace/'progress.txt'
        old=int(counter.read_text()) if counter.exists() else 0
        assert old==int(text)-1,'previous task edits must survive'
        counter.write_text(str(old+1))
        assert (self.state/'raw.txt').read_text()=='old\ncorrection\n'
        self.calls.append({'usage':{'input_tokens':10},'wall_seconds':1,'status':'completed','returncode':0})
        (evidence/'checker.json').write_text(json.dumps({'status':'completed','returncode':0,'wall_seconds':.1}))
        return {'calls':self.calls,'checker_pass':True,'error':None,'context_mode':self.args.mode,
                'context_bytes':10,'memory_error':None}


class SequenceRunnerTest(unittest.TestCase):
    def test_history_is_persistent_separate_and_setup_cost_is_not_duplicated(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(source/'a').write_text('base')
            for args in [['git','init','-q'],['git','add','.'],['git','-c','user.name=T','-c','user.email=t@example.invalid','commit','-qm','base']]:
                subprocess.run(args,cwd=source,check=True,capture_output=True)
            base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
            paths={}
            for arm in ARMS:
                path=root/arm;shutil.copytree(source,path);(path/'.agent-benchmark-worktree').touch();paths[arm]=str(path)
            manifest={'schema':2,'clusters':[{'id':'repo','base_commit':base,'workspaces':paths,'steps':[
                {'id':'first','kind':'necessary_update','prompt':'1','paths':['.'],'checker':['true'],'history':['old','correction']},
                {'id':'next','kind':'same_topic_control','prompt':'2','paths':['.'],'checker':['true'],'history':[]},
            ]}]}
            with patch('sequence_runner.Host',FakeHost),contextlib.redirect_stdout(io.StringIO()):
                summary=run(manifest,root/'results',['codex'])
            self.assertEqual(summary['setup']['codex_clean']['cli_runs'],0)
            self.assertEqual(summary['setup']['codex_memory']['cli_runs'],2)
            self.assertEqual(summary['setup']['codex_memory']['usage']['input_tokens'],4)
            self.assertEqual(summary['arms']['codex_memory']['checker_pass'],2)
            self.assertFalse(summary['pass'])


if __name__=='__main__':unittest.main()
