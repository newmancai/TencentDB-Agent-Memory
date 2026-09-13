import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from backend import isolated_filesystem_command, run_command


class BackendProcessTest(unittest.TestCase):
    def test_isolated_filesystem_hides_siblings_and_rebinds_workspace(self):
        with TemporaryDirectory() as directory:
            hidden = Path(directory) / 'benchmark-root'
            workspace = hidden / 'workspaces' / 'project' / 'arm'
            sibling = hidden / 'results' / 'other-arm'
            workspace.mkdir(parents=True)
            sibling.mkdir(parents=True)
            (workspace / 'visible').write_text('yes')
            (sibling / 'secret').write_text('no')
            probe = ('from pathlib import Path; '
                     'assert Path("visible").read_text() == "yes"; '
                     f'assert not Path({str(sibling)!r}).exists()')
            command = isolated_filesystem_command(
                [sys.executable, '-c', probe], workspace, hidden)
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_isolated_filesystem_rejects_external_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'below the hidden root'):
                isolated_filesystem_command(['true'], root / 'outside', root / 'hidden')

    def test_events_are_visible_before_command_completion(self):
        with TemporaryDirectory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
            root=Path(directory); logs=root/'logs'
            future=pool.submit(run_command,[sys.executable,'-c',
                "import time;print('started',flush=True);time.sleep(.8);print('finished',flush=True)"],root,3,log_directory=logs)
            deadline=time.monotonic()+2
            path=logs/'stdout.jsonl'
            while (not path.exists() or not path.read_text()) and time.monotonic()<deadline:time.sleep(.01)
            self.assertIn('started',path.read_text())
            self.assertFalse(future.done())
            result=future.result(timeout=3)
            self.assertEqual(result['stdout'],path.read_text())
            self.assertIn('finished',result['stdout'])
    def test_timeout_stops_descendants(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            child="import time;from pathlib import Path;time.sleep(.5);Path('late').write_text('bad')"
            command="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);time.sleep(10)"
            result=run_command([sys.executable,'-c',command],root,.1)
            self.assertEqual(result['status'],'timeout')
            time.sleep(.6)
            self.assertFalse((root/'late').exists())

    def test_cancel_preserves_partial_output_and_stops_descendants(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            child="import time;from pathlib import Path;time.sleep(.8);Path('late').write_text('bad')"
            command="import subprocess,sys,time;from pathlib import Path;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);print('partial',flush=True);Path('started').touch();time.sleep(10)"
            driver="import sys,json;from pathlib import Path;sys.path.insert(0,"+repr(str(Path(__file__).parent.resolve()))+");from backend import run_command;print(json.dumps(run_command([sys.executable,'-c',"+repr(command)+"],Path.cwd(),10)),flush=True)"
            process=subprocess.Popen([sys.executable,'-c',driver],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+3
                while not (root/'started').exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue((root/'started').exists())
                os.kill(process.pid,signal.SIGINT)
                stdout,stderr=process.communicate(timeout=3)
                self.assertEqual(process.returncode,0,stderr)
                result=json.loads(stdout)
                self.assertEqual(result['status'],'cancelled')
                self.assertIn('partial',result['stdout'])
                time.sleep(.9)
                self.assertFalse((root/'late').exists())
            finally:
                if process.poll() is None:process.kill();process.wait()


if __name__=='__main__':unittest.main()
