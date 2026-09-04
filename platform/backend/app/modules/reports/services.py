# 충격 리포트 HTML 인제스트·정규화 저장과 구조화 질의(케이스/파트/랭킹) 서비스.
"""Service layer for impact/drop report ingestion + structured queries.

Ingest: store the uploaded HTML as a SessionFile(kind="report") WITHOUT the
K-file inspector (it is not a deck), parse the embedded data via
``app.reports.parser``, and persist a normalized ImpactReport + per-case rows.
Query helpers back the routes and the MCP analysis tools.
"""
from __future__ import annotations

import asyncio
import math
import statistics
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.models import ImpactCase, ImpactReport, Session, SessionFile
from app.reports import parser
from app.reports.scenario import ScenarioParseError, summarize_scenario
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


_SEVERITY_RANK = {"CRITICAL": 3, "WARNING": 2, "INFO": 1}


def _search_axes(study: dict, cases: list[dict], scenario_summary: dict | None) -> dict:
    """리포트 검색·정렬용 승격 컬럼 값 계산(worst/severity/height/scenario_type)."""
    def _mx(key):
        xs = [c.get("rollup", {}).get(key) for c in cases]
        xs = [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool)]
        return max(xs) if xs else None
    sev = None
    for f in study.get("findings") or []:
        s = (f.get("severity") or "").upper()
        if _SEVERITY_RANK.get(s, 0) > _SEVERITY_RANK.get(sev or "", 0):
            sev = s
    sp = study.get("sim_params") or {}
    stype = None
    if scenario_summary:
        scens = scenario_summary.get("scenarios") or []
        stype = scens[0].get("source_type") if scens else None
    return {
        "worst_stress": _mx("max_stress"),
        "worst_g": _mx("max_g"),
        "max_severity": sev,
        "drop_height": sp.get("drop_height"),
        "scenario_type": stype,
    }


def build_eng_meta(
    project: str | None, dev_rev: str | None,
    variation: str | None = None, doe: str | None = None,
) -> dict | None:
    """과제/개발단계 수동 메타 → eng_meta dict. 전부 비면 None. dev_rev 형식 검증.

    DataHub eng_meta 와 같은 모양({project, dev_revision, design_variation, doe})이라
    등재 폼 기본값으로 그대로 쓰인다. 형식 오류는 ValueError.
    """
    if not any(x for x in (project, dev_rev, variation, doe)):
        return None
    meta: dict = {}
    if project:
        meta["project"] = project
    if dev_rev:
        from app.reports.datahub import DataHubError, parse_stage
        try:
            meta["dev_revision"] = parse_stage(dev_rev)
        except DataHubError as exc:
            raise ValueError(str(exc))
        meta["dev_revision"]["code"] = dev_rev
    if variation:
        meta["design_variation"] = variation
    if doe:
        st, _, case = doe.partition(":")
        meta["doe"] = {"study": st, **({"case": case} if case else {})}
    return meta


async def _resolve_session_kfile(
    db: AsyncSession, session_id: str, kfile_id: int
) -> SessionFile:
    """kfile_id 가 이 세션의 파일인지 검증. 아니면 ValueError."""
    f = await db.get(SessionFile, kfile_id)
    if f is None or f.session_id != session_id:
        raise ValueError(f"kfile_id {kfile_id} 는 이 세션의 파일이 아닙니다.")
    return f


async def _match_kfile_by_templates(
    db: AsyncSession, session_id: str, templates: list[str]
) -> int | None:
    """scenario.json 의 template(.k 파일명)으로 세션 내 K파일을 자동 매칭.

    같은 이름을 재업로드하면 세션이 foo_1.k 로 dedup 하므로, 정확 일치뿐 아니라
    ``stem_N.ext`` 변형까지 후보로 보고 **가장 최근 것(id 최대)** 을 고른다 —
    안 그러면 항상 낡은 첫 업로드에 매칭된다.
    """
    if not templates:
        return None
    import re as _re
    rows = list((await db.execute(
        select(SessionFile).where(SessionFile.session_id == session_id)
    )).scalars())
    for tpl in templates:
        p = Path(tpl)
        pat = _re.compile(rf"^{_re.escape(p.stem)}(_\d+)?{_re.escape(p.suffix)}$")
        cands = [f for f in rows if pat.match(f.filename)]
        if cands:
            return max(cands, key=lambda f: f.id).id
    return None


def _parse_scenario_summary(raw: bytes) -> dict:
    """scenario.json 바이트 → 조건 요약. 디스크 쓰기 전에 호출해 검증 실패 시 고아 파일이
    안 생기게 한다. 오류는 ValueError."""
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"scenario.json 파싱 실패: {exc}")
    try:
        return summarize_scenario(data)
    except ScenarioParseError as exc:
        raise ValueError(str(exc))


async def _store_scenario(
    db: AsyncSession, session: Session, raw: bytes, filename: str,
    summary: dict | None = None,
) -> tuple[SessionFile, dict]:
    """scenario.json 저장(SessionFile kind=scenario) + 조건 요약. 오류는 ValueError."""
    if summary is None:
        summary = _parse_scenario_summary(raw)
    safe = storage.safe_filename(filename or "scenario.json")
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
    row = SessionFile(
        session_id=session.id, filename=safe,
        rel_path=f"{session.storage_path}/{safe}", kind="scenario",
        size_bytes=dest.stat().st_size,
        sha256=await asyncio.to_thread(storage.sha256_of, dest),
        meta={"scenario": True},
    )
    db.add(row)
    await db.flush()
    return row, summary


async def ingest_report(
    db: AsyncSession,
    session: Session,
    *,
    filename: str,
    raw: bytes,
    kind_hint: str | None = None,
    label: str | None = None,
    scenario_raw: bytes | None = None,
    scenario_filename: str | None = None,
    kfile_id: int | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    focus: str | None = None,
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

    # ── 검증·파싱을 전부 먼저 — 실패 시(400) 디스크에 고아 파일이 안 남게 한다 ──
    proj = (study.get("project") or {})
    # eng_meta.project 미지정 시 임베드 project_name 으로 폴백 — 수동 안 채워도 과제로 찾아진다.
    eng_meta = build_eng_meta(project or proj.get("name"), dev_rev, variation, doe)
    scenario_summary = None
    if scenario_raw is not None:  # 0바이트 동반도 조용히 무시하지 않고 명시 오류
        scenario_summary = _parse_scenario_summary(scenario_raw)
    source_kfile_id = None
    if kfile_id is not None:
        source_kfile_id = (await _resolve_session_kfile(db, session.id, kfile_id)).id

    # ── 여기부터 디스크/DB 쓰기 ──
    file_row = await _store_report_html(session, filename, raw)
    db.add(file_row)
    await db.flush()  # source_file_id 확보

    scenario_file_id = None
    if scenario_raw is not None:
        scen_row, _ = await _store_scenario(
            db, session, scenario_raw, scenario_filename or "scenario.json",
            summary=scenario_summary,
        )
        scenario_file_id = scen_row.id

    if source_kfile_id is None and scenario_summary:
        source_kfile_id = await _match_kfile_by_templates(
            db, session.id, scenario_summary.get("templates") or []
        )

    src = study.get("source") or {}
    axes = _search_axes(study, cases, scenario_summary)
    rid = ulid.new().str
    report = ImpactReport(
        id=rid,
        session_id=session.id,
        user_id=session.user_id,
        kind=study["kind"],
        label=label or proj.get("name") or study["kind"],
        focus=focus or None,
        source_file_id=file_row.id,
        source_kfile_id=source_kfile_id,
        scenario_file_id=scenario_file_id,
        scenario=scenario_summary,
        eng_meta=eng_meta,
        worst_stress=axes["worst_stress"],
        worst_g=axes["worst_g"],
        max_severity=axes["max_severity"],
        drop_height=axes["drop_height"],
        scenario_type=axes["scenario_type"],
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


async def list_reports(
    db: AsyncSession, session_id: str, *, kfile_id: int | None = None
) -> list[ImpactReport]:
    """세션 리포트 목록. kfile_id 를 주면 그 K파일에 매달린 리포트만(1 K : N 결과 조회)."""
    q = select(ImpactReport).where(ImpactReport.session_id == session_id)
    if kfile_id is not None:
        q = q.where(ImpactReport.source_kfile_id == kfile_id)
    return list((await db.execute(q.order_by(ImpactReport.created_at.desc()))).scalars())


async def update_report_meta(
    db: AsyncSession,
    report: ImpactReport,
    *,
    label: str | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    kfile_id: int | None = None,
    focus: str | None = None,
) -> ImpactReport:
    """과제명·rev·초점 등 수동 메타 설정(부분 갱신). 형식/소속 오류는 ValueError.

    시맨틱: None=건드리지 않음, **빈 문자열("")=그 필드 삭제**, 값=설정. (빈 값을
    조용히 무시하면 '칸 비우고 저장'이 no-op 이 되어 낡은 과제로 등재될 수 있다.)
    kfile_id 는 세션 소속 검증.
    """
    if label is not None:
        report.label = label or None
    if focus is not None:
        report.focus = focus or None
    field_map = {  # 입력 인자 → eng_meta 키
        "project": ("project", project),
        "dev_rev": ("dev_revision", dev_rev),
        "variation": ("design_variation", variation),
        "doe": ("doe", doe),
    }
    if any(v is not None for _, (_, v) in field_map.items()):
        cur = dict(report.eng_meta or {})
        # ""=삭제 를 먼저 반영하고, 값이 있는 것만 build_eng_meta 로 검증·설정.
        for _, (meta_key, v) in field_map.items():
            if v == "":
                cur.pop(meta_key, None)
        new = build_eng_meta(project or None, dev_rev or None, variation or None, doe or None) or {}
        cur.update(new)
        report.eng_meta = cur or None
    if kfile_id is not None:
        report.source_kfile_id = (await _resolve_session_kfile(db, report.session_id, kfile_id)).id
    await db.commit()
    await db.refresh(report)
    return report


async def attach_scenario(
    db: AsyncSession,
    report: ImpactReport,
    *,
    raw: bytes,
    filename: str | None = None,
) -> ImpactReport:
    """이미 인제스트된 리포트에 scenario.json(시뮬 조건)을 첨부한다.

    저장+요약을 리포트에 캐시하고, K파일 미연결이면 template 로 자동 매칭 시도.
    """
    session = await db.get(Session, report.session_id)
    if session is None:
        raise ValueError("세션이 없습니다.")
    scen_row, summary = await _store_scenario(db, session, raw, filename or "scenario.json")
    report.scenario_file_id = scen_row.id
    report.scenario = summary
    scens = summary.get("scenarios") or []
    if scens and scens[0].get("source_type"):
        report.scenario_type = scens[0]["source_type"]  # 검색축 갱신
    if report.source_kfile_id is None:
        report.source_kfile_id = await _match_kfile_by_templates(
            db, report.session_id, summary.get("templates") or []
        )
    await db.commit()
    await db.refresh(report)
    return report


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


async def publish_to_datahub(
    db: AsyncSession,
    report: ImpactReport,
    *,
    hub_url: str,
    project: str | None = None,
    stage: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    unit: str = "mm-t-s",
    title: str | None = None,
) -> dict:
    """리포트를 AI Data Hub 의 범용 sim_report 레코드로 등재한다.

    project/stage 를 안 주면 리포트에 수동 설정된 eng_meta 를 기본값으로 쓴다
    (한 번 설정해두면 등재 때 재입력 불필요). 둘 다 없으면 ValueError(400).
    원본 HTML(source_file_id)을 첨부로 싣는다.
    """
    from app.reports import datahub

    em = report.eng_meta or {}
    project = project or em.get("project")
    stage = stage or (em.get("dev_revision") or {}).get("code")
    variation = variation or em.get("design_variation")
    if doe is None and isinstance(em.get("doe"), dict):
        d = em["doe"]
        doe = d.get("study") and (d["study"] + (f":{d['case']}" if d.get("case") else ""))
    if not project or not stage:
        raise ValueError(
            "project/stage 가 없습니다 — 요청에 넣거나 리포트 메타(PATCH /reports/{id})에 먼저 설정하세요."
        )

    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())

    html_name = "report.html"
    html_bytes = b""
    if report.source_file_id is not None:
        f = await db.get(SessionFile, report.source_file_id)
        if f is not None:
            html_name = f.filename
            p = storage.abs_path(f.rel_path)
            if p.exists():
                html_bytes = await asyncio.to_thread(p.read_bytes)
    if not html_bytes:
        raise ValueError("원본 리포트 HTML 을 찾을 수 없어 등재할 수 없습니다.")

    return await datahub.publish(
        report, cases, hub_url=hub_url, html_bytes=html_bytes, html_name=html_name,
        project=project, stage=stage, variation=variation, doe=doe, unit=unit, title=title,
    )


# fact 질의에 허용되는 물리량(parts_metrics 키) + 그 값이 나온 시각 키.
_QUERY_METRICS = {
    "peak_stress": "time_of_peak_stress", "peak_strain": None,
    "peak_g": "time_of_peak_g", "peak_disp": None, "peak_vel": None,
    "peak_plastic_strain": None,
    "peak_principal": None, "min_principal": None,
    "peak_principal_stress": None, "min_principal_stress": None,
    "peak_principal_strain": None, "min_principal_strain": None,
    "peak_vm_strain": None, "safety_factor": None,
    "peak_ie": "peak_ie_time", "peak_ke": "peak_ke_time",
    "final_ie": None, "final_ke": None,
}
_MAX_FACT_SCAN = 20000  # 한 질의가 훑는 케이스×파트 상한(서버 보호)


def _angle_of(identity: dict | None) -> dict:
    return ((identity or {}).get("angle") or {}) if isinstance(identity, dict) else {}


async def query_facts(
    db: AsyncSession,
    report: ImpactReport,
    *,
    part_id: int | None = None,
    category: str | None = None,
    angle_name: str | None = None,
    near_roll: float | None = None,
    near_pitch: float | None = None,
    near_yaw: float | None = None,
    angle_tol_deg: float | None = None,
    metric: str = "peak_stress",
    min_value: float | None = None,
    max_value: float | None = None,
    sort: str = "desc",
    limit: int = 200,
) -> dict:
    """리포트 내부를 서버에서 필터해 (케이스=각도 × 부품 × 물리량 = 값) fact 슬라이스를 준다.

    필터: part_id(특정 부품) · category(면/엣지/코너·F1~F6) · angle_name(F1_Back 등) ·
    near_(roll,pitch,yaw)+angle_tol_deg(각도 근접, 대원거리) · metric · min/max_value.
    정렬·limit 까지 서버에서 처리 — LLM 은 걸러진 결과만 받는다. 대형 sphere 안전.
    """
    from math import acos, cos, radians, sin
    if metric not in _QUERY_METRICS:
        raise ValueError(f"metric 은 {sorted(_QUERY_METRICS)} 중 하나여야 합니다.")

    # 각도 근접 타깃 벡터(주어졌을 때). identity 저장 규약과 동일하게 계산해 self-consistent.
    target_vec = None
    if angle_tol_deg is not None or any(x is not None for x in (near_roll, near_pitch, near_yaw)):
        lat, lon = radians(near_roll or 0.0), radians(near_pitch or 0.0)
        target_vec = (cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat))
        tol = angle_tol_deg if angle_tol_deg is not None else 15.0

    # SQL 선필터: report_id (+ 가능하면 category 를 JSONB 로). 나머지는 로드 후 판정.
    q = select(ImpactCase).where(ImpactCase.report_id == report.id)
    cases = list((await db.execute(q)).scalars())

    name_of = {int(p["part_id"]): p.get("name") for p in (report.parts or []) if _isint(p.get("part_id"))}
    tkey = _QUERY_METRICS[metric]
    facts: list[dict] = []
    scanned = 0
    truncated_scan = False
    for c in cases:
        cat = _category_of(c, report.kind)
        if category and cat != category:
            continue
        ang = _angle_of(c.identity)
        if angle_name and ang.get("name") != angle_name:
            continue
        if target_vec is not None:
            # 저장된 lon/lat(swap 규약 반영)을 우선 사용. 구버전 리포트는 raw 로 폴백.
            a_lat, a_lon = ang.get("lat"), ang.get("lon")
            if a_lat is None or a_lon is None:
                a_lat, a_lon = ang.get("roll") or 0.0, ang.get("pitch") or 0.0
            lat, lon = radians(a_lat), radians(a_lon)
            v = (cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat))
            dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v, target_vec))))
            if acos(dot) * 180.0 / 3.141592653589793 > tol:
                continue
        pm = c.parts_metrics or {}
        pids = [str(part_id)] if part_id is not None else list(pm.keys())
        for pid in pids:
            scanned += 1
            if scanned > _MAX_FACT_SCAN:
                truncated_scan = True
                break
            m = pm.get(pid)
            if not isinstance(m, dict):
                continue
            val = m.get(metric)
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            if min_value is not None and val < min_value:
                continue
            if max_value is not None and val > max_value:
                continue
            try:
                pid_i = int(pid)
            except (TypeError, ValueError):
                pid_i = pid
            fact = {
                "case_key": c.case_key,
                "identity": c.identity,
                "part_id": pid_i,
                "part_name": name_of.get(pid_i),
                "quantity": metric,
                "value": val,
            }
            if tkey and isinstance(m.get(tkey), (int, float)) and not isinstance(m.get(tkey), bool):
                fact["at_time"] = m.get(tkey)
            facts.append(fact)
        if truncated_scan:
            break

    facts.sort(key=lambda f: f["value"], reverse=(sort != "asc"))
    return {
        "report_id": report.id, "kind": report.kind, "metric": metric,
        "n_matched": len(facts),
        "returned": min(len(facts), limit),
        "truncated": len(facts) > limit or truncated_scan,
        "facts": facts[:limit],
    }


_REPORT_SORTS = {
    "created_at": ImpactReport.created_at,
    "worst_stress": ImpactReport.worst_stress,
    "worst_g": ImpactReport.worst_g,
    "drop_height": ImpactReport.drop_height,
}


def _find_reports_query(
    user_id: int,
    *,
    is_admin: bool,
    session_id: str | None = None,
    kind: str | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    kfile_id: int | None = None,
    focus: str | None = None,
    doe_strategy: str | None = None,
    scenario_type: str | None = None,
    drop_height: float | None = None,
    height_tol: float = 1.0,
    severity: str | None = None,
    min_worst_stress: float | None = None,
    min_worst_g: float | None = None,
    has_part: str | None = None,
    q_text: str | None = None,
    since=None,
    until=None,
):
    """find_reports/facets 공용 WHERE 절 빌더 — 모든 필터를 서버(SQL)에서 건다."""
    from sqlalchemy import func as _f, or_
    stmt = select(ImpactReport)
    if not is_admin:
        stmt = stmt.where(ImpactReport.user_id == user_id)
    if session_id:
        stmt = stmt.where(ImpactReport.session_id == session_id)
    if kind:
        stmt = stmt.where(ImpactReport.kind == kind)
    if kfile_id is not None:
        stmt = stmt.where(ImpactReport.source_kfile_id == kfile_id)
    if focus:
        stmt = stmt.where(ImpactReport.focus == focus)
    if doe_strategy:
        stmt = stmt.where(ImpactReport.doe_strategy == doe_strategy)
    if scenario_type:
        stmt = stmt.where(ImpactReport.scenario_type == scenario_type)
    if project:
        # 과제 = 수동 eng_meta.project 또는 임베드 project_name (수동 미기입분도 잡힌다).
        stmt = stmt.where(or_(
            ImpactReport.eng_meta["project"].astext == project,
            ImpactReport.project_name == project,
        ))
    if dev_rev:
        stmt = stmt.where(ImpactReport.eng_meta[("dev_revision", "code")].astext == dev_rev)
    if variation:
        stmt = stmt.where(ImpactReport.eng_meta["design_variation"].astext == variation)
    if doe:
        stmt = stmt.where(ImpactReport.eng_meta[("doe", "study")].astext == doe)
    if drop_height is not None:
        stmt = stmt.where(ImpactReport.drop_height.between(drop_height - height_tol, drop_height + height_tol))
    if severity:
        want = {"CRITICAL": ["CRITICAL"], "WARNING": ["CRITICAL", "WARNING"]}.get(severity.upper(), [severity.upper()])
        stmt = stmt.where(ImpactReport.max_severity.in_(want))
    if min_worst_stress is not None:
        stmt = stmt.where(ImpactReport.worst_stress >= min_worst_stress)
    if min_worst_g is not None:
        stmt = stmt.where(ImpactReport.worst_g >= min_worst_g)
    if has_part:
        # parts JSONB 배열에 그 부품명이 있는가 (부품 기준 리포트 검색). JSONB containment(@>)
        # 로 매칭 — 백슬래시 등 이스케이프를 Postgres 가 정확히 처리한다.
        stmt = stmt.where(ImpactReport.parts.contains([{"name": has_part}]))
    if q_text:
        like = f"%{q_text}%"
        stmt = stmt.where(or_(
            ImpactReport.label.ilike(like),
            ImpactReport.project_name.ilike(like),
            _f.coalesce(ImpactReport.eng_meta["project"].astext, "").ilike(like),
        ))
    if since is not None:
        stmt = stmt.where(ImpactReport.created_at >= since)
    if until is not None:
        stmt = stmt.where(ImpactReport.created_at <= until)
    return stmt


async def find_reports(
    db: AsyncSession,
    user_id: int,
    *,
    is_admin: bool = False,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0,
    **filters,
) -> list[ImpactReport]:
    """소유(또는 admin=전사) 리포트를 다축 조건으로 서버에서 필터·정렬 — 슬라이스만.

    필터(kwargs): kind·project(eng_meta OR project_name)·dev_rev·variation·doe·
    kfile_id·focus·doe_strategy·scenario_type·drop_height(±height_tol)·severity·
    min_worst_stress·min_worst_g·has_part·q_text·since·until.
    """
    stmt = _find_reports_query(user_id, is_admin=is_admin, **filters)
    col = _REPORT_SORTS.get(sort, ImpactReport.created_at)
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(col.is_(None), direction(col), ImpactReport.id.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars())


async def report_facets(db: AsyncSession, user_id: int, *, is_admin: bool = False) -> dict:
    """리포트 검색 facet — 어떤 kind·과제·rev·설계안·방향컨셉·초점·심각도가 있나 + 건수.

    목표지향 접근의 '먼저 뭐가 있나' 화면. distinct 값과 개수를 서버 집계로 준다.
    """
    from sqlalchemy import func as _f
    base = ImpactReport.user_id == user_id

    async def _count_by(expr):
        q = select(expr, _f.count()).group_by(expr)
        if not is_admin:
            q = q.where(base)
        rows = (await db.execute(q)).all()
        return [{"value": v, "count": n} for v, n in rows if v is not None]

    return {
        "kind": await _count_by(ImpactReport.kind),
        "project": await _count_by(_f.coalesce(ImpactReport.eng_meta["project"].astext, ImpactReport.project_name)),
        "dev_rev": await _count_by(ImpactReport.eng_meta[("dev_revision", "code")].astext),
        "design_variation": await _count_by(ImpactReport.eng_meta["design_variation"].astext),
        "doe_strategy": await _count_by(ImpactReport.doe_strategy),
        "scenario_type": await _count_by(ImpactReport.scenario_type),
        "focus": await _count_by(ImpactReport.focus),
        "max_severity": await _count_by(ImpactReport.max_severity),
        "drop_height": await _count_by(ImpactReport.drop_height),
    }


def _category_of(case: ImpactCase, kind: str) -> str:
    """케이스의 방향 범주. sphere=angle.category(face/edge/corner/…), impact=face, deep=single."""
    idt = case.identity or {}
    if kind == "sphere":
        return (idt.get("angle") or {}).get("category") or "unknown"
    if kind == "impact":
        return idt.get("face") or "unknown"
    return "single"


async def directional(db: AsyncSession, report: ImpactReport, part_id: int | None = None) -> dict:
    """방향 취약도. part_id 없으면 방향 범주별 최악, 있으면 그 파트의 범주별 최악.

    sphere=면/엣지/코너 등 방향 범주, impact=면(F1~F6). "어느 방향이 가장 위험한가".
    """
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    name_of = {int(p["part_id"]): p.get("name") for p in (report.parts or []) if _isint(p.get("part_id"))}

    agg: dict[str, dict] = {}
    for c in cases:
        cat = _category_of(c, report.kind)
        slot = agg.setdefault(cat, {
            "category": cat, "n_cases": 0,
            "worst_stress": {"value": None, "part_id": None, "part_name": None, "case_key": None},
            "worst_g": {"value": None, "part_id": None, "part_name": None, "case_key": None},
        })
        slot["n_cases"] += 1
        for pid_s, m in (c.parts_metrics or {}).items():
            try:
                pid = int(pid_s)
            except (TypeError, ValueError):
                continue
            if part_id is not None and pid != part_id:
                continue
            for key, metric in (("worst_stress", "peak_stress"), ("worst_g", "peak_g")):
                v = m.get(metric)
                if v is not None and (slot[key]["value"] is None or v > slot[key]["value"]):
                    slot[key] = {"value": v, "part_id": pid, "part_name": name_of.get(pid), "case_key": c.case_key}

    directions = sorted(
        agg.values(),
        key=lambda d: (d["worst_stress"]["value"] is None, -(d["worst_stress"]["value"] or 0)),
    )
    return {"report_id": report.id, "kind": report.kind, "part_id": part_id, "directions": directions}


def _available_metrics(cases: list[ImpactCase]) -> list[str]:
    """리포트에 실제로 존재하는 파트 물리량 키(시계열 *_ts·time_of_* 제외)."""
    keys: set[str] = set()
    for c in cases:
        for m in (c.parts_metrics or {}).values():
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                if k.startswith("time_of_") or k.endswith("_ts"):
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    keys.add(k)
    return sorted(keys)


def _percentile(s: list[float], q: float) -> float:
    """정렬된 표본의 백분위(선형보간). q∈[0,100]."""
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * (q / 100.0)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _stat_block(vals: list[float]) -> dict:
    """표준 통계 블록 — 어느 각도군이든 동일 스키마라 비교 가능. std 는 표본(n-1)."""
    s = sorted(vals)
    n = len(s)
    mean = statistics.fmean(s)
    std = statistics.stdev(s) if n > 1 else 0.0
    p25, p75 = _percentile(s, 25), _percentile(s, 75)
    return {
        "n": n, "mean": mean, "std": std, "cov": (std / mean) if mean else None,
        "min": s[0], "p05": _percentile(s, 5), "p25": p25, "median": _percentile(s, 50),
        "p75": p75, "p95": _percentile(s, 95), "max": s[-1],
        "iqr": p75 - p25, "range": s[-1] - s[0],
    }


def _part_breakdown(recs: list[dict], name_of: dict, top: int) -> dict:
    """각도군 안에서 부품별 위험(max)·민감도(CoV) 분해 — '이 방향군에서 어느 부품이'."""
    by_part: dict[int, list[float]] = {}
    for r in recs:
        for pid, v in r["per_part"].items():
            by_part.setdefault(pid, []).append(v)
    rows = []
    for pid, vs in by_part.items():
        mean = statistics.fmean(vs)
        std = statistics.stdev(vs) if len(vs) > 1 else 0.0
        rows.append({"part_id": pid, "part_name": name_of.get(pid), "n": len(vs),
                     "mean": mean, "max": max(vs), "cov": (std / mean) if mean else None})
    top_risk = sorted(rows, key=lambda d: -d["max"])[:top]
    sens = [d for d in rows if d["n"] >= 2 and d["cov"] is not None]
    most_sensitive = sorted(sens, key=lambda d: -(d["cov"] or 0))[:top]
    return {"top_risk": top_risk, "most_sensitive": most_sensitive}


async def angle_group_stats(
    db: AsyncSession, report: ImpactReport, *,
    metric: str = "peak_stress", part_id: int | None = None,
    category: str | None = None, angle_name: str | None = None,
    near_lon: float | None = None, near_lat: float | None = None,
    tol_deg: float = 15.0, top_parts: int = 5,
) -> dict:
    """특정 각도군의 표준 통계(분포 + 부품별 분해) — 한 도구, 전 선택 모드.

    각도군 선택(우선순위): near(임의 각도 콘, sphere) > angle_name(그 방향의 최근접 26-base
    퍼터베이션 구름, sphere) > category(면/엣지/코너 또는 impact 면) > 미지정(전체 그룹:
    sphere=base별, 그 외=범주별). part_id 미지정 시 케이스별 파트 최댓값을 대표값으로.
    모든 그룹이 동일 통계 스키마(n/mean/std/cov/min/p05/p25/median/p75/p95/max/iqr/range +
    worst + 부품별 top_risk·most_sensitive)라 리포트·방향 간 비교가 표준화된다.
    """
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    avail = _available_metrics(cases)
    base = {"report_id": report.id, "kind": report.kind, "metric": metric,
            "part_id": part_id, "available_metrics": avail}
    if metric not in avail:
        return {**base, "groups": [], "n_cases_total": 0,
                "note": f"이 리포트엔 '{metric}' 가 없습니다. 사용 가능: {avail}"}
    name_of = {int(p["part_id"]): p.get("name") for p in (report.parts or []) if _isint(p.get("part_id"))}
    is_sphere = report.kind == "sphere"

    recs: list[dict] = []
    for c in cases:
        ang = _angle_of(c.identity)
        per_part: dict[int, float] = {}
        for pid_s, m in (c.parts_metrics or {}).items():
            if not isinstance(m, dict):
                continue
            v = m.get(metric)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                try:
                    per_part[int(pid_s)] = float(v)
                except (TypeError, ValueError):
                    pass
        if part_id is not None:
            if part_id not in per_part:
                continue
            case_val, val_part = per_part[part_id], part_id
        else:
            if not per_part:
                continue
            val_part = max(per_part, key=lambda k: per_part[k])
            case_val = per_part[val_part]
        vec = parser._angle_vec(ang) if is_sphere else None
        bkey, berr = parser._nearest_base(vec) if vec else (None, None)
        recs.append({"case_key": c.case_key, "angle_name": ang.get("name"),
                     "category": _category_of(c, report.kind), "base_key": bkey, "base_err": berr,
                     "vec": vec, "case_val": case_val, "val_part": val_part, "per_part": per_part})

    # ── 각도군 선택 ──
    buckets: dict[str, dict] = {}   # label → {"cat","rep","recs"}
    if near_lon is not None and near_lat is not None:
        if not is_sphere:
            return {**base, "groups": [], "n_cases_total": len(recs),
                    "selection": {"mode": "near"}, "note": "near 각도 콘은 sphere 전용입니다."}
        selection = {"mode": "near", "near_lon": near_lon, "near_lat": near_lat, "tol_deg": tol_deg}
        la, lo = math.radians(near_lat), math.radians(near_lon)
        tvec = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
        picked = [r for r in recs if math.degrees(math.acos(
            max(-1.0, min(1.0, sum(a * b for a, b in zip(r["vec"], tvec)))))) <= tol_deg]
        if picked:
            buckets[f"near({near_lon:.0f},{near_lat:.0f})"] = {"cat": "near", "rep": None, "recs": picked}
    elif angle_name:
        if not is_sphere:
            return {**base, "groups": [], "n_cases_total": len(recs),
                    "selection": {"mode": "base"}, "note": "기준방향(퍼터베이션 구름) 선택은 sphere 전용입니다."}
        selection = {"mode": "base", "angle_name": angle_name}
        target = next((r for r in recs if r["angle_name"] == angle_name), None)
        if target and target["base_key"] is not None:
            key = target["base_key"]
            picked = [r for r in recs if r["base_key"] == key]
            buckets[f"base:{angle_name}"] = {"cat": parser._base_category(key), "rep": angle_name, "recs": picked}
    elif category:
        selection = {"mode": "category", "category": category}
        picked = [r for r in recs if r["category"] == category]
        if picked:
            buckets[category] = {"cat": category, "rep": None, "recs": picked}
    else:
        selection = {"mode": "all_bases" if is_sphere else "all_categories"}
        for r in recs:
            if is_sphere and r["base_key"] is not None:
                label = ",".join(str(x) for x in r["base_key"])
                b = buckets.setdefault(label, {"cat": parser._base_category(r["base_key"]),
                                               "rep": r["angle_name"], "rep_err": r["base_err"], "recs": []})
                if r["base_err"] is not None and r["base_err"] < (b.get("rep_err") or 1e9):
                    b["rep_err"], b["rep"] = r["base_err"], r["angle_name"]
                b["recs"].append(r)
            else:
                b = buckets.setdefault(r["category"], {"cat": r["category"], "rep": None, "recs": []})
                b["recs"].append(r)

    groups = []
    for label, b in buckets.items():
        rs = b["recs"]
        stats = _stat_block([r["case_val"] for r in rs])
        w = max(rs, key=lambda r: r["case_val"])
        g = {"group_key": label, "category": b["cat"], "representative": b.get("rep"),
             "stats": stats,
             "worst": {"value": w["case_val"], "angle_name": w["angle_name"],
                       "part_id": w["val_part"], "part_name": name_of.get(w["val_part"]),
                       "case_key": w["case_key"]}}
        if part_id is None:
            g["parts"] = _part_breakdown(rs, name_of, top_parts)
        groups.append(g)
    groups.sort(key=lambda d: -(d["stats"]["mean"] or 0))

    return {**base, "selection": selection, "n_cases_total": len(recs),
            "n_groups": len(groups), "groups": groups,
            "note": None if recs else "선택 조건에 맞는 케이스가 없습니다."}


async def _load_html_data(db: AsyncSession, report: ImpactReport) -> tuple[dict, str]:
    """원본 HTML 을 다시 파싱해 임베드 데이터(dict)와 kind 를 돌려준다."""
    if report.source_file_id is None:
        raise ValueError("원본 리포트 HTML 이 없어 상세를 복원할 수 없습니다.")
    f = await db.get(SessionFile, report.source_file_id)
    if f is None:
        raise ValueError("원본 리포트 파일 레코드가 없습니다.")
    p = storage.abs_path(f.rel_path)
    if not p.exists():
        raise ValueError("원본 리포트 HTML 실물이 없습니다.")
    text = await asyncio.to_thread(p.read_text, encoding="utf-8", errors="replace")
    data = await asyncio.to_thread(parser.extract_embedded_data, text)
    return data, report.kind


async def case_energy(db: AsyncSession, report: ImpactReport, case_key: str | None) -> dict:
    """케이스 에너지/접촉 상세(원본 재파싱). deep=에너지밸런스·접촉, sphere/impact=하중경로."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.case_energy, data, kind, case_key)


async def part_series(db: AsyncSession, report: ImpactReport, case_key: str, part_id: int) -> dict:
    """케이스·파트 시계열(원본 재파싱, 다운샘플)."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.part_series, data, kind, case_key, part_id)


async def part_energy_series(db: AsyncSession, report: ImpactReport, part_id: int | None = None) -> dict:
    """파트별 에너지(IE/KE) 시계열(원본 재파싱) — deep matsum. part_id 로 한정."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.part_energy_series, data, kind, part_id)


async def geometry(db: AsyncSession, report: ImpactReport) -> dict:
    """공간 컨텍스트(부품 위치 시각화용, 원본 재파싱). impact=디바이스 외곽선+파트 footprint."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.extract_geometry, data, kind)


async def scatter(db: AsyncSession, report: ImpactReport, *, metric: str = "peak_stress",
                  part_id: int | None = None) -> dict:
    """방향 섭동 산포 분석(sphere) — 원본 재파싱(swap 포함 authoritative angle 필요)."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.scatter_analysis, data, kind, metric=metric, part_id=part_id)


async def delete_report(db: AsyncSession, report: ImpactReport) -> None:
    # 원본 HTML + scenario.json SessionFile 도 함께 정리(있으면). K파일은 모델
    # 자산이라 남긴다(다른 리포트가 참조 가능).
    for fid in (report.source_file_id, report.scenario_file_id):
        if fid is None:
            continue
        f = await db.get(SessionFile, fid)
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
