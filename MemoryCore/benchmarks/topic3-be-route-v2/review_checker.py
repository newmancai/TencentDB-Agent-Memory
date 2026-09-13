"""Check real PR-review decisions without exposing them to the coding agent."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
from types import ModuleType


def cachetools(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    import cachetools

    def compatibility():
        cache = cachetools.LRUCache(maxsize=3)
        cache['a'] = 1; cache['b'] = 2
        assert cache['a'] == 1 and cache['b'] == 2 and len(cache) == 2
        cache['c'] = 3
        assert len(cache) == 3 and cache.currsize == 3

    def replacement_behavior():
        cache = cachetools.LRUCache(maxsize=10, getsizeof=lambda value: value)
        cache[3] = 3; cache[4] = 4; cache[4] = 7
        assert dict(cache) == {3: 3, 4: 7} and cache.currsize == 10
        cache[4] = 7
        assert dict(cache) == {3: 3, 4: 7} and cache.currsize == 10
        cache[4] = 1
        assert dict(cache) == {3: 3, 4: 1} and cache.currsize == 4

    def behavior():
        replacement_behavior()
        changelog = (Path.cwd() / 'CHANGELOG.rst').read_text()
        entry = 'Fix ``Cache.__setitem__`` over-evicting when growing an existing key'
        if stage == 1:
            assert entry not in changelog, 'PR-time review requires no changelog entry'
            source = inspect.getsource(cachetools.Cache.__setitem__)
            assert 'if key not in self.__data:' in source
            assert source.count('while self.__currsize + diffsize > maxsize:') == 2
        else:
            assert entry in changelog, 'explicit release-preparation request requires the entry'

    return compatibility, behavior


def httpx(stage):
    # Loading httpx.__init__ at this 2022 revision requires optional historical
    # dependencies unrelated to multipart parsing. Create only the package shell
    # so Python can resolve the module's real relative imports from this worktree.
    package = ModuleType('httpx'); package.__path__ = [str(Path.cwd() / 'httpx')]
    sys.modules['httpx'] = package
    from httpx._multipart import get_multipart_boundary_from_content_type as boundary

    def compatibility():
        assert boundary(None) is None
        assert boundary(b'application/json') is None
        assert boundary(b'multipart/form-data; boundary=simple') == b'simple'

    def behavior():
        assert boundary(b'multipart/form-data; BOUNDARY="AbC"') == b'AbC'
        assert boundary(b'multipart/form-data; boundary="abc-boundary=def"') == b'abc-boundary=def'
        assert boundary(b"multipart/form-data; boundary='legacy'") == b"'legacy'"
        if stage >= 2:
            assert boundary(b'multipart/form-data; boundary="Case-Sensitive_Value"') == b'Case-Sensitive_Value'
            assert boundary(b'multipart/form-data; BOUNDARY=MiXeD') == b'MiXeD'

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {'cachetools': cachetools, 'httpx': httpx}[project](stage)
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
