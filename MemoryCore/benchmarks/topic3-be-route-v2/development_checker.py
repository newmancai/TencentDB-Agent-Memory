"""Behavioral checker for route-v2 development sources; never included in agent prompts."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def raises(call):
    try:
        call()
    except Exception:
        return
    raise AssertionError('expected an exception')


def tenacity(stage):
    sys.path.insert(0, str(Path.cwd()))
    import tenacity

    def compatibility():
        original = tenacity.Retrying(stop=tenacity.stop_after_attempt(7), reraise=True)
        replacement = tenacity.stop_after_attempt(2)
        copied = original.copy(stop=replacement)
        assert copied.stop is replacement
        assert copied.wait is original.wait and copied.retry is original.retry
        assert copied.before is original.before and copied.after is original.after

    def behavior():
        class CustomRetryError(tenacity.RetryError):
            pass

        def old_callback(retry_state):
            return ('old', retry_state.attempt_number)

        original = tenacity.Retrying(stop=tenacity.stop_after_attempt(1),
                                     retry_error_cls=CustomRetryError,
                                     retry_error_callback=old_callback)
        copied = original.copy(wait=tenacity.wait_none())
        assert copied.retry_error_cls is CustomRetryError
        assert copied.retry_error_callback is old_callback
        assert copied(lambda: (_ for _ in ()).throw(ValueError('boom'))) == ('old', 1)
        if stage >= 2:
            def new_callback(retry_state):
                return ('new', retry_state.attempt_number)
            replaced = original.copy(retry_error_callback=new_callback)
            assert replaced.retry_error_callback is new_callback
            assert replaced(lambda: (_ for _ in ()).throw(ValueError('boom'))) == ('new', 1)
            cleared = original.copy(retry_error_callback=None)
            assert cleared.retry_error_callback is None
            try:
                cleared(lambda: (_ for _ in ()).throw(ValueError('boom')))
            except CustomRetryError:
                pass
            else:
                raise AssertionError('explicit None must clear the callback, not preserve it')

    return compatibility, behavior


def cattrs(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from attr import define
    from cattr import Converter
    from cattr.gen import make_dict_structure_fn, make_dict_unstructure_fn, override

    @define
    class Record:
        count: int
        label: str

    def compatibility():
        converter = Converter()
        converter.register_structure_hook(Record, make_dict_structure_fn(
            Record, converter, _cattrs_forbid_extra_keys=True))
        assert converter.structure({'count': 2, 'label': 'ok'}, Record) == Record(2, 'ok')
        raises(lambda: converter.structure({'count': 2, 'label': 'ok', 'unknown': 3}, Record))
        unstructure = make_dict_unstructure_fn(Record, converter, label=override(rename='external'))
        assert unstructure(Record(2, 'ok')) == {'count': 2, 'external': 'ok'}

    def behavior():
        converter = Converter()
        converter.register_structure_hook(Record, make_dict_structure_fn(
            Record, converter, label=override(rename='external'), _cattrs_forbid_extra_keys=True))
        assert converter.structure({'count': 2, 'external': 'ok'}, Record) == Record(2, 'ok')
        if stage >= 2:
            raises(lambda: converter.structure({'count': 2, 'label': 'old'}, Record))
            raises(lambda: converter.structure(
                {'count': 2, 'label': 'old', 'external': 'ok'}, Record))
            raises(lambda: converter.structure({'count': 2, 'external': 'ok', 'other': 1}, Record))

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {'tenacity': tenacity, 'cattrs': cattrs}[project](stage)
    result = {}
    for name, operation in [('compatibility', compatibility), ('behavior', behavior)]:
        try:
            operation(); result[name] = {'pass': True}
        except Exception as error:
            result[name] = {'pass': False, 'error': f'{type(error).__name__}: {error}'}
    return result


if __name__ == '__main__':
    try:
        result = check(sys.argv[1], int(sys.argv[2]))
    except Exception as error:
        result = {'compatibility': {'pass': False, 'error': repr(error)}, 'behavior': {'pass': False}}
    print(json.dumps(result))
    raise SystemExit(2 if not result['compatibility']['pass'] else 0 if result['behavior']['pass'] else 1)
