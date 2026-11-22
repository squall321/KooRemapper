"""Router registry. Each module exposes `router` and is mounted here under /api/v1."""
from __future__ import annotations

from fastapi import FastAPI

API_PREFIX = "/api/v1"


def register_routers(app: FastAPI) -> None:
    from app.modules.admin.routes import router as admin_router
    from app.modules.analysis.routes import router as analysis_router
    from app.modules.auth.routes import router as auth_router
    from app.modules.campaigns.routes import router as campaigns_router
    from app.modules.campaigns.routes import bundles_router
    from app.modules.campaigns.analysis_routes import part_maps_router
    from app.modules.campaigns.analysis_routes import router as campaign_analysis_router
    from app.modules.corpus.routes import router as corpus_router
    from app.modules.jobs.routes import router as jobs_router
    from app.modules.ontology.routes import admin as ontology_admin_router
    from app.modules.ontology.routes import router as ontology_router
    from app.modules.operations.routes import router as operations_router
    from app.modules.recipes.routes import router as recipes_router
    from app.modules.reports.routes import router as reports_router
    from app.modules.sessions.routes import router as sessions_router
    from app.modules.system.routes import router as system_router
    from app.modules.users.routes import router as users_router

    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(users_router, prefix=API_PREFIX)
    app.include_router(sessions_router, prefix=API_PREFIX)
    app.include_router(reports_router, prefix=API_PREFIX)
    # 캠페인 — 런 묶음과 그 적재 상태. 리포트 본문은 /reports/intake 가 받는다.
    app.include_router(campaigns_router, prefix=API_PREFIX)
    # 보고서용 묶음(DF-13) — 캠페인 숫자 · 그림 재료를 판으로. 캠페인의 마지막 판은 /campaigns/{id}/bundles/latest
    app.include_router(bundles_router, prefix=API_PREFIX)
    # 캠페인 분석(DF-05 · 06 · 08 ~ 12) — 각도 표 · 통계 · 피크 · 여유 · 구면 지도 · 자리 · 리비전 비교 · 설정 쌍. /campaigns/compare 가 있다
    app.include_router(campaign_analysis_router, prefix=API_PREFIX)
    app.include_router(part_maps_router, prefix=API_PREFIX)
    app.include_router(recipes_router, prefix=API_PREFIX)
    app.include_router(analysis_router, prefix=API_PREFIX)
    app.include_router(operations_router, prefix=API_PREFIX)
    app.include_router(jobs_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    # 과제·개정 — 읽기는 로그인만, 과거 붙이기·별칭·수신은 시스템 관리자.
    app.include_router(ontology_router, prefix=API_PREFIX)
    app.include_router(ontology_admin_router, prefix=API_PREFIX)
    app.include_router(system_router, prefix=API_PREFIX)
    # 전사 통계 — 개인 식별 없는 집계라 인증만 되면 누구나(심의 근거용).
    app.include_router(corpus_router, prefix=API_PREFIX)
