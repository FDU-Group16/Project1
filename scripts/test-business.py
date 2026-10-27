"""Run behavior tests against an isolated real PostgreSQL, never a production DB.

Default: create and remove a Docker container with random credentials and a
loopback-only random port. --external requires explicit TEST_* database URLs.
"""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, text=True)
    if result.returncode:
        # Never include command arguments: they can carry ephemeral passwords.
        raise RuntimeError('Docker test database command failed. Ensure Docker is running and postgres:18-alpine is available.')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--external', action='store_true')
    args = parser.parse_args()
    env = os.environ.copy()
    container = None
    try:
        if args.external:
            for service in ('M1', 'D', 'M3'):
                env[f'{service}_DATABASE_URL'] = env[f'TEST_{service}_DATABASE_URL']
        else:
            container = 'project1-check-' + secrets.token_hex(6)
            secret, m1_password, d_password, m3_password = [secrets.token_hex(24) for _ in range(4)]
            docker('run', '--rm', '-d', '--name', container, '-e', f'POSTGRES_PASSWORD={secret}',
                   '-e', 'POSTGRES_DB=campus_test', '-p', '127.0.0.1::5432', 'postgres:18-alpine')
            for _ in range(100):
                ready = subprocess.run(['docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], capture_output=True)
                if ready.returncode == 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('PostgreSQL did not become ready')
            port = docker('port', container, '5432/tcp').split(':')[-1]
            env.update(DATABASE_ADMIN_URL=f'postgresql://postgres:{secret}@127.0.0.1:{port}/campus_test',
                       M1_DATABASE_PASSWORD=m1_password, D_DATABASE_PASSWORD=d_password, M3_DATABASE_PASSWORD=m3_password)
            for service, password in (('M1', m1_password), ('D', d_password), ('M3', m3_password)):
                url = f'postgresql://campus_{service.lower()}:{password}@127.0.0.1:{port}/campus_test'
                env[f'{service}_DATABASE_URL'] = env[f'TEST_{service}_DATABASE_URL'] = url
            subprocess.run([sys.executable, 'scripts/provision-databases.py'], cwd=ROOT, env=env, check=True)
        env.update(APP_ENV='test', M1_USE_DEV_DEPENDENCIES='1', D_USE_DEV_IDENTITY='1')
        for key in ('D_M1_TOKEN', 'M1_M2_TOKEN', 'M1_M3_TOKEN', 'M1_CHECKIN_SECRET'):
            env[key] = secrets.token_hex(32)
        integration = ROOT / 'scripts' / 'test-m1-d-integration.py'
        if integration.exists():
            subprocess.run([sys.executable, str(integration)], cwd=ROOT, env=env, check=True)
        for service in ('d', 'm1'):
            suite = ROOT / 'services' / service / 'tests'
            if not list(suite.glob('test_*.py')):
                raise RuntimeError(f'No behavior tests found for {service}')
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(suite), '-v'], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, 'scripts/test-mutations.py'], cwd=ROOT, env=env, check=True)
        # The dedicated schemas are tested sequentially; M3 fixtures clear only
        # their own disposable test rows. No consumer writes another schema.
        env.update(M3_TEST_DATABASE_URL=env['TEST_M3_DATABASE_URL'], M3_REQUIRE_POSTGRES='1', M3_REQUIRE_SCHEMA_OWNER='1', M3_TEST_ALLOW_RESET='1')
        subprocess.run([sys.executable, 'services/m3/tests/integration_real_providers.py'], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, 'services/m3/tests/test_accounts_integration.py'], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, '-m', 'pytest', 'services/m3/tests', '-q'], cwd=ROOT, env=env, check=True)
    finally:
        if container:
            subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
