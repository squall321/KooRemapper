# 충격 리포트 인제스트/조회 REST 라우트 (/api/v1).
from __future__ import annotations

import gzip
import io

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


def _maybe_gunzip(raw: bytes, filename: str | None) -> tuple[bytes, str | None]:
    """gzip(.gz) 업로드면 서버에서 압축 해제한다 — 대용량 리포트는 압축으로 올려 전송을 줄인다.

    gzip 매직바이트(1f 8b) 또는 .gz 확장자로 감지. 압축 해제 크기는 max_report_mb 로
    상한(스트리밍 읽기라 zip-bomb 이 메모리를 다 먹기 전에 끊는다). .gz 를 벗긴 파일명 반환.
    """
    is_gz = raw[:2] == b"\x1f\x8b" or (filename or "").lower().endswith(".gz")
    if not is_gz:
        return raw, filename
    cap = settings.max_report_mb * 1024 * 1024
    out = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            while True:
                chunk = gz.read(1024 * 1024)
                if not chunk:
                    break
                out += chunk
                if len(out) > cap:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"압축 해제 크기가 상한(최대 {settings.max_report_mb}MB)을 넘었습니다.",
                    )
    except (OSError, EOFError) as exc:  # 손상된 gzip
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"gzip 압축 해제 실패: {exc}")
    name = filename[:-3] if (filename or "").lower().endswith(".gz") else filename
    return bytes(out), name


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
    scenario: UploadFile | None = File(default=None),
    kind: str | None = Form(default=None),
    label: str | None = Form(default=None),
    kfile_id: int | None = Form(default=None),
    project: str | None = Form(default=None),
    dev_rev: str | None = Form(default=None),
    variation: str | None = Form(default=None),
    doe: str | None = Form(default=None),
    focus: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """낙하/충격 리포트 HTML 을 받아 구조화 저장한다.

    kind(deep|sphere|impact) 를 주면 자동판별을 덮어쓴다. 데이터는 HTML 에 임베드된
    ``const … = {…}`` 를 파싱해 공통 스키마로 정규화된다.

    선택 동반물: scenario(시뮬 조건 scenario.json — 조건 요약 + template 로 K파일
    자동매칭), kfile_id(원본 K파일 수동 지정), project/dev_rev/variation/doe(과제 메타).
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
            f"파일이 너무 큽니다 (전송 최대 {settings.max_upload_mb}MB — 대용량 리포트는 .gz 로 올리세요)",
        )
    raw, up_name = _maybe_gunzip(raw, file.filename)   # .gz 면 서버에서 압축 해제(전송량↓, GB 리포트 대응)
    scenario_raw = await scenario.read() if scenario is not None else None
    if scenario_raw is not None and len(scenario_raw) > cap:  # 동반 scenario 도 캡 적용
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"scenario 파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
        )
    sc_name = scenario.filename if scenario is not None else None
    if scenario_raw is not None:
        scenario_raw, sc_name = _maybe_gunzip(scenario_raw, sc_name)
    try:
        report = await svc.ingest_report(
            db, s, filename=up_name or "report.html", raw=raw, kind_hint=kind, label=label,
            scenario_raw=scenario_raw,
            scenario_filename=sc_name,
            kfile_id=kfile_id, project=project, dev_rev=dev_rev, variation=variation, doe=doe,
            focus=focus,
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
    kfile_id: int | None = Query(default=None, description="이 K파일에 매달린 리포트만(1 K:N 결과)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    rows = await svc.list_reports(db, session_id, kfile_id=kfile_id)
    return ok([ReportListItem.model_validate(r).model_dump() for r in rows])


class ReportMetaPatch(BaseModel):
    # 시맨틱: None=유지, ""=삭제, 값=설정. 길이는 DataHub 등재 검증과 정합하게 제한.
    label: str | None = Field(default=None, max_length=255)
    project: str | None = Field(default=None, max_length=64)   # 과제명
    dev_rev: str | None = Field(default=None, max_length=8)    # 개발단계 (pre|dv1..dvr|pv..|pra|mp)
    variation: str | None = Field(default=None, max_length=64)  # 설계안
    doe: str | None = Field(default=None, max_length=128)       # DOE 참조 study[:case]
    focus: str | None = Field(default=None, max_length=64)      # 초점 라벨(camera-detail 등)
    kfile_id: int | None = None     # 원본 K파일(세션 내 file id)


@router.patch("/reports/{report_id}")
async def patch_report_meta(
    report_id: str,
    body: ReportMetaPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """과제명·rev·설계안·DOE·원본 K파일 링크를 수동 설정(부분 갱신)."""
    r = await _require_report(db, user, report_id)
    try:
        r = await svc.update_report_meta(
            db, r, label=body.label, project=body.project, dev_rev=body.dev_rev,
            variation=body.variation, doe=body.doe, kfile_id=body.kfile_id, focus=body.focus,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return ok(ReportRead.model_validate(r).model_dump(), message="메타 갱신됨")


@router.post(
    "/reports/{report_id}/scenario",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def attach_report_scenario(
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트에 시뮬 조건(scenario.json)을 첨부 — 조건 요약 캐시 + K파일 자동매칭."""
    r = await _require_report(db, user, report_id)
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
        )
    try:
        r = await svc.attach_scenario(db, r, raw=raw, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return ok(ReportRead.model_validate(r).model_dump(), message="시뮬 조건(scenario) 첨부됨")


@router.get("/reports/facets")
async def report_facets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트 검색 facet — 어떤 kind·과제·rev·설계안·방향컨셉·초점·심각도·높이가 있나 + 건수.
    목표를 정하기 전 '먼저 뭐가 있나'를 보는 화면. 소유분(관리자는 전사)."""
    return ok(await svc.report_facets(db, user.id, is_admin=user.is_system_admin))


def _parse_dt(v: str | None, field: str):
    if not v:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{field} 형식 오류(ISO-8601): {v}")


@router.get("/reports")
async def find_reports(
    kind: str | None = Query(default=None, pattern="^(deep|sphere|impact)$"),
    project: str | None = Query(default=None, description="과제 (eng_meta 또는 임베드 project_name)"),
    dev_rev: str | None = Query(default=None, description="개발단계 (dv1 등)"),
    variation: str | None = Query(default=None, description="설계안"),
    doe: str | None = Query(default=None, description="DOE 캠페인(study)"),
    session_id: str | None = Query(default=None),
    kfile_id: int | None = Query(default=None),
    focus: str | None = Query(default=None, description="초점 라벨(예 camera-detail)"),
    doe_strategy: str | None = Query(default=None, description="방향 컨셉(cuboid_26·fibonacci_162 등)"),
    scenario_type: str | None = Query(default=None, description="scenario source_type"),
    drop_height: float | None = Query(default=None, description="낙하 높이(±height_tol)"),
    height_tol: float = Query(1.0, ge=0),
    severity: str | None = Query(default=None, pattern="^(CRITICAL|WARNING|INFO)$", description="이 심각도 이상 소견 보유"),
    min_worst_stress: float | None = Query(default=None),
    min_worst_g: float | None = Query(default=None),
    has_part: str | None = Query(default=None, description="이 부품명을 포함한 리포트"),
    q: str | None = Query(default=None, description="라벨/과제 텍스트 검색"),
    since: str | None = Query(default=None, description="created_at ≥ (ISO)"),
    until: str | None = Query(default=None, description="created_at ≤ (ISO)"),
    sort: str = Query("created_at", pattern="^(created_at|worst_stress|worst_g|drop_height)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """조건으로 리포트 검색(결과 폭증 대비 다축 서버 필터). 소유분(관리자는 전사).

    같은 전각도라도 방향 컨셉(doe_strategy)·초점(focus)·조건(scenario_type)·높이별로
    각기 골라낼 수 있다. 전부 서버에서 걸러 슬라이스만 반환.
    """
    rows = await svc.find_reports(
        db, user.id, is_admin=user.is_system_admin,
        sort=sort, order=order, limit=limit, offset=offset,
        session_id=session_id, kind=kind, project=project, dev_rev=dev_rev,
        variation=variation, doe=doe, kfile_id=kfile_id, focus=focus,
        doe_strategy=doe_strategy, scenario_type=scenario_type,
        drop_height=drop_height, height_tol=height_tol, severity=severity,
        min_worst_stress=min_worst_stress, min_worst_g=min_worst_g,
        has_part=has_part, q_text=q,
        since=_parse_dt(since, "since"), until=_parse_dt(until, "until"),
    )
    return ok([ReportListItem.model_validate(r).model_dump() for r in rows])


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id)
    return ok(ReportRead.model_validate(r).model_dump())


@router.get("/reports/{report_id}/query")
async def query_report_facts(
    report_id: str,
    part_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    angle_name: str | None = Query(default=None),
    near_roll: float | None = Query(default=None),
    near_pitch: float | None = Query(default=None),
    near_yaw: float | None = Query(default=None),
    angle_tol_deg: float | None = Query(default=None, ge=0, le=180),
    metric: str = Query("peak_stress"),
    min_value: float | None = Query(default=None),
    max_value: float | None = Query(default=None),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트 내부 fact 드릴다운 — 부품·각도(범주/이름/근접)·물리량·임계로 서버 필터.

    "특정 부품이 특정 각도(±허용)에서 응력 상위 N" 같은 데이터 질의를 한 콜로.
    반환은 (case_key·각도·부품·물리량·값·at_time) 평탄 fact 리스트(정렬·limit 적용).
    """
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.query_facts(
            db, r, part_id=part_id, category=category, angle_name=angle_name,
            near_roll=near_roll, near_pitch=near_pitch, near_yaw=near_yaw,
            angle_tol_deg=angle_tol_deg, metric=metric,
            min_value=min_value, max_value=max_value, sort=sort, limit=limit,
        ))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


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


@router.get("/reports/{report_id}/scatter")
async def report_scatter(
    report_id: str,
    metric: str = Query("peak_stress"),
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """방향 섭동 산포 분석(sphere) — 26 정준방향별 metric 산포(mean/std/CoV/최악)·민감도."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.scatter(db, r, metric=metric, part_id=part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/part-energy")
async def report_part_energy(
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """파트별 에너지(내부/운동) 시계열 — deep matsum(있을 때). part_id 로 한 파트만.
    sphere/impact 는 파트별 에너지 시계열이 없어 note 반환(글로벌 에너지는 /energy)."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.part_energy_series(db, r, part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/angle-stats")
async def report_angle_stats(
    report_id: str,
    metric: str = Query("peak_stress"),
    part_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    angle_name: str | None = Query(default=None),
    near_lon: float | None = Query(default=None),
    near_lat: float | None = Query(default=None),
    tol_deg: float = Query(15.0, ge=0.0, le=180.0),
    top_parts: int = Query(5, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 각도군 표준 통계 — 선택(near/angle_name/category/전체) × 분포(mean/std/CoV/
    백분위/IQR/최악) + 부품별 위험·민감도 분해. 있는 물리량은 available_metrics 로 안내."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.angle_group_stats(
            db, r, metric=metric, part_id=part_id, category=category, angle_name=angle_name,
            near_lon=near_lon, near_lat=near_lat, tol_deg=tol_deg, top_parts=top_parts))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/geometry")
async def report_geometry(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공간 컨텍스트(부품 위치 시각화) — impact=디바이스 외곽선+파트 footprint(XY)+z범위.
    sphere/deep 은 각도 기반이라 부품 형상은 원본 렌더(iframe)에만 있다."""
    r = await _require_report(db, user, report_id)
    try:
        return ok(await svc.geometry(db, r))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


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
    # 비우면 리포트에 수동 설정된 eng_meta(PATCH /reports/{id})를 기본값으로 쓴다.
    project: str | None = Field(default=None, max_length=64)  # 과제코드
    stage: str | None = Field(default=None, max_length=8)     # 개발단계 pre|dv1..dvr|pv..|pra|mp
    variation: str | None = None                               # 설계안
    doe: str | None = None                                     # DOE 참조 study[:case]
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
    # (미지정이면 서비스가 리포트 eng_meta 로 폴백하므로 여기선 준 값만 검증)
    if body.stage:
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
