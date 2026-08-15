# 충격 리포트 HTML 인제스트·정규화 저장과 구조화 질의(케이스/파트/랭킹) 서비스.
"""Service layer for impact/drop report ingestion + structured queries.

Ingest: store the uploaded HTML as a SessionFile(kind="report") WITHOUT the
K-file inspector (it is not a deck), parse the embedded data via
``app.reports.parser``, and persist a normalized ImpactReport + per-case rows.
Query helpers back the routes and the MCP analysis tools.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImpactCase, ImpactReport, Session, SessionFile
from app.reports import parser
from app.shared import storage

# 케이스 랭킹에 허용되는 정렬 키(승격 컬럼) — 그 외 값은 거부해 임의 컬럼 정렬을 막는다.
_SORT_COLS = {
    "max_stress": ImpactCase.max_stress,
    "max_g": ImpactCase.max_g,
    "max_disp": ImpactCase.max_disp,
    "min_safety_factor": ImpactCase.min_safety_factor,
}


async def _store_report_html(session: Session, filename: str, raw: bytes) -> SessionFile:
    """리포트 HTML 을 세션 디렉토리에 저장하고 SessionFile(kind=report) 로 기록.

    K파일 인스펙터를 태우지 않는다(리포트는 덱이 아님). meta 에 report 표식만 남긴다.
    """
    safe = storage.safe_filename(filename)
    sess_dir = storage.ensure_session_dir(session.user_id, session.id)
    dest = sess_dir / safe
    if dest.exists():
        stem, suffix = Path(safe).stem, Path(safe).suffix
        n = 1
        while (sess_dir / f"{stem}_{n}{suffix}").exists():
            n += 1
        safe = f"{stem}_{n}{suffix}"
        dest = sess_dir / safe
    await asyncio.to_thread(dest.write_bytes, raw)
    sha = await asyncio.to_thread(storage.sha256_of, dest)
    return SessionFile(
        session_id=session.id,
        filename=safe,
        rel_path=f"{session.storage_path}/{safe}",
        kind="report",
        size_bytes=dest.stat().st_size,
        sha256=sha,
        meta={"report": True},
    )


async def ingest_report(
    db: AsyncSession,
    session: Session,
    *,
    filename: str,
    raw: bytes,
    kind_hint: str | None = None,
    label: str | None = None,
) -> ImpactReport:
    """리포트 HTML 을 파싱·정규화해 ImpactReport + ImpactCase 로 저장한다.

    파싱 실패/케이스 없음(예: chunked 로 데이터가 분할돼 단일 HTML만으론 불완전)이면
    ValueError 를 던져 상위(라우트)에서 400 으로 변환한다.
    """
    text = raw.decode("utf-8", errors="replace")
    # 파싱을 스레드로 오프로드(대형 HTML JSON 로드가 이벤트 루프를 막지 않게).
    study = await asyncio.to_thread(parser.parse_html, text, kind_hint=kind_hint)
    cases = study.get("cases") or []
    if not cases:
        raise ValueError(
            "리포트에서 케이스를 추출하지 못했습니다(데이터가 비었거나 chunked 임베드일 수 있음)."
        )

    file_row = await _store_report_html(session, filename, raw)
    db.add(file_row)
    await db.flush()  # source_file_id 확보

    src = study.get("source") or {}
    proj = study.get("project") or {}
    rid = ulid.new().str
    report = ImpactReport(
        id=rid,
        session_id=session.id,
        user_id=session.user_id,
        kind=study["kind"],
        label=label or proj.get("name") or study["kind"],
        source_file_id=file_row.id,
        generator=src.get("generator"),
        generator_version=src.get("generator_version"),
        schema_str=src.get("schema"),
        project_name=proj.get("name"),
        doe_strategy=proj.get("doe_strategy"),
        test_dir=proj.get("test_dir"),
        sim_params=study.get("sim_params"),
        parts=study.get("parts"),
        findings=study.get("findings"),
        summary=study.get("summary"),
        n_cases=len(cases),
    )
    db.add(report)

    for c in cases:
        roll = c.get("rollup") or {}
        db.add(ImpactCase(
            report_id=rid,
            case_key=str(c.get("case_key")),
            identity=c.get("identity"),
            num_states=(c.get("meta") or {}).get("num_states"),
            success=(c.get("meta") or {}).get("success"),
            parts_metrics=c.get("parts_metrics"),
            max_stress=roll.get("max_stress"),
            max_g=roll.get("max_g"),
            max_disp=roll.get("max_disp"),
            min_safety_factor=roll.get("min_safety_factor"),
        ))

    await db.commit()
    await db.refresh(report)
    return report


async def list_reports(db: AsyncSession, session_id: str) -> list[ImpactReport]:
    return list((await db.execute(
        select(ImpactReport)
        .where(ImpactReport.session_id == session_id)
        .order_by(ImpactReport.created_at.desc())
    )).scalars())


async def get_owned_report(
    db: AsyncSession, user_id: int, report_id: str
) -> Optional[ImpactReport]:
    row = await db.get(ImpactReport, report_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def list_cases(
    db: AsyncSession,
    report_id: str,
    *,
    sort: str = "max_stress",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[ImpactCase]:
    col = _SORT_COLS.get(sort, ImpactCase.max_stress)
    # NULL 을 항상 뒤로 보내고 값 기준 정렬.
    direction = desc if order == "desc" else asc
    q = (
        select(ImpactCase)
        .where(ImpactCase.report_id == report_id)
        .order_by(col.is_(None), direction(col), ImpactCase.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(q)).scalars())


async def get_case(db: AsyncSession, report_id: str, case_key: str) -> Optional[ImpactCase]:
    return (await db.execute(
        select(ImpactCase).where(
            ImpactCase.report_id == report_id, ImpactCase.case_key == case_key
        )
    )).scalars().first()


async def part_risk(db: AsyncSession, report: ImpactReport, part_id: int | None = None) -> dict:
    """파트별 최악값과 그게 난 케이스를 케이스들을 훑어 계산한다.

    part_id 를 주면 그 파트만, 없으면 전 파트. sphere=최악 각도, impact=최악 위치,
    deep=단건. 안전율은 있으면 최소값을 함께 준다.
    """
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    name_of = {int(p["part_id"]): p.get("name") for p in (report.parts or []) if _isint(p.get("part_id"))}

    acc: dict[int, dict] = {}
    for c in cases:
        for pid_s, m in (c.parts_metrics or {}).items():
            try:
                pid = int(pid_s)
            except (TypeError, ValueError):
                continue
            if part_id is not None and pid != part_id:
                continue
            a = acc.setdefault(pid, {
                "part_id": pid, "part_name": name_of.get(pid),
                "worst_stress": {"value": None, "case_key": None},
                "worst_g": {"value": None, "case_key": None},
                "worst_disp": {"value": None, "case_key": None},
                "min_safety_factor": None,
            })
            _bump(a["worst_stress"], m.get("peak_stress"), c.case_key)
            _bump(a["worst_g"], m.get("peak_g"), c.case_key)
            _bump(a["worst_disp"], m.get("peak_disp"), c.case_key)
            sf = m.get("safety_factor")
            if sf is not None and (a["min_safety_factor"] is None or sf < a["min_safety_factor"]):
                a["min_safety_factor"] = sf

    parts = sorted(acc.values(), key=lambda a: (a["worst_stress"]["value"] is None, -(a["worst_stress"]["value"] or 0)))
    return {"report_id": report.id, "kind": report.kind, "parts": parts}


async def delete_report(db: AsyncSession, report: ImpactReport) -> None:
    # 원본 HTML SessionFile 도 함께 정리(있으면).
    if report.source_file_id is not None:
        f = await db.get(SessionFile, report.source_file_id)
        if f is not None:
            try:
                storage.abs_path(f.rel_path).unlink(missing_ok=True)
            except OSError:
                pass
            await db.delete(f)
    await db.delete(report)
    await db.commit()


def _bump(slot: dict, value, case_key: str) -> None:
    if value is not None and (slot["value"] is None or value > slot["value"]):
        slot["value"] = value
        slot["case_key"] = case_key


def _isint(v) -> bool:
    try:
        int(v)
        return True
    except (TypeError, ValueError):
        return False
