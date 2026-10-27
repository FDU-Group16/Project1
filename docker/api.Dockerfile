FROM ghcr.io/astral-sh/uv:0.10.0 AS uv

FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /workspace

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services ./services
COPY scripts/start-api.sh ./start-api.sh

ENV PATH="/workspace/.venv/bin:$PATH"
CMD ["sh", "/workspace/start-api.sh"]
