# 충격 리포트 인제스트/조회 REST 라우트 (/api/v1).
from __future__ import annotations

import gzip
import io
import zlib

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query, Request,
                     UploadFile, status)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.reports import services as svc
from app.modules.reports.schemas import CaseRead, ReportListItem, ReportRead
from app.modules.sessions import services as sess_svc
from app.shared.auth import get_current_user
from app.shared.affiliation import verified_affiliation
from app.shared.ratelimit import rate_limit
from app.reports import bundle as bundle_mod
from app.reports.cad_bundle import CadBundleError
from app.reports.onto_package import OntoPackageError
from app.reports.render_result import RenderResultError
from app.shared.responses import ok

router = APIRouter(tags=["reports"])

_KINDS = {"deep", "sphere", "impact"}


def _maybe_gunzip(raw: bytes, filename: str | None, cap_mb: int | None = None) -> tuple[bytes, str | None]:
    """gzip(.gz) 업로드면 서버에서 압축 해제한다 — 대용량 리포트는 압축으로 올려 전송을 줄인다.

    gzip 매직바이트(1f 8b) 또는 .gz 확장자로 감지. 압축 해제 크기는 cap_mb(미지정 시
    max_report_mb) 로 상한(스트리밍 읽기라 zip-bomb 이 메모리를 다 먹기 전에 끊는다) —
    scenario/K파일은 작은 상한을 넘겨 증폭을 막는다. .gz 를 벗긴 파일명 반환.
    """
    is_gz = raw[:2] == b"\x1f\x8b" or (filename or "").lower().endswith(".gz")
    if not is_gz:
        return raw, filename
    limit_mb = cap_mb if cap_mb is not None else settings.max_report_mb
    cap = limit_mb * 1024 * 1024
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
                        f"압축 해제 크기가 상한(최대 {limit_mb}MB)을 넘었습니다.",
                    )
    except (OSError, EOFError, zlib.error) as exc:  # 손상된 gzip(zlib.error 는 OSError 하위 아님)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"gzip 압축 해제 실패: {exc}")
    name = filename[:-3] if (filename or "").lower().endswith(".gz") else filename
    return bytes(out), name


async def _read_upload(
    file: UploadFile, *, what: str = "파일", decompress_cap_mb: int | None = None,
) -> tuple[bytes, str | None]:
    """업로드를 읽어 전송 상한 검사 후 .gz 면 서버에서 해제한다(ingest·intake 공용).
    decompress_cap_mb: 압축 해제 상한(리포트=기본 max_report_mb, K파일·scenario=작게)."""
    cap = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > cap:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{what}이 너무 큽니다 (전송 최대 {settings.max_upload_mb}MB — 대용량은 .gz 로 올리세요)",
        )
    raw = await file.read()
    if len(raw) > cap:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{what}이 너무 큽니다 (전송 최대 {settings.max_upload_mb}MB — 대용량은 .gz 로 올리세요)",
        )
    return _maybe_gunzip(raw, file.filename, cap_mb=decompress_cap_mb)


async def _require_session(db, user, session_id):
    s = await sess_svc.get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_report(db, user, report_id, request: Request | None = None):
    """읽기 관문 — 소유자거나 같은 소속(게이트웨이 서명 검증)이면 연다.

    소속은 요청마다 새로 검증한다. 리포트 쪽 값은 반입 때 얼린 것이라 소유자가 소속을 옮겨도
    과거 리포트의 공유 범위는 움직이지 않는다(요청서 §8).
    """
    aff = ""
    if request is not None:
        aff = verified_affiliation(request.headers, user.email, settings.heax_gateway_secret)
    r = await svc.get_readable_report(db, user.id, report_id, aff)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    return r


async def _require_owned_report(db, user, report_id):
    """수정·삭제 관문 — 소유자만(요청서 §7)."""
    r = await svc.get_owned_report(db, user.id, report_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리포트를 찾을 수 없습니다.")
    return r


@router.post(
    "/sessions/{session_id}/reports",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def ingest_report(
    request: Request,
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
    raw, up_name = await _read_upload(file, what="파일")   # 전송 상한 + .gz 서버 해제
    scenario_raw, sc_name = (None, None)
    if scenario is not None:
        scenario_raw, sc_name = await _read_upload(scenario, what="scenario 파일",
                                                   decompress_cap_mb=settings.max_upload_mb)
    try:
        report = await svc.ingest_report(
            db, s, filename=up_name or "report.html", raw=raw, kind_hint=kind, label=label,
            scenario_raw=scenario_raw,
            scenario_filename=sc_name,
            kfile_id=kfile_id, project=project, dev_rev=dev_rev, variation=variation, doe=doe,
            focus=focus,
            # 읽기 공유 범위는 반입 시점 값으로 얼린다(요청서 §8)
            shared_affiliation=verified_affiliation(
                request.headers, user.email, settings.heax_gateway_secret),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return ok(
        ReportRead.model_validate(report).model_dump(),
        message=f"{report.kind} 리포트 인제스트 완료 ({report.n_cases} 케이스)",
        status_code=201,
    )


@router.post(
    "/reports/intake",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def report_intake(
    request: Request,
    file: UploadFile = File(...),                       # 리포트 HTML(.gz) 또는 **번들**(.zip/.tar(.gz))
    kfile: UploadFile | None = File(default=None),      # 원본 K파일(.gz 가능) — 리포트와 함께 올려 링크
    scenario: UploadFile | None = File(default=None),   # 시뮬 조건 scenario.json(.gz 가능)
    session_id: str | None = Form(default=None),        # 기존 세션에 넣을 때
    session_name: str | None = Form(default=None),      # 새 세션 이름(미지정 시 자동)
    kind: str | None = Form(default=None),
    label: str | None = Form(default=None),
    project: str | None = Form(default=None),
    dev_rev: str | None = Form(default=None),
    variation: str | None = Form(default=None),
    doe: str | None = Form(default=None),
    focus: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """**한 번에 반입** — (세션 생성/지정) + K파일 + 리포트 + scenario 를 한 호출로.

    지금까지는 세 번 불러야 했다(세션 생성 → K 업로드 → 리포트 인제스트+kfile_id 링크).
    "전각도 낙하/전위치 충격/deep 리포트를 K파일과 함께" 올리는 걸 한 호출로 얇게 조립한다
    (안에서 하는 일은 기존 경로 그대로 — 로직 복제 없음). 파일은 전부 .gz 로 올려 전송을 줄일
    수 있다(서버가 해제). 반환: session_id·report_id·kfile_id.
    """
    if kind is not None and kind not in _KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind 는 {sorted(_KINDS)} 중 하나여야 합니다.")
    # ① 모든 업로드를 먼저 읽고 검증(전송상한+gz 해제) — 아무것도 영속되기 전에 크기/gz 실패를
    #    반려해 orphan 세션·파일을 안 남긴다(원샷 원자성). K파일·scenario 는 작은 해제 상한.
    raw, up_name = await _read_upload(file, what="리포트")
    # ★번들이면 리포트 HTML 과 **사이드카 미디어**를 함께 푼다. 결과 이미지는 HTML 안에
    #   임베드되지 않으므로(옆에 딸린 파일이다), HTML 하나만 올리면 그림이 애초에 들어오지
    #   않는다 — LLM 도 화면도 결과를 볼 수 없다. 가드는 전부 `app/reports/bundle.py` 에 있다.
    bundle_media: list[dict] = []
    bundle_onto: dict | None = None
    bundle_info: dict | None = None
    if bundle_mod.looks_like_bundle(up_name, raw):
        try:
            b = bundle_mod.extract(raw, up_name)
        except bundle_mod.BundleError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        raw, up_name = b["html"], b["html_name"]
        bundle_media = b["media"]
        bundle_onto = b.get("ontology")
        bundle_info = {"html_name": b["html_name"], "n_html": b["n_html"],
                       "n_media": len(b["media"]), "skipped": b["skipped"]}
        if b.get("note"):
            bundle_info["note"] = b["note"]
    k_raw, k_name = (None, None)
    if kfile is not None:
        k_raw, k_name = await _read_upload(kfile, what="K파일", decompress_cap_mb=settings.max_upload_mb)
    scenario_raw, sc_name = (None, None)
    if scenario is not None:
        scenario_raw, sc_name = await _read_upload(scenario, what="scenario 파일",
                                                   decompress_cap_mb=settings.max_upload_mb)
    # ② 세션 확정 — 기존 지정 우선(소유 검증), 없으면 신규 생성(이름: session_name>project>label).
    created_here = not session_id
    if session_id:
        s = await _require_session(db, user, session_id)
    else:
        s = await sess_svc.create_session(
            db, user.id, name=(session_name or project or label or "report intake"),
            description="report intake",
        )
    # ③ K 저장 + 인제스트 — 실패하면 이번 호출이 만든 것(신규 세션 또는 방금 넣은 K)을 되돌린다.
    kfile_id: int | None = None
    krow = None
    try:
        if k_raw is not None:
            krow = await sess_svc.add_uploaded_file(db, s, filename=k_name or "model.k", raw=k_raw, kind="input")
            kfile_id = krow.id
        report = await svc.ingest_report(
            db, s, filename=up_name or "report.html", raw=raw, kind_hint=kind, label=label,
            scenario_raw=scenario_raw, scenario_filename=sc_name,
            kfile_id=kfile_id, project=project, dev_rev=dev_rev, variation=variation, doe=doe,
            focus=focus,
            shared_affiliation=verified_affiliation(
                request.headers, user.email, settings.heax_gateway_secret),
        )
        media_summary: dict | None = None
        if bundle_media:
            # 매핑 정본은 리포트 자신(`set_report.media`)이다 — 서비스가 읽는다.
            media_summary = await svc.attach_media(
                db, s, report, media=bundle_media, html=raw)
        onto_summary: dict | None = None
        if bundle_onto:
            # 후처리 꾸러미(같은 이름 줄기) — 실패해도 리포트 반입은 막지 않고 까닭을 돌려준다(사용자 결정 10-31 (가))
            try:
                got = await svc.attach_ontology(db, report, bundle_onto["data"], filename=bundle_onto["name"])
                onto_summary = {"ok": True, "loaded": got["counts"]["loaded"], "warnings": got["warnings"]}
            except OntoPackageError as exc:
                onto_summary = {"ok": False, "why": str(exc)}
    except ValueError as exc:
        if created_here:
            await sess_svc.delete_session(db, s)          # 신규 세션+K 통째로 정리(cascade+rmtree)
        elif krow is not None:
            await sess_svc.delete_file(db, krow)          # 기존 세션엔 방금 넣은 K만 회수
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    payload = {"session_id": s.id, "report_id": report.id, "kfile_id": kfile_id,
               "kind": report.kind, "n_cases": report.n_cases, "label": report.label,
               "source_kfile_id": report.source_kfile_id}
    if bundle_info:
        payload["bundle"] = bundle_info
    if media_summary:
        payload["media"] = media_summary
    if onto_summary:
        payload["ontology"] = onto_summary
    return ok(
        payload,
        message=f"{report.kind} 리포트 반입 완료 ({report.n_cases} 케이스"
                + ("· K파일 링크" if kfile_id else "") + ")",
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
    request: Request,
    report_id: str,
    body: ReportMetaPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """과제명·rev·설계안·DOE·원본 K파일 링크를 수동 설정(부분 갱신)."""
    r = await _require_owned_report(db, user, report_id)
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
    request: Request,
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트에 시뮬 조건(scenario.json)을 첨부 — 조건 요약 캐시 + K파일 자동매칭."""
    r = await _require_owned_report(db, user, report_id)   # 리포트를 바꾸는 일이라 소유자만
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
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트 검색 facet — 어떤 kind·과제·rev·설계안·방향컨셉·초점·심각도·높이가 있나 + 건수.
    목표를 정하기 전 '먼저 뭐가 있나'를 보는 화면. 소유분 + 같은 소속 공유분(관리자는 전사)."""
    return ok(await svc.report_facets(
        db, user.id, is_admin=user.is_system_admin,
        affiliation=verified_affiliation(request.headers, user.email, settings.heax_gateway_secret),
    ))


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
    request: Request,
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
    """조건으로 리포트 검색(결과 폭증 대비 다축 서버 필터). 소유분 + 같은 소속 공유분(관리자는 전사).

    같은 전각도라도 방향 컨셉(doe_strategy)·초점(focus)·조건(scenario_type)·높이별로
    각기 골라낼 수 있다. 전부 서버에서 걸러 슬라이스만 반환.
    """
    rows = await svc.find_reports(
        db, user.id, is_admin=user.is_system_admin,
        affiliation=verified_affiliation(request.headers, user.email, settings.heax_gateway_secret),
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
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id, request)
    return ok(ReportRead.model_validate(r).model_dump())


@router.get("/reports/{report_id}/query")
async def query_report_facts(
    request: Request,
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
    r = await _require_report(db, user, report_id, request)
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
    request: Request,
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
    await _require_report(db, user, report_id, request)
    rows = await svc.list_cases(db, report_id, sort=sort, order=order, limit=limit, offset=offset)
    return ok([CaseRead.model_validate(c).model_dump() for c in rows])


@router.get("/reports/{report_id}/cases/{case_key}")
async def get_report_case(
    request: Request,
    report_id: str,
    case_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_report(db, user, report_id, request)
    c = await svc.get_case(db, report_id, case_key)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "케이스를 찾을 수 없습니다.")
    return ok(CaseRead.model_validate(c).model_dump())


@router.get("/reports/{report_id}/parts")
async def report_part_risk(
    request: Request,
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """파트별 최악값과 발생 케이스(각도/위치) + 최소 안전율."""
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.part_risk(db, r, part_id))


@router.get("/reports/{report_id}/directional")
async def report_directional(
    request: Request,
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """방향 취약도 — 방향 범주(면/엣지/코너·F1~F6)별 최악. part_id 로 파트 한정."""
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.directional(db, r, part_id))


@router.get("/reports/{report_id}/scatter")
async def report_scatter(
    request: Request,
    report_id: str,
    metric: str = Query("peak_stress"),
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """방향 섭동 산포 분석(sphere) — 26 정준방향별 metric 산포(mean/std/CoV/최악)·민감도."""
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.scatter(db, r, metric=metric, part_id=part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/part-energy")
async def report_part_energy(
    request: Request,
    report_id: str,
    part_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """파트별 에너지(내부/운동) 시계열 — deep matsum(있을 때). part_id 로 한 파트만.
    sphere/impact 는 파트별 에너지 시계열이 없어 note 반환(글로벌 에너지는 /energy)."""
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.part_energy_series(db, r, part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/angle-stats")
async def report_angle_stats(
    request: Request,
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
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.angle_group_stats(
            db, r, metric=metric, part_id=part_id, category=category, angle_name=angle_name,
            near_lon=near_lon, near_lat=near_lat, tol_deg=tol_deg, top_parts=top_parts))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/geometry")
async def report_geometry(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공간 컨텍스트(부품 위치 시각화) — impact=디바이스 외곽선+파트 footprint(XY)+z범위.
    sphere/deep 은 각도 기반이라 부품 형상은 원본 렌더(iframe)에만 있다."""
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.geometry(db, r))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/blocks")
async def report_blocks(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """임베드 블록 **전수** 목록(원본 재파싱) — 이름·형태·크기·`read_by_parser`.

    ★`read_by_parser=false` 는 "쓸 수 없다" 가 아니라 "정규화가 아직 해석하지 않는다" 다.
    `/blocks/{name}` 으로 꺼낼 수 있다. 그 칸을 두는 이유는 **해석 여부를 숨기지 않으려는**
    것이다 — 전에는 생성기가 키를 늘려도 플랫폼이 조용히 뒤처졌다(핫스팟 군집이 그랬다).
    """
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.blocks(db, r))


@router.get("/reports/{report_id}/blocks/{name}")
async def report_block(
    request: Request,
    report_id: str,
    name: str,
    path: str | None = Query(default=None, description="하위 경로 `a.b.0.c`"),
    limit: int | None = Query(default=None, ge=1, description="배열 앞에서 n 개"),
    max_bytes: int = Query(default=200_000, ge=1_000, le=4_000_000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """블록 하나(또는 하위 경로). 크면 **잘랐다고 말한다** — 조용히 자르지 않는다."""
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.block(db, r, name, path=path, limit=limit, max_bytes=max_bytes))


@router.get("/reports/{report_id}/hotspots")
async def report_hotspots(
    request: Request,
    report_id: str,
    criterion: str | None = Query(default=None, description="von_mises · max_principal · …"),
    part_id: int | None = Query(default=None),
    top: int = Query(default=20, ge=1, le=500),
    order: str = Query(default="stress_max"),
    case_key: str | None = Query(default=None, description="sphere — 한 각도 런(폴더)만"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """핫스팟 군집(deep · sphere) — 어디가 뜨거운가. 중심·반경·요소수·피크시각(deep 은 부피·피크요소까지).

    sphere 는 각도 런마다 실린 군집을 각도와 함께 내고, 파트 × 기준마다 전 각도에서 가장 센 군집(`envelope`)을 붙인다.
    ★`stress_*` 정렬은 **절대값**이다(`min_principal` 기준의 값은 음수다).
    ★`uniform=true` 레코드의 군집은 '가장 뜨거운 곳' 이 아니다(값이 고르다는 뜻) — 그렇게 적는다. sphere 압축본에는
      그 표시가 없다(`compact_note`).
    """
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.hotspots(db, r, criterion=criterion, part_id=part_id,
                                 top=top, order=order, case_key=case_key))


@router.get("/reports/{report_id}/contact_profile")
async def report_contact_profile(
    request: Request,
    report_id: str,
    metric: str = Query(default="pf", pattern="^(pf|ti|tw)$",
                        description="pf=peak_force · ti=total_impulse · tw=total_work"),
    top: int = Query(default=30, ge=1, le=1000),
    case_key: str | None = Query(default=None, description="이 각도(위치)의 파트쌍 엣지를 함께"),
    matrix: bool = Query(default=False, description="히트맵용 pairs × 축 행렬(상한 있음)"),
    axis_top: int | None = Query(default=None, ge=1, le=5000,
                                 description="축 요약을 가장 센 각도(위치) 상위 N 개로"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """파트쌍 × 각도(위치) 접촉 스칼라(sphere · impact) — 어느 파트가 어느 파트를 언제 세게 미는가.

    ★None 은 '그 각도에 그 접촉이 없다' 이다(0 이 아니다). resolved=false 는 파트로 분해되지 않은 접촉이다.
    ★전 각도가 실린다 — 시계열 상세(`/energy`)가 상위 각도에만 있는 것과 다르다.
    """
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.contact_profile(db, r, metric=metric, top=top, case_key=case_key,
                                        matrix=matrix, axis_top=axis_top))


@router.get("/reports/{report_id}/clusters")
async def report_behavior_clusters(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """거동 아키타입 군집(impact) — 위치를 몇 가지 거동으로 묶은 결과.

    ★선언한 군집 수와 **실제로 쓰인** 수가 다르면 `degenerate` 로 말한다(실측 4 선언/1 사용).
    ★`is_mock=true` 면 합성이다 — 결론의 근거로 쓰면 안 된다.
    """
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.behavior_clusters(db, r))


@router.get("/reports/{report_id}/analytics")
async def report_analytics(
    request: Request,
    report_id: str,
    block: str | None = Query(default=None, description="한 블록만 — doe_analysis 등"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """큰 분석 블록 요약 — `doe_analysis`·`deep_analytics`·`insights`·`physics` 등.

    ★요약을 **다시 계산하지 않는다**: 하위 분석이 들고 있는 생성기 `summary` 를 그대로 올린다
    (다시 계산하면 HTML 화면의 숫자와 조용히 갈린다).
    ★`available=false`·`empty=true` 는 "값이 0" 이 아니라 **계산되지 않았다**는 뜻으로 적는다.
    원본은 `/blocks/{name}?path=…` 로 끝까지 되짚을 수 있다.
    """
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.analytics(db, r, block))


@router.get("/reports/{report_id}/media")
async def report_media(
    request: Request,
    report_id: str,
    case_key: str | None = Query(default=None),
    kind: str | None = Query(default=None, description="image | video"),
    role: str | None = Query(default=None, description="peak | view"),
    images_only: bool = Query(default=False, description="모델이 볼 수 있는 것만"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트에 붙은 **결과 이미지·영상** 목록. 내용은 세션 파일 다운로드로 받는다.

    ★결과 이미지는 리포트 HTML 안에 없고 **옆에 딸린 파일**이다 — 리포트를 번들(.zip/.tar.gz)로
    올려야 함께 들어온다. 비어 있으면 그렇게 말한다.
    ★`can_llm_view` 가 모델이 볼 수 있는지를 가른다(png/jpeg/gif/webp 는 보고 mp4 는 못 본다).
    """
    r = await _require_report(db, user, report_id, request)
    return ok(svc.media_list(r, case_key=case_key, kind=kind, role=role,
                             images_only=images_only))


@router.get("/reports/{report_id}/energy")
async def report_energy(
    request: Request,
    report_id: str,
    case_key: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에너지/접촉 상세(원본 재파싱). deep=에너지밸런스·접촉력, sphere/impact=하중경로 그래프.

    sphere/impact 는 HTML 압축본·중립 꼴을 둘 다 읽는다(`energy_flow.form`). `case_key` 에 상세가 없으면 **다른 각도로
    떨어지지 않고** null + 까닭이다 — 상세는 생성기가 상위 각도에만 싣는다(`detail_note`). 실제로 쓴 케이스는 `flow_case_key`.
    """
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.case_energy(db, r, case_key))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/cases/{case_key}/series")
async def report_part_series(
    request: Request,
    report_id: str,
    case_key: str,
    part_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """케이스·파트의 시계열(원본 재파싱, 다운샘플)."""
    r = await _require_report(db, user, report_id, request)
    try:
        return ok(await svc.part_series(db, r, case_key, part_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/reports/{report_id}/findings")
async def report_findings(
    request: Request,
    report_id: str,
    severity: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_report(db, user, report_id, request)
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


@router.post(
    "/reports/{report_id}/renders",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def attach_render(
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SceneForge 렌더 결과(C-11 — `render_result.json` + mp4 · 정지 화면을 담은 zip)를 리포트에 더한다.

    소유자만(리포트 수정은 소유자 — 요청서 §7). 기존 미디어를 지우지 않고 더하며, 같은 render_id 는 멱등이다.
    계약에 안 맞으면 422 — 아무것도 저장하지 않는다(전부 아니면 전무). 실패한 렌더(`ok: false`)는 기록만 남긴다.
    """
    r = await _require_owned_report(db, user, report_id)
    raw, _ = await _read_upload(file, what="렌더 결과 묶음")
    try:
        summary = await svc.attach_render(db, r, raw)
    except RenderResultError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"렌더 결과를 받지 않았다: {exc}")
    msg = ("이미 받은 렌더다 — 바꾼 것이 없다" if summary["already"]
           else "렌더 결과를 붙였다" if summary["ok"] else "실패한 렌더를 기록했다(붙인 그림 없음)")
    return ok(summary, message=msg)


@router.post(
    "/reports/{report_id}/cad",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def attach_cad(
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """StepForge fe_cad 묶음(C-6 가중치 · C-7 glb — manifest.json + 적힌 파일을 담은 zip)을 리포트의 형상으로 붙인다.

    소유자만(리포트 수정은 소유자). 리포트 하나에 묶음 하나 — 같은 묶음은 멱등, 다른 열쇠면 갈아 끼운다.
    받는 쪽 검사(파일 sha · 열쇠 · 가중치 배열 · glb 정점 수 · 이 리포트의 파트인가)에 안 맞으면 422 — 아무것도 저장하지 않는다.
    """
    r = await _require_owned_report(db, user, report_id)
    raw, _ = await _read_upload(file, what="CAD 묶음")
    try:
        summary = await svc.attach_cad(db, r, raw)
    except CadBundleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"CAD 묶음을 받지 않았다: {exc}")
    msg = ("이미 붙은 묶음이다 — 바꾼 것이 없다" if summary["already"]
           else "CAD 묶음을 갈아 끼웠다" if summary.get("replaced") else "CAD 묶음을 붙였다")
    return ok(summary, message=msg)


@router.post(
    "/reports/{report_id}/cae",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def attach_ontology(
    report_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """후처리 온톨로지 꾸러미(`<리포트 이름>.ontology.json`, `dynaforge.onto_package`)를 리포트에 싣는다 — 캠페인 수준만 행으로
    (사용자 결정 10-31 (가)). 소유자만. 받아들인 어휘 판 · 짝 HTML 지문 · 종류 · 런 키에 안 맞으면 422 — 아무것도 바꾸지 않는다.
    같은 바이트는 멱등, 다른 꾸러미면 그 리포트의 행을 통째로 바꾼다."""
    r = await _require_owned_report(db, user, report_id)
    raw, name = await _read_upload(file, what="온톨로지 꾸러미")
    try:
        summary = await svc.attach_ontology(db, r, raw, filename=name or "")
    except OntoPackageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"온톨로지 꾸러미를 받지 않았다: {exc}")
    loaded = summary["counts"]["loaded"]
    msg = ("이미 실은 꾸러미다 — 바꾼 것이 없다" if summary["already"]
           else "해석 온톨로지를 실었다 — " + " · ".join(f"{t.removeprefix('cae_')} {n}" for t, n in loaded.items() if n))
    return ok(summary, message=msg)


@router.get("/reports/{report_id}/cae")
async def report_ontology(
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트 하나의 해석 온톨로지(cae — 과제 · 개정 스위치와 무관하게 돈다) — 캠페인 · 파트 판정(위험한 것부터, 최악 런의 각도 · 위치) · 하중 경로(충격량 큰 것부터) ·
    접촉(양쪽 파트) · 소견 · 응력 집중. 리포트를 읽을 수 있는 사람만(소유 · 같은 소속). 안 실었으면 `loaded: false` 와 까닭."""
    r = await _require_report(db, user, report_id, request)
    return ok(await svc.ontology_view(db, r))


@router.get("/cae/parts")
async def find_cae_parts(
    request: Request,
    min_severity: str | None = Query(default=None, pattern="^(CRITICAL|WARNING|UNKNOWN|OK)$",
                                     description="이 판정 이상(CRITICAL > WARNING > UNKNOWN > OK)"),
    max_safety_factor: float | None = Query(default=None, ge=0, description="최소 안전율이 이 값 이하"),
    project: str | None = Query(default=None, description="과제(수동 메타 또는 리포트에 박힌 이름)"),
    kind: str | None = Query(default=None, pattern="^(deep|sphere|impact)$"),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트를 건너 파트 판정을 찾는다 — 위험한 것부터(판정 · 안전율 · 최악 응력 순으로 매긴 뒤 자른다). **읽을 수 있는 리포트의 것만**
    (소유 · 같은 소속, 관리자는 전사 — 리포트 검색과 같은 술어)."""
    rows = await svc.find_cae_rows(
        db, user.id, type_slug="cae_part", is_admin=user.is_system_admin,
        affiliation=verified_affiliation(request.headers, user.email, settings.heax_gateway_secret),
        project=project, kind=kind, min_severity=min_severity, max_safety_factor=max_safety_factor, limit=limit)
    return ok({"items": rows, "total": len(rows), "truncated": len(rows) >= limit})


@router.get("/cae/load-paths")
async def find_cae_load_paths(
    request: Request,
    sort: str = Query(default="impulse_max", pattern="^(impulse_max|engage_ratio|peak_force_max|work_max)$"),
    min_engage_ratio: float | None = Query(default=None, ge=0, le=1, description="맞닿은 런의 비율 하한(0~1)"),
    project: str | None = Query(default=None, description="과제(수동 메타 또는 리포트에 박힌 이름)"),
    kind: str | None = Query(default=None, pattern="^(deep|sphere|impact)$"),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트를 건너 하중 경로(파트 쌍)를 찾는다 — sort 가 큰 것부터. 읽을 수 있는 리포트의 것만."""
    rows = await svc.find_cae_rows(
        db, user.id, type_slug="cae_load_path", is_admin=user.is_system_admin,
        affiliation=verified_affiliation(request.headers, user.email, settings.heax_gateway_secret),
        project=project, kind=kind, min_engage_ratio=min_engage_ratio, sort=sort, limit=limit)
    return ok({"items": rows, "total": len(rows), "truncated": len(rows) >= limit})


@router.post("/reports/{report_id}/publish-datahub")
async def publish_report_to_datahub(
    request: Request,
    report_id: str,
    body: PublishDataHubBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """리포트를 AI Data Hub 의 범용 sim_report 레코드로 등재한다(과제/개발단계/BOM 연계)."""
    from app.reports.datahub import DataHubError, parse_stage

    # 외부(DataHub)에 이 리포트 명의로 레코드를 만드는 일이라 소유자만 — 읽기 공유와는 다르다.
    r = await _require_owned_report(db, user, report_id)
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
    request: Request,
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await _require_owned_report(db, user, report_id)
    await svc.delete_report(db, r)
    return ok(message="리포트가 삭제되었습니다.")
