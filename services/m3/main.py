"""M3 API. Default configuration exposes health/context and rejects business use."""
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from fastapi import Body, Depends, FastAPI, Header, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from .database import Database
from .dev_dependencies import DevelopmentDirectory
from .http_directory import DirectoryFailure, HttpDirectory, valid_base_url
from .m1_client import M1Client
from .ports import UnavailableDirectory
from .service import DomainError, WorkOrderService, utcnow
from .settings import Settings
from .worker import Worker

Text = Annotated[str, Field(min_length=1, max_length=2000)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class CreateBody(StrictBody):
    roomId: Annotated[str, Field(min_length=1, max_length=128)]
    category: Literal["facilities", "electrical", "environment", "other"]
    title: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=4000)]


class ActionBody(StrictBody):
    version: Annotated[int, Field(ge=1)]


class AssignBody(ActionBody):
    assigneeId: Annotated[str, Field(min_length=1, max_length=128)]
    note: Annotated[str, Field(max_length=2000)] = ""


class NoteBody(ActionBody):
    note: Text


class AcceptBody(ActionBody):
    note: Annotated[str, Field(max_length=2000)] = ""


class RateBody(ActionBody):
    score: Annotated[int, Field(ge=1, le=5)]
    comment: Annotated[str, Field(max_length=2000)] = ""


ACTION_MODELS = {"assign": AssignBody, "start": ActionBody, "complete": NoteBody,
                 "accept": AcceptBody, "reject": NoteBody, "cancel": NoteBody,
                 "rate": RateBody, "retry-sync": ActionBody}


def create_app(settings=None, *, directory=None, db=None, clock=utcnow, m1_client=None):
    settings = settings or Settings.from_env()
    if directory is None:
        directory = (DevelopmentDirectory() if settings.directory_mode == "development" else
                     HttpDirectory(settings.identity_base_url, settings.d_base_url, settings.directory_timeout_seconds)
                     if settings.directory_mode == "http" else UnavailableDirectory())
    ready = not isinstance(directory, UnavailableDirectory)
    if isinstance(directory, HttpDirectory):
        ready = directory.configured
    if settings.mode == "production":
        if ready and not isinstance(directory, HttpDirectory):
            raise ValueError("Production requires the real HTTP directory adapter")
        ready = (ready and settings.directory_mode == "http" and bool(settings.database_url) and valid_base_url(settings.m1_base_url)
                 and bool(settings.m1_token) and all(33 <= ord(c) <= 126 for c in settings.m1_token))
    owned_db = db is None
    service, worker = None, None
    if ready:
        if db is None:
            if not settings.database_url:
                raise ValueError("M3_DATABASE_URL is required for business operations")
            db = Database(settings.database_url)
        if settings.mode == "production" and db.engine.dialect.name != "postgresql":
            raise ValueError("Production requires PostgreSQL")
        db.migrate()
        service = WorkOrderService(db, directory, settings, clock)
        if settings.mode == "production":
            service.assert_production_data()
        client = m1_client or M1Client(settings.m1_base_url, settings.m1_token, settings.m1_timeout_seconds)
        worker = Worker(service, client)

    @asynccontextmanager
    async def lifespan(app):
        if worker and settings.worker_enabled:
            worker.start()
        yield
        if worker:
            worker.stop()
        if ready and owned_db and db:
            db.close()

    app = FastAPI(title="M3 Repair Work Orders", version="1.0.0", lifespan=lifespan)
    app.state.service, app.state.worker, app.state.db = service, worker, db
    app.state.settings, app.state.directory = settings, directory

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(DirectoryFailure)
    async def directory_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "INVALID_INPUT", "message": "请求字段缺失、类型错误或超过长度限制"}}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse({"error": {"code": "STORAGE_UNAVAILABLE", "message": "工单存储暂不可用，请稍后重试"}}, status_code=503)

    def identity(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
            raise DomainError("UNAUTHENTICATED", "请先提供有效身份", 401)
        if not ready:
            raise DomainError("DEPENDENCY_UNAVAILABLE", "正式身份与房间目录尚未接入，业务暂不可用", 503)
        actor = directory.authenticate(authorization[7:])
        if actor is None:
            raise DomainError("UNAUTHENTICATED", "身份无效或已过期", 401)
        if actor.role not in {"reporter", "admin", "technician"}:
            raise DomainError("FORBIDDEN", "此身份无权使用报修模块", 403)
        return actor

    @app.get("/healthz")
    def health():
        return {"service": "m3-api", "status": "ok"}

    @app.get("/api/m3/v1/context")
    def context():
        return {"mode": settings.mode, "directoryMode": settings.directory_mode,
                "m1Mode": settings.m1_mode, "businessReady": ready,
                "demoIdentities": directory.demo_identities() if ready and isinstance(directory, DevelopmentDirectory) else []}

    @app.get("/api/m3/v1/me")
    def me(actor=Depends(identity)):
        return actor.public()

    @app.get("/api/m3/v1/rooms")
    def rooms(actor=Depends(identity)):
        return {"items": directory.rooms(actor)}

    @app.get("/api/m3/v1/technicians")
    def technicians(actor=Depends(identity)):
        if not actor.can("dispatch"):
            raise DomainError("FORBIDDEN", "仅管理员可查看维修人员目录", 403)
        return {"items": [t.public() for t in directory.technicians(actor)]}

    @app.get("/api/m3/v1/work-orders")
    def list_orders(
        status: Literal["SUBMITTED", "ASSIGNED", "BLOCK_PENDING", "IN_PROGRESS", "PENDING_ACCEPTANCE", "RELEASE_PENDING", "CLOSED", "CANCELLED"] | None = None,
        roomId: Annotated[str | None, Query(max_length=128)] = None,
        view: Literal["all", "mine", "assigned", "acceptance", "overdue"] = "all",
        q: Annotated[str, Query(max_length=200)] = "", actor=Depends(identity)
    ):
        return {"items": service.list(actor, status, roomId, view, q.strip())}

    @app.post("/api/m3/v1/work-orders")
    def create_order(payload: CreateBody, response: Response,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
        actor=Depends(identity)
    ):
        key = idempotency_key.strip()
        if not key or not all(32 <= ord(char) <= 126 for char in key):
            raise DomainError("INVALID_IDEMPOTENCY_KEY", "幂等键必须为非空可打印 ASCII 字符", 422)
        order, created = service.create(actor, payload.model_dump(), key)
        response.status_code = 201 if created else 200
        return order

    @app.get("/api/m3/v1/work-orders/{order_id}")
    def get_order(order_id: str, actor=Depends(identity)):
        return service.get(order_id, actor)

    @app.post("/api/m3/v1/work-orders/{order_id}/{action}")
    def action_order(order_id: str, action: str, payload: Annotated[dict, Body()], actor=Depends(identity)):
        model = ACTION_MODELS.get(action)
        if model is None:
            raise DomainError("NOT_FOUND", "工单操作不存在", 404)
        try:
            valid = model.model_validate(payload)
        except ValidationError:
            raise DomainError("INVALID_INPUT", "操作字段缺失、类型错误或超过长度限制", 422) from None
        return service.act(order_id, action, actor, valid.model_dump())

    return app


app = create_app()
