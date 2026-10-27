"""M3 ASGI entry point. Default startup remains fail-closed without D."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from .database import Database
from .m1_client import HttpBlockGateway
from .models import (Actor, Assign, Command, Complete, Context, CreateOrder, DirectoryList,
                     OrderList, Problem, Rate, Reason, WorkOrder)
from .ports import UnavailableDirectory, UnavailableGateway
from .service import WorkOrders
from .settings import Settings
from .worker import Worker

PREFIX = '/api/m3/v1'
bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = None
        worker = None
        application.state.directory = UnavailableDirectory()
        application.state.service = None
        # Production D integration remains unavailable. In particular, never
        # run a stub or process an old development database in normal mode.
        if config.mode == 'development':
            from .dev_dependencies import DevelopmentDirectory, DevelopmentGateway
            application.state.directory = DevelopmentDirectory()
            if config.database_url:
                database = Database(config.database_url, allow_sqlite=True)
                database.migrate()
                service = WorkOrders(database, application.state.directory,
                    assignment_hours=config.assignment_hours, repair_hours=config.repair_hours)
                if config.m1_mode == 'stub':
                    gateway = DevelopmentGateway()
                elif config.m1_mode == 'http':
                    gateway = HttpBlockGateway(config.m1_url, config.m1_token)
                else:
                    gateway = UnavailableGateway()
                application.state.service = service
                worker = Worker(service, gateway, interval=config.worker_interval)
                worker.start()
        try:
            yield
        finally:
            if worker:
                worker.stop()
            if database:
                database.close()

    application = FastAPI(title='M3 物业报修工单', version='0.1.0-proposed', lifespan=lifespan,
        description='M3 业务接口；角色、SLA 和 D 接入仍待组内评审。开发替身不表示真实跨模块联调。')

    @application.exception_handler(Problem)
    async def problem_handler(request: Request, error: Problem):
        return JSONResponse(status_code=error.status,
                            content={'code': error.code, 'detail': error.detail})

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, error: SQLAlchemyError):
        # SQLAlchemy exceptions can contain query parameters/report text.
        # Do not expose them in responses or application logs.
        return JSONResponse(status_code=503, content={
            'code': 'STORAGE_UNAVAILABLE', 'detail': '工单存储暂不可用，请稍后重试。'})

    @application.get('/healthz', include_in_schema=False)
    def healthz():
        return {'service': 'm3-api', 'status': 'ok'}

    @application.get(PREFIX + '/context', response_model=Context)
    def context():
        active = config.mode == 'development' and bool(config.database_url)
        message = ('开发环境：身份和房间为合成数据；M1 写回为模拟回执，未验证真实座位状态。'
                   if active and config.m1_mode == 'stub' else
                   '开发环境：身份和房间为合成数据；M1 通过配置的 HTTP 接口同步。'
                   if active and config.m1_mode == 'http' else
                   '开发环境：身份和房间为合成数据；M1 未配置，维修与验收将等待联动。'
                   if active else
                   '公共身份与空间目录尚未接入，业务服务暂不可用。')
        return Context(mode=config.mode, dependencyMode=config.m1_mode if active else 'unavailable',
                       message=message)

    def actor(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Actor:
        if credentials is None or credentials.scheme.lower() != 'bearer':
            raise Problem(401, 'AUTHENTICATION_REQUIRED', '请先登录。')
        return request.app.state.directory.authenticate(credentials.credentials)

    def service(request: Request) -> WorkOrders:
        result = request.app.state.service
        if result is None:
            raise Problem(503, 'SERVICE_UNAVAILABLE', 'M3 数据库或公共身份依赖尚未配置。')
        return result

    ActorDependency = Annotated[Actor, Depends(actor)]
    ServiceDependency = Annotated[WorkOrders, Depends(service)]

    @application.get(PREFIX + '/me', response_model=Actor)
    def me(user: ActorDependency):
        return user

    @application.get(PREFIX + '/rooms', response_model=DirectoryList)
    def rooms(request: Request, user: ActorDependency):
        return {'items': request.app.state.directory.rooms(user)}

    @application.get(PREFIX + '/technicians', response_model=DirectoryList)
    def technicians(request: Request, user: ActorDependency, orders: ServiceDependency):
        orders.require_dispatcher(user)
        return {'items': request.app.state.directory.technicians()}

    @application.post(PREFIX + '/work-orders', response_model=WorkOrder, status_code=201)
    def create_order(body: CreateOrder, user: ActorDependency, orders: ServiceDependency,
                     idempotency_key: Annotated[str, Header(alias='Idempotency-Key')]):
        return orders.create(user, body, idempotency_key)

    @application.get(PREFIX + '/work-orders', response_model=OrderList)
    def list_orders(user: ActorDependency, orders: ServiceDependency):
        return {'items': orders.list(user)}

    @application.get(PREFIX + '/work-orders/{order_id}', response_model=WorkOrder)
    def get_order(order_id: str, user: ActorDependency, orders: ServiceDependency):
        return orders.get(user, order_id)

    @application.post(PREFIX + '/work-orders/{order_id}/assign', response_model=WorkOrder)
    def assign(order_id: str, body: Assign, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'assign', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/start', response_model=WorkOrder)
    def start(order_id: str, body: Command, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'start', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/complete', response_model=WorkOrder)
    def complete(order_id: str, body: Complete, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'complete', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/accept', response_model=WorkOrder)
    def accept(order_id: str, body: Command, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'accept', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/reject', response_model=WorkOrder)
    def reject(order_id: str, body: Reason, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'reject', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/cancel', response_model=WorkOrder)
    def cancel(order_id: str, body: Reason, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'cancel', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/rate', response_model=WorkOrder)
    def rate(order_id: str, body: Rate, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'rate', body.model_dump())

    @application.post(PREFIX + '/work-orders/{order_id}/retry-sync', response_model=WorkOrder)
    def retry(order_id: str, body: Reason, user: ActorDependency, orders: ServiceDependency):
        return orders.command(user, order_id, 'retry-sync', body.model_dump())

    return application


app = create_app()
