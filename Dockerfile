FROM python:3.12-slim AS build

# Pinned to the uv version that produced uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
# Dependencies first, so code changes do not invalidate this layer.
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable


# The runtime image carries only the virtualenv: no uv, no build cache.
FROM python:3.12-slim

RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
COPY --from=build --chown=app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    CACHE_SERVICE_DATABASE_URL="sqlite:////data/cache.db"
USER app
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "caching_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
