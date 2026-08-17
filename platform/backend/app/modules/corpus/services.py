# 전사 코퍼스 통계 — 개인 식별 없이 '조직이 무엇을 어떻게 모델링해 왔는가'만 집계한다.
"""왜 집계를 따로 두는가.

세션·파일·잡은 전부 user_id 스코프라, 게이트웨이 서비스 계정으로 조회하는 심의는
아무것도 못 본다(세션 12·K파일 25건이 있는데 0건, 2026-08-17 실측). 그렇다고 남의
모델 내용을 열어 줄 수는 없다.

그래서 '내용'이 아니라 '분포'를 낸다 — 세션명·파일명·소유자를 담지 않고 수치와
표준 키워드(물성 카드·오퍼레이션 이름)만 낸다. 개인을 식별하지 않으므로 시야 배선
(신원 전달) 없이도 지금 붙고, 심의는 "일반적으로" 대신 "우리 조직은 이렇게" 를 말할 수 있다.

표본이 적으면 분포가 오해를 부르므로 모든 응답에 모집단 크기(n)를 함께 낸다.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImpactCase, ImpactReport, Job, Session, SessionFile

# 물성·요소·접촉 계열만 센다. *NODE/*ELEMENT 같은 구조 키워드는 모든 덱에 있어 정보가 없다.
_PREFIX_MATERIAL = "*MAT_"
_PREFIX_SECTION = "*SECTION_"
_PREFIX_CONTACT = "*CONTACT_"


def _kw(meta: Any) -> dict:
    """session_files.meta 의 keyword_counts. 형식이 다르면 빈 dict(집계가 멈추지 않게)."""
    if not isinstance(meta, dict):
        return {}
    kc = meta.get("keyword_counts")
    return kc if isinstance(kc, dict) else {}


async def corpus_summary(db: AsyncSession) -> dict:
    """모델 규모 감각 — 몇 개를 얼마나 크게 다루는 조직인가."""
    n_sessions = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
    n_files = (await db.execute(select(func.count()).select_from(SessionFile))).scalar_one()
    n_jobs = (await db.execute(select(func.count()).select_from(Job))).scalar_one()

    rows = (await db.execute(select(SessionFile.meta).where(SessionFile.meta.isnot(None)))).scalars().all()
    nodes, elems, parts = [], [], []
    for m in rows:
        if not isinstance(m, dict):
            continue
        for key, bucket in (("nodes", nodes), ("elements", elems), ("parts", parts)):
            v = m.get(key)
            if isinstance(v, (int, float)) and v > 0:
                bucket.append(int(v))

    def _dist(vals: list[int]) -> dict:
        if not vals:
            return {"n": 0}
        s = sorted(vals)
        return {"n": len(s), "min": s[0], "median": s[len(s) // 2], "max": s[-1], "total": sum(s)}

    return {
        "sessions": n_sessions,
        "files": n_files,
        "jobs": n_jobs,
        "mesh_scale": {"nodes": _dist(nodes), "elements": _dist(elems), "parts": _dist(parts)},
        "note": "전사 집계(개인 식별 없음). 소유자·세션명·파일명은 담지 않는다.",
    }


async def material_usage(db: AsyncSession, limit: int = 30) -> dict:
    """물성 카드별 사용 모델 수.

    시험 계획의 우선순위 근거가 '민감도 추정'에서 '실사용 빈도'로 바뀌는 지점이다 —
    어떤 물성 모델이 실제로 몇 개 덱에 들어가 있는지는 추정이 아니라 조회다.
    """
    rows = (await db.execute(select(SessionFile.meta).where(SessionFile.meta.isnot(None)))).scalars().all()
    files_with = 0
    per_file: Counter[str] = Counter()   # 이 카드가 등장한 '파일 수'(카드 개수가 아니라)
    occurrences: Counter[str] = Counter()
    for m in rows:
        kws = _kw(m)
        seen = {k for k in kws if k.startswith(_PREFIX_MATERIAL)}
        if seen:
            files_with += 1
        for k in seen:
            per_file[k] += 1
            try:
                occurrences[k] += int(kws.get(k) or 0)
            except (TypeError, ValueError):
                pass
    items = [
        {"card": k, "files": c, "occurrences": occurrences.get(k, c)}
        for k, c in per_file.most_common(limit)
    ]
    return {
        "n_files_scanned": len(rows),
        "n_files_with_material": files_with,
        "materials": items,
        "note": "files = 이 카드가 등장한 K파일 수. 물성 확보 우선순위의 실사용 근거로 쓴다.",
    }


async def operation_usage(db: AsyncSession) -> dict:
    """오퍼레이션 실행 이력 — 조직이 실제로 쓰는 전처리 관행."""
    rows = (await db.execute(
        select(Job.operation, Job.status, func.count()).group_by(Job.operation, Job.status)
    )).all()
    agg: dict[str, dict] = {}
    for op, status, cnt in rows:
        e = agg.setdefault(op, {"operation": op, "total": 0, "succeeded": 0, "failed": 0, "other": 0})
        e["total"] += cnt
        if status == "succeeded":
            e["succeeded"] += cnt
        elif status in ("failed", "canceled"):
            e["failed"] += cnt
        else:
            e["other"] += cnt
    items = sorted(agg.values(), key=lambda e: -e["total"])
    return {
        "n_jobs": sum(e["total"] for e in items),
        "operations": items,
        "note": "실행 이력 기준. 카탈로그에 있으나 한 번도 안 쓴 오퍼레이션은 여기 없다.",
    }


async def section_contact_usage(db: AsyncSession, limit: int = 20) -> dict:
    """요소 정식(*SECTION_)·접촉(*CONTACT_) 사용 분포 — 해석 설계의 관행 근거."""
    rows = (await db.execute(select(SessionFile.meta).where(SessionFile.meta.isnot(None)))).scalars().all()
    sec: Counter[str] = Counter()
    con: Counter[str] = Counter()
    for m in rows:
        kws = _kw(m)
        for k in kws:
            if k.startswith(_PREFIX_SECTION):
                sec[k] += 1
            elif k.startswith(_PREFIX_CONTACT):
                con[k] += 1
    return {
        "n_files_scanned": len(rows),
        "sections": [{"card": k, "files": c} for k, c in sec.most_common(limit)],
        "contacts": [{"card": k, "files": c} for k, c in con.most_common(limit)],
    }


async def report_corpus(db: AsyncSession) -> dict:
    """해석 결과 분포 — 어떤 실패모드가 반복되는가.

    리포트가 아직 없으면 0 을 그대로 낸다. '없다'와 '조회 못 했다'는 다르고,
    심의가 그 차이를 알아야 근거 없이 단정하지 않는다.
    """
    n_rep = (await db.execute(select(func.count()).select_from(ImpactReport))).scalar_one()
    n_case = (await db.execute(select(func.count()).select_from(ImpactCase))).scalar_one()
    kinds = (await db.execute(
        select(ImpactReport.kind, func.count()).group_by(ImpactReport.kind)
    )).all()

    sev: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    if n_rep:
        for findings in (await db.execute(
            select(ImpactReport.findings).where(ImpactReport.findings.isnot(None))
        )).scalars().all():
            if not isinstance(findings, list):
                continue
            for f in findings:
                if not isinstance(f, dict):
                    continue
                sev[str(f.get("severity") or "UNKNOWN").upper()] += 1
                t = str(f.get("title") or "").strip()
                if t:
                    titles[t[:80]] += 1

    return {
        "reports": n_rep,
        "cases": n_case,
        "by_kind": [{"kind": k, "reports": c} for k, c in kinds],
        "findings_by_severity": dict(sev),
        "frequent_findings": [{"title": t, "count": c} for t, c in titles.most_common(10)],
        "note": ("해석 결과 리포트가 아직 없다." if not n_rep else
                 "전사 집계. 반복되는 findings 는 설계 규칙 후보다."),
    }
