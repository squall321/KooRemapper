"""FastAPI application factory for the KooRemapper Platform backend.

Deployment shapes:
  1. Independent  : only /api/* exposed; frontend hosted separately (Vite/web instance).
  2. Combined     : KOORM_SERVE_FRONTEND_DIST points at frontend/dist; this app
                    also serves the SPA with a fallback route.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.modules import register_routers
from app.shared.errors import register_exception_handlers
from app.shared.logctx import reset_correlator, sanitize, set_correlator, setup_logging

# ⚠ `basicConfig(level=INFO)` 이던 자리다. 그 포맷에는 **시각이 없어서** "14:30 에 실패했다" 를
# 로그와 맞출 수 없었다(진단 체계, context-notes 28). 상관자도 여기서 들어간다.
setup_logging()
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
    try:
        await asyncio.wait_for(stop_worker(), timeout=3.5)
    except asyncio.TimeoutError:
        logger.warning("worker did not stop within 3.5s — forcing shutdown")
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
    _install_correlator(app)
    register_exception_handlers(app)
    register_routers(app)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        # 기존 네 칸은 그대로 둔다 — 소비자(supervisor.sh·start.sh·nginx)는 상태코드만 보지만
        # 칸 이름을 바꾸면 조용히 깨질 수 있는 자리다. **더하기만** 한다.
        #
        # 리비전·해시를 왜 여기 싣나 — 게시본이 21커밋 뒤에 멈춰 있었는데 **밖에서 볼 방법이
        # 없었다.** 바이너리는 넷이 다 `version 1.8.0` 만 찍는다. 출처는 배포가 내려놓은
        # bin/BUILD_INFO.txt 하나다(런타임에 git 을 부르지 않는다 — 폐쇄망에 git 실행 파일이 없다).
        from app.runner.gmsh_probe import probe as gmsh_probe
        from app.shared.buildinfo import build_info

        info = build_info(settings.kooremapper_bin)
        # gmsh 가용 여부 — `meshfix` 는 이것 없이는 못 돈다(P1-9).
        # ⚠ 경로와 거절 목록은 **싣지 않는다.** 이 엔드포인트는 인증 없이 열린다 —
        # 배치 구조를 밖에 알릴 이유가 없다. 그 둘은 잡 거절 메시지로 (인증된) 사용자에게 간다.
        _g = gmsh_probe(settings.kooremapper_bin)
        return {
            "success": True,
            "data": {
                "status": "ok",
                "env": settings.app_env,
                "name": settings.app_name,
                "binary_present": settings.kooremapper_bin.exists(),
                **info,
                "gmsh": {"available": _g["available"], "version": _g["version"]},
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
        # 브라우저는 목록에 없는 응답 헤더를 스크립트에 **안 보여 준다.** 상관자를 화면에서
        # 읽어 사용자가 넘기게 하려면 이것이 있어야 한다(같은 오리진이면 없어도 되지만,
        # 개발에서는 프런트가 다른 포트다).
        expose_headers=["X-Request-Id"],
    )


def _install_correlator(app: FastAPI) -> None:
    """요청마다 상관자를 세우고, 요청 한 줄을 **우리가** 찍는다.

    ⚠ uvicorn 의 접근 로그에는 시각이 없고 포맷을 바꾸려면 `--log-config` 가 필요한데, 그 명령줄은
    `api.def` 의 `%runscript` 에 있고 **SIF 에 구워진다.** 그래서 한 줄을 우리가 찍는다 — 어차피
    상관자를 들고 있는 쪽이 우리다.

    ⚠ `/api/health` 는 찍지 않는다. 감독자가 분당 폴링해서 그 줄만 1,461개였다(실측).
    """

    @app.middleware("http")
    async def _correlate(request: Request, call_next):
        corr = sanitize(request.headers.get("x-request-id") or "")
        token = set_correlator(corr)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            path = request.url.path
            if path != "/api/health":
                logger.info(
                    "%s %s -> %s in %.0fms",
                    request.method, path, response.status_code,
                    (time.perf_counter() - t0) * 1000,
                )
            # 실패 응답에도 붙는다 — 사용자가 이 값을 넘기면 서버 줄을 바로 찾을 수 있다.
            response.headers["X-Request-Id"] = corr
            return response
        finally:
            reset_correlator(token)


def _mount_frontend_if_configured(app: FastAPI) -> None:
    dist_path: Path | None = settings.frontend_dist_path
    if dist_path is None or not dist_path.exists():
        return

    assets_dir = dist_path / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    index_file = dist_path / "index.html"
    # HEAX 포탈 프록시(/apps/kooremapper/) 경유 요청용 index — base 가 서브패스로
    # 구워진 빌드. 게이트웨이 헤더 존재로 판별한다 (build-frontend.sh 가 생성).
    portal_index = dist_path / "index.portal.html"

    def _index_for(request: Request) -> FileResponse:
        if portal_index.is_file() and request.headers.get("x-heax-gateway-secret"):
            return FileResponse(portal_index)
        return FileResponse(index_file)

    @app.get("/", include_in_schema=False)
    def _serve_index(request: Request) -> FileResponse:
        return _index_for(request)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str, request: Request):
        if full_path.startswith("api/"):
            return JSONResponse(
                {"success": False, "data": None,
                 "message": f"API endpoint not found: /{full_path}", "errors": None},
                status_code=404,
            )
        candidate = dist_path / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return _index_for(request)

    logger.info("Serving frontend dist from %s", dist_path)


app = create_app()
