"""Application assembly: middleware, routers, error handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import DeviceIdMiddleware, SecurityHeadersMiddleware
from app.api.v1.router import api_v1_router
from app.api.v1.routes import health
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import build_rate_limiter

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared resources (rate limiter) on startup."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("app_startup", environment=settings.environment)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    # get_settings() runs the fail-closed prod guard (ADR-009): with APP_ENV=prod
    # and an empty API_KEY it raises here, before the app starts serving traffic.
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.api_key:
        # Reached only when APP_ENV=local (prod is blocked by the guard above).
        logger.warning("app_level_api_key_auth_disabled", app_env=settings.app_env)

    app = FastAPI(title="Mood Tracker API", version="1.0.0", lifespan=lifespan)
    app.state.rate_limiter = build_rate_limiter(settings)

    # Middleware (outermost first). CORS wraps everything; security headers and
    # device-id validation run for each request.
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(DeviceIdMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_v1_router)
    return app


app = create_app()
