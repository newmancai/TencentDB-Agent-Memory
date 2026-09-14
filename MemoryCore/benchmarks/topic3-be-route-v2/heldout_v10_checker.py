"""Behavior checks for v10, including every declared semantic boundary."""
from __future__ import annotations

from contextlib import contextmanager
import ast
import json
from importlib.machinery import ModuleSpec
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types

sys.dont_write_bytecode = True


def h2_check(stage):
    class ProtocolError(Exception):
        pass

    source = Path('src/h2/stream.py').read_text()
    tree = ast.parse(source)
    stream_class = next(node for node in tree.body
                        if isinstance(node, ast.ClassDef) and node.name == 'H2Stream')
    method = next(node for node in stream_class.body
                  if isinstance(node, ast.FunctionDef) and node.name == '_initialize_content_length')
    method.decorator_list = []
    namespace = {'ProtocolError': ProtocolError, 'Iterable': object, 'Header': object}
    extracted = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(extracted, 'src/h2/stream.py', 'exec'), namespace)
    initialize_method = namespace['_initialize_content_length']

    def initialize(headers):
        stream = types.SimpleNamespace(request_method=None, _expected_content_length=None)
        initialize_method(stream, headers)
        return stream._expected_content_length

    def compatibility():
        assert initialize([]) is None
        assert initialize([(b'content-length', b'7')]) == 7
        try:
            initialize([(b'content-length', b'not-a-number')])
        except ProtocolError:
            pass
        else:
            raise AssertionError('invalid content length was accepted')

    def behavior():
        assert initialize([(b'content-length', b'7'), (b'content-length', b'7')]) == 7
        conflicting = [(b'content-length', b'7'), (b'x-extra', b'1'),
                       (b'content-length', b'8')]
        try:
            initialize(conflicting)
        except ProtocolError:
            pass
        else:
            raise AssertionError('conflicting content lengths were accepted')
        if stage >= 2:
            assert initialize([(b'content-length', b'9')] * 3) == 9

    return compatibility, behavior


def pycodestyle_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    import pycodestyle

    @contextmanager
    def config_names():
        old = pycodestyle.PROJECT_CONFIG
        try:
            pycodestyle.PROJECT_CONFIG = ('setup.cfg',)
            yield
        finally:
            pycodestyle.PROJECT_CONFIG = old

    def read(paths):
        parser = pycodestyle.get_parser()
        parser.add_option('--config')
        arguments = [str(path) for path in paths]
        options, parsed = parser.parse_args(arguments)
        with config_names():
            return pycodestyle.read_config(options, parsed, arguments, parser)

    def compatibility():
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            target = source / 'one.py'
            target.touch()
            (source / 'setup.cfg').write_text('[pycodestyle]\nexclude = local\n')
            assert read([target]).exclude == ['local']

    def behavior():
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'setup.cfg').write_text('[pycodestyle]\nexclude = root\n')
            decoy = root / 'aaa'
            left = root / 'aaabbb'
            right = root / 'aaaccc'
            for item in (decoy, left, right):
                item.mkdir()
            (decoy / 'setup.cfg').write_text('[pycodestyle]\nexclude = decoy\n')
            (left / 'setup.cfg').write_text('[pycodestyle]\nexclude = left\n')
            left_file = left / 'one.py'
            right_file = right / 'two.py'
            left_file.touch()
            right_file.touch()
            assert read([left_file, right_file]).exclude == ['root']
            if stage >= 2:
                assert read([left_file]).exclude == ['left']

    return compatibility, behavior


def path_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from path import TempDir

    def compatibility():
        temporary = TempDir()
        assert temporary.is_dir()
        name = str(temporary)
        temporary.rmtree()
        assert not os.path.exists(name)

    def behavior():
        with TemporaryDirectory() as parent:
            keyword = TempDir(dir=parent, prefix='pre-', suffix='-suf')
            try:
                assert Path(keyword).parent == Path(parent)
                assert keyword.name.startswith('pre-') and keyword.name.endswith('-suf')
            finally:
                keyword.rmtree()
            positional = TempDir('-tail', 'head-', parent)
            try:
                assert Path(positional).parent == Path(parent)
                assert positional.name.startswith('head-') and positional.name.endswith('-tail')
            finally:
                positional.rmtree()
        if stage >= 2:
            with TempDir(prefix='managed-') as managed:
                assert managed.is_dir()
            assert not managed.exists()

    return compatibility, behavior


def resources_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    import importlib_resources
    from importlib_resources import files

    def compatibility():
        assert files(importlib_resources).is_dir()

    def assert_none_spec(name):
        module = types.ModuleType(name)
        assert module.__spec__ is None
        try:
            files(module)
        except TypeError as error:
            message = str(error)
            assert name in message and '__spec__ is None' in message
        else:
            raise AssertionError('None module spec was accepted')

    def behavior():
        assert_none_spec('__main__')
        class Reader:
            def files(self):
                return Path.cwd()

        class Loader:
            def get_resource_reader(self, fullname):
                return Reader()

        class FalseySpec(ModuleSpec):
            def __bool__(self):
                return False

        module = types.ModuleType('falsey_but_importable')
        module.__spec__ = FalseySpec(module.__name__, Loader())
        assert files(module).is_dir()
        if stage >= 2:
            assert_none_spec('tool_runner')

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'h2': h2_check,
        'pycodestyle': pycodestyle_check,
        'path': path_check,
        'importlib_resources': resources_check,
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
        raise SystemExit('usage: heldout_v10_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
