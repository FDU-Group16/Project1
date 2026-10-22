"""M1 ASGI entrypoint. Business routes are not implemented yet."""

from services.common import create_app

app = create_app("m1-api")
