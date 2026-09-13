"""Behavior-oriented external checks for the replacement held-out matrix."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace


def urllib3_check(stage):
    package = ModuleType('urllib3')
    package.__path__ = [str(Path.cwd() / 'src' / 'urllib3')]
    sys.modules['urllib3'] = package
    from urllib3._collections import HTTPHeaderDict

    def compatibility():
        headers = HTTPHeaderDict({'Content-Length': '4', 'X-Request-ID': 'kept'})
        headers._prepare_for_method_change()
        assert 'Content-Length' not in headers
        assert headers['X-Request-ID'] == 'kept'

    def behavior():
        headers = HTTPHeaderDict({
            'Transfer-Encoding': 'chunked',
            'Authorization': 'Bearer x',
            'X-Request-ID': 'kept',
        })
        headers._prepare_for_method_change()
        assert 'Transfer-Encoding' not in headers
        assert headers['Authorization'] == 'Bearer x'
        assert headers['X-Request-ID'] == 'kept'

    return compatibility, behavior


def starlette(stage):
    sys.path.insert(0, str(Path.cwd()))
    from starlette.datastructures import URL

    def compatibility():
        assert str(URL('https://example.test/a').replace_query_params(x='a b')) == (
            'https://example.test/a?x=a+b'
        )

    def behavior():
        original = URL('https://example.test/a?flag&x=a%20b&&bad=%ZZ')
        appended = original.append_query_params({'z': 'c d'})
        assert str(appended) == 'https://example.test/a?flag&x=a%20b&&bad=%ZZ&z=c+d'
        assert str(original.append_query_params({})) == str(original)
        if stage >= 2:
            assert str(original.replace_query_params(z='c d')) == 'https://example.test/a?z=c+d'

    return compatibility, behavior


def anyio_check(stage):
    class FakeFile:
        def __init__(self): self.closed = False; self.data = b''
        def close(self): self.closed = True
        def write(self, value): self.data += value; return len(value)

    class Shield:
        def __init__(self, *, shield): assert shield is True
        def __enter__(self): return self
        def __exit__(self, *args): return False

    async def placeholder_run_sync(operation, *args, **kwargs):
        return operation(*args)

    async def placeholder_checkpoint():
        return None

    package = ModuleType('anyio'); package.__path__ = []
    package.BrokenResourceError = type('BrokenResourceError', (Exception,), {})
    package.CancelScope = Shield
    package.ClosedResourceError = type('ClosedResourceError', (Exception,), {})
    package.EndOfStream = type('EndOfStream', (Exception,), {})
    package.TypedAttributeSet = type('TypedAttributeSet', (), {})
    package.to_thread = SimpleNamespace(run_sync=placeholder_run_sync)
    package.typed_attribute = lambda: object()
    abc = ModuleType('anyio.abc')
    abc.ByteReceiveStream = type('ByteReceiveStream', (), {})
    abc.ByteSendStream = type('ByteSendStream', (), {})
    streams = ModuleType('anyio.streams'); streams.__path__ = []
    lowlevel = ModuleType('anyio.lowlevel')
    lowlevel.checkpoint_if_cancelled = placeholder_checkpoint
    sys.modules.update({'anyio': package, 'anyio.abc': abc, 'anyio.streams': streams,
                        'anyio.lowlevel': lowlevel})
    path = Path.cwd() / 'src' / 'anyio' / 'streams' / 'file.py'
    spec = importlib.util.spec_from_file_location('anyio.streams.file', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load file stream module')
    module = importlib.util.module_from_spec(spec)
    sys.modules['anyio.streams.file'] = module
    spec.loader.exec_module(module)

    async def exercise():
        events = []
        file = FakeFile()
        stream = object.__new__(module.FileReadStream)
        stream._file = file

        async def run_sync(operation, *args, **kwargs):
            events.append(operation.__name__)
            return operation(*args)

        async def checkpoint():
            events.append('checkpoint')

        original_scope = module.CancelScope
        original_run_sync = module.to_thread.run_sync
        had_checkpoint = hasattr(module, 'checkpoint_if_cancelled')
        original_checkpoint = getattr(module, 'checkpoint_if_cancelled', None)
        try:
            module.CancelScope = Shield
            module.to_thread.run_sync = run_sync
            module.checkpoint_if_cancelled = checkpoint
            await stream.aclose()
        finally:
            module.CancelScope = original_scope
            module.to_thread.run_sync = original_run_sync
            if had_checkpoint:
                module.checkpoint_if_cancelled = original_checkpoint
            else:
                del module.checkpoint_if_cancelled
        return events, file.closed

    async def exercise_send():
        events = []
        file = FakeFile()
        stream = object.__new__(module.FileWriteStream)
        stream._file = file

        async def run_sync(operation, *args, **kwargs):
            events.append(operation.__name__)
            return operation(*args)

        async def checkpoint():
            events.append('checkpoint')

        original_run_sync = module.to_thread.run_sync
        had_checkpoint = hasattr(module, 'checkpoint_if_cancelled')
        original_checkpoint = getattr(module, 'checkpoint_if_cancelled', None)
        try:
            module.to_thread.run_sync = run_sync
            module.checkpoint_if_cancelled = checkpoint
            await stream.send(b'x')
        finally:
            module.to_thread.run_sync = original_run_sync
            if had_checkpoint:
                module.checkpoint_if_cancelled = original_checkpoint
            else:
                del module.checkpoint_if_cancelled
        return events, file.data

    def compatibility():
        assert hasattr(module.FileReadStream, 'receive')
        assert hasattr(module.FileWriteStream, 'send')

    def behavior():
        events, closed = asyncio.run(exercise())
        assert closed
        assert events == ['close', 'checkpoint']
        if stage >= 2:
            send_events, data = asyncio.run(exercise_send())
            assert send_events == ['write'] and data == b'x'

    return compatibility, behavior


def trio(stage):
    requirements = (Path.cwd() / 'test-requirements.in').read_text()
    project = (Path.cwd() / 'pyproject.toml').read_text()
    match = re.search(r'^coverage\s*>=\s*([^\s#]+)', requirements, re.MULTILINE)

    def compatibility():
        assert 'pytest >= 8.4' in requirements
        assert '[tool.pytest.ini_options]' in project

    def behavior():
        assert match is not None and match.group(1) == '7.15.0'
        assert 'ignore:Module globals; __loader__ != __spec__.loader:DeprecationWarning' not in project

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'urllib3': urllib3_check,
        'starlette': starlette,
        'anyio': anyio_check,
        'trio': trio,
    }[project](stage)
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
