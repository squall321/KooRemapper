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

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select, update

from app.models import (SOURCE_HUB, SOURCE_SELF, ImpactReport, OntoAlias,
                        OntoObject, OntoPreviousKey, OntoRelation)
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
    # ★리포트 하나에 개정 하나(앞 계획 §7 ③) — 다른 판으로 다시 확정하면 옛 선을 뗀다. 안 떼면 같은 리포트가 두 판에
    #   다 잡혀 판끼리 견준 숫자가 틀어진다(10-30 실측: dv1 → pv1 다시 확정 뒤 선 둘). 떼는 꼴은 `unlink_revision` 과 같다.
    for old in (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
            OntoRelation.src_key == str(report.id), OntoRelation.dst_key != key))).scalars().all():
        await db.delete(old)
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
    # 허브가 바꾼 옛 과제명이면 지금 것으로 — 안 풀면 옛 key 로 개정이 새로 생겨 같은 판이 둘이 된다(층 2)
    task = await current_key(db, TYPE_TASK, task)
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
    # ★수동 메타는 고치지 않는다(DataHub 칸이 거기 물려 있다). 허브가 과제명을 바꿨거나 합쳤고 이어진 개정이
    #   그리로 옮겨졌으면 「다르다」 가 아니라 그 사실을 말한다 — 둘 다 잘못이 아니고, 수동 메타가 옛 이름일 뿐이다.
    now = await current_key(db, TYPE_TASK, task)
    if now != task and revision_key(now, code) == linked:
        return {"kind": "renamed", "linked": linked, "eng_meta": expected,
                "said": f"수동 메타의 과제 {task!r} 는 허브에서 {now!r} 로 바뀌었다 — 이어진 개정은 옮겼다(수동 메타는 그대로 둔다)"}
    st = await task_state(db, task)
    if st["state"] == "merged" and revision_key(st["into"], code) == linked:
        return {"kind": "merged", "linked": linked, "eng_meta": expected,
                "said": f"수동 메타의 과제 {task!r} 는 허브에서 {st['into']!r} 로 합쳐졌다 — 이어진 개정은 옮겼다(수동 메타는 그대로 둔다)"}
    return {"kind": "differs", "linked": linked, "eng_meta": expected,
            "said": "수동 메타와 이어진 개정이 다르다 — 관계가 정본이다"}


async def linked_revision(db, report: ImpactReport) -> dict | None:
    """이 리포트에 이어진 개정(없으면 `None`) — 그 개정이 가리키는 과제와 함께."""
    edge = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_MEASURED,
                                   OntoRelation.src_type == TYPE_REPORT,
                                   OntoRelation.src_key == str(report.id),
                                   OntoRelation.deleted.is_(False)))).scalars().first()
    if edge is None:
        return None
    rev = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == TYPE_REVISION, OntoObject.key == edge.dst_key))).scalar_one_or_none()
    props = (rev.properties or {}) if rev is not None else {}
    return {"key": edge.dst_key, "task": str(props.get("task") or edge.dst_key.rsplit("@", 1)[0]),
            "code": props.get("code") or edge.dst_key.rsplit("@", 1)[-1]}


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


# ── 과거 붙이기 (S4) ───────────────────────────────────────────────────────
# 과거 리포트의 과제는 **자유 문자열**이다. 정본은 허브의 `plm_task.key` 다. 둘을 잇는 일이
# 남는데 ★**짐작으로 붙이지 않는다** — 틀려도 그럴듯하고, 그럴듯한 오류는 몇 달 뒤 결과를
# 비교할 때 발견된다. 그래서 계획을 먼저 내고(쓰지 않는다) 사람이 고른 것만 적용한다
# (SP 의 계획 → 확인 → 적용 꼴).

_STRIP = str.maketrans("", "", " \t-_./()[]")


def normalize(text: str) -> str:
    """비교용으로만 쓰는 정규화 — 대소문자·공백·구분기호를 지운다.

    ⚠**저장에는 쓰지 않는다.** 정규화한 값을 저장하면 원문이 사라지고, 원문이 사라지면
    "무엇을 보고 붙였나" 를 되짚을 수 없다.
    """
    return (text or "").strip().lower().translate(_STRIP)


async def resolve_task(db, free: str) -> tuple[str, str]:
    """자유 문자열 → (과제 key, 어떻게). 못 풀면 `("", "")`.

    **짐작이 없는 길만** 여기서 푼다 —
      `exact`        과제명(plm_task.key)과 글자 그대로 같다
      `task_code`    과제코드(`properties.task_code`)와 글자 그대로 같다
      `previous_key` 허브가 바꾼 옛 과제명이다(`onto_previous_keys` — 같은 과제다)
      `alias`        사람이 이 플랫폼에서 이미 붙인 기록이 있다
      `hub_alias`    허브 행의 별칭(`properties.aliases`)과 글자 그대로 같고 그런 과제가 **하나뿐**이다(KR-01 다시, 10-30)
    ⚠ key 는 **과제명**이다(rootdesign plm_task.key). 과제코드는 `properties.task_code` 에 있다 —
      보고서에는 과제코드가 적혀 오므로 그 경로가 없으면 과제코드로는 영영 안 풀린다(KR-01, 2026-10-27).
    ★우리 별칭이 허브 별칭보다 먼저다 — 허브가 나중에 같은 별칭을 다른 과제에 달아도 사람이 정한 것을 조용히 바꾸지 않는다.
    정규화해서 같아 보이는 것은 **여기서 풀지 않는다**(후보일 뿐이다 — `task_candidates`).
    """
    free = (free or "").strip()
    if not free:
        return "", ""
    hit = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.key == free,
                                 OntoObject.deleted.is_(False)))).scalar_one_or_none()
    if hit is not None:
        return hit.key, "exact"
    code_hit = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.properties["task_code"].astext == free,
                                 OntoObject.deleted.is_(False)))).scalars().first()
    if code_hit is not None:
        return code_hit.key, "task_code"
    now = await current_key(db, TYPE_TASK, free)
    if now != free and await task_exists(db, now):
        return now, "previous_key"
    al = (await db.execute(
        select(OntoAlias).where(OntoAlias.type_slug == TYPE_TASK,
                                OntoAlias.alias == free))).scalar_one_or_none()
    if al is not None:
        return al.key, "alias"
    named = [t.key for t in (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.properties["aliases"].contains([free]),
                                 OntoObject.deleted.is_(False)))).scalars().all()
             if free in hub_aliases(t)]
    if len(named) == 1:
        return named[0], "hub_alias"
    return "", ""


def hub_aliases(obj: OntoObject) -> list[str]:
    """허브 행의 별칭 — SP 는 있으면 `properties.aliases` 에 배열로 준다(키트 10-21 §5.2). 모양이 어긋나면 없는 것으로 본다."""
    raw = (obj.properties or {}).get("aliases")
    return [str(a) for a in raw if str(a or "").strip()] if isinstance(raw, list) else []


async def task_candidates(db, free: str, *, limit: int = 5) -> list[dict]:
    """붙일 만한 과제 **후보와 근거**. 고르지 않는다.

    근거를 함께 내는 것이 요점이다 — 근거 없는 후보 목록은 사람이 검증할 수 없고,
    검증할 수 없는 목록은 결국 맨 위를 누르게 된다.
    """
    free = (free or "").strip()
    if not free:
        return []
    norm = normalize(free)
    rows = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.deleted.is_(False)))).scalars().all()
    out: list[dict] = []
    for t in rows:
        if t.status == "deprecated":
            continue        # 그만 씀 — 새로 고르는 목록에서만 숨긴다(사용자 결정 10-30). 이미 이은 것 · 검색에는 그대로 보인다
        # key 는 **과제명**, 과제코드는 properties.task_code 에 있다(KR-01). 둘 다 본다.
        code = normalize(str((t.properties or {}).get("task_code") or ""))
        if code and code == norm:
            out.append({"key": t.key, "label": t.label, "task_code": (t.properties or {}).get("task_code"),
                        "why": "과제코드가 구분기호만 다르다", "rank": 0})
        elif normalize(t.key) == norm:
            out.append({"key": t.key, "label": t.label, "why": "과제명이 구분기호만 다르다",
                        "rank": 1})
        elif normalize(t.label) == norm:
            out.append({"key": t.key, "label": t.label, "why": "이름(label)이 구분기호만 다르다",
                        "rank": 2})
        elif norm and any(normalize(a) == norm for a in hub_aliases(t)):
            out.append({"key": t.key, "label": t.label, "why": "허브 별칭이 구분기호만 다르다",
                        "rank": 2})
        elif norm and norm in normalize(t.label):
            out.append({"key": t.key, "label": t.label, "why": "이름(label)이 이 말을 품고 있다",
                        "rank": 3})
        elif norm and code and norm in code:
            out.append({"key": t.key, "label": t.label, "task_code": (t.properties or {}).get("task_code"),
                        "why": "과제코드가 이 말을 품고 있다", "rank": 4})
    out.sort(key=lambda c: (c["rank"], c["key"]))
    return out[:limit]


_BOUNDARY = r"(^|[\s\-_./()\[\]])"
_KIND_RANK = {"prefix": 0, "word": 1, "substring": 2}
_FIELD_RANK = {"task_name": 0, "task_code": 1, "alias": 2, "label": 3}


def match_kind(q: str, text: str) -> str | None:
    """`q` 가 `text` 에 어떻게 걸렸나 — `prefix`(앞부분) · `word`(낱말 경계) · `substring`(부분) · 안 걸리면 `None`."""
    ql, t = (q or "").lower(), (text or "").lower()
    if not ql or ql not in t:
        return None
    if t.startswith(ql):
        return "prefix"
    if re.search(_BOUNDARY + re.escape(ql), t):
        return "word"
    return "substring"


async def search_tasks(db, q: str = "", *, project: str = "", include_deleted: bool = False,
                       limit: int = 100) -> dict:
    """과제 검색 — 과제명(key) · 과제코드 · 별칭(허브 `properties.aliases` 와 우리 별칭 표) · 이름을 본다.

    ★**순위를 매긴 뒤 자른다**(KR-16 다시, 10-30) — key 순으로 먼저 자른 창 안에서만 순위를 매기면 짧은 질의의 앞부분
    일치가 창 밖으로 밀린다. 걸린 것을 전부 받아(과제는 수천 건 이하) 앞부분 · 낱말 경계 · 부분 순, 같은 꼴이면 과제명 ·
    과제코드 · 별칭 · 이름 순으로 놓는다. 행마다 `matched_by`(어느 칸) · `match_kind`(어떻게)를 단다. 별칭으로 걸렸으면
    `matched_alias` 에 그 별칭이 온다(KR-01 다시).
    """
    q = (q or "").strip()
    stmt = select(OntoObject).where(OntoObject.type_slug == TYPE_TASK)
    if not include_deleted:
        stmt = stmt.where(OntoObject.deleted.is_(False))
    if project:
        stmt = stmt.where(OntoObject.properties["project"].astext == project)
    if not q:
        rows = (await db.execute(stmt.order_by(OntoObject.key).limit(limit + 1))).scalars().all()
        return {"items": [_task_item(r) for r in rows[:limit]], "truncated": len(rows) > limit}
    like = f"%{q}%"
    ours: dict[str, list[str]] = {}
    for alias, key in (await db.execute(select(OntoAlias.alias, OntoAlias.key).where(
            OntoAlias.type_slug == TYPE_TASK, OntoAlias.alias.ilike(like)))).all():
        ours.setdefault(key, []).append(alias)
    # 허브 별칭은 배열의 글자(`->>`)로 먼저 거르고(넉넉한 거르개) 아래에서 원소마다 정확히 본다
    cond = (OntoObject.key.ilike(like) | OntoObject.label.ilike(like)
            | OntoObject.properties["task_code"].astext.ilike(like)
            | OntoObject.properties["aliases"].astext.ilike(like))
    if ours:
        cond = cond | OntoObject.key.in_(sorted(ours))
    hits = []
    for r in (await db.execute(stmt.where(cond))).scalars().all():
        fields = [("task_name", r.key or "", None), ("task_code", str((r.properties or {}).get("task_code") or ""), None),
                  *[("alias", a, "hub") for a in hub_aliases(r)], *[("alias", a, "dynaforge") for a in ours.get(r.key, [])],
                  ("label", r.label or "", None)]
        best = None
        for field, text, origin in fields:
            kind = match_kind(q, text)
            if kind and (best is None or (_KIND_RANK[kind], _FIELD_RANK[field]) < best[0]):
                best = ((_KIND_RANK[kind], _FIELD_RANK[field]), field, kind, text, origin)
        if best is not None:
            hits.append((best, r))
    hits.sort(key=lambda h: (h[0][0], h[1].key or ""))
    items = []
    for (_, field, kind, text, origin), r in hits[:limit]:
        item = {**_task_item(r), "matched_by": field, "match_kind": kind}
        if field == "alias":
            item.update(matched_alias=text, alias_source=origin)
        items.append(item)
    return {"items": items, "total": len(hits), "truncated": len(hits) > limit}


def _task_item(r: OntoObject) -> dict:
    return {"key": r.key, "label": r.label, "status": r.status, "deleted": r.deleted,
            "properties": r.properties or {}, "matched_by": None, "updated_at": r.updated_at}


def report_free_task(report: ImpactReport) -> str:
    """리포트가 말하는 과제 — 수동 메타가 먼저, 없으면 리포트에 박힌 이름.

    `services.py:232` 의 폴백과 **같은 순서**다. 두 벌이 되면 한쪽만 고쳐진다.
    """
    em = report.eng_meta or {}
    return str(em.get("project") or report.project_name or "").strip()


async def plan_task_links(db, *, limit: int | None = None) -> dict:
    """★**계획이다 — 아무것도 쓰지 않는다.**

    자유 문자열별로 묶어서 「붙는 것」·「후보가 있는 것」·「못 붙인 것」 을 가른다.
    못 붙인 것을 **목록으로 돌려주는 것이 요점**이다 — 조용히 건너뛰면 "다 붙었다" 로 읽힌다.
    """
    reps = (await db.execute(select(ImpactReport))).scalars().all()
    groups: dict[str, list[ImpactReport]] = {}
    no_name: list[str] = []
    for r in reps:
        free = report_free_task(r)
        if not free:
            no_name.append(r.id)
            continue
        groups.setdefault(free, []).append(r)

    plan: list[dict] = []
    for free in sorted(groups):
        rows = groups[free]
        key, how = await resolve_task(db, free)
        codes = sorted({str((r.eng_meta or {}).get("dev_revision", {}).get("code") or "")
                        for r in rows} - {""})
        entry = {
            "free": free,
            "reports": sorted(r.id for r in rows),
            "n_reports": len(rows),
            "codes": codes,
            "task_key": key,
            "how": how or None,
        }
        if key:
            entry["verdict"] = "links"
        else:
            cands = await task_candidates(db, free)
            entry["candidates"] = cands
            entry["verdict"] = "proposal" if cands else "unmatched"
        plan.append(entry)
        if limit and len(plan) >= limit:
            break

    counts = {
        "reports": len(reps),
        "reports_without_a_name": len(no_name),
        "strings": len(groups),
        "links": sum(1 for e in plan if e["verdict"] == "links"),
        "proposal": sum(1 for e in plan if e["verdict"] == "proposal"),
        "unmatched": sum(1 for e in plan if e["verdict"] == "unmatched"),
    }
    # ★붙은 수만 말하지 않는다. 못 붙인 수와 **이름조차 없는 리포트 수**를 같이 말한다 —
    #   그것을 빼면 "다 붙었다" 가 거짓이 된다.
    return {"counts": counts, "plan": plan, "reports_without_a_name": sorted(no_name)}


async def confirm_alias(db, *, alias: str, key: str, by: str = "", note: str = "",
                        type_slug: str = TYPE_TASK) -> dict:
    """사람이 "이 문자열은 저 과제다" 를 적는다. **한 문자열은 한 과제만** 가리킨다."""
    alias, key = (alias or "").strip(), (key or "").strip()
    if not alias or not key:
        return {"ok": False, "error": "missing", "detail": "문자열과 식별자가 둘 다 필요하다"}
    found = (await db.execute(
        select(OntoAlias).where(OntoAlias.type_slug == type_slug,
                                OntoAlias.alias == alias))).scalar_one_or_none()
    if found is not None and found.key != key:
        # 조용히 갈아치우지 않는다 — 앞서 붙인 사람의 판단을 덮는 일이다.
        return {"ok": False, "error": "already_bound", "existing": found.key,
                "detail": f"{alias!r} 는 이미 {found.key!r} 에 붙어 있다 — 먼저 떼야 한다"}
    if found is None:
        db.add(OntoAlias(type_slug=type_slug, alias=alias, key=key, source="manual",
                         confirmed_by=by or "", note=note or ""))
    else:
        found.confirmed_by = by or found.confirmed_by
        found.note = note or found.note
    await db.flush()
    return {"ok": True, "alias": alias, "key": key}


async def apply_task_links(db, *, only: list[str] | None = None,
                           decided_by: str = "") -> dict:
    """계획 중 **붙는 것만** 실제로 잇는다(후보·못 붙인 것은 건드리지 않는다).

    `only` 를 주면 그 자유 문자열만. 각 리포트는 자기 `dev_revision` 코드로 이어진다 —
    코드가 없는 리포트는 **과제만 알고 개정은 모르는 것**이므로 건너뛰고 그 수를 돌려준다.
    """
    planned = await plan_task_links(db)
    done = {"linked": 0, "skipped_no_code": 0, "strings": 0, "refused": []}
    for entry in planned["plan"]:
        if entry["verdict"] != "links":
            continue
        if only is not None and entry["free"] not in only:
            continue
        done["strings"] += 1
        task_key = entry["task_key"]
        for rid in entry["reports"]:
            rep = await db.get(ImpactReport, rid)
            if rep is None:
                continue
            code = str((rep.eng_meta or {}).get("dev_revision", {}).get("code") or "")
            if not code:
                done["skipped_no_code"] += 1
                continue
            got = await set_revision(db, rep, task_key=task_key, code=code,
                                     decided_by=decided_by, source="manual")
            if got.get("ok"):
                done["linked"] += 1
            else:
                done["refused"].append({"report": rid, "why": got.get("error")})
    return done


# ── 되돌리기 ───────────────────────────────────────────────────────────────
# ★사람이 확정하는 기능에 **되돌리는 길이 없으면 반쪽**이다. 그리고 `confirm_alias` 는
#   이미 "먼저 떼야 한다" 고 말하는데 뗄 길이 없었다 — **불가능한 것을 지시하는 오류 메시지**가
#   가장 나쁘다(사람이 그 말을 믿고 찾아다닌다).

async def remove_alias(db, *, alias: str, type_slug: str = TYPE_TASK) -> dict:
    """붙여 둔 별칭을 뗀다. 없으면 **없다고 말한다**(조용히 성공하지 않는다)."""
    alias = (alias or "").strip()
    if not alias:
        return {"ok": False, "error": "missing", "detail": "뗄 문자열이 필요하다"}
    found = (await db.execute(
        select(OntoAlias).where(OntoAlias.type_slug == type_slug,
                                OntoAlias.alias == alias))).scalar_one_or_none()
    if found is None:
        return {"ok": False, "error": "not_found", "detail": f"{alias!r} 에 붙은 것이 없다"}
    was = found.key
    await db.delete(found)
    await db.flush()
    # ⚠**이미 이어 둔 개정은 건드리지 않는다.** 별칭은 "다음부터 이렇게 붙여라" 는 규칙이고,
    #   과거에 그 규칙으로 붙인 것은 사람이 확정한 사실이다. 함께 끊으면 되돌릴 수 없다.
    return {"ok": True, "alias": alias, "was": was,
            "detail": "이미 이어 둔 개정은 그대로 둔다 — 끊으려면 리포트마다 해제한다"}


async def unlink_revision(db, report: ImpactReport) -> dict:
    """리포트와 개정 사이의 선을 끊는다. **개정 객체는 지우지 않는다.**

    왜 객체를 남기나 — 그 판에 다른 리포트가 달려 있을 수 있고, `supersedes` 줄의 가운데일
    수도 있다. 지우면 줄이 끊기고 그것은 되돌릴 수 없다. 선만 끊으면 다시 이을 수 있다.
    """
    edges = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_MEASURED,
                                   OntoRelation.src_type == TYPE_REPORT,
                                   OntoRelation.src_key == str(report.id),
                                   OntoRelation.deleted.is_(False)))).scalars().all()
    if not edges:
        return {"ok": False, "error": "not_linked", "detail": "이어진 개정이 없다"}
    keys = sorted({e.dst_key for e in edges})
    for e in edges:
        await db.delete(e)
    await db.flush()
    return {"ok": True, "was": keys,
            "detail": "개정 객체는 남긴다 — 다른 리포트가 달려 있거나 줄의 가운데일 수 있다"}


# ── 개정 간 비교 ───────────────────────────────────────────────────────────

async def compare(db, task_key: str) -> dict:
    """한 과제의 개정을 **나란히** 놓는다 — 그것이 이 기능의 목적이다.

    숫자는 **리포트에 이미 승격된 칸**(`worst_stress`·`worst_g`·`max_severity`·`n_cases`)을
    그대로 쓴다. 다시 계산하지 않는다 — 같은 값을 두 곳에서 계산하면 반드시 갈린다.

    ★**판마다 리포트가 여럿일 수 있다.** 그때 하나를 골라 대표로 삼지 않는다 — 어느 것을
    골랐는지가 안 보이면 비교가 거짓이 된다. 최악값은 **그 판의 리포트 전부에서** 모으고,
    몇 건에서 모았는지를 함께 낸다.
    """
    line = await history(db, task_key)
    # ★모르는 과제와 '개정 없음' 을 가른다(KR-07). 단, **개정이 있으면 그 자체로 '아는' 과제다** —
    #   개정은 거울에 없는 자유 문자열 key 에도 붙을 수 있다(set_revision). 그래서 개정이 없을 때만
    #   거울 존재를 따진다: 거울에 있으면 '개정 없음', 없으면 unknown_task.
    if not line:
        if await task_exists(db, task_key):
            return {"task": task_key, "task_found": True, "revisions": [],
                    "note": "이 과제는 있으나 이어진 개정이 없다"}
        return {"task": task_key, "task_found": False, "reason": "unknown_task", "revisions": [],
                "hint": "list_tasks 로 정본 과제명을 먼저 찾으라 — 과제코드로도 검색되고 matched_by 로 무엇으로 걸렸는지 온다"}

    ids = sorted({rid for r in line for rid in r["reports"]})
    rows = {}
    if ids:
        for rep in (await db.execute(
                select(ImpactReport).where(ImpactReport.id.in_(ids)))).scalars():
            rows[rep.id] = rep

    out = []
    for rev in line:
        reps = [rows[i] for i in rev["reports"] if i in rows]
        stresses = [r.worst_stress for r in reps if r.worst_stress is not None]
        gs = [r.worst_g for r in reps if r.worst_g is not None]
        sev = [r.max_severity for r in reps if r.max_severity]
        out.append({
            **rev,
            "n_reports": len(rev["reports"]),
            # ★없는 것을 0 으로 만들지 않는다 — 0 은 "쟀는데 0" 으로 읽힌다.
            "worst_stress": max(stresses) if stresses else None,
            "worst_g": max(gs) if gs else None,
            "max_severity": ("CRITICAL" if "CRITICAL" in sev else
                             "WARNING" if "WARNING" in sev else
                             sev[0] if sev else None),
            "n_cases": sum(r.n_cases or 0 for r in reps),
            # 몇 건에서 모았나 — 한 건과 열 건의 최악값은 같은 뜻이 아니다.
            "measured_from": len(reps),
            "missing_reports": sorted(set(rev["reports"]) - set(rows)),
        })
    # 앞 판 대비 변화 — **양쪽에 값이 있을 때만** 낸다(한쪽이 비면 변화를 말할 수 없다).
    for i, cur in enumerate(out):
        prev = out[i - 1] if i else None
        if prev and cur["worst_stress"] is not None and prev["worst_stress"] is not None:
            cur["d_worst_stress"] = round(cur["worst_stress"] - prev["worst_stress"], 3)
        else:
            cur["d_worst_stress"] = None
    return {"task": task_key, "task_found": True, "revisions": out}


async def task_exists(db, key: str) -> bool:
    """받은 거울에 이 과제명(plm_task.key)이 있나 — '모르는 과제'와 '개정 없음'을 가르는 데 쓴다(KR-07)."""
    row = (await db.execute(
        select(OntoObject.id).where(OntoObject.type_slug == TYPE_TASK,
                                    OntoObject.key == key,
                                    OntoObject.deleted.is_(False)))).first()
    return row is not None


# ── 허브 식별자 바뀜 · 합침 — 층 2(SP 키트 10-21 §6) ────────────────────────
# 층 1(`app/runner/sp_core.py`)은 사본(허브 거울 행 · 허브 선)만 맞춘다. 우리 것 — 개정(`<과제>@<코드>` 열쇠 · 우리 선) ·
# 별칭 표 · 개정의 모델 칸 — 은 여기서 **사본 표만 읽고** 맞춘다. SP API 를 부르지 않는다.
#   식별자 바뀜 — 같은 것이다. 저절로 옮긴다(키트 §6: 같은 레코드의 key 만 바꾼다. 새 레코드를 만들지 않는다).
#   합침(`merged_into`) — 저절로 옮기지 않는다. 알리고 관리자가 누른다(사용자 결정 10-30 「알리고 사람이 옮긴다」).

MOVE_RENAME = "hub_rename"
MOVE_MERGE = "hub_merge"
_HOPS = 10      # 합침 · 바뀜이 줄줄이 이어질 때 따라가는 한도 — 데이터가 돌아도 멈춘다


async def renamed_keys(db, type_slug: str) -> dict[str, str]:
    """(옛 key → 지금 key). 그 옛 key 로 허브 행이 다시 있으면 뺀다 — 다시 쓰인 식별자다(지금 key 로 살아 있다)."""
    pairs = [(o, k) for o, k in (await db.execute(select(OntoPreviousKey.old_key, OntoPreviousKey.key).where(
        OntoPreviousKey.type_slug == type_slug))).all() if o and k and o != k]
    if not pairs:
        return {}
    live = set((await db.execute(select(OntoObject.key).where(
        OntoObject.type_slug == type_slug, OntoObject.source == SOURCE_HUB,
        OntoObject.key.in_([o for o, _ in pairs])))).scalars())
    return {o: k for o, k in pairs if o not in live}


async def current_key(db, type_slug: str, key: str) -> str:
    """옛 식별자면 지금 것으로, 아니면 그대로(키트 §6 — 못 찾으면 옛 → 새 로 풀어 다시 찾는다)."""
    key = (key or "").strip()
    if not key:
        return key
    if (await db.execute(select(OntoObject.id).where(
            OntoObject.type_slug == type_slug, OntoObject.key == key,
            OntoObject.source == SOURCE_HUB))).first() is not None:
        return key
    now = (await db.execute(select(OntoPreviousKey.key).where(
        OntoPreviousKey.type_slug == type_slug, OntoPreviousKey.old_key == key))).scalar_one_or_none()
    return now or key


async def _hub_task(db, key: str) -> OntoObject | None:
    return (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == TYPE_TASK, OntoObject.key == key,
        OntoObject.source == SOURCE_HUB))).scalar_one_or_none()


async def _merge_end(db, key: str) -> tuple[str, OntoObject | None]:
    """합쳐진 곳을 끝까지 — A→B 로 합쳤는데 B 도 C 로 합쳐졌거나 이름이 바뀌었으면 C."""
    cur, row, seen = key, None, set()
    for _ in range(_HOPS):
        cur = await current_key(db, TYPE_TASK, cur)
        if cur in seen:
            break
        seen.add(cur)
        row = await _hub_task(db, cur)
        if row is None or not row.deleted or not row.merged_into:
            break
        cur = row.merged_into
    return cur, row


async def task_state(db, key: str) -> dict:
    """과제 하나의 지금 처지 — 화면이 띄울 알림 재료.

    state — `active` · `deprecated`(그만 씀 — 새로 고르는 목록에서만 숨긴다) · `merged`(합쳐짐 — 관리자가 옮긴다) ·
    `gone`(허브에서 사라짐 — 「사용 안 함」) · `hidden`(이 자격으로 안 보임) · `renamed`(옛 식별자 — 다음 반영이 옮긴다) ·
    `unknown`(허브에 없는 자유 문자열). 사용자 결정 10-30(지시서 기본안).
    """
    key = (key or "").strip()
    row = await _hub_task(db, key) if key else None
    if row is None:
        now = await current_key(db, TYPE_TASK, key) if key else key
        if now != key:
            return {"key": key, "state": "renamed", "now": now}
        return {"key": key, "state": "unknown"}
    base = {"key": key, "label": row.label}
    if row.deleted and row.hidden:
        return {**base, "state": "hidden"}
    if row.deleted and row.merged_into:
        into, end = await _merge_end(db, row.merged_into)
        return {**base, "state": "merged", "merged_into": row.merged_into, "into": into,
                "into_label": end.label if end is not None else None,
                "into_active": bool(end is not None and not end.deleted)}
    if row.deleted:
        return {**base, "state": "gone"}
    if row.status == "deprecated":
        return {**base, "state": "deprecated"}
    return {**base, "state": "active"}


async def _same_edge(db, r: OntoRelation, src: str, dst: str) -> OntoRelation | None:
    return (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == r.relation, OntoRelation.src_type == r.src_type, OntoRelation.src_key == src,
        OntoRelation.dst_type == r.dst_type, OntoRelation.dst_key == dst,
        OntoRelation.id != r.id))).scalar_one_or_none()


async def _repoint(db, old: str, new: str, *, incoming_only: bool) -> dict:
    """우리 선에서 개정 끝 `old` 를 `new` 로. 같은 선이 이미 있으면 옛 줄을 지운다(살아 있는 쪽을 남긴다).

    `supersedes` 가 제 자신을 가리키거나 줄이 돌게 되면 옮기지 않고 끊는다(`deleted`) — 개정 줄을 따라가는 질의가
    돈다(`set_revision` 의 순환 거절과 같은 까닭). 끊은 것은 돌려줘서 실행 기록에 남긴다.
    """
    done = {"reports": 0, "edges": 0, "dropped": []}
    ends = [and_(OntoRelation.dst_type == TYPE_REVISION, OntoRelation.dst_key == old)]
    if not incoming_only:
        ends.append(and_(OntoRelation.src_type == TYPE_REVISION, OntoRelation.src_key == old))
    rows = (await db.execute(select(OntoRelation).where(
        OntoRelation.source == SOURCE_SELF, OntoRelation.deleted.is_(False), or_(*ends)))).scalars().all()
    for r in rows:
        src = new if (not incoming_only and r.src_type == TYPE_REVISION and r.src_key == old) else r.src_key
        dst = new if (r.dst_type == TYPE_REVISION and r.dst_key == old) else r.dst_key
        if r.relation == REL_SUPERSEDES and (src == dst or src in await _chain_keys(db, dst)):
            r.deleted = True
            done["dropped"].append(f"{r.src_key} → {r.dst_key}")
            await db.flush()
            continue
        clash = await _same_edge(db, r, src, dst)
        if clash is not None:
            clash.deleted = False
            await db.delete(r)
        else:
            r.src_key, r.dst_key = src, dst
        await db.flush()
        done["reports" if r.relation == REL_MEASURED else "edges"] += 1
    return done


async def move_task_revisions(db, from_key: str, to_key: str, *, by: str = "", reason: str = "") -> dict:
    """과제 A 에 매달린 **우리 것**(개정 · 별칭)을 과제 B 로 옮긴다 — 식별자 바뀜(저절로)과 합침(관리자)이 함께 쓴다.

    개정 key 는 `<과제>@<코드>` 라 과제가 바뀌면 key 도 바뀐다 — 같은 개정 행의 key 만 바꾸고 선의 끝을 따라 옮긴다.
    ★B 에 같은 코드 개정이 이미 있으면 A 쪽 리포트 선(`measured_at`)과 A 쪽을 앞 판으로 둔 선만 B 개정으로 옮기고,
    A 쪽 개정은 지우지 않고 비활성(`merged_into`)으로 둔다 — 지우면 되돌릴 수 없다. 옮긴 사람 · 까닭은 개정 칸에 남긴다.
    """
    from_key, to_key = (from_key or "").strip(), (to_key or "").strip()
    done: dict[str, Any] = {"from": from_key, "to": to_key, "revisions": 0, "collapsed": 0,
                            "reports": 0, "edges": 0, "aliases": 0, "dropped": []}
    if not from_key or not to_key or from_key == to_key:
        return done
    revs = [r for r in (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == TYPE_REVISION, OntoObject.source == SOURCE_SELF,
        OntoObject.deleted.is_(False)))).scalars().all()
        if str((r.properties or {}).get("task") or "") == from_key]
    for rev in revs:
        props = dict(rev.properties or {})
        code = str(props.get("code") or rev.key.rsplit("@", 1)[-1])
        old, new = rev.key, revision_key(to_key, code)
        note = {"from": old, "to": new, "why": reason, "by": by, "at": _now()}
        props["moves"] = [*(props.get("moves") or []), note]
        there = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == TYPE_REVISION, OntoObject.key == new))).scalar_one_or_none()
        if there is None:
            # 같은 개정이다 — key 만 바꾼다
            for e in (await db.execute(select(OntoRelation).where(
                    OntoRelation.relation == REL_OF, OntoRelation.source == SOURCE_SELF,
                    OntoRelation.src_type == TYPE_REVISION, OntoRelation.src_key == old))).scalars().all():
                await db.delete(e)
            rev.key = new
            rev.label = f"{to_key} {code}"
            rev.properties = {**props, "task": to_key}
            rev.previous_keys = list(dict.fromkeys([*(rev.previous_keys or []), old]))
            await db.flush()
            await _edge(db, REL_OF, TYPE_REVISION, new, TYPE_TASK, to_key)
            moved = await _repoint(db, old, new, incoming_only=False)
            done["revisions"] += 1
        else:
            # B 에 같은 판이 있다 — 리포트와 「이것을 앞 판으로 둔 선」 만 그리로. A 쪽 개정은 비활성.
            if there.deleted:
                there.deleted, there.merged_into = False, None
            moved = await _repoint(db, old, new, incoming_only=True)
            rev.properties = props
            rev.deleted, rev.merged_into = True, new
            await db.flush()
            done["collapsed"] += 1
        done["reports"] += moved["reports"]
        done["edges"] += moved["edges"]
        done["dropped"] += moved["dropped"]
    res = await db.execute(update(OntoAlias).where(
        OntoAlias.type_slug == TYPE_TASK, OntoAlias.key == from_key).values(key=to_key))
    done["aliases"] = int(res.rowcount or 0)
    await db.flush()
    return done


async def merged_tasks(db) -> list[dict]:
    """허브에서 합쳐졌는데(`merged_into`) 우리 것(개정 · 별칭)이 아직 진 쪽에 매달린 과제 — 관리자가 옮길 목록."""
    gone = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == TYPE_TASK, OntoObject.source == SOURCE_HUB, OntoObject.deleted.is_(True),
        OntoObject.hidden.is_(False), OntoObject.merged_into.isnot(None)))).scalars().all()
    if not gone:
        return []
    keys = {g.key for g in gone}
    revs: dict[str, list[str]] = {}
    for r in (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == TYPE_REVISION, OntoObject.source == SOURCE_SELF,
            OntoObject.deleted.is_(False)))).scalars().all():
        task = str((r.properties or {}).get("task") or "")
        if task in keys:
            revs.setdefault(task, []).append(r.key)
    aliases: dict[str, int] = {}
    for a in (await db.execute(select(OntoAlias.key).where(
            OntoAlias.type_slug == TYPE_TASK, OntoAlias.key.in_(sorted(keys))))).scalars():
        aliases[a] = aliases.get(a, 0) + 1
    out = []
    for g in sorted(gone, key=lambda x: x.key):
        mine = sorted(revs.get(g.key, []))
        if not mine and not aliases.get(g.key):
            continue
        reports = 0
        if mine:
            reports = len((await db.execute(select(OntoRelation.id).where(
                OntoRelation.relation == REL_MEASURED, OntoRelation.dst_type == TYPE_REVISION,
                OntoRelation.dst_key.in_(mine), OntoRelation.deleted.is_(False)))).all())
        into, end = await _merge_end(db, g.merged_into)
        out.append({"key": g.key, "label": g.label, "merged_into": g.merged_into, "into": into,
                    "into_label": end.label if end is not None else None,
                    "into_active": bool(end is not None and not end.deleted),
                    "revisions": mine, "reports": reports, "aliases": aliases.get(g.key, 0)})
    return out


async def move_merged_task(db, key: str, *, by: str = "", note: str = "") -> dict:
    """관리자가 누른 「B 로 옮기기」 — 허브가 합친 과제(A)의 우리 것을 합쳐진 곳(끝까지 따라간 B)으로.

    받는 곳은 허브가 정한 것뿐이다 — 고를 칸을 두지 않는다(사람이 고르는 것은 「옮길까」 이지 「어디로」 가 아니다).
    """
    row = await _hub_task(db, (key or "").strip())
    if row is None or not row.deleted or not row.merged_into or row.hidden:
        return {"ok": False, "error": "not_merged", "detail": f"{key!r} 는 허브에서 합쳐진 과제가 아니다"}
    into, end = await _merge_end(db, row.merged_into)
    if end is None or end.deleted:
        return {"ok": False, "error": "target_gone", "into": into,
                "detail": f"합쳐진 곳 {into!r} 도 허브에 살아 있지 않다 — 옮길 곳이 없다"}
    got = await move_task_revisions(db, row.key, into, by=by, reason=MOVE_MERGE + (f" — {note}" if note else ""))
    return {"ok": True, **got}


async def reflect_after_sync(db) -> dict:
    """층 2 — 받은 사본만 읽고 이 플랫폼의 것에 반영한다(받기 한 번마다 `plm_sync.sync_once` 가 부른다).

    ① 과제 식별자 바뀜 — 우리 개정 · 별칭을 새 key 로 저절로 옮긴다. ② 모델 식별자 바뀜 — 개정의 `model` 칸.
    ③ 합쳐진 과제 — **옮기지 않고 센다**(실행 기록 · 관리 화면이 띄운다). 매번 전체 대조다(키트 §6 — 수만 건 이하면
    그것이 가장 단순하고 틀릴 일이 적다). 옮길 것이 없으면 아무것도 쓰지 않는다.
    """
    out: dict[str, Any] = {"renamed": 0, "revisions": 0, "collapsed": 0, "reports": 0, "aliases": 0,
                           "models": 0, "dropped": [], "merged_waiting": 0}
    for old, new in sorted((await renamed_keys(db, TYPE_TASK)).items()):
        got = await move_task_revisions(db, old, new, reason=MOVE_RENAME)
        if got["revisions"] or got["collapsed"] or got["aliases"]:
            out["renamed"] += 1
        for k in ("revisions", "collapsed", "reports", "aliases"):
            out[k] += got[k]
        out["dropped"] += got["dropped"]
    models = await renamed_keys(db, TYPE_MODEL)
    if models:
        for r in (await db.execute(select(OntoObject).where(
                OntoObject.type_slug == TYPE_REVISION, OntoObject.source == SOURCE_SELF))).scalars().all():
            was = str((r.properties or {}).get("model") or "")
            if was in models:
                r.properties = {**(r.properties or {}), "model": models[was]}
                out["models"] += 1
        await db.flush()
    out["merged_waiting"] = len(await merged_tasks(db))
    return out
