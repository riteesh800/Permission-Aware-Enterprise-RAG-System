from __future__ import annotations

import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app import database as dbmod
from app import models  # noqa: F401
from app.api.admin_audit import router as admin_audit_router
from app.api.admin_documents import router as admin_documents_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.employee import router as employee_router
from app.config import get_settings
from app.database import Base, ensure_pgvector
from app.observability import configure_logging, get_logger

configure_logging()
logger = get_logger("permission_rag")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "request",
            request_id=request_id,
            route=request.url.path,
            method=request.method,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(bind=dbmod.engine)
        ensure_pgvector(dbmod.engine)
        yield

    app = FastAPI(
        title=settings.app_name,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Authorization"],
    )

    app.include_router(auth_router)
    app.include_router(admin_users_router)
    app.include_router(admin_documents_router)
    app.include_router(admin_audit_router)
    app.include_router(chat_router)
    app.include_router(employee_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        logger.error(f"HTTPException: status={exc.status_code}, detail={exc.detail}")
        if exc.status_code == 403:
            import traceback
            traceback.print_stack()
        message = exc.detail if isinstance(exc.detail, str) else "Unable to process request"
        return JSONResponse(status_code=exc.status_code, content={"error": message})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"error": "Unable to process request", "details": _exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        logger.error("unhandled_error", request_id=getattr(_request.state, "request_id", "-"))
        if settings.debug:
            traceback.print_exc()
        if isinstance(exc, HTTPException):
            message = exc.detail if isinstance(exc.detail, str) else "Unauthorized"
            return JSONResponse(status_code=exc.status_code, content={"error": message})
        return JSONResponse(status_code=500, content={"error": "Unable to process request"})

    return app


app = create_app()


def init_db() -> None:
    Base.metadata.create_all(bind=dbmod.engine)
