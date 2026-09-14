"""Behavior checks for the single-source-file two-arm v7 replication."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
from types import ModuleType
from zipfile import ZipFile

sys.dont_write_bytecode = True


def hpack_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from hpack import Encoder

    def compatibility():
        encoder = Encoder()
        assert encoder.encode([(b':method', b'GET')], huffman=False) == b'\x82'
        assert list(encoder.header_table.dynamic_entries) == []

    def behavior():
        encoder = Encoder()
        assert encoder.encode([(b':authority', b'')], huffman=False) == b'\x81'
        assert list(encoder.header_table.dynamic_entries) == []
        if stage >= 2:
            encoded = encoder.encode([(b':authority', b'example.test')], huffman=False)
            assert encoded != b'\x81'
            assert list(encoder.header_table.dynamic_entries) == [(b':authority', b'example.test')]

    return compatibility, behavior


def prettytable_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    version = ModuleType('prettytable._version')
    version.__version__ = '0'
    sys.modules[version.__name__] = version
    wcwidth = ModuleType('wcwidth')
    wcwidth.width = len
    wcwidth.ljust = lambda text, width: text.ljust(width)
    wcwidth.rjust = lambda text, width: text.rjust(width)
    wcwidth.center = lambda text, width: text.center(width)
    sys.modules[wcwidth.__name__] = wcwidth
    from prettytable import PrettyTable

    def rendered(value, formatter=None):
        table = PrettyTable(['code', 'note'])
        if formatter is not None:
            table.custom_format = {'code': formatter}
        table.add_row([value, 'marker'])
        return table.get_string()

    def compatibility():
        result = rendered('plain')
        assert 'plain' in result and 'marker' in result

    def behavior():
        result = rendered('if ok:\n\treturn 1')
        assert '\t' not in result
        assert len({len(line) for line in result.splitlines()}) == 1
        if stage >= 2:
            formatted = rendered('ignored', lambda field, value: '\tcustom')
            assert '\t' not in formatted and 'custom' in formatted
            assert len({len(line) for line in formatted.splitlines()}) == 1

    return compatibility, behavior


def importlib_metadata_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from importlib_metadata import Distribution

    class StubDistribution(Distribution):
        def __init__(self, files):
            self._texts = files

        def read_text(self, filename):
            return self._texts.get(filename)

        def locate_file(self, path):
            return Path(path)

    def compatibility():
        dist = StubDistribution({'METADATA': 'Name: demo\nVersion: 1.2\n'})
        assert dist.metadata['Name'] == 'demo' and dist.version == '1.2'

    def behavior():
        assert StubDistribution({}).metadata is None
        if stage >= 2:
            fallback = StubDistribution({'PKG-INFO': 'Name: fallback\nVersion: 2\n'})
            assert fallback.metadata['Name'] == 'fallback'

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
            root = zipp.Path(target)
            assert (root / 'root.txt').read_text() == 'root'

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
        'hpack': hpack_check,
        'prettytable': prettytable_check,
        'importlib-metadata': importlib_metadata_check,
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
        raise SystemExit('usage: heldout_v7_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
