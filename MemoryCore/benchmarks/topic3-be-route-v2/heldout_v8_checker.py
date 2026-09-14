"""Behavior checks for path-enforced two-arm v8 replication."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import random
import struct
import sys
import warnings
from zipfile import ZipFile

sys.dont_write_bytecode = True


def hyperframe_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from hyperframe.frame import SettingsFrame

    def compatibility():
        frame = SettingsFrame(settings={1: 100})
        assert frame.serialize_body() == struct.pack('!HI', 1, 100)

    def behavior():
        frame = SettingsFrame(settings={0x1234: 0x1_0000_0002})
        assert frame.serialize_body() == struct.pack('!HI', 0x1234, 2)
        if stage >= 2:
            assert SettingsFrame(settings={2: 0}).serialize_body() == struct.pack('!HI', 2, 0)

    return compatibility, behavior


def jmespath_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from jmespath import parser as parser_module
    Parser = parser_module.Parser

    def compatibility():
        Parser.purge()
        parsed = Parser().parse('alpha')
        assert parsed.search({'alpha': 3}) == 3

    def behavior():
        assert Parser._MAX_SIZE == 512
        original_size = Parser._MAX_SIZE
        original_sample = getattr(getattr(parser_module, 'random', None), 'sample', None)
        try:
            Parser._MAX_SIZE = 2
            Parser.purge()
            if original_sample is not None:
                parser_module.random.sample = lambda values, count: list(values)[-count:]
            parser = Parser()
            first = parser.parse('alpha')
            assert parser.parse('alpha') is first
            parser.parse('beta')
            parser.parse('gamma')
            assert list(Parser._CACHE) == ['beta', 'gamma']
        finally:
            if original_sample is not None:
                parser_module.random.sample = original_sample
            Parser._MAX_SIZE = original_size
            Parser.purge()
        if stage >= 2:
            class MutationRaceCache(dict):
                def __iter__(self):
                    raise RuntimeError('simulated concurrent mutation')

            original_cache = Parser._CACHE
            try:
                Parser._MAX_SIZE = 1
                Parser._CACHE = MutationRaceCache({'occupied': object()})
                parsed = Parser().parse('epsilon')
                assert parsed.search({'epsilon': 5}) == 5
                assert 'epsilon' not in Parser._CACHE
                assert len(Parser._CACHE) == 1
            finally:
                Parser._CACHE = original_cache
                Parser._MAX_SIZE = original_size
                Parser.purge()
            parser = Parser()
            assert parser.parse('delta').search({'delta': 4}) == 4
            Parser.purge()
            assert Parser._CACHE == {}

    return compatibility, behavior


def pluggy_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from pluggy import HookspecMarker, PluginManager

    hookspec = HookspecMarker('v8')

    class Spec:
        @hookspec
        def hello(self, required):
            """Test hook."""

    manager = PluginManager('v8')
    manager.add_hookspecs(Spec)

    def compatibility():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            manager.hook.hello(required=1)
        assert caught == []

    def behavior():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            manager.hook.hello()
        assert len(caught) == 1
        assert Path(caught[0].filename).resolve() == Path(__file__).resolve()
        if stage >= 2:
            with warnings.catch_warnings(record=True) as extra:
                warnings.simplefilter('always')
                manager.hook.hello.call_extra([], kwargs={})
            assert len(extra) == 1
            assert Path(extra[0].filename).resolve() == Path(__file__).resolve()

    return compatibility, behavior


def zipp_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    import zipp

    def archive():
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as target:
            target.writestr('folder/item.txt', 'value')
            target.writestr('root.txt', 'root')
        return ZipFile(buffer)

    def compatibility():
        with archive() as target:
            assert (zipp.Path(target) / 'root.txt').read_text() == 'root'

    def behavior():
        with archive() as target:
            root = zipp.Path(target)
            try:
                list((root / 'root.txt').iterdir())
            except NotADirectoryError:
                pass
            else:
                raise AssertionError('iterdir on a file did not raise NotADirectoryError')
            if stage >= 2:
                assert [child.name for child in (root / 'folder').iterdir()] == ['item.txt']

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'hyperframe': hyperframe_check,
        'jmespath': jmespath_check,
        'pluggy': pluggy_check,
        'zipp': zipp_check,
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
        raise SystemExit('usage: heldout_v8_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
