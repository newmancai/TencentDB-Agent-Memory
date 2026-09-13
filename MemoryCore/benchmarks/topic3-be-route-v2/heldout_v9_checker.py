"""Behavior checks for the path-enforced two-arm v9 replication."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Literal

sys.dont_write_bytecode = True

from heldout_v8_checker import jmespath_check, pluggy_check, zipp_check


def typeguard_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from typeguard import TypeCheckError, check_type

    def compatibility():
        assert check_type(1, Literal[1, True]) == 1
        try:
            check_type('wrong', Literal['expected'])
        except TypeCheckError:
            pass
        else:
            raise AssertionError('ordinary literal mismatch was accepted')

    def behavior():
        assert check_type(True, Literal[1, True]) is True
        assert check_type(False, Literal[0, False]) is False
        if stage >= 2:
            assert check_type(1, Literal[True, 1]) == 1
            assert check_type(0, Literal[False, 0]) == 0
            for value, annotation in ((True, Literal[1]), (False, Literal[0])):
                try:
                    check_type(value, annotation)
                except TypeCheckError:
                    pass
                else:
                    raise AssertionError('bool matched an equal integer literal')

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'jmespath': jmespath_check,
        'pluggy': pluggy_check,
        'zipp': zipp_check,
        'typeguard': typeguard_check,
    }[project](stage)
    result = {}
    for name, operation in [('compatibility', compatibility), ('behavior', behavior)]:
        try:
            operation()
        except Exception as error:
            result[name] = {'pass': False, 'error': f'{type(error).__name__}: {error}'}
        else:
            result[name] = {'pass': True}
    return result


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: heldout_v9_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
