"""D ASGI entrypoint: D-02 master data plus health; other D subdomains pending."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from psycopg.errors import UniqueViolation

from services.common import create_app
from services.platform import install_errors
from services.d.dependencies import identity_mode
from services.d.master_data import db, router


@asynccontextmanager
async def lifespan(app):
    mode = identity_mode()
    logging.getLogger("uvicorn.error").info("D-02 identity dependency mode: %s", mode)
    if db.configured:
        db.migrate(Path(__file__).parent / "migrations")
    yield


app = create_app("d-api")
app.router.lifespan_context = lifespan
install_errors(app)
app.include_router(router)


@app.exception_handler(UniqueViolation)
async def unique_conflict(request: Request, exc: UniqueViolation):
    return JSONResponse(status_code=409, media_type="application/problem+json", content={
        "type": "about:blank", "title": "DUPLICATE_SEAT_NUMBER", "status": 409,
        "code": "DUPLICATE_SEAT_NUMBER", "detail": "Seat number already exists in this room, including retired seats",
    })


@app.middleware("http")
async def dependency_mode_header(request: Request, call_next):
    response = await call_next(request)
    try:
        mode = identity_mode()
    except Exception:
        mode = "invalid-configuration"
    response.headers["X-Identity-Mode"] = mode
    return response
