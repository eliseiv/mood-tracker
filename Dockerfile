# syntax=docker/dockerfile:1

############################
# Stage 1 — builder
############################
FROM python:3.12-slim AS builder

# Pinned uv, matching the version that produced uv.lock (revision 3).
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /usr/local/bin/

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install prod dependencies only (asyncpg + redis via --extra prod), without the
# project source — better layer caching, source changes don't re-resolve deps.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra prod --no-install-project --no-dev

############################
# Stage 2 — runtime
############################
FROM python:3.12-slim AS runtime

# Non-root system user/group.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Virtualenv with all prod dependencies from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Application source (no secrets baked in — see .dockerignore).
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY pyproject.toml uv.lock ./
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
