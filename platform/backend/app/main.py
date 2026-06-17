"""FastAPI application factory for the KooRemapper Platform backend.

Deployment shapes:
  1. Independent  : only /api/* exposed; frontend hosted separately (Vite/web instance).
  2. Combined     : KOORM_SERVE_FRONTEND_DIST points at frontend/dist; this app
                    also serves the SPA with a fallback route.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.modules import register_routers
from app.shared.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Starting %s (%s) — bin=%s storage=%s",
        settings.app_name,
        settings.app_env,
        settings.kooremapper_bin,
        settings.storage_dir,
    )
    if not settings.kooremapper_bin.exists():
        logger.warning(
            "KooRemapper binary not found at %s — build with "
            "-DKOOREMAPPER_PLATFORM_BIN=platform/backend/bin",
            settings.kooremapper_bin,
        )
    from app.worker.runner_loop import start_worker, stop_worker

    start_worker()
    yield
    await stop_worker()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    _configure_cors(app)
    register_exception_handlers(app)
    register_routers(app)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {
            "success": True,
            "data": {
                "status": "ok",
                "env": settings.app_env,
                "name": settings.app_name,
                "binary_present": settings.kooremapper_bin.exists(),
            },
            "message": None,
            "errors": None,
        }

    _mount_frontend_if_configured(app)
    return app


def _configure_cors(app: FastAPI) -> None:
    # Auth is via the Authorization: Bearer header (not cookies), so credentials
    # are not needed — which lets us safely keep a wildcard fallback in dev
    # (wildcard + allow_credentials is rejected by browsers and unsafe).
    origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )


def _mount_frontend_if_configured(app: FastAPI) -> None:
    dist_path: Path | None = settings.frontend_dist_path
    if dist_path is None or not dist_path.exists():
        return

    assets_dir = dist_path / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    index_file = dist_path / "index.html"

    @app.get("/", include_in_schema=False)
    def _serve_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str, _request: Request):
        if full_path.startswith("api/"):
            return JSONResponse(
                {"success": False, "data": None,
                 "message": f"API endpoint not found: /{full_path}", "errors": None},
                status_code=404,
            )
        candidate = dist_path / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)

    logger.info("Serving frontend dist from %s", dist_path)


app = create_app()
