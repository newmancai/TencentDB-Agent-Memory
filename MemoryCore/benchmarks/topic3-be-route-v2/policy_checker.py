"""Check maintainer-selected policy decisions that code alone does not determine."""
from __future__ import annotations

from base64 import b64encode
import hashlib
import json
from pathlib import Path
import re
import sys


def httpcore(stage):
    text = (Path.cwd() / 'pyproject.toml').read_text()
    dependencies = re.findall(r'^\s*"(h11[^"]*)",?\s*$', text, re.MULTILINE)

    def compatibility():
        assert re.search(r'^name = "httpcore"$', text, re.MULTILINE)
        assert re.search(r'^\s*"certifi",?\s*$', text, re.MULTILINE)
        assert len(dependencies) == 1

    def behavior():
        expected = 'h11>=0.16' if stage == 1 else 'h11>=0.15.1'
        assert dependencies == [expected]

    return compatibility, behavior


def werkzeug(stage):
    sys.path.insert(0, str(Path.cwd() / 'src'))
    from werkzeug.http import generate_etag

    def compatibility():
        assert generate_etag(b'')
        assert generate_etag(b'a') == generate_etag(b'a')
        assert generate_etag(b'a') != generate_etag(b'b')

    def behavior():
        digest = hashlib.sha3_256(b'Hello World', usedforsecurity=False).digest()
        padded = b64encode(digest).decode()
        expected = padded.rstrip('=') if stage == 1 else padded
        assert generate_etag(b'Hello World') == expected
        assert len(expected) == (43 if stage == 1 else 44)

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {'httpcore': httpcore, 'werkzeug': werkzeug}[project](stage)
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
