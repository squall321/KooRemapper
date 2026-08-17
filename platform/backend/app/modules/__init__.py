"""Router registry. Each module exposes `router` and is mounted here under /api/v1."""
from __future__ import annotations

from fastapi import FastAPI

API_PREFIX = "/api/v1"


def register_routers(app: FastAPI) -> None:
    from app.modules.admin.routes import router as admin_router
    from app.modules.auth.routes import router as auth_router
    from app.modules.corpus.routes import router as corpus_router
    from app.modules.jobs.routes import router as jobs_router
    from app.modules.operations.routes import router as operations_router
    from app.modules.reports.routes import router as reports_router
    from app.modules.sessions.routes import router as sessions_router
    from app.modules.system.routes import router as system_router
    from app.modules.users.routes import router as users_router

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(users_router, prefix=API_PREFIX)
    app.include_router(sessions_router, prefix=API_PREFIX)
    app.include_router(reports_router, prefix=API_PREFIX)
    app.include_router(operations_router, prefix=API_PREFIX)
    app.include_router(jobs_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    app.include_router(system_router, prefix=API_PREFIX)
    # 전사 통계 — 개인 식별 없는 집계라 인증만 되면 누구나(심의 근거용).
    app.include_router(corpus_router, prefix=API_PREFIX)
