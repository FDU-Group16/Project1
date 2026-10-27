"""TEMPORARY-DEPENDENCY M3-D-DEV: explicit, idempotent synthetic demo orders.

This is separate from Alembic and never runs automatically during deployment.
"""
from .database import Database
from .dev_dependencies import DevelopmentDirectory
from .service import WorkOrderService
from .settings import Settings


def seed(service):
    if service.settings.mode != "development" or not isinstance(service.directory, DevelopmentDirectory):
        raise ValueError("Synthetic seeds require explicit development mode and directory")
    reporter = service.directory.authenticate("demo-reporter")
    fixtures = [
        ("lamp", {"roomId": "room-101", "category": "electrical", "title": "靠窗阅读灯不亮",
                  "description": "开发演示数据：第一排靠窗阅读灯无法点亮，请检查。"}),
        ("chair", {"roomId": "room-202", "category": "facilities", "title": "座椅靠背松动",
                   "description": "开发演示数据：第二排座椅靠背松动，请安排检修。"}),
    ]
    return [service.create(reporter, payload, f"m3-development-seed-v1:{key}")
            for key, payload in fixtures]


def main():
    settings = Settings.from_env()
    if settings.mode != "development" or settings.directory_mode != "development" or not settings.database_url:
        raise SystemExit("Set M3_MODE=development, M3_DIRECTORY_MODE=development and M3_DATABASE_URL; run migrate first")
    db = Database(settings.database_url)
    try:
        result = seed(WorkOrderService(db, DevelopmentDirectory(), settings))
        print(f"Synthetic M3 seeds: {sum(created for _, created in result)} created; {len(result)} present")
    finally:
        db.close()


if __name__ == "__main__":
    main()
