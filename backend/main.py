"""FastAPI application entrypoint for SettleSense.

Phase 4 surface: /health + the batch API (create validated batches, inspect,
page results/exceptions). Reconciliation is NOT wired to a route yet — batch
creation never claims a reconciled state.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import Database
from backend.routes import ai, batches, cash, export, reconcile, trace
from backend.schemas import HealthResponse
from backend.settings import service_settings

SERVICE_NAME = "settlesense-backend"
SERVICE_VERSION = "0.7.0"


def create_app() -> FastAPI:
    """Application factory keeps tests independent of import-time state."""
    settings = service_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Schema is initialized exactly once per process (M2); request paths
        # open connections with init=False. Settings are read at STARTUP so
        # env overrides (e.g. tests pointing at an isolated DB file) apply.
        conn = Database(service_settings().database_path).connect(init=True)
        conn.close()
        yield

    app = FastAPI(
        title="SettleSense API",
        description="Finance-operations reconciliation service "
        "(deterministic engine; AI layer planned for a later phase).",
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )

    # Dev convenience only; the dashboard calls same-origin relative URLs in
    # hosted deployments. A wildcard allowlist outside local is a misconfig:
    # fail fast instead of silently opening the API (review L6).
    if settings.environment != "local" and "*" in settings.cors_origins:
        raise ValueError(
            "CORS wildcard origins are not allowed outside local development; "
            "set SETTLESENSE_CORS_ORIGINS to explicit origins"
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """One error envelope everywhere: {"error": {code, message}}.
        Route-raised details carry {code, message}; framework-raised
        (404/405) string details map to code 'http_error'."""
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "http_error")
            message = exc.detail.get("message", str(exc.detail))
        else:
            code, message = "http_error", str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message}},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "invalid_request",
                "message": "request parameters failed validation",
                "details": {"errors": str(exc.errors()[:5])},
            }},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        # Structured, secret-free: no stack traces, no filesystem paths.
        return JSONResponse(
            status_code=500,
            content={"error": {
                "code": "internal_error",
                "message": "unexpected server error; see server logs",
            }},
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Liveness probe. Never includes secrets, keys, or file paths."""
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            environment=settings.environment,
            timezone=settings.timezone,
        )

    app.include_router(batches.router)
    app.include_router(cash.router)
    app.include_router(export.router)
    app.include_router(trace.router)
    app.include_router(reconcile.router)
    app.include_router(ai.router)
    return app


app = create_app()
