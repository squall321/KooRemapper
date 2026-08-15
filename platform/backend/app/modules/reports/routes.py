# 충격 리포트 인제스트/조회 REST 라우트 (/api/v1).
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.reports import services as svc
from app.modules.reports.schemas import CaseRead, ReportListItem, ReportRead
from app.modules.sessions import services as sess_svc
from app.shared.auth import get_current_user
from app.shared.ratelimit import rate_limit
from app.shared.responses import ok

router = APIRouter(tags=["reports"])

_KINDS = {"deep", "sphere", "impact"}


async def _require_session(db, user, session_id):
    s = await sess_svc.get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_report(db, user, report_id):
    r = await svc.get_owned_report(db, user.id, report_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    return r


@router.post(
    "/sessions/{session_id}/reports",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def ingest_report(
    session_id: str,
    file: UploadFile = File(...),
    kind: str | None = Form(default=None),
    label: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """낙하/충격 리포트 HTML 을 받아 구조화 저장한다.

    kind(deep|sphere|impact) 를 주면 자동판별을 덮어쓴다. 데이터는 HTML 에 임베드된
    ``const … = {…}`` 를 파싱해 공통 스키마로 정규화된다.
    """
    s = await _require_session(db, user, session_id)
    if kind is not None and kind not in _KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind 는 {sorted(_KINDS)} 중 하나여야 합니다.")
    cap = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > cap:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
        )
    raw = await file.read()
    if len(raw) > cap:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
        )
    try:
        report = await svc.ingest_report(
            db, s, filename=file.filename or "report.html", raw=raw, kind_hint=kind, label=label
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return ok(
        ReportRead.model_validate(report).model_dump(),
        message=f"{report.kind} 리포트 인제스트 완료 ({report.n_cases} 케이스)",
        status_code=201,
    )


@router.get("/sessions/{session_id}/reports")
async def list_reports(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    rows = await svc.list_reports(db, session_id)
    return ok([ReportListItem.model_validate(r).model_dump() for r in rows])


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id)
    return ok(ReportRead.model_validate(r).model_dump())


@router.get("/reports/{report_id}/cases")
async def list_report_cases(
    report_id: str,
    sort: str = Query("max_stress"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """케이스 랭킹. sort ∈ {max_stress,max_g,max_disp,min_safety_factor}.

    sphere=최악 방향, impact=최악 위치, deep=단건.
    """
    await _require_report(db, user, report_id)
    rows = await svc.list_cases(db, report_id, sort=sort, order=order, limit=limit, offset=offset)
    return ok([CaseRead.model_validate(c).model_dump() for c in rows])


@router.get("/reports/{report_id}/cases/{case_key}")
async def get_report_case(
    report_id: str,
    case_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_report(db, user, report_id)
    c = await svc.get_case(db, report_id, case_key)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "케이스를 찾을 수 없습니다.")
    return ok(CaseRead.model_validate(c).model_dump())


@router.get("/reports/{report_id}/parts")
async def report_part_risk(
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """파트별 최악값과 발생 케이스(각도/위치) + 최소 안전율."""
    r = await _require_report(db, user, report_id)
    return ok(await svc.part_risk(db, r, part_id))


@router.get("/reports/{report_id}/directional")
async def report_directional(
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """방향 취약도 — 방향 범주(면/엣지/코너·F1~F6)별 최악. part_id 로 파트 한정."""
    r = await _require_report(db, user, report_id)
    return ok(await svc.directional(db, r, part_id))


@router.get("/reports/{report_id}/energy")
async def report_energy(
    report_id: str,
    case_key: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에너지/접촉 상세(원본 재파싱). deep=에너지밸런스·접촉력, sphere/impact=하중경로 그래프."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.case_energy(db, r, case_key))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/cases/{case_key}/series")
async def report_part_series(
    report_id: str,
    case_key: str,
    part_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """케이스·파트의 시계열(원본 재파싱, 다운샘플)."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.part_series(db, r, case_key, part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/findings")
async def report_findings(
    report_id: str,
    severity: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id)
    items = r.findings or []
    if severity:
        sev = severity.upper()
        items = [f for f in items if (f.get("severity") or "").upper() == sev]
    return ok(items)


class PublishDataHubBody(BaseModel):
    project: str = Field(min_length=1, max_length=64)  # 과제코드
    stage: str = Field(min_length=1, max_length=8)     # 개발단계 pre|dv1..dvr|pv1..pvr|pra|mp
    variation: str | None = None                        # 설계안
    doe: str | None = None                              # DOE 참조 study[:case]
    unit: str = "mm-t-s"
    title: str | None = None


@router.post("/reports/{report_id}/publish-datahub")
async def publish_report_to_datahub(
    report_id: str,
    body: PublishDataHubBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트를 AI Data Hub 의 범용 sim_report 레코드로 등재한다(과제/개발단계/BOM 연계)."""
    from app.reports.datahub import DataHubError, parse_stage

    r = await _require_report(db, user, report_id)
    if not settings.datahub_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "datahub_url 이 설정되지 않았습니다.")
    # stage 형식 오류는 클라이언트 잘못 → 400 으로 먼저 걸러낸다.
    try:
        parse_stage(body.stage)
    except DataHubError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    try:
        res = await svc.publish_to_datahub(
            db, r, hub_url=settings.datahub_url,
            project=body.project, stage=body.stage, variation=body.variation,
            doe=body.doe, unit=body.unit, title=body.title,
        )
    except ValueError as exc:  # 원본 HTML 없음 등
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except DataHubError as exc:  # 업로드/네트워크 실패
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"DataHub 등재 실패: {exc}")
    return ok(res, message=f"DataHub 등재 완료: {res['record_id']}", status_code=201)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id)
    await svc.delete_report(db, r)
    return ok(message="리포트가 삭제되었습니다.")
