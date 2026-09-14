"""Behavior-oriented checks for the filesystem-isolated held-out matrix."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import MappingProxyType, ModuleType
from unittest.mock import patch


def pytest_check(stage):
    package = ModuleType('_pytest')
    package.__path__ = [str(Path.cwd() / 'src' / '_pytest')]
    compat = ModuleType('_pytest.compat')
    compat.NotSetType = type('NotSetType', (), {})
    compat.NOTSET = compat.NotSetType()
    deprecated = ModuleType('_pytest.deprecated')
    deprecated.MONKEYPATCH_LEGACY_NAMESPACE_PACKAGES = 'legacy namespace package'
    fixtures = ModuleType('_pytest.fixtures')
    fixtures.fixture = lambda operation: operation
    warning_types = ModuleType('_pytest.warning_types')
    warning_types.PytestWarning = type('PytestWarning', (Warning,), {})
    sys.modules.update({'_pytest': package, '_pytest.compat': compat,
                        '_pytest.deprecated': deprecated, '_pytest.fixtures': fixtures,
                        '_pytest.warning_types': warning_types})
    from _pytest.monkeypatch import MonkeyPatch

    def compatibility():
        values = {'x': 1, 'y': 2}
        monkeypatch = MonkeyPatch()
        monkeypatch.setitem(values, 'x', 9)
        monkeypatch.delitem(values, 'y')
        monkeypatch.undo()
        assert values == {'x': 1, 'y': 2}

    def behavior():
        class Fixed:
            __slots__ = ()
            value = 1

        monkeypatch = MonkeyPatch()
        try:
            monkeypatch.delattr(Fixed(), 'value')
        except AttributeError:
            pass
        else:
            raise AssertionError('fixed-slot deletion unexpectedly succeeded')
        monkeypatch.undo()

        readonly = MappingProxyType({'x': 1})
        for operation in (
            lambda item: item.setitem(readonly, 'x', 2),
            lambda item: item.delitem(readonly, 'x'),
        ):
            monkeypatch = MonkeyPatch()
            try:
                operation(monkeypatch)
            except TypeError:
                pass
            else:
                raise AssertionError('read-only mapping mutation unexpectedly succeeded')
            monkeypatch.undo()
        if stage >= 2:
            monkeypatch = MonkeyPatch()
            try:
                monkeypatch.delitem({}, 'missing')
            except KeyError:
                pass
            else:
                raise AssertionError('raising=True no longer raises for a missing key')
            monkeypatch.delitem({}, 'missing', raising=False)
            monkeypatch.undo()

    return compatibility, behavior


def packaging_check(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from packaging._ranges import NEG_INF, POS_INF, LowerBound, UpperBound
    from packaging.version import Version

    def compatibility():
        lower = LowerBound(Version('1'), True)
        upper = UpperBound(Version('2'), True)
        assert lower.inclusive is True and upper.inclusive is True
        assert lower < LowerBound(Version('1'), False)
        assert UpperBound(Version('2'), False) < upper

    def behavior():
        lowers = LowerBound(None, True), LowerBound(None, False), NEG_INF
        uppers = UpperBound(None, True), UpperBound(None, False), POS_INF
        for values in (lowers, uppers):
            assert all(value.inclusive is False for value in values)
            assert len(set(values)) == 1
            for left in values:
                for right in values:
                    assert left == right
                    assert not left < right and not left > right
                    assert left <= right and left >= right
        if stage >= 2:
            assert LowerBound(Version('1'), True).inclusive is True
            assert UpperBound(Version('1'), True).inclusive is True

    return compatibility, behavior


def flask_check(stage):
    try:
        import blinker  # noqa: F401
    except ImportError:
        from contextlib import contextmanager

        class Signal:
            def send(self, *args, **kwargs): return []
            async def send_async(self, *args, **kwargs): return []
            def connect(self, *args, **kwargs): return None
            def disconnect(self, *args, **kwargs): return None
            def connect_via(self, *args, **kwargs): return lambda function: function
            @contextmanager
            def connected_to(self, *args, **kwargs): yield

        class Namespace:
            def signal(self, name): return Signal()

        module = ModuleType('blinker'); module.Namespace = Namespace
        sys.modules['blinker'] = module
    sys.path.insert(0, str(Path.cwd() / 'src'))
    import flask

    def run_address(server_name):
        observed = []
        app = flask.Flask(__name__)
        app.config['SERVER_NAME'] = server_name

        def fake_run_simple(host, port, application, **options):
            observed.append((host, port))

        with patch.dict(os.environ, {'FLASK_RUN_FROM_CLI': ''}, clear=False):
            with patch('flask.cli.show_server_banner'), patch(
                    'werkzeug.serving.run_simple', fake_run_simple):
                app.run(load_dotenv=False)
        assert len(observed) == 1
        return observed[0]

    def compatibility():
        assert run_address('localhost:8080') == ('localhost', 8080)
        assert run_address('localhost:0') == ('localhost', 0)

    def behavior():
        assert run_address('[::1]:8080') == ('::1', 8080)
        app = flask.Flask(__name__)
        app.secret_key = 'test-only'
        from flask.sessions import SessionMixin

        class MemorySession(dict, SessionMixin):
            pass

        class SessionInterface:
            def open_session(self, app, request): return MemorySession()
            def save_session(self, app, session, response): return None
            def is_null_session(self, session): return False

        app.session_interface = SessionInterface()
        client = app.test_client()
        client._cookies = {}
        client._add_cookies_to_wsgi = lambda environ: None
        cookie_hosts = []
        client._update_cookies_from_response = lambda host, path, headers: cookie_hosts.append(host)

        with client.session_transaction(base_url='http://[::1]:8000/') as session:
            session['value'] = 42
        assert cookie_hosts == ['::1']
        if stage >= 2:
            with client.session_transaction(base_url='http://localhost:5000/') as session:
                session['value'] = 7
            assert cookie_hosts[-1] == 'localhost'

    return compatibility, behavior


def h11_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from h11._headers import normalize_and_validate
    from h11._util import LocalProtocolError

    def compatibility():
        assert normalize_and_validate([('Content-Length', '0')])[-1][-1] == b'0'
        assert normalize_and_validate([('Content-Length', '9' * 20)])[-1][-1] == b'9' * 20

    def behavior():
        try:
            normalize_and_validate([('Content-Length', '1' * 21)])
        except LocalProtocolError as error:
            assert str(error) == 'bad Content-Length'
        else:
            raise AssertionError('oversized Content-Length was accepted')
        if stage >= 2:
            assert normalize_and_validate([('Transfer-Encoding', 'chunked')])[-1][-1] == b'chunked'

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'pytest': pytest_check,
        'packaging': packaging_check,
        'flask': flask_check,
        'h11': h11_check,
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
        raise SystemExit('usage: heldout_v3_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
