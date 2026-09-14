"""Behavior checks for the small-task two-arm v6 replication."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from types import ModuleType

sys.dont_write_bytecode = True


@contextmanager
def environment(**values):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def platformdirs_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    # The repository generates this module while building a wheel. The behavior
    # under test doesn't depend on version metadata, so keep source-checkout
    # preflights installation-free.
    version = ModuleType('platformdirs.version')
    version.__version__ = '0'
    version.__version_tuple__ = (0,)
    sys.modules[version.__name__] = version
    from platformdirs.unix import Unix

    def compatibility():
        with environment(HOME='/tmp/v6-home', XDG_CONFIG_HOME='/opt/xdg'):
            assert Unix('demo').user_config_dir == '/opt/xdg/demo'

    def behavior():
        fallbacks = {
            'XDG_DATA_HOME': ('user_data_dir', '/tmp/v6-home/.local/share/demo'),
            'XDG_CONFIG_HOME': ('user_config_dir', '/tmp/v6-home/.config/demo'),
            'XDG_CACHE_HOME': ('user_cache_dir', '/tmp/v6-home/.cache/demo'),
            'XDG_STATE_HOME': ('user_state_dir', '/tmp/v6-home/.local/state/demo'),
        }
        for env_var, (attribute, expected) in fallbacks.items():
            for invalid in ('relative/path', '~/path', '$HOME/path', 'C:/path'):
                with environment(HOME='/tmp/v6-home', **{env_var: invalid}):
                    assert getattr(Unix('demo'), attribute) == expected
        with environment(XDG_CONFIG_DIRS='relative:/opt/one:../other:/opt/two'):
            assert Unix('demo', multipath=True).site_config_dir == '/opt/one/demo:/opt/two/demo'
        if stage >= 2:
            with environment(HOME='/tmp/v6-home', XDG_CONFIG_HOME='  /srv/config  '):
                assert Unix('demo').user_config_dir == '/srv/config/demo'

    return compatibility, behavior


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
    # Only ASCII layout is exercised here. Keep the source checkout independent
    # of optional environment packages while preserving the width/padding API.
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
            assert '\t' not in formatted
            assert 'custom' in formatted
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
        assert dist.metadata['Name'] == 'demo'
        assert dist.version == '1.2'

    def behavior():
        assert StubDistribution({}).metadata is None
        if stage >= 2:
            fallback = StubDistribution({'PKG-INFO': 'Name: fallback\nVersion: 2\n'})
            assert fallback.metadata['Name'] == 'fallback'

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'platformdirs': platformdirs_check,
        'hpack': hpack_check,
        'prettytable': prettytable_check,
        'importlib-metadata': importlib_metadata_check,
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
        raise SystemExit('usage: heldout_v6_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
