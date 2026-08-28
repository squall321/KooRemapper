# ReportArchive pull 연동 REST — 결과 목록(A) + NDJSON 다운로드(B).
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.analysis import services as svc
from app.modules.analysis.ndjson import iter_ndjson_lines
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["analysis"])


def _parse_since(since: str | None) -> datetime | None:
    """ISO 시각 파싱(Z 접미 허용). 형식 오류면 400."""
    if not since:
        return None
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"since 형식 오류(ISO-8601 필요): {since}")


def _base_url(request: Request) -> str:
    return (settings.analysis_public_base_url or str(request.base_url)).rstrip("/")


# ── A. 결과 목록 ─────────────────────────────────────────────────────
@router.get("/analysis/runs")
async def list_runs(
    request: Request,
    since: str | None = Query(default=None, description="ISO 워터마크(analyzed_at 증분)"),
    after: str | None = Query(default=None, description="커서(직전 next_after)"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 해석 결과 목록(ReportArchive §1). id(시각순) 커서로 페이지네이션.

    시스템 관리자 PAT 면 전 사용자 리포트(전사 수집), 아니면 소유 리포트만.
    """
    rows = await svc.list_runs(
        db, user.id, is_admin=user.is_system_admin,
        since=_parse_since(since), after=after, limit=limit,
    )
    base = _base_url(request)
    site = settings.analysis_site_id or None
    items = [{
        "run_key": r.id,
        "id": r.id,
        "title": r.label,
        "kind": r.kind,
        "site": site,  # 어느 DynaForge 인스턴스인지(여러→하나 집계용). None 이면 미설정.
        "owner_user_id": r.user_id,  # 전사(admin) 수집 시 어느 계정 결과인지 구분용.
        "analyzed_at": r.created_at.isoformat() if r.created_at else None,
        "file_url": f"{base}/api/v1/analysis/runs/{r.id}/export.ndjson",
        "n_cases": r.n_cases,
    } for r in rows]
    body = {"items": items}
    if len(rows) == limit and rows:
        body["next_after"] = rows[-1].id  # 다음 페이지 커서
    return ok(body)


# ── B. 결과 파일(NDJSON) ─────────────────────────────────────────────
@router.get("/analysis/runs/{run_key}/export.ndjson")
async def export_run_ndjson(
    run_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ra.analysis.v1 NDJSON 스트리밍(ReportArchive §2·§3). run + fact 줄."""
    report = await svc.get_report(db, user.id, run_key, is_admin=user.is_system_admin)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "결과를 찾을 수 없습니다.")
    cases = await svc.load_cases(db, report.id)
    # 이미 로드된 report+cases 위를 도는 순수 제너레이터 → 상수 메모리 스트리밍.
    gen = iter_ndjson_lines(report, cases, site=settings.analysis_site_id or None)
    headers = {"Content-Disposition": f'attachment; filename="{run_key}.ndjson"'}
    return StreamingResponse(gen, media_type="application/x-ndjson", headers=headers)
