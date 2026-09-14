"""Behavior checks for the two-arm v5 lossless-history replication."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType


def websockets_check(stage):
    class Headers:
        def __init__(self):
            self.values = {}

        def __setitem__(self, name, value):
            value.encode('ascii')
            self.values[name] = value

        def set_insecure(self, name, value):
            self.values[name] = value

        def __getitem__(self, name):
            return self.values[name]

    class SecurityError(Exception):
        pass

    root = Path.cwd() / 'src' / 'websockets'
    for name, path in [('websockets', root), ('websockets.legacy', root / 'legacy')]:
        package = ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    datastructures = ModuleType('websockets.datastructures')
    datastructures.Headers = Headers
    exceptions = ModuleType('websockets.exceptions')
    exceptions.SecurityError = SecurityError
    sys.modules[datastructures.__name__] = datastructures
    sys.modules[exceptions.__name__] = exceptions
    module_spec = importlib.util.spec_from_file_location(
        'websockets.legacy.http', root / 'legacy' / 'http.py')
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)

    async def parse(line):
        stream = asyncio.StreamReader()
        stream.feed_data(line + b'\r\n\r\n')
        stream.feed_eof()
        return await module.read_headers(stream)

    def compatibility():
        assert asyncio.run(parse(b'X-Test: value'))['X-Test'] == 'value'

    def behavior():
        headers = asyncio.run(parse(b'X-Drink: caf\xe9'))
        assert headers['X-Drink'] == 'caf\udce9'
        if stage >= 2:
            try:
                asyncio.run(parse(b'X-Test: bad\x00value'))
            except ValueError:
                pass
            else:
                raise AssertionError('invalid control byte was accepted')

    return compatibility, behavior


def jsonschema_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import best_match

    def select(instance, schema):
        return best_match(Draft202012Validator(schema).iter_errors(instance))

    def compatibility():
        error = select(1, {'type': 'string'})
        assert error.validator == 'type' and error.instance == 1

    def behavior():
        schema = {'anyOf': [
            {'type': 'string'},
            {'properties': {'foo': {'minProperties': 2,
                                     'properties': {'bar': {'type': 'object'}}}}},
        ]}
        error = select({'foo': {'bar': []}}, schema)
        assert error.validator == 'minProperties'
        if stage >= 2:
            tied = {'anyOf': [
                {'properties': {'foo': {'type': 'string'}}},
                {'properties': {'bar': {'type': 'string'}}},
            ]}
            assert select({'foo': 1, 'bar': 1}, tied).validator == 'anyOf'

    return compatibility, behavior


def scrapy_check(stage):
    spec = importlib.util.spec_from_file_location(
        'heldout_scrapy_datatypes', Path.cwd() / 'scrapy' / 'utils' / 'datatypes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    LocalCache = module.LocalCache

    def compatibility():
        cache = LocalCache(limit=2)
        cache['a'] = 1
        cache['b'] = 2
        cache['c'] = 3
        assert list(cache.items()) == [('b', 2), ('c', 3)]

    def behavior():
        cache = LocalCache(limit=2)
        cache['a'] = 1
        cache['b'] = 2
        cache['b'] = 20
        assert list(cache.items()) == [('a', 1), ('b', 20)]
        if stage >= 2:
            cache['c'] = 3
            assert list(cache.items()) == [('b', 20), ('c', 3)]

    return compatibility, behavior


def wsproto_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from wsproto.events import CloseConnection
    from wsproto.utilities import LocalProtocolError, RemoteProtocolError

    hint = CloseConnection(code=1002, reason='protocol')

    def compatibility():
        assert RemoteProtocolError('bad frame', hint).event_hint is hint
        assert str(LocalProtocolError('local')) == 'local'

    def behavior():
        try:
            RemoteProtocolError('missing hint')
        except TypeError:
            pass
        else:
            raise AssertionError('event_hint remains optional')
        if stage >= 2:
            assert RemoteProtocolError('again', hint).event_hint is hint

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'websockets': websockets_check,
        'jsonschema': jsonschema_check,
        'scrapy': scrapy_check,
        'wsproto': wsproto_check,
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
        raise SystemExit('usage: heldout_v5_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
