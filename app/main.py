"""FastAPI Application Factory and Entry Point.

Trustworthy Multi-Agent Financial Research and Decision Support System.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Explicit application startup and shutdown lifecycle management."""
    # 1. Provision persistent data directories
    settings.ensure_directories()

    # 2. Deterministically initialize SQLite database tables
    init_db()

    yield

    # Clean shutdown tasks (if any) can be added here


def create_app() -> FastAPI:
    """FastAPI application factory configuring middleware, routes, and error handlers."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Trustworthy Multi-Agent Financial Research and Decision Support System.\n\n"
            "Provides citation-backed, deterministically verified financial research "
            "with claim-level provenance, contradiction detection, and human review boundaries."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS for development frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(api_router)

    # Mount frontend static web application
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    # Structured error handlers
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        code_map = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            413: "FILE_TOO_LARGE",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_SERVER_ERROR",
            501: "NOT_IMPLEMENTED",
            503: "SERVICE_UNAVAILABLE",
        }
        error_code = code_map.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": error_code,
                    "message": exc.detail if isinstance(exc.detail, str) else "An error occurred.",
                    "details": exc.detail if not isinstance(exc.detail, str) else None,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Use jsonable_encoder to ensure nested Exception objects in error context are serialized
        safe_errors = jsonable_encoder(exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": {"validation_errors": safe_errors},
                }
            },
        )

    @app.get("/", tags=["Root"])
    def root():
        """Root API welcome message."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "documentation": "/docs",
            "health": "/api/health",
        }

    return app


# Application instance for ASGI runners (uvicorn app.main:app)
app = create_app()
