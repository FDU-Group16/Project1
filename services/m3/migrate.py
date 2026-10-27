from .database import Database
from .settings import Settings


def main():
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("M3_DATABASE_URL is required")
    db = Database(settings.database_url)
    try:
        db.migrate()
    finally:
        db.close()


if __name__ == "__main__":
    main()
