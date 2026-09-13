"""External checks for the frozen four-project held-out route evaluation."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys


def source_text(path):
    text = (Path.cwd() / path).read_text()
    ast.parse(text)
    return text


def click(stage):
    text = source_text('src/click/testing.py')

    def compatibility():
        assert 'class _FDCapture:' in text
        assert 'CaptureMode: t.TypeAlias' in text

    def behavior():
        if stage == 1:
            assert 'ExceptionInfo: t.TypeAlias' in text
            assert '_ExceptionInfo: t.TypeAlias' not in text
            assert 'exc_info: ExceptionInfo | None' in text
        else:
            assert '_ExceptionInfo: t.TypeAlias' in text
            assert re.search(r'(?<!_)ExceptionInfo: t\.TypeAlias', text) is None
            assert 'exc_info: _ExceptionInfo | None' in text

    return compatibility, behavior


def httpcore(stage):
    text = (Path.cwd() / '.github/workflows/test-suite.yml').read_text()
    match = re.search(r'python-version:\s*\[([^\]]+)]', text)
    versions = [] if match is None else [item.strip().strip('"\'') for item in match.group(1).split(',')]

    def compatibility():
        assert 'actions/setup-python' in text
        assert all(value in versions for value in ['3.8', '3.9', '3.10', '3.11', '3.12', '3.14'])

    def behavior():
        if stage == 1:
            assert '3.13' in versions and '3.x' not in versions
        else:
            assert '3.x' in versions and '3.13' not in versions

    return compatibility, behavior


def attrs(stage):
    text = source_text('tests/test_validators.py')

    def compatibility():
        assert 'class TestMatchesRe:' in text
        assert "'func' must be one of None, fullmatch, match, search." in text

    def behavior():
        assert 'fullmatch, prefixmatch, search.' in text
        if stage == 1:
            assert 'if sys.version_info >= (3, 15):' in text
            assert "(3, 15, 0, 'alpha', 7)" not in text
        else:
            assert "if sys.version_info >= (3, 15, 0, 'alpha', 7):" in text

    return compatibility, behavior


def markupsafe(stage):
    text = (Path.cwd() / 'pyproject.toml').read_text()
    classifiers = re.findall(r'^\s*"([^"]+)",?\s*$', text, re.MULTILINE)
    free_threading = [value for value in classifiers if 'Free Threading' in value]

    def compatibility():
        assert re.search(r'^name\s*=\s*"MarkupSafe"$', text, re.MULTILINE)
        assert 'Typing :: Typed' in classifiers

    def behavior():
        if stage == 1:
            assert free_threading == []
        else:
            assert free_threading == ['Programming Language :: Python :: Free Threading :: 3 - Stable']

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'click': click,
        'httpcore': httpcore,
        'attrs': attrs,
        'markupsafe': markupsafe,
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
