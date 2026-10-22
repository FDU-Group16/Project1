"""M1 ASGI entrypoint with isolated persistence and explicit external dependencies."""
from contextlib import asynccontextmanager
from services.common import create_app
from services.platform import install_errors
from services.m1 import core,dependencies,search,reservations,checkin,history


@asynccontextmanager
async def lifespan(app):
    if core.DB.configured:
        core.migrate()
    yield


app=create_app('m1-api')
app.router.lifespan_context=lifespan
install_errors(app)
for router in (search.router,reservations.router,checkin.router,history.router):
    app.include_router(router)


@app.middleware('http')
async def dependency_header(request,call_next):
    response=await call_next(request)
    try:
        response.headers['X-Dependency-Mode']=dependencies.dependency_mode()
    except Exception:
        response.headers['X-Dependency-Mode']='invalid-configuration'
    return response
