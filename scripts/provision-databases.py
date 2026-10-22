"""Provision isolated service roles/schemas using an explicit database admin URL.

Credentials come from the environment and are never printed. Re-running updates
passwords and ensures the two owners have no privileges on each other's schema.
This script provisions no business rows. Run migrations as the service owners.
"""
import os
import psycopg
from psycopg import sql


def provision():
    with psycopg.connect(os.environ['DATABASE_ADMIN_URL'], autocommit=True) as conn:
        conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        for name in ('m1', 'd'):
            role = f'campus_{name}'
            password = os.environ[f'{name.upper()}_DATABASE_PASSWORD']
            if len(password) < 16:
                raise ValueError('Service database passwords must have at least 16 characters')
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
            conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))
            conn.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}').format(sql.Identifier(name), sql.Identifier(role)))
            conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(name)))
            other = 'campus_d' if name == 'm1' else 'campus_m1'
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (other,)).fetchone():
                conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM {}').format(sql.Identifier(name), sql.Identifier(other)))
            conn.execute(sql.SQL('ALTER ROLE {} SET search_path TO {}').format(sql.Identifier(role), sql.Identifier(name)))
    print('Provisioned isolated M1 and D schemas; credentials omitted.')

if __name__ == '__main__':
    provision()
