# 충격 리포트 HTML 인제스트·정규화 저장과 구조화 질의(케이스/파트/랭킹) 서비스.
"""Service layer for impact/drop report ingestion + structured queries.

Ingest: store the uploaded HTML as a SessionFile(kind="report") WITHOUT the
K-file inspector (it is not a deck), parse the embedded data via
``app.reports.parser``, and persist a normalized ImpactReport + per-case rows.
Query helpers back the routes and the MCP analysis tools.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.models import ImpactCase, ImpactReport, Session, SessionFile
from app.reports import analyze, blockstore, cad_bundle, parser, render_result
from app.reports.scenario import ScenarioParseError, summarize_scenario
from app.modules.sessions import services as sess_svc
from app.shared import storage

# 케이스 랭킹에 허용되는 정렬 키(승격 컬럼) — 그 외 값은 거부해 임의 컬럼 정렬을 막는다.
_SORT_COLS = {
    "max_stress": ImpactCase.max_stress,
    "max_g": ImpactCase.max_g,
    "max_disp": ImpactCase.max_disp,
    "min_safety_factor": ImpactCase.min_safety_factor,
}



logger = logging.getLogger("koorm.reports")

# 곁파일(blockstore)을 새로 만드는 일은 한 번에 하나 — 1,000각도 리포트는 만드는 동안 전체를 메모리에 올린다(약 3 GB).
_BLOCK_BUILD_LOCK = asyncio.Lock()

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
    shared_affiliation: str = "",
    reservation: dict | None = None,
) -> ImpactReport:
    """리포트 HTML 을 파싱·정규화해 ImpactReport + ImpactCase 로 저장한다.

    파싱 실패/케이스 없음(예: chunked 로 데이터가 분할돼 단일 HTML만으론 불완전)이면
    ValueError 를 던져 상위(라우트)에서 400 으로 변환한다.

    `reservation` — 후처리 예약(7-1)이 반입할 때의 예약 원장(`job_key` · `conditions` …). `job_key` 가
    유일 키(`external_job_key`)가 되고, 리포트에 낙하 높이가 없으면 예약 조건의 `height` 로 채운다
    (리포트 자신의 값은 덮지 않는다). 같은 키가 이미 있으면 커밋에서 IntegrityError — 부르는 쪽이 다룬다.
    """
    text = raw.decode("utf-8", errors="replace")
    # 파싱을 스레드로 오프로드(대형 HTML JSON 로드가 이벤트 루프를 막지 않게).
    # 임베드 데이터는 한 번만 푼다 — sphere 면 같은 데이터로 곁파일(blockstore)을 쓴다.
    data = await asyncio.to_thread(parser.extract_embedded_data, text)
    del text
    study = await asyncio.to_thread(parser.parse_data, data, kind_hint=kind_hint)
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
        external_job_key=(reservation or {}).get("job_key") or None,
        reservation=reservation,
        # 반입 시점에 검증한 소속을 얼려 적는다 — 소유자가 나중에 소속을 옮겨도 이 리포트의
        # 읽기 공유 범위는 움직이지 않는다(요청서 §8). 빈 값이면 소유자만 읽는다.
        shared_affiliation=shared_affiliation or None,
        source_file_id=file_row.id,
        source_kfile_id=source_kfile_id,
        scenario_file_id=scenario_file_id,
        scenario=scenario_summary,
        eng_meta=eng_meta,
        worst_stress=axes["worst_stress"],
        worst_g=axes["worst_g"],
        max_severity=axes["max_severity"],
        drop_height=(axes["drop_height"] if axes["drop_height"] is not None
                     else ((reservation or {}).get("conditions") or {}).get("height")),
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

    # 개정 자동 잇기 — `eng_meta` 에 과제·코드가 있으면 찾거나 만들어 잇는다.
    # 커밋 **전에** 해서 한 트랜잭션으로 묶는다 — 리포트는 들어갔는데 선이 없는
    # 중간 상태를 만들지 않는다. 이을 것이 없으면(수동 메타 미기입) 조용히 지나간다.
    # ★이미 사람이 확정한 개정은 **건드리지 않는다**(`set_revision` 의 manual 보호).
    await _link_revision(db, report)
    await db.commit()
    await db.refresh(report)
    if report.kind == "sphere":
        # 곁파일은 상세 질의의 빠른 길일 뿐이다 — 못 써도 반입은 성공이고, 첫 상세 질의가 다시 만든다.
        try:
            async with _BLOCK_BUILD_LOCK:
                await asyncio.to_thread(blockstore.write, storage.abs_path(file_row.rel_path), data, file_row.sha256)
        except Exception as e:  # noqa: BLE001 — 어떤 실패든 반입을 되돌리지 않는다
            logger.warning("report %s: 곁파일을 못 썼다(%s) — 상세 질의는 원본을 읽는다", report.id, e)
    return report


async def attach_media(
    db: AsyncSession,
    session: Session,
    report: ImpactReport,
    *,
    media: list[dict],
    html: bytes,
) -> dict:
    """번들로 함께 온 결과 이미지·영상을 저장하고 리포트에 **붙인다**.

    `media` = `bundle.extract()` 의 `media` 항목들(`{path, data, kind, can_llm_view, bytes}`).
    `html` = 리포트 HTML 바이트 — 매핑 정본(`set_report.media`)을 **여기서** 읽는다.
    (인제스트가 안에서 이미 파싱하지만 그 결과를 돌려주지 않는다. 반입은 뜨거운 경로가
     아니므로 중복 파싱을 감수하고 **라우트가 파싱을 모르게** 둔다 — 경계가 단순해진다.)

    ★매핑은 **리포트가 선언한 것만** 쓴다. 선언이 없는 종류(deep)의 그림은 케이스에 묶지 않고
    목록으로만 둔다 — 파일명으로 추측한 매핑은 틀려도 그럴듯해서 가장 나쁘다.

    ★선언됐는데 번들에 없는 그림은 `missing_in_bundle` 로 **센다.** 조용히 빼면 받는 쪽이
    "그 위치는 그림이 없다" 로 읽는다(사실은 안 올라온 것이다).
    """
    try:
        data = parser.extract_embedded_data(html.decode("utf-8", "replace"))
    except Exception:          # noqa: BLE001 — 매핑을 못 읽어도 저장은 한다(목록으로만 둔다)
        data = {}
    decl = parser.report_media_map(data, report.kind)
    by_path = {d["path"]: d for d in decl["declared"]}
    rows: list[dict] = []
    stored_paths: set[str] = set()
    for item in media:
        path = item["path"]
        # ⚠ 하위 경로를 살려 저장한다 — 선언된 상대경로와 **같은 문자열**이어야 조인이 된다.
        f = await sess_svc.add_uploaded_file(
            db, session, filename=path, raw=item["data"], kind="media")
        d = by_path.get(path) or {}
        rows.append({
            "path": path,
            "stored_as": f.filename,
            "file_id": f.id,
            "bytes": item["bytes"],
            "kind": item["kind"],
            "can_llm_view": item["can_llm_view"],
            "case_key": d.get("case_key"),
            "set_name": d.get("set_name"),
            "set_title": d.get("set_title"),
            "role": d.get("role"),
            "face": d.get("face"),
            "declared": bool(d),
        })
        stored_paths.add(path)
    missing = [d for d in decl["declared"] if d["path"] not in stored_paths]
    report.media = rows
    # ⚠ **커밋**해야 한다. `ingest_report` 가 이미 커밋하고 돌아오므로, 여기서 flush 만 하면
    #   미디어 칸이 트랜잭션에 남아 **사라진다**(실측: 반입 응답은 16장 저장이라고 말하는데
    #   `/media` 가 0 을 냈다). 이 모듈의 다른 쓰기 함수들과 같은 규율이다.
    await db.commit()
    summary = {
        "n_stored": len(rows),
        "n_images": sum(1 for r in rows if r["can_llm_view"]),
        "n_videos": sum(1 for r in rows if not r["can_llm_view"]),
        "n_declared": decl["n_declared"],
        "n_mapped": sum(1 for r in rows if r["declared"]),
        "n_unmapped": sum(1 for r in rows if not r["declared"]),
        "n_empty_slots": decl["n_empty_slots"],
        "mapped_by": decl.get("mapped_by"),
    }
    if missing:
        summary["missing_in_bundle"] = [m["path"] for m in missing[:40]]
        summary["n_missing_in_bundle"] = len(missing)
        summary["missing_note"] = (
            "리포트가 선언한 그림 %d 장이 번들에 없다 — '그 위치는 그림이 없다' 가 아니라 "
            "**안 올라왔다**는 뜻이다" % len(missing))
    if decl.get("generator_note"):
        summary["generator_note"] = decl["generator_note"]
    if summary["n_unmapped"]:
        summary["unmapped_note"] = (
            "그림 %d 장은 리포트가 케이스를 선언하지 않아 목록으로만 둔다(파일명으로 "
            "추측하지 않는다)" % summary["n_unmapped"])
    return summary


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
    if any(v is not None for _, (_, v) in field_map.items()):
        # 과제·개정이 손으로 바뀌었다 — 선을 다시 본다. 사람이 개정 화면에서 확정한 것은
        # 그대로 두고(manual 보호), `eng_meta` 만 고친 경우에 선이 뒤처지지 않게 한다.
        await _link_revision(db, report)
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
    """소유자만. 수정·삭제는 이 자리를 쓴다(요청서 §7 — 수정·삭제는 소유자만)."""
    row = await db.get(ImpactReport, report_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def get_readable_report(
    db: AsyncSession, user_id: int, report_id: str, affiliation: str = ""
) -> Optional[ImpactReport]:
    """읽기(상세·판독·비교) 판정 — 소유자거나, 리포트에 얼린 소속과 읽는 사람의 소속이 같을 때.

    ⚠ 빈 소속은 매칭하지 않는다. 소속 없는 사람끼리 서로의 리포트를 읽게 되면
    '소속 공유' 가 사실상 전체 공개가 된다(shared/visibility.py 가 team·department 에서 지키는 규칙과 같다).
    affiliation 은 **요청마다 서명을 검증한 지금 값**이어야 한다 — 헤더를 그대로 넘기지 마라.
    """
    row = await db.get(ImpactReport, report_id)
    if row is None:
        return None
    if row.user_id == user_id:
        return row
    if affiliation and row.shared_affiliation and row.shared_affiliation == affiliation:
        return row
    return None


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
        hotspots=await _datahub_hotspot_summary(db, report),
    )


# DataHub 에 싣는 핫스팟 요약의 항목 수 — sphere 는 포락(파트 × 기준마다 가장 센 각도), deep 은 군집 순위
_DATAHUB_HOTSPOT_TOP = 10


async def _datahub_hotspot_summary(db: AsyncSession, report: ImpactReport) -> dict | None:
    """등재 레코드의 핫스팟 요약(결정 7A, 10-24) — `/hotspots` 와 같은 계산(parser.hotspot_clusters)을 그대로 쓴다.

    sphere 는 포락 상위 N(가장 센 각도 · 그 값 · 군집이 난 각도 수), deep 은 군집 상위 N. 핫스팟이 없는 리포트 · 다른 종류는 None
    (레코드에 키를 두지 않는다 — 없는 것을 빈 목록으로 지어내지 않는다).
    """
    if report.kind not in ("deep", "sphere"):
        return None
    hs = await hotspots(db, report, top=_DATAHUB_HOTSPOT_TOP)
    if not hs.get("available"):
        return None
    out = {k: hs.get(k) for k in ("n_clusters", "criteria", "parts", "order", "order_note")}
    if "envelope" in hs:
        out["envelope"] = hs["envelope"]
        out["envelope_note"] = hs.get("envelope_note")
        if hs.get("envelope_truncated"):
            out["envelope_truncated"] = hs["envelope_truncated"]
    else:
        out["clusters"] = hs.get("clusters")
        if hs.get("truncated"):
            out["truncated"] = hs["truncated"]
    return out


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
    near_(roll,pitch)+angle_tol_deg(각도 근접, 대원거리; yaw 는 낙하방향 무영향이라 무시) · metric · min/max_value.
    정렬·limit 까지 서버에서 처리 — LLM 은 걸러진 결과만 받는다. 대형 sphere 안전.
    """
    from math import acos, cos, radians, sin
    if metric not in _QUERY_METRICS:
        raise ValueError(f"metric 은 {sorted(_QUERY_METRICS)} 중 하나여야 합니다.")

    # SQL 선필터: report_id. 나머지는 로드 후 판정.
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())

    # 각도 근접 타깃 벡터 — 후보는 저장 lon/lat(swap 반영)을 쓰므로, 타깃도 같은 규약으로
    # 투영해야 정합한다(과거엔 raw roll/pitch 를 lat/lon 으로 직접 써 swap=true 서 어긋났다).
    # 리포트 단위 swap 은 케이스에서 취득(같은 DOE → 동일). yaw 는 낙하 방향 무영향이라 무시.
    target_vec = None
    if angle_tol_deg is not None or any(x is not None for x in (near_roll, near_pitch)):
        rep_swap = next((bool(_angle_of(c.identity).get("swap")) for c in cases
                         if _angle_of(c.identity).get("swap") is not None), False)
        t_lon, t_lat = parser._angle_lonlat(
            {"roll": near_roll or 0.0, "pitch": near_pitch or 0.0, "swap": rep_swap})
        lat, lon = radians(t_lat), radians(t_lon)
        target_vec = (cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat))
        tol = angle_tol_deg if angle_tol_deg is not None else 15.0

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


def _readable_scope(user_id: int, affiliation: str = ""):
    """검색·facet 의 '읽을 수 있는 것' 범위 — 소유분 + 같은 소속으로 얼려 반입된 것.

    빈 소속은 매칭하지 않는다(get_readable_report 와 같은 규칙). 상세를 열 수 있는 것과
    찾을 수 있는 것이 어긋나면 비교가 안 되므로 두 자리가 같은 술어를 쓴다.
    """
    own = ImpactReport.user_id == user_id
    if not affiliation:
        return own
    from sqlalchemy import or_ as _or
    return _or(own, ImpactReport.shared_affiliation == affiliation)


def _find_reports_query(
    user_id: int,
    *,
    is_admin: bool,
    affiliation: str = "",
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
        stmt = stmt.where(_readable_scope(user_id, affiliation))
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
    affiliation: str = "",
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
    stmt = _find_reports_query(user_id, is_admin=is_admin, affiliation=affiliation, **filters)
    col = _REPORT_SORTS.get(sort, ImpactReport.created_at)
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(col.is_(None), direction(col), ImpactReport.id.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars())


async def report_facets(
    db: AsyncSession, user_id: int, *, is_admin: bool = False, affiliation: str = ""
) -> dict:
    """리포트 검색 facet — 어떤 kind·과제·rev·설계안·방향컨셉·초점·심각도가 있나 + 건수.

    목표지향 접근의 '먼저 뭐가 있나' 화면. distinct 값과 개수를 서버 집계로 준다.
    """
    from sqlalchemy import func as _f
    base = _readable_scope(user_id, affiliation)

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
    """케이스의 방향 범주(analyze 코어에 위임). query_facts 등이 참조."""
    return analyze._category_of(case.identity or {}, kind)


async def directional(db: AsyncSession, report: ImpactReport, part_id: int | None = None) -> dict:
    """방향 취약도(범주별 최악) — DB 케이스 로드 후 analyze 코어에 위임(CLI 공유)."""
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    res = analyze.directional(cases, report.kind, report.parts, part_id)
    return {"report_id": report.id, **res}


# 분석 프리미티브·각도군 코어는 analyze(DB-free)로 옮겼다 — 서비스·CLI 공유. 이름 하위호환 재노출.
_available_metrics = analyze.available_metrics


async def angle_group_stats(
    db: AsyncSession, report: ImpactReport, *,
    metric: str = "peak_stress", part_id: int | None = None,
    category: str | None = None, angle_name: str | None = None,
    near_lon: float | None = None, near_lat: float | None = None,
    tol_deg: float = 15.0, top_parts: int = 5,
) -> dict:
    """특정 각도군의 표준 통계(분포 + 부품별 분해). DB 케이스를 로드해 analyze 코어에 위임한다
    (같은 로직을 CLI 도 공유). 선택 우선순위·스키마는 analyze.angle_group_stats 참조."""
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    res = analyze.angle_group_stats(
        cases, report.kind, report.parts, metric=metric, part_id=part_id,
        category=category, angle_name=angle_name, near_lon=near_lon, near_lat=near_lat,
        tol_deg=tol_deg, top_parts=top_parts)
    return {"report_id": report.id, **res}


async def _report_source(db: AsyncSession, report: ImpactReport) -> tuple[Path, SessionFile]:
    if report.source_file_id is None:
        raise ValueError("원본 리포트 HTML 이 없어 상세를 복원할 수 없습니다.")
    f = await db.get(SessionFile, report.source_file_id)
    if f is None:
        raise ValueError("원본 리포트 파일 레코드가 없습니다.")
    p = storage.abs_path(f.rel_path)
    if not p.exists():
        raise ValueError("원본 리포트 HTML 실물이 없습니다.")
    return p, f


async def _load_html_data(db: AsyncSession, report: ImpactReport) -> tuple[dict, str]:
    """원본 HTML 을 다시 파싱해 임베드 데이터(dict)와 kind 를 돌려준다."""
    p, _f = await _report_source(db, report)
    text = await asyncio.to_thread(p.read_text, encoding="utf-8", errors="replace")
    data = await asyncio.to_thread(parser.extract_embedded_data, text)
    return data, report.kind


async def _load_detail_data(db: AsyncSession, report: ImpactReport, *,
                            case_key: str | None = None,
                            case_index: int | None = None) -> tuple[dict, str]:
    """상세 질의용 데이터. sphere 는 곁파일의 가벼운 본(+ 고른 각도의 시계열), 나머지는 원본.

    가벼운 본에는 `results[i].parts[pid].*_ts` 가 없다 — 시계열이 필요한 자리는 그 각도를 고르거나
    (case_key · case_index) 원본(`_load_html_data`)을 쓴다. 곁파일이 없거나 원본 sha 와 다르면 한 번
    만들고, 만드는 동안 이미 쥔 전체 데이터를 그대로 돌려준다.
    """
    if report.kind != "sphere":
        return await _load_html_data(db, report)
    p, f = await _report_source(db, report)
    meta = await asyncio.to_thread(blockstore.read_meta, p)
    if not blockstore.is_fresh(meta, f.sha256):
        async with _BLOCK_BUILD_LOCK:
            meta = await asyncio.to_thread(blockstore.read_meta, p)
            if not blockstore.is_fresh(meta, f.sha256):
                data, kind = await _load_html_data(db, report)
                try:
                    await asyncio.to_thread(blockstore.write, p, data, f.sha256)
                except OSError as e:
                    logger.warning("report %s: 곁파일을 못 썼다(%s) — 원본으로 답한다", report.id, e)
                return data, kind
    try:
        slim = await asyncio.to_thread(blockstore.load_slim, p)
        n = int(meta.get("n_cases") or 0)
        idx = (meta.get("case_index") or {}).get(case_key) if case_key is not None else case_index
        if idx is not None and -n <= idx < n:
            idx %= n
            heavy = await asyncio.to_thread(blockstore.load_case, p, idx)
            blockstore.merge_case(slim, idx, heavy)
    except (OSError, ValueError, KeyError, IndexError) as e:
        # 곁파일이 깨졌다 — 지우고 원본으로 답한다(다음 질의가 다시 만든다).
        logger.warning("report %s: 곁파일을 못 읽었다(%s) — 지우고 원본으로 답한다", report.id, e)
        await asyncio.to_thread(blockstore.remove, p)
        return await _load_html_data(db, report)
    return slim, report.kind


async def case_energy(db: AsyncSession, report: ImpactReport, case_key: str | None) -> dict:
    """케이스 에너지/접촉 상세. deep=에너지밸런스·접촉, sphere/impact=하중경로(최상위 energy_flows)."""
    data, kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(parser.case_energy, data, kind, case_key)


async def part_series(db: AsyncSession, report: ImpactReport, case_key: str, part_id: int) -> dict:
    """케이스·파트 시계열(다운샘플). sphere 는 곁파일에서 그 각도만 합쳐 읽는다."""
    data, kind = await _load_detail_data(db, report, case_key=case_key)
    return await asyncio.to_thread(parser.part_series, data, kind, case_key, part_id)


async def part_energy_series(db: AsyncSession, report: ImpactReport, part_id: int | None = None) -> dict:
    """파트별 에너지(IE/KE) 시계열(원본 재파싱) — deep matsum. part_id 로 한정."""
    data, kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.part_energy_series, data, kind, part_id)


async def blocks(db: AsyncSession, report: ImpactReport) -> dict:
    """임베드 블록 전수 목록 — `read_by_parser` 로 해석 여부를 숨기지 않는다.

    sphere 는 곁파일을 만들 때 **전체 기준**으로 센 목록을 쓴다(가벼운 본으로 세면 results 가 작게 보인다).
    """
    data, _kind = await _load_detail_data(db, report)
    if report.kind == "sphere":
        p, f = await _report_source(db, report)
        meta = await asyncio.to_thread(blockstore.read_meta, p)
        if blockstore.is_fresh(meta, f.sha256):
            return meta["blocks"]
    return await asyncio.to_thread(parser.list_blocks, data)


async def block(db: AsyncSession, report: ImpactReport, name: str, *,
                path: str | None = None, limit: int | None = None,
                max_bytes: int = 200_000) -> dict:
    """블록 하나(또는 하위 경로)를 꺼낸다 — 무엇이든 끝까지 되짚을 수 있게.

    sphere 의 `results` 는 가벼운 본에 시계열이 없다. `results.<순번>…` 이면 그 각도를 합쳐 읽고,
    `results` 통째면 원본을 읽는다 — 시계열이 조용히 빠진 값을 내지 않는다.
    """
    first = (path or "").split(".")[0]
    if report.kind == "sphere" and name == "results":
        if first.lstrip("-").isdigit():
            data, _kind = await _load_detail_data(db, report, case_index=int(first))
        else:
            data, _kind = await _load_html_data(db, report)
    else:
        data, _kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(parser.get_block, data, name, path, max_bytes, limit)


async def hotspots(db: AsyncSession, report: ImpactReport, *, criterion: str | None = None,
                   part_id: int | None = None, top: int = 20,
                   order: str = "stress_max", case_key: str | None = None) -> dict:
    """핫스팟 군집(deep · sphere) — 파트·판정기준별 공간 군집. sphere 는 각도 런마다 · 포락(envelope) 포함."""
    data, _kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(
        parser.hotspot_clusters, data, criterion=criterion, part_id=part_id,
        top=top, order=order, case_key=case_key)


async def contact_profile(db: AsyncSession, report: ImpactReport, *, metric: str = "pf", top: int = 30,
                          case_key: str | None = None, matrix: bool = False,
                          axis_top: int | None = None) -> dict:
    """파트쌍 × 각도(위치) 접촉 스칼라(sphere · impact)."""
    data, kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(
        parser.contact_profile, data, kind, metric=metric, top=top, case_key=case_key,
        matrix=matrix, axis_top=axis_top)


async def behavior_clusters(db: AsyncSession, report: ImpactReport) -> dict:
    """거동 아키타입 군집(impact)."""
    data, _kind = await _load_html_data(db, report)
    return await asyncio.to_thread(parser.behavior_clusters, data)


async def analytics(db: AsyncSession, report: ImpactReport, block_name: str | None = None) -> dict:
    """큰 분석 블록 요약 — 생성기 `summary` 를 그대로 올린다(다시 계산하지 않는다)."""
    data, _kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(parser.analytics_summary, data, block_name)


def media_list(report: ImpactReport, *, case_key: str | None = None,
               kind: str | None = None, role: str | None = None,
               images_only: bool = False) -> dict:
    """리포트에 붙은 결과 이미지·영상 목록 — DB 칸만 읽는다(재파싱 없음).

    ★`can_llm_view` 를 그대로 낸다. 모델은 png/jpeg/gif/webp 를 보고 **mp4 는 못 본다** —
    그 구분을 숨기면 "영상을 보여 줬는데 못 봤다" 가 된다.
    """
    rows = list(report.media or [])
    total = len(rows)
    if case_key:
        rows = [r for r in rows if r.get("case_key") == case_key]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    if role:
        rows = [r for r in rows if r.get("role") == role]
    if images_only:
        rows = [r for r in rows if r.get("can_llm_view")]
    cases = sorted({r.get("case_key") for r in (report.media or []) if r.get("case_key")})
    out = {
        "report_id": report.id,
        "kind": report.kind,
        "n_total": total,
        "n_returned": len(rows),
        "n_images": sum(1 for r in rows if r.get("can_llm_view")),
        "n_videos": sum(1 for r in rows if not r.get("can_llm_view")),
        "cases_with_media": cases,
        "filter": {"case_key": case_key, "kind": kind, "role": role,
                   "images_only": images_only},
        "media": rows,
    }
    if not total:
        out["note"] = ("이 리포트에는 붙은 그림이 없다 — 결과 이미지는 HTML 안에 없고 **옆에 "
                       "딸린 파일**이라, 리포트를 번들(.zip/.tar.gz)로 올려야 함께 들어온다")
    return out


async def geometry(db: AsyncSession, report: ImpactReport) -> dict:
    """공간 컨텍스트(부품 위치 시각화용). impact=디바이스 외곽선+파트 footprint."""
    data, kind = await _load_detail_data(db, report)
    return await asyncio.to_thread(parser.extract_geometry, data, kind)


async def scatter(db: AsyncSession, report: ImpactReport, *, metric: str = "peak_stress",
                  part_id: int | None = None) -> dict:
    """방향 섭동 산포 분석(sphere) — 각도(swap 포함)와 스칼라만 쓴다."""
    data, kind = await _load_detail_data(db, report)
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
                blockstore.remove(storage.abs_path(f.rel_path))  # 곁파일(sphere 상세 질의용)도 같이
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


async def _link_revision(db, report) -> None:
    """`eng_meta` 로 개발 개정에 잇는다. **실패가 인제스트를 죽이지 않는다.**

    리포트가 들어오는 길은 여럿이고(업로드 · 번들 · MCP) 과제 메타는 **선택**이다. 여기서
    예외를 올리면 메타를 안 채운 리포트가 **아예 안 들어온다** — 그것이 훨씬 비싸다.
    흠은 로그로만 남긴다(화면은 `ontology.services.mismatch` 가 따로 말한다).
    """
    from app.modules.ontology import services as onto
    try:
        got = await onto.link_from_eng_meta(db, report)
    except Exception:                       # noqa: BLE001
        logger.exception("개정 잇기 실패 — report %s", report.id)
        return
    if not got.get("ok") and got.get("error") != "nothing_to_link":
        logger.warning("개정 잇기 거절 — report %s: %s", report.id, got.get("detail"))


# ── 렌더 결과(C-11) — SceneForge 가 그린 mp4 · 정지 화면을 리포트에 더한다 ─────────────────────────
def _render_media_entry(f: SessionFile, o: dict, checked: dict, meta: dict, prefix: str, rid: str) -> dict:
    """렌더 출력 하나 → 리포트 미디어 항목(번들 미디어와 같은 칸 + render_id · render)."""
    return {
        "path": prefix + o["file"], "stored_as": f.filename, "file_id": f.id, "bytes": len(o["data"]),
        "sha256": o["sha256"].lower(),
        "kind": "video" if o["kind"] == "mp4" else "image",
        "can_llm_view": o["kind"] == "still",          # 모델은 영상을 못 본다
        "case_key": checked["case_key"],
        "set_name": (meta.get("template") or {}).get("id") if isinstance(meta.get("template"), dict) else None,
        "set_title": meta.get("deform_label"),
        "role": "render", "face": None, "declared": False, "render_id": rid,
        # 화면이 영상 옆에 글로 보일 것 — 글씨는 영상에도 새겨져 있다(SceneForge)
        "render": {**{k: o.get(k) for k in ("width", "height", "fps", "frames", "time_window_ms", "slowmo", "time_ms")},
                   "mode": meta.get("mode"), "deform_scale": meta.get("deform_scale"),
                   "notice": meta.get("notice"), "frame": meta.get("frame")},
    }


async def attach_render(db: AsyncSession, report: ImpactReport, raw: bytes) -> dict:
    """SceneForge 렌더 결과 zip(`render_result.json` + 출력)을 리포트에 **더한다**.

    번들 반입의 `attach_media` 와 달리 기존 미디어를 지우지 않는다(반입 규칙 10-29 합의).
    - 검사(`render_result.check`)에 걸리면 RenderResultError — 아무것도 저장하지 않는다(전부 아니면 전무).
    - 같은 render_id · 같은 출력(sha)이면 그대로 둔다(멱등). 출력이 다르면 그 렌더의 옛 파일 · 항목만 바꾼다.
    - 같은 render_id 가 성공 · 실패를 바꿔 오면 거절한다(한 렌더는 한 결과다).
    - `ok: false` 는 그림 없이 렌더 기록(`report.renders`)에만 남긴다.
    """
    from datetime import datetime, timezone

    result, files = render_result.unzip(raw)
    case_keys = set((await db.execute(
        select(ImpactCase.case_key).where(ImpactCase.report_id == report.id))).scalars())
    checked = render_result.check(result, files, report_id=report.id, case_keys=case_keys)
    rid = checked["render_id"]
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    prior = next((r for r in (report.renders or []) if r.get("render_id") == rid), None)
    if prior is not None and bool(prior.get("ok")) != checked["ok"]:
        raise render_result.RenderResultError(
            f"같은 render_id({rid})가 다른 결과로 왔다(전 {'성공' if prior.get('ok') else '실패'}) — 한 렌더는 한 결과다")
    prefix = f"renders/{rid}/"
    new_sig = sorted((prefix + o["file"], o["sha256"].lower()) for o in checked["outputs"])
    old_media = [m for m in (report.media or []) if m.get("render_id") == rid]
    if prior is not None and sorted((m.get("path"), m.get("sha256")) for m in old_media) == new_sig:
        return {"render_id": rid, "ok": checked["ok"], "already": True, "stored": 0,
                "media_total": len(report.media or []), "warnings": prior.get("warnings") or []}

    session = await db.get(Session, report.session_id)
    if session is None:
        raise render_result.RenderResultError("리포트의 세션을 찾지 못했다")
    # 그 렌더의 옛 파일을 걷어 낸다 — 남겨 두면 저장 함수가 이름을 `_1` 로 피해 가며 쌓인다
    for f in (await db.execute(select(SessionFile).where(
            SessionFile.session_id == session.id, SessionFile.filename.like(prefix + "%")))).scalars().all():
        await sess_svc.delete_file(db, f)

    added: list[dict] = []
    stored: list[SessionFile] = []
    try:
        for o in checked["outputs"]:
            f = await sess_svc.add_uploaded_file(db, session, filename=prefix + o["file"], raw=o["data"], kind="media")
            stored.append(f)
            added.append(_render_media_entry(f, o, checked, meta, prefix, rid))
        if checked["ok"]:
            # 출처 — 받은 render_result.json 도 그 렌더 자리에 둔다
            stored.append(await sess_svc.add_uploaded_file(
                db, session, filename=prefix + render_result.RESULT_NAME,
                raw=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"), kind="generated"))
    except Exception:
        # 저장 도중 깨지면(디스크 등) 이번에 넣은 파일을 걷어 낸다 — 반쯤 붙은 렌더를 남기지 않는다
        for f in stored:
            await sess_svc.delete_file(db, f)
        raise

    warnings = [str(w) for w in (result.get("warnings") or [])]
    inputs = meta.get("inputs") if isinstance(meta.get("inputs"), dict) else {}
    if inputs.get("c3_manifest_sha256"):
        # 지어내지 않는다 — DynaForge 가 C-3 manifest 를 아직 내지 않아 맞춰 볼 정본이 없다
        warnings.append("C-3 manifest 를 DynaForge 가 아직 내지 않아 그 sha256 을 대조하지 못했다")
    elif inputs.get("s1_sha256"):
        # 임시 `inputs.s1`(SceneForge 10-30 — manifest 꼴이 정해지기 전)로 S1 을 바로 읽어 그렸다. 대조할 manifest 가 없다는
        # 것은 같으니 같은 규칙(계약 6항)으로 말한다 — 어느 S1 인지는 `inputs.s1_sha256` 에 남는다
        warnings.append("C-3 manifest 없이 S1 을 바로 읽어 그렸다(임시 inputs.s1) — manifest 로 대조하지 못했다")
    entry = {
        "render_id": rid, "request_id": result.get("request_id"), "ok": checked["ok"],
        "reason": result.get("reason"), "warnings": warnings, "case_key": checked["case_key"],
        "created_at": meta.get("created_at"), "received_at": datetime.now(timezone.utc).isoformat(),
        "mode": meta.get("mode"), "deform_scale": meta.get("deform_scale"),
        "outputs": [{"file": o["file"], "kind": o["kind"], "bytes": len(o["data"]), "sha256": o["sha256"].lower()}
                    for o in checked["outputs"]],
        "renderer": meta.get("renderer"), "inputs": inputs or None,
    }
    report.media = [m for m in (report.media or []) if m.get("render_id") != rid] + added
    report.renders = [r for r in (report.renders or []) if r.get("render_id") != rid] + [entry]
    await db.commit()
    return {"render_id": rid, "ok": checked["ok"], "already": False, "stored": len(added),
            "media_total": len(report.media), "warnings": warnings}


# ── CAD 형상 묶음(C-6 · C-7) — StepForge fe_cad 를 리포트의 형상으로 붙인다(뷰어 1단계, 사용자 결정 10-30) ─────────
async def attach_cad(db: AsyncSession, report: ImpactReport, raw: bytes) -> dict:
    """StepForge fe_cad 묶음 zip(manifest.json + 적힌 파일)을 리포트의 형상으로 붙인다.

    - 검사(`cad_bundle.check`)에 걸리면 CadBundleError — 아무것도 저장하지 않는다(전부 아니면 전무).
    - 리포트 하나에 묶음 하나. 같은 열쇠 · 같은 파일(sha)이면 그대로 둔다(멱등), 다른 열쇠면 갈아 끼운다.
      같은 열쇠에 다른 파일은 거절한다(StepForge 는 같은 열쇠면 같은 바이트다).
    - 새 파일을 먼저 저장하고 리포트 칸을 바꾼 뒤 옛 파일을 지운다 — 저장이 깨지면 이번 파일만 걷어 내 옛 묶음이 남는다.
    """
    from datetime import datetime, timezone

    manifest, files = cad_bundle.unzip(raw)
    part_ids = {int(p["part_id"]) for p in (report.parts or []) if isinstance(p, dict) and _isint(p.get("part_id"))}
    checked = cad_bundle.check(manifest, files, report_part_ids=part_ids)
    key = checked["key"]
    prior = report.cad if isinstance(report.cad, dict) else None
    sig = sorted((m["file"], m["sha256"]) for m in checked["files"])
    if prior and prior.get("key") == key and \
            sorted((m.get("file"), m.get("sha256")) for m in prior.get("files") or []) == sig:
        return {"key": key, "already": True, "stored": 0, "n_parts": prior.get("n_parts"),
                "warnings": prior.get("warnings") or []}

    session = await db.get(Session, report.session_id)
    if session is None:
        raise cad_bundle.CadBundleError("리포트의 세션을 찾지 못했다")
    base = f"cad/{report.id}/"
    old = (await db.execute(select(SessionFile).where(
        SessionFile.session_id == session.id, SessionFile.filename.like(base + "%")))).scalars().all()
    if prior and prior.get("key") == key:
        # StepForge 는 같은 판 열쇠면 같은 바이트다(D-645) — 다르면 위쪽이 어긋난 것이라 갈아 끼우지 않고 알린다
        raise cad_bundle.CadBundleError(f"같은 열쇠({key[:12]})인데 파일이 이미 붙은 묶음과 다르다 — StepForge 는 같은 "
                                        "열쇠면 같은 바이트다. 그쪽 산출을 확인해 달라")
    prefix = f"{base}{key[:12]}/"
    stored: list[SessionFile] = []
    ids: dict[str, int] = {}
    try:
        for name, data in files.items():
            f = await sess_svc.add_uploaded_file(db, session, filename=prefix + name, raw=data, kind="generated")
            stored.append(f)
            ids[name] = f.id
        view = checked["view"]
        report.cad = {
            "key": key, "attached_at": datetime.now(timezone.utc).isoformat(),
            "deck": checked["deck"], "cad_project": checked["cad_project"], "step_revision": checked["step_revision"],
            "units": checked["units"], "render_variant": checked["render"],
            "view": {"glb": [{"file": n, "file_id": ids[n]} for n in view["glb"]],
                     "weights": {"file": view["weights"], "file_id": ids[view["weights"]]},
                     "bin": {"file": view["bin"], "file_id": ids[view["bin"]]}},
            "manifest_file_id": ids[cad_bundle.MANIFEST_NAME],
            "parts_file_id": ids[cad_bundle.PARTS_NAME], "pairs_file_id": ids[cad_bundle.PAIRS_NAME],
            "parts": checked["parts"], "n_parts": checked["n_parts"], "rows": checked["rows"], "nnz": checked["nnz"],
            "pids_matched": checked["pids_matched"], "pids_bundle_only": checked["pids_bundle_only"],
            "files": checked["files"], "warnings": checked["warnings"],
        }
        await db.commit()
    except Exception:
        # 저장 도중 깨지면(디스크 등) 이번에 넣은 파일을 걷어 낸다 — 반쯤 붙은 묶음을 남기지 않는다
        await db.rollback()
        for f in stored:
            await sess_svc.delete_file(db, f)
        raise
    for f in old:
        await sess_svc.delete_file(db, f)
    return {"key": key, "already": False, "stored": len(stored), "n_parts": checked["n_parts"],
            "replaced": prior.get("key") if prior else None, "warnings": checked["warnings"]}

