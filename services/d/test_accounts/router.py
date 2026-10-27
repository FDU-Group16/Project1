"""Optional existing-contract routes. Disabled by default at app assembly."""
from typing import Annotated
from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from . import enabled
from .service import TestAccountService


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: Annotated[str, Field(min_length=1, max_length=100)]
    password: Annotated[str, Field(min_length=1, max_length=200)]


def install(app, database, *, clock=None):
    if not enabled():
        return None
    service = TestAccountService(database, **({"clock": clock} if clock else {}))
    router = APIRouter()

    @router.get("/api/v1/auth/context")
    def context():
        return {"mode": "test-accounts"}

    @router.post("/api/v1/auth/login")
    def login(body: LoginBody):
        return service.login(body.username, body.password)

    @router.get("/api/v1/auth/me")
    def current(authorization: Annotated[str | None, Header()] = None):
        return service.current(authorization)

    @router.post("/api/v1/auth/logout", status_code=204)
    def logout(authorization: Annotated[str | None, Header()] = None):
        service.logout(authorization)
        return Response(status_code=204)

    @router.get("/api/v1/repair-technicians")
    def technicians(authorization: Annotated[str | None, Header()] = None):
        return service.technicians(authorization)

    @app.middleware("http")
    async def no_cache_test_identity(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/auth/") or request.url.path == "/api/v1/repair-technicians":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Identity-Mode"] = "test-accounts"
        return response

    app.include_router(router)
    app.state.test_accounts = service
    return service
