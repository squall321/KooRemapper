# 인제스트된 시뮬레이션 리포트를 AI Data Hub 의 범용 sim_report 레코드로 등재한다.
"""Publish an ingested simulation report to AI Data Hub as a generic sim record.

도메인 중립 설계: doc_type 은 ``sim_report`` 로 고정하고, 실제 종류는
content.sim_domain(현재 "drop_impact") + content.report_kind(deep/sphere/impact)
메타로 구분한다. 낙하/충격을 넘어 다른 시뮬레이션(열·진동·CFD…)이 붙어도 스키마 변경
없이 새 domain/kind 값만 추가하면 된다(DynaForge = 범용 시뮬레이션 forge).

번들 포맷은 kr2datahub.py 와 동일: record.json + 첨부파일을 ZIP 으로 묶어
``/api/ingest/bundle`` 에 multipart POST. 이 도메인의 리포트는 재료 카드 매칭이
없으므로(리포트 parts 는 이름·그룹만 보유) 재료 연계는 생략한다.
"""
from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from datetime import date
from pathlib import Path

import httpx

from app.models import ImpactCase, ImpactReport

# 현재 이 파서 계열이 다루는 시뮬레이션 도메인. 새 도메인 추가 시 여기 확장.
SIM_DOMAIN = "drop_impact"
_TEAM, _GROUP = "MX", "CAE"
# 개발단계 코드 분해 규칙(kr2datahub 와 동일) — dv/pv 는 차수 필수.
_STAGE_RE = re.compile(r"(pre|dv|pv|pra|mp)([123r])?$")


class DataHubError(RuntimeError):
    pass


def parse_stage(stage: str) -> dict:
    """개발단계 코드 → eng_meta.dev_revision. 형식 오류면 DataHubError."""
    m = _STAGE_RE.fullmatch(stage or "")
    if not m or (m.group(1) in ("dv", "pv")) != bool(m.group(2)):
        raise DataHubError(f"stage 형식 오류: {stage} (dv/pv는 차수 필수, pre/pra/mp는 금지)")
    rev = {"phase": m.group(1)}
    if m.group(2):
        rev["round"] = m.group(2)
    return rev


async def _next_sim_id(hub: str) -> str:
    """SIM-{TEAM}-{GROUP}-{year}-{seq} 다음 id. seq 는 (team,group,year) 자연키별 max+1.

    서버가 id 를 자동 부여하지 않고 번들이 record.id 를 요구하므로 클라이언트가 생성한다.
    자연키 접두로만 세어 다른 팀/그룹의 seq 에 영향받지 않게 한다.
    """
    year = date.today().year
    prefix = f"SIM-{_TEAM}-{_GROUP}-{year}-"
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{hub}/api/records", params={"data_type": "SIM", "limit": 100})
            r.raise_for_status()
            items = (r.json() or {}).get("items") or []
    except httpx.HTTPError as exc:
        raise DataHubError(f"DataHub SIM 목록 조회 실패: {exc}") from exc
    max_seq = 0
    for it in items:
        rid = it.get("id", "")
        if rid.startswith(prefix):
            m = re.match(rf"{re.escape(prefix)}(\d+)$", rid)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
    return f"{prefix}{max_seq + 1:010d}"


def build_record(
    report: ImpactReport,
    cases: list[ImpactCase],
    *,
    sim_id: str,
    project: str,
    stage: str,
    variation: str | None,
    doe: str | None,
    unit: str,
    title: str | None,
    html_name: str,
) -> dict:
    """리포트 → 범용 sim_report DataHub 레코드(dict). 첨부 경로는 {sim_id}/... 규약."""
    dev_rev = parse_stage(stage)
    eng_meta: dict = {"project": project, "dev_revision": dev_rev}
    if variation:
        eng_meta["design_variation"] = variation
    if doe:
        # DoeRef 는 study(필수)·case·factors 만 허용(extra 금지). 리포트 DOE 전략은
        # factors 에 실어 남긴다(전각도/전위치 등 슬라이스 축 메타).
        st, _, case = doe.partition(":")
        d: dict = {"study": st}
        if case:
            d["case"] = case
        if report.doe_strategy:
            d["factors"] = {"strategy": report.doe_strategy}
        eng_meta["doe"] = d

    parts = report.parts or []
    components = [
        {"pid": p.get("part_id"), "title": p.get("name"), "group": p.get("group")}
        for p in parts
    ]

    # FTS·태그 승격: 파트명 + 최악 파트 + 소견 심각도.
    kw = [p.get("name") for p in parts if p.get("name")]
    tags = [f"sim:{SIM_DOMAIN}", f"kind:{report.kind}", f"stage:{stage}"]
    tags += [f"part:{p.get('name')}" for p in parts if p.get("name")]
    sev = sorted({(f.get("severity") or "").upper() for f in (report.findings or []) if f.get("severity")})
    tags += [f"finding:{s}" for s in sev if s]

    # 도메인 무관 최악 케이스 요약(상위 5) — sphere=방향, impact=위치, deep=단건.
    worst = sorted(
        cases,
        key=lambda c: (c.max_stress is None, -(c.max_stress or 0.0)),
    )[:5]
    worst_cases = [
        {
            "case_key": c.case_key,
            "identity": c.identity,
            "max_stress": c.max_stress,
            "max_g": c.max_g,
            "max_disp": c.max_disp,
            "min_safety_factor": c.min_safety_factor,
        }
        for c in worst
    ]

    title = title or f"{project} {stage} — {report.project_name or report.kind} {report.kind} 리포트"
    summary = (
        f"{SIM_DOMAIN}/{report.kind} 시뮬레이션 리포트: 케이스 {report.n_cases}개, "
        f"파트 {len(parts)}개, 소견 {len(report.findings or [])}건 — DynaForge 자동 인제스트 | "
        + " ".join(list(dict.fromkeys(kw))[:30])
    )[:900]

    attachments = [{
        "id": f"{sim_id}-A001", "record_id": sim_id, "number": 1, "kind": "document",
        "caption": f"{report.kind} 리포트 HTML — {report.project_name or report.kind} ({unit})",
        "file_name": html_name, "file_path": f"{sim_id}/{html_name}",
        "extra": {
            "solver": "LS-DYNA", "format": "html", "role": "report",
            "sim_domain": SIM_DOMAIN, "report_kind": report.kind,
            "generator": report.generator, "unit_system": unit,
        },
    }]

    return {
        "id": sim_id, "data_type": "SIM", "doc_type": "sim_report",
        "title": title,
        "summary": summary,
        "project": project,
        "tags": list(dict.fromkeys(tags)),
        "subject_keywords": list(dict.fromkeys(kw))[:50],
        "related_record_ids": [],
        "source_system": "DynaForge",
        "agents": ["dynaforge-report"],
        "content": {
            "solver": "LS-DYNA",
            # sim_domain·report_kind 은 SimContent 정의 필드가 아니라 정규화에서 떨어지므로
            # 생존하는 inputs(자유 dict)·tags·첨부 extra 에 둔다(도메인 판별자 = 모든 forge 공통).
            "inputs": {
                "sim_domain": SIM_DOMAIN,
                "report_kind": report.kind,
                "generator": report.generator,
                "test_dir": report.test_dir,
                "doe_strategy": report.doe_strategy,
            },
            "outputs": {
                "sim_params": report.sim_params,
                "summary": report.summary,
                "findings": report.findings,
                "worst_cases": worst_cases,
                "n_cases": report.n_cases,
            },
            "eng_meta": eng_meta,
            "components": components,
            "attachments": attachments,
        },
    }


async def publish(
    report: ImpactReport,
    cases: list[ImpactCase],
    *,
    hub_url: str,
    html_bytes: bytes,
    html_name: str,
    project: str,
    stage: str,
    variation: str | None = None,
    doe: str | None = None,
    unit: str = "mm-t-s",
    title: str | None = None,
) -> dict:
    """레코드+첨부를 ZIP 번들로 묶어 AI Data Hub 에 POST. 등재된 레코드 요약 반환."""
    if not hub_url:
        raise DataHubError("datahub_url 이 설정되지 않았습니다.")
    sim_id = await _next_sim_id(hub_url)
    record = build_record(
        report, cases, sim_id=sim_id, project=project, stage=stage,
        variation=variation, doe=doe, unit=unit, title=title, html_name=html_name,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("record.json", json.dumps(record, ensure_ascii=False, indent=1))
        z.writestr(f"{sim_id}/{html_name}", html_bytes)
    body = buf.getvalue()

    boundary = uuid.uuid4().hex
    payload = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="bundle.zip"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode() + body + f"\r\n--{boundary}--\r\n".encode()

    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{hub_url}/api/ingest/bundle",
                content=payload,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
    except httpx.HTTPError as exc:
        raise DataHubError(f"DataHub 연결 실패: {exc}") from exc
    if r.status_code >= 400:
        raise DataHubError(f"DataHub 업로드 실패 HTTP {r.status_code}: {r.text[:300]}")
    resp = r.json()
    rid = resp.get("id", sim_id)
    return {
        "record_id": rid,
        "data_type": "SIM",
        "doc_type": "sim_report",
        "sim_domain": SIM_DOMAIN,
        "report_kind": report.kind,
        "view": f"{hub_url}/api/records/{rid}",
    }
