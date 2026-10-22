"""TEMPORARY-DEPENDENCY M1-D01, M1-D03, M1-D04: explicit synthetic development of M1 + D-02; no real D-01/03/04 providers.

Requires Docker, installed Python dependencies and npm dependencies. Creates a
persistent local PostgreSQL container and ignored random-credential config.
Ctrl+C stops API/Web/scheduler children but preserves the development database.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='prepare database and seeds, without starting servers')
    args = parser.parse_args()
    python = ROOT / '.venv/bin/python'
    if not python.exists():
        parser.error('Run uv sync --frozen first')
    if not (ROOT / 'apps/web/node_modules').exists():
        parser.error('Run npm --prefix apps/web ci first')
    for port in (3101, 3104, 5173):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                parser.error(f'Port {port} is already in use; existing processes were not stopped')
    config_path = ROOT / '.env.m1-development.json'
    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = {key: secrets.token_hex(32) for key in ('postgres', 'm1', 'd', 'service', 'm2', 'm3', 'checkin')}
        config_path.write_text(json.dumps(config))
        config_path.chmod(0o600)
    container = 'project1-m1-dev-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]
    found = subprocess.run(['docker', 'inspect', container], capture_output=True)
    if found.returncode:
        result = subprocess.run(['docker', 'run', '-d', '--name', container, '-e', f"POSTGRES_PASSWORD={config['postgres']}",
                                 '-e', 'POSTGRES_DB=campus', '-p', '127.0.0.1::5432', 'postgres:18-alpine'], capture_output=True)
    else:
        result = subprocess.run(['docker', 'start', container], capture_output=True)
    if result.returncode:
        raise RuntimeError('Cannot start local PostgreSQL; ensure Docker is running')
    for _ in range(100):
        if subprocess.run(['docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], capture_output=True).returncode == 0:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('PostgreSQL readiness timed out')
    port = subprocess.check_output(['docker', 'port', container, '5432/tcp'], text=True).strip().split(':')[-1]
    env = os.environ.copy()
    env.update(APP_ENV='development', M1_USE_DEV_DEPENDENCIES='1', D_USE_DEV_IDENTITY='1',
               VITE_USE_DEV_IDENTITY='true', D_BASE_URL='http://127.0.0.1:3104', D_M1_TOKEN=config['service'],
               M1_M2_TOKEN=config['m2'], M1_M3_TOKEN=config['m3'], M1_CHECKIN_SECRET=config['checkin'],
               DATABASE_ADMIN_URL=f"postgresql://postgres:{config['postgres']}@127.0.0.1:{port}/campus",
               M1_DATABASE_PASSWORD=config['m1'], D_DATABASE_PASSWORD=config['d'])
    for service in ('m1', 'd'):
        env[f'{service.upper()}_DATABASE_URL'] = f"postgresql://campus_{service}:{config[service]}@127.0.0.1:{port}/campus"
    subprocess.run([str(python), 'scripts/provision-databases.py'], cwd=ROOT, env=env, check=True)
    subprocess.run([str(python), '-m', 'services.d.seed'], cwd=ROOT, env=env, check=True)
    if args.prepare_only:
        print('Prepared synthetic development data; persistent container:', container)
        return
    commands = [
        [str(python), '-m', 'uvicorn', 'services.d.main:app', '--host', '127.0.0.1', '--port', '3104'],
        [str(python), '-m', 'uvicorn', 'services.m1.main:app', '--host', '127.0.0.1', '--port', '3101'],
        [str(python), '-m', 'services.m1.scheduler'],
        ['npm', '--prefix', 'apps/web', 'run', 'dev', '--', '--host', '127.0.0.1', '--strictPort'],
    ]
    children = []
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True))
        print('Development substitutes ENABLED: synthetic identity and simulated notification/audit. D-02 and M1 use real PostgreSQL + HTTP.', flush=True)
        print('Web: http://127.0.0.1:5173 — select a synthetic identity on the login page. Ctrl+C stops this run.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.3)
        raise RuntimeError('A development service exited; stopping the others')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        print('Services stopped; development database preserved in', container)


if __name__ == '__main__':
    main()
