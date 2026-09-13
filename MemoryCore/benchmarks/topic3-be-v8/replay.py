"""Reproduce both recorded attribution protocols without corpus/model downloads."""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    output = Path(sys.argv[1])
    here = Path(__file__).resolve().parent
    shutil.copytree(here / 'results/replay', output)
    for mode in ('model', 'model32'):
        subprocess.run([sys.executable, str(here / 'evaluate.py'), str(output), mode], check=True)
        destination = output if mode == 'model' else output / mode
        for name in ('summary.json', 'policy.json', 'predictions.json'):
            expected = json.loads((here / 'results' / mode / name).read_text())
            if json.loads((destination / name).read_text()) != expected:
                raise ValueError(f'Replay mismatch: {mode}/{name}')
    print('PASS: both summaries, fitted policies and predictions reproduced')


if __name__ == '__main__':
    main()
