"""Behavior checks for the web-disabled, filesystem-isolated v4 held-out set."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from heldout_v3_checker import flask_check, packaging_check


def tqdm_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from tqdm.contrib.concurrent import _min_map_len

    def compatibility():
        assert _min_map_len([range(9), range(5)]) == 5
        assert _min_map_len([range(0)]) == 0

    def behavior():
        assert _min_map_len([]) == 0
        assert _min_map_len([(value for value in range(9))]) == 0
        if stage >= 2:
            assert _min_map_len([(value for value in range(9)), range(5)]) == 5

    return compatibility, behavior


class _Timer:
    def __init__(self, timers):
        self.timers = timers
        timers.append(self)

    def cancel(self):
        if self in self.timers:
            self.timers.remove(self)


class _Task:
    def add_done_callback(self, callback):
        return None


class _Loop:
    def __init__(self):
        self.tasks = []
        self.timers = []

    def create_task(self, coroutine):
        self.tasks.insert(0, coroutine)
        return _Task()

    def call_later(self, delay, callback, *args):
        return _Timer(self.timers)

    async def run_one(self):
        return await self.tasks.pop()


class _Transport:
    def __init__(self):
        self.closed = False
        self.buffer = b''
        self.protocol = None

    def get_extra_info(self, key):
        return {'sockname': ('127.0.0.1', 8000),
                'peername': ('127.0.0.1', 8001), 'sslcontext': False}.get(key)

    def write(self, data):
        self.buffer += data

    def close(self):
        self.closed = True

    def pause_reading(self):
        return None

    def resume_reading(self):
        return None

    def is_closing(self):
        return self.closed

    def set_protocol(self, protocol):
        self.protocol = protocol


class _WebSocket:
    def __init__(self, **kwargs):
        pass

    def connection_made(self, transport):
        pass

    def data_received(self, data):
        pass


def uvicorn_check(stage):
    sys.path.insert(0, str(Path.cwd()))
    from tests.response import Response
    from uvicorn.config import Config
    from uvicorn.lifespan.off import LifespanOff
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.server import ServerState

    simple = b'GET / HTTP/1.1\r\nHost: example.org\r\n\r\n'
    upgrade = (b'GET / HTTP/1.1\r\nHost: example.org\r\nConnection: upgrade\r\n'
               b'Upgrade: websocket\r\nSec-WebSocket-Version: 11\r\n\r\n')

    def protocol():
        loop = _Loop()
        transport = _Transport()
        config = Config(app=Response('ok'), ws=_WebSocket, access_log=False, log_level='critical')
        instance = H11Protocol(config, ServerState(), LifespanOff(config).state, _loop=loop)
        instance.connection_made(transport)
        return instance, loop

    async def ordinary_request():
        instance, loop = protocol()
        instance.data_received(simple)
        await loop.run_one()
        assert instance.timeout_keep_alive_task is not None

    async def pipelined_upgrade():
        instance, loop = protocol()
        instance.data_received(simple + upgrade)
        await loop.run_one()
        assert instance.timeout_keep_alive_task is None

    async def pipelined_http():
        instance, loop = protocol()
        instance.data_received(simple + simple)
        await loop.run_one()
        assert instance.timeout_keep_alive_task is None
        await loop.run_one()
        assert instance.timeout_keep_alive_task is not None

    def compatibility():
        asyncio.run(ordinary_request())

    def behavior():
        asyncio.run(pipelined_upgrade())
        if stage >= 2:
            asyncio.run(pipelined_http())

    return compatibility, behavior


def check(project, stage):
    compatibility, behavior = {
        'packaging': packaging_check,
        'flask': flask_check,
        'tqdm': tqdm_check,
        'uvicorn': uvicorn_check,
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
        raise SystemExit('usage: heldout_v4_checker.py PROJECT STAGE')
    observed = check(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(observed))
    raise SystemExit(2 if not observed['compatibility']['pass'] else
                     0 if observed['behavior']['pass'] else 1)
