# 리포트를 **개발 개정**에 잇는다 — 기계는 후보를 내고 **사람이 확정**한다
"""왜 사람이 확정하나. 개정 이름은 원천마다 뜻이 다르다 — SP 스스로 `model_revision` 은
"BOM 부품 리비전과 다른 것" 이라고 적었다. 짐작으로 붙이면 **틀려도 그럴듯하고**, 그럴듯한
오류는 몇 달 뒤 결과를 비교할 때 발견된다. 그래서 근거를 함께 보이고 사람이 고른다
(StepForge 와 같은 규율 · 계획서 §3-2).

**과제는 허브 것이다**(`source="hub"`). 우리는 `dev_revision` 만 만들고, 그것이 과제를
가리킨다 — 그 방향만 허용된다(SP `managed.py`: "막지 않는 것은 이 설치의 관계가 그 객체를
가리키는 것").

★**`eng_meta` 를 지우지 않는다.** DataHub 등재 양식과 같은 모양이고 필터·패싯이 거기 물려
있다(계획서 §3-3). 둘이 어긋나면 **관계가 정본**이고, 어긋났다는 사실을 **띄운다** —
조용히 맞추면 사람이 넣은 값과 저장된 값이 달라지고 그 차이는 아무 데도 안 뜬다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.models import (SOURCE_HUB, SOURCE_SELF, ImpactReport, OntoObject, OntoRelation)
from app.reports.datahub import DataHubError, parse_stage

TYPE_REVISION = "dev_revision"
TYPE_TASK = "plm_task"
TYPE_MODEL = "plm_model"
TYPE_REPORT = "impact_report"       # 우리 1급 표 — `onto_objects` 에 행을 만들지 않는다
REL_OF = "revision_of"
REL_SUPERSEDES = "supersedes"
REL_MEASURED = "measured_at"

# ★개정 순서를 **데이터로** 만드는 규칙. 코드에 암묵이던 것(정규식 나열 순서)을 꺼낸 값이다.
#   `r` 을 그 단계의 **끝**에 두는 것은 우리가 고른 약속이다 — 재차수가 정규 차수 뒤에 온다고
#   본다. 틀렸으면 `rev_seq` 를 손으로 고칠 수 있다(그래서 데이터로 둔다).
PHASE_ORDER = {"pre": 0, "dv": 1, "pv": 2, "pra": 3, "mp": 4}
ROUND_RANK = {None: 0, "1": 1, "2": 2, "3": 3, "r": 4}


def rev_seq(phase: str, round_: str | None) -> int:
    return PHASE_ORDER[phase] * 10 + ROUND_RANK.get(round_, 0)


def revision_key(task_key: str, code: str) -> str:
    return f"{task_key}@{code}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 후보 ───────────────────────────────────────────────────────────────────

async def candidates(db, report: ImpactReport, *, task_key: str = "") -> list[dict]:
    """개정 코드 후보와 **근거**. 고르지 않는다 — 고르는 것은 사람이다.

    근거 셋(계획서 §3-2) —
      ① `eng_meta.dev_revision.code` — 이미 형식 검증을 통과한 값이다(가장 강한 근거)
      ② 리포트에 박힌 `project_name` — 수동 메타를 안 채운 리포트도 잡힌다
      ③ 허브 `plm_model.model_revision` — 과제가 정해졌을 때만 물을 수 있다
    """
    out: list[dict] = []
    seen: set[str] = set()

    def add(code: str, source: str, evidence: str) -> None:
        code = (code or "").strip()
        if not code or code in seen:
            return
        try:
            rev = parse_stage(code)
        except DataHubError as exc:
            # 형식이 아닌 것도 **버리지 않고** 보여 준다 — 사람이 보고 고칠 수 있다.
            out.append({"code": code, "source": source, "evidence": evidence,
                        "valid": False, "why": str(exc)})
            seen.add(code)
            return
        seen.add(code)
        out.append({"code": code, "phase": rev["phase"], "round": rev.get("round"),
                    "rev_seq": rev_seq(rev["phase"], rev.get("round")),
                    "source": source, "evidence": evidence, "valid": True})

    em = report.eng_meta or {}
    dev = em.get("dev_revision") or {}
    if dev.get("code"):
        add(str(dev["code"]), "eng_meta", "수동 메타의 dev_revision.code")

    # ② 리포트에 박힌 이름의 꼬리에서 단계를 찾아본다. **찾지 못하면 아무 말도 하지 않는다** —
    #    없는 후보를 만들어 내면 사람이 그것을 고를 수 있게 된다.
    embed = str(report.project_name or "")
    if embed:
        tail = embed.replace("-", "_").split("_")[-1].lower()
        add(tail, "report_embed", f"리포트에 박힌 project_name {embed!r} 의 꼬리")

    # ③ 허브 개발모델의 model_revision — 과제가 정해졌을 때만.
    if task_key:
        rows = (await db.execute(
            select(OntoObject).where(OntoObject.type_slug == TYPE_MODEL,
                                     OntoObject.source == SOURCE_HUB,
                                     OntoObject.deleted.is_(False)))).scalars().all()
        for m in rows:
            props = m.properties or {}
            if str(props.get("task") or "") != task_key:
                continue
            if props.get("model_revision"):
                add(str(props["model_revision"]), "hub_model_revision",
                    f"허브 개발모델 {m.key!r} 의 model_revision"
                    f"({props.get('model_revision_kind') or '종류 미지정'})")
    return out


# ── 확정 ───────────────────────────────────────────────────────────────────

async def _chain_keys(db, start_key: str) -> list[str]:
    """`supersedes` 를 따라 앞으로 거슬러 간 키들(자기 포함)."""
    seen: list[str] = []
    cur = start_key
    while cur and cur not in seen:
        seen.append(cur)
        row = (await db.execute(
            select(OntoRelation).where(OntoRelation.relation == REL_SUPERSEDES,
                                       OntoRelation.src_type == TYPE_REVISION,
                                       OntoRelation.src_key == cur,
                                       OntoRelation.deleted.is_(False)))).scalars().first()
        cur = row.dst_key if row else ""
    return seen


async def _edge(db, relation: str, src_type: str, src_key: str,
                dst_type: str, dst_key: str, **props) -> None:
    found = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == relation,
                                   OntoRelation.src_type == src_type,
                                   OntoRelation.src_key == src_key,
                                   OntoRelation.dst_type == dst_type,
                                   OntoRelation.dst_key == dst_key))).scalar_one_or_none()
    if found is None:
        db.add(OntoRelation(relation=relation, src_type=src_type, src_key=src_key,
                            dst_type=dst_type, dst_key=dst_key, source=SOURCE_SELF,
                            properties=props or None, deleted=False))
    else:
        found.deleted = False
        if props:
            found.properties = {**(found.properties or {}), **props}
    await db.flush()


async def set_revision(db, report: ImpactReport, *, task_key: str, code: str,
                       model_key: str = "", supersedes: str = "",
                       decided_by: str = "", note: str = "",
                       source: str = "manual") -> dict:
    """리포트를 과제의 한 개정에 **확정해서** 잇는다.

    실패를 예외로 올리지 않는다 — `{"ok": False, "error": …}` 다(이 리포 규약).
    """
    task_key = (task_key or "").strip()
    code = (code or "").strip()
    if not task_key or not code:
        return {"ok": False, "error": "missing", "detail": "과제와 개정 코드가 둘 다 필요하다"}
    try:
        rev = parse_stage(code)
    except DataHubError as exc:
        return {"ok": False, "error": "bad_code", "detail": str(exc)}

    # 과제 거울이 있으면 확인한다. **없다고 막지는 않는다** — 허브가 아직 없을 수 있고,
    # 그때 막으면 개정을 아예 못 붙인다. 대신 "확인 못 했다" 를 돌려준다.
    task = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.key == task_key))).scalar_one_or_none()
    unverified = task is None

    key = revision_key(task_key, code)
    if supersedes:
        if supersedes == key:
            return {"ok": False, "error": "self_supersede", "detail": "자기를 앞 판으로 둘 수 없다"}
        # ★순환을 막는다 — 막지 않으면 개정 줄을 따라가는 질의가 **영원히 돈다.**
        if key in await _chain_keys(db, supersedes):
            return {"ok": False, "error": "cycle",
                    "detail": f"{supersedes!r} 의 앞줄에 이미 {key!r} 가 있다"}

    obj = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_REVISION,
                                 OntoObject.key == key))).scalar_one_or_none()
    props: dict[str, Any] = {
        "task": task_key,
        "code": code,
        "phase": rev["phase"],
        "round": rev.get("round"),
        "rev_seq": rev_seq(rev["phase"], rev.get("round")),
        "rev_source": source,
        "status": "current",
    }
    if model_key:
        props["model"] = model_key
    if note:
        props["note"] = note
    if source == "manual":
        props["decided_by"] = decided_by or ""
        props["decided_at"] = _now()

    if obj is None:
        obj = OntoObject(type_slug=TYPE_REVISION, key=key,
                         label=f"{task_key} {code}", status="active",
                         properties=props, source=SOURCE_SELF)
        db.add(obj)
    else:
        # ★**사람의 확정을 기계가 덮지 않는다.** 이미 사람이 정한 개정을 자동 경로가 다시
        #   지나가며 `rev_source` 를 `eng_meta` 로 되돌리면, 사람이 고친 사실이 사라진다.
        was = (obj.properties or {}).get("rev_source")
        if was == "manual" and source != "manual":
            keep = {k: (obj.properties or {}).get(k)
                    for k in ("rev_source", "decided_by", "decided_at", "note")}
            props.update({k: v for k, v in keep.items() if v is not None})
        obj.properties = {**(obj.properties or {}), **props}
        obj.label = f"{task_key} {code}"
        obj.deleted = False
    await db.flush()

    await _edge(db, REL_OF, TYPE_REVISION, key, TYPE_TASK, task_key)
    if supersedes:
        await _edge(db, REL_SUPERSEDES, TYPE_REVISION, key, TYPE_REVISION, supersedes)
    # 리포트는 우리 1급 표다 — 행을 만들지 않고 **선의 끝점**으로만 쓴다.
    await _edge(db, REL_MEASURED, TYPE_REPORT, str(report.id), TYPE_REVISION, key)

    return {"ok": True, "key": key, "rev_seq": props["rev_seq"],
            "task_unverified": unverified,
            "detail": ("과제 거울이 없어 확인하지 못했다 — 허브 수신이 켜지면 확인된다"
                       if unverified else "")}


async def link_from_eng_meta(db, report: ImpactReport) -> dict:
    """인제스트·PATCH 가 부르는 자동 경로. `eng_meta` 로 **찾거나 만들고** 잇는다.

    사람이 이미 정한 개정은 **건드리지 않는다**(`set_revision` 의 `manual` 보호).
    """
    em = report.eng_meta or {}
    task = str(em.get("project") or report.project_name or "").strip()
    code = str((em.get("dev_revision") or {}).get("code") or "").strip()
    if not task or not code:
        return {"ok": False, "error": "nothing_to_link",
                "detail": "eng_meta 에 과제와 dev_revision.code 가 둘 다 있어야 한다"}
    return await set_revision(db, report, task_key=task, code=code, source="eng_meta")


# ── 어긋남 ─────────────────────────────────────────────────────────────────

async def mismatch(db, report: ImpactReport) -> dict | None:
    """`eng_meta` 와 이어진 개정이 다르면 그 사실을 돌려준다(없으면 `None`).

    ★**관계가 정본**이다. 그러나 조용히 맞추지 않는다 — 맞추면 사람이 넣은 값과 저장된
    값이 달라지고 그 차이는 아무 데도 안 뜬다. 화면이 보여 주고 사람이 고른다.
    """
    edge = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_MEASURED,
                                   OntoRelation.src_type == TYPE_REPORT,
                                   OntoRelation.src_key == str(report.id),
                                   OntoRelation.deleted.is_(False)))).scalars().first()
    if edge is None:
        return None
    linked = edge.dst_key
    em = report.eng_meta or {}
    task = str(em.get("project") or "").strip()
    code = str((em.get("dev_revision") or {}).get("code") or "").strip()
    if not task or not code:
        return {"kind": "eng_meta_missing", "linked": linked,
                "said": "이어진 개정은 있는데 수동 메타가 비었다"}
    expected = revision_key(task, code)
    if expected == linked:
        return None
    return {"kind": "differs", "linked": linked, "eng_meta": expected,
            "said": "수동 메타와 이어진 개정이 다르다 — 관계가 정본이다"}


# ── 개정 줄 ────────────────────────────────────────────────────────────────

async def history(db, task_key: str) -> list[dict]:
    """한 과제의 개정 줄 — `rev_seq` 순으로, 각 판에 달린 리포트와 함께."""
    revs = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_REVISION,
                                 OntoObject.deleted.is_(False)))).scalars().all()
    mine = [r for r in revs if str((r.properties or {}).get("task") or "") == task_key]
    if not mine:
        return []
    keys = [r.key for r in mine]
    edges = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_MEASURED,
                                   OntoRelation.dst_type == TYPE_REVISION,
                                   OntoRelation.dst_key.in_(keys),
                                   OntoRelation.deleted.is_(False)))).scalars().all()
    by_rev: dict[str, list[str]] = {}
    for e in edges:
        by_rev.setdefault(e.dst_key, []).append(e.src_key)
    sups = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_SUPERSEDES,
                                   OntoRelation.src_key.in_(keys),
                                   OntoRelation.deleted.is_(False)))).scalars().all()
    prev = {e.src_key: e.dst_key for e in sups}

    out = []
    for r in sorted(mine, key=lambda x: ((x.properties or {}).get("rev_seq") or 0, x.key)):
        p = r.properties or {}
        out.append({
            "key": r.key, "code": p.get("code"), "phase": p.get("phase"),
            "round": p.get("round"), "rev_seq": p.get("rev_seq"),
            "rev_source": p.get("rev_source"), "status": p.get("status"),
            "decided_by": p.get("decided_by"), "decided_at": p.get("decided_at"),
            "model": p.get("model"), "supersedes": prev.get(r.key),
            "reports": sorted(by_rev.get(r.key, [])),
        })
    return out
