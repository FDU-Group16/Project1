"""Apply versioned M3 migrations: python -m services.m3.migrate."""

import os

from .database import Database


def main():
    url = os.environ.get('M3_DATABASE_URL')
    if not url:
        raise SystemExit('Set M3_DATABASE_URL to the M3-owned database')
    db = Database(url, allow_sqlite=os.environ.get('M3_MODE') == 'development')
    try:
        db.migrate()
        db.check_schema()
        print('M3 migration 0001 applied and verified (idempotent).')
    finally:
        db.close()


if __name__ == '__main__':
    main()
