"""Process-level HTTP shell shared by the four services."""

from fastapi import FastAPI


def create_app(service_name: str) -> FastAPI:
    app = FastAPI(title=service_name, version="0.1.0")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"service": service_name, "status": "ok"}

    return app
