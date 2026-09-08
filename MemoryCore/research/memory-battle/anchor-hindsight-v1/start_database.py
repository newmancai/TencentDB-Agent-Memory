"""Isolated PostgreSQL using the already cached, previously verified compatible image."""
import argparse
import json
import ipaddress
import os
import shlex
import subprocess
import tempfile
import importlib.util
from pathlib import Path


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--name', default='anchor-hindsight-runtime-20260908')
    p.add_argument('--port', type=int, default=65438)
    p.add_argument('--pg0-binary', type=Path, help='Defaults to the pg0 installed in this Python environment')
    p.add_argument('--image', default='nvidia/cuda:12.9.1-devel-ubuntu22.04', help='An already cached compatible image; no GPU is requested')
    a = p.parse_args()
    if a.pg0_binary:
        binary = a.pg0_binary.resolve()
    else:
        spec = importlib.util.find_spec('pg0')
        if spec is None or not spec.submodule_search_locations:
            p.error('pg0 is not installed; use its Python environment or --pg0-binary')
        binary = Path(next(iter(spec.submodule_search_locations))) / 'bin/pg0'
    if not binary.is_file():p.error(f'pg0 binary missing: {binary}')
    image = a.image
    root = Path(tempfile.mkdtemp(prefix='anchor-hindsight-db-'))
    container = run('docker', 'run', '--pull=never', '--init', '--rm', '-d', '--name', a.name,
                    '-p', f'127.0.0.1:{a.port}:5432', '-v', f'{root}:/data',
                    '-v', f'{binary}:/pg0:ro', '-v', '/usr/share/zoneinfo:/usr/share/zoneinfo:ro',
                    '--entrypoint', '/bin/sleep', image, 'infinity')
    try:
        # This user and its home exist only inside the disposable container.
        run('docker', 'exec', a.name, 'useradd', '--create-home', '--uid', str(os.getuid()), 'hindsight')
        run('docker', 'exec', a.name, 'chown', 'hindsight:hindsight', '/data')
        command = shlex.join(['/pg0', 'start', '--name', a.name, '--data-dir', '/data/db',
                             '--port', '5432', '--username', 'hindsight', '--password', 'hindsight',
                             '--database', 'hindsight', '--config', 'listen_addresses=*'])
        output = run('docker', 'exec', a.name, 'runuser', '-l', 'hindsight', '-c', command)
        gateway = run('docker', 'inspect', '--format', '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}', a.name)
        gateway = str(ipaddress.ip_address(gateway))
        subprocess.run(['docker', 'exec', '-i', a.name, 'tee', '-a', '/data/db/pg_hba.conf'],
                       input=f'\nhost hindsight hindsight {gateway}/32 scram-sha-256\n', text=True,
                       check=True, stdout=subprocess.DEVNULL)
        pid = int(run('docker', 'exec', a.name, 'head', '-1', '/data/db/postmaster.pid'))
        run('docker', 'exec', a.name, 'kill', '-HUP', str(pid))
        a.manifest.parent.mkdir(parents=True, exist_ok=True)
        a.manifest.write_text(json.dumps(dict(container_id=container, name=a.name, host='127.0.0.1',
            port=a.port, data_dir=str(root), image=image, newly_created_directory=True,
            startup_output=output, gpu_requested=False), indent=2) + '\n')
        print(json.dumps(dict(name=a.name, port=a.port, data_dir=str(root), manifest=str(a.manifest))))
    except BaseException:
        subprocess.run(['docker', 'exec', a.name, 'cat', '/data/db/start.log'], check=False)
        subprocess.run(['docker', 'stop', a.name], check=False, stdout=subprocess.DEVNULL)
        raise


if __name__ == '__main__':
    main()
