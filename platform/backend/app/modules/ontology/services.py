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

import logging
import re
import weakref
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, inspect, or_, select, text, update
from sqlalchemy.exc import DBAPIError

from app.models import (SOURCE_HUB, SOURCE_SELF, ImpactReport, OntoAlias,
                        OntoObject, OntoPreviousKey, OntoRelation)
from app.reports.datahub import DataHubError, parse_stage
from app.shared.errors import short_error

logger = logging.getLogger("koorm.ontology")

TYPE_REVISION = "dev_revision"
TYPE_TASK = "plm_task"
TYPE_MODEL = "plm_model"
TYPE_REPORT = "impact_report"       # 우리 1급 표 — `onto_objects` 에 행을 만들지 않는다
REL_OF = "revision_of"
REL_SUPERSEDES = "supersedes"
REL_MEASURED = "measured_at"
UNLINK_MARK = "unlinked_at"        # 사람이 끊은 리포트 선에 다는 칸(+ unlinked_by) — 「끊은 기록」(11-11)

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


class ReportsBusy(Exception):
    """판 이름을 쥔 트랜잭션이 잠그려던 리포트 행(또는 옮길 판)을 다른 트랜잭션이 쥐고 있다 — 기다리면 교착할 수 있어 기다리지 않았다."""


_NAMES_HELD = "onto_rev_names_tx"     # 판 이름 잠금을 쥔 바깥 트랜잭션(약한 참조) — `db.info` 에 둔다


def _names_held(db) -> bool:
    """이 세션의 지금 바깥 트랜잭션이 판 이름 잠금을 쥐었나(트랜잭션 잠금이라 그 트랜잭션이 끝나면 풀린다)."""
    ref, tx = db.info.get(_NAMES_HELD), db.sync_session.get_transaction()
    return ref is not None and tx is not None and ref() is tx


async def lock_reports(db, ids, *, wait: bool = True) -> set[str]:
    """리포트 행을 id 차례로 잠근다(`SELECT … ORDER BY id FOR UPDATE`, 트랜잭션이 끝날 때 풀린다).

    ★리포트 선(리포트 → 개정)을 고치는 **모든 길**이 다른 행을 건드리기 전에 이것부터 한다 — 사람 확정 · 끊기 · 끊은 기록 지우기 ·
    인제스트 때 잇기 · 자동 잇기 · 관리자 일괄 적용 · 허브 이름 바뀜 옮기기. 잠금 차례가 하나(리포트 행 먼저 id 차례, 그다음 판
    이름 — `lock_revision_names`)라 서로 교착하지 않고, 잠근 뒤에 다시 읽으므로 겹친 쪽이 본 것을 덮지 않는다(검토 R11 · R7 · R2 —
    받기 뒤 자동 잇기는 긴 트랜잭션이다).
    DB 에 없는 리포트(시험의 손 객체)는 잠글 것이 없어 지나간다 — 돌려주는 것은 잠근 리포트 id(DB 에 있는 것)다.
    ★판 이름을 이미 쥔 트랜잭션은 리포트 행을 **기다리지 않는다**(NOWAIT) — 그 리포트를 쥐고 판 이름을 기다리는 길(손 확정 · 인제스트
    때 잇기)과 교착한다(재검토 11-12 rr5 — 이름 바뀜 옮기기가 앞 과제의 판을 쥔 채 뒤 과제에 그새 이어진 리포트를 기다렸다). 못 잠그면
    그 저장점만 되감고 `ReportsBusy` 다(부르는 쪽 — 옮기기 — 가 미룬다). 이미 쥔 행은 NOWAIT 이어도 그대로 잠긴다.
    `wait=False` 면 판 이름을 쥐기 전에도 기다리지 않는다 — 관리자가 누른 합침 옮기기가 쓴다(재검토 11-14 F-08 — 누름이 그 리포트를
    쥔 트랜잭션이 끝날 때까지 답 없이 기다렸다).
    """
    keys = sorted({str(i) for i in ids if i})
    if not keys:
        return set()
    stmt = select(ImpactReport.id).where(ImpactReport.id.in_(keys)).order_by(ImpactReport.id)
    if wait and not _names_held(db):
        return set((await db.execute(stmt.with_for_update())).scalars().all())
    try:
        async with db.begin_nested():
            return set((await db.execute(stmt.with_for_update(nowait=True))).scalars().all())
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == "55P03":          # lock_not_available
            raise ReportsBusy("누가 지금 고치는 중인 리포트가 있다") from exc
        raise


async def lock_revision_names(db, keys, *, wait: bool = True) -> None:
    """판 **이름** 잠금 — 아직 없는 판 key 도 잠근다(`pg_advisory_xact_lock`, 트랜잭션이 끝날 때 풀린다).

    리포트 행 잠금은 리포트마다라 **다른 리포트 둘**이 같은 새 판을 같은 순간 처음 만들면 서로 막지 못했다 — 둘째가 유일 제약
    (`uq_onto_objects_type_key`)에 걸려 인제스트는 리포트째 잃고 손 확정은 500 이었다(재검토 11-12 rr1). 판 행을 만들거나 고치거나 판
    key 를 그리로 바꾸는 길(`set_revision` · `move_task_revisions`)은 판 행을 읽기 **전에** 이것을 건다 — 둘째는 첫째가 끝날 때까지
    기다렸다가 그때의 판을 읽어 쓴다. 행이 아직 없을 수 있어 행 잠금(FOR UPDATE)으로는 못 한다(이름 잠금이라야 한다).
    ★잠금 차례 — 리포트 행 먼저(`lock_reports`), 그다음 판 이름(key 차례). 두 정수 꼴(`hashtext('dynaforge.rev')` · `hashtext(key)`)이라
    받기 잠금(정수 하나 꼴 — `plm_sync.try_lock`)과 열쇠 공간이 겹치지 않는다.
    `wait=False` 면 남이 쥔 이름을 기다리지 않는다(`pg_try_advisory_xact_lock`) — 하나라도 못 쥐면 이번에 쥔 이름을 다 놓고(저장점을
    되감으면 그 안에서 쥔 이름이 풀린다) `ReportsBusy` 다. 관리자가 누른 합침 옮기기가 쓴다(재검토 11-14 F-08).
    """
    keys = sorted({str(k) for k in keys if k})
    if wait:
        for k in keys:
            await db.execute(text("select pg_advisory_xact_lock(hashtext('dynaforge.rev'), hashtext(:k))"), {"k": k})
    else:
        async with db.begin_nested():
            for k in keys:
                if not (await db.execute(text(
                        "select pg_try_advisory_xact_lock(hashtext('dynaforge.rev'), hashtext(:k))"), {"k": k})).scalar():
                    raise ReportsBusy("누가 지금 고치는 중인 판이 있다")
    if keys:
        db.info[_NAMES_HELD] = weakref.ref(db.sync_session.get_transaction())   # 이 트랜잭션은 이제 리포트를 기다리지 않는다


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
    ★사람이 끊은 리포트(끊은 기록이 있다)는 기계 경로(`source` 가 manual 이 아닌 것)를 `unlinked` 로 거절하고, 사람이 잇는
    것(manual)은 끊은 기록을 지우고 잇는다(11-11). 사람이 **이 리포트를** 다른 판에 확정해 두었으면 기계 경로는 `kept_manual` 로
    거절한다 — 리포트마다(선의 `link_source`) 가른다. 리포트 행을 먼저 잠그고 그 뒤에 읽는다(`lock_reports`).
    """
    task_key = (task_key or "").strip()
    code = (code or "").strip()
    if not task_key or not code:
        return {"ok": False, "error": "missing", "detail": "과제와 개정 코드가 둘 다 필요하다"}
    try:
        rev = parse_stage(code)
    except DataHubError as exc:
        return {"ok": False, "error": "bad_code", "detail": str(exc)}
    # 리포트 행을 먼저 잠그고 그 뒤에 읽는다 — 같은 리포트를 고치는 다른 길과 겹쳐도 선이 둘이 되거나(R11) 끊은 기록이 지워지지
    # 않는다(R2). 받기 뒤 자동 잇기가 이 리포트를 쥐고 있으면 그것이 커밋할 때까지 기다린다.
    locked = await lock_reports(db, [report.id])
    if str(report.id) not in locked and inspect(report).has_identity:
        # 읽은 뒤 그사이 지워졌다(지우기가 굳은 뒤 차례가 왔다) — 선을 넣으면 지운 리포트의 선이 남는다(0019 트리거는 지울 때 한 번
        # 돈다 — 재검토 11-12). DB 에 넣은 적 없는 손 객체(시험)는 잠글 것이 없어 지나간다.
        return {"ok": False, "error": "report_gone", "detail": "리포트가 그사이 지워졌다"}
    # ★사람이 끊은 리포트(11-11) — 기계 경로(인제스트 때 잇기 · 수동 메타 고침 · 자동 잇기)는 **다시 잇지 않는다**. 이 자리에서
    #   막아야 앞으로 생길 자동 경로도 같은 규칙을 지난다. 사람이 손으로 이으면(manual) 아래에서 기록을 지운다.
    marks = await unlink_rows(db, report.id)
    if marks and source != "manual":
        return {"ok": False, "error": "unlinked",
                "detail": "사람이 이 리포트의 개정 연결을 끊었다 — 기계는 다시 잇지 않는다"
                          "(손으로 다시 잇거나 끊은 기록을 지우면 다시 잇는다)"}
    key = revision_key(task_key, code)
    live = (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
        OntoRelation.src_key == str(report.id), OntoRelation.deleted.is_(False))
        .execution_options(populate_existing=True))).scalars().all()
    if source != "manual":
        # ★사람이 **이 리포트를** 다른 판에 확정했으면 기계(인제스트 때 잇기 · 수동 메타 고침 · 자동 잇기 · 일괄 적용)는 옮기지
        #   않는다 — 리포트마다 가른다(검토 R5: 남이 자기 리포트를 같은 판에 확정했다고 내 기계 선이 굳으면 안 된다).
        others = [e for e in live if e.dst_key != key]
        legacy = await _manual_revisions(db, [e.dst_key for e in others if not (e.properties or {}).get("link_source")])
        if any(_human_link(e.properties, e.dst_key, legacy) for e in others):
            return {"ok": False, "error": "kept_manual",
                    "detail": "사람이 이 리포트를 다른 판에 확정했다 — 기계는 옮기지 않는다(사람이 다시 확정하거나 끊으면 바뀐다)"}

    # 과제 거울이 있으면 확인한다. **없다고 막지는 않는다** — 허브가 아직 없을 수 있고,
    # 그때 막으면 개정을 아예 못 붙인다. 대신 "확인 못 했다" 를 돌려준다.
    task = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.key == task_key))).scalar_one_or_none()
    unverified = task is None

    if supersedes:
        if supersedes == key:
            return {"ok": False, "error": "self_supersede", "detail": "자기를 앞 판으로 둘 수 없다"}
        # ★순환을 막는다 — 막지 않으면 개정 줄을 따라가는 질의가 **영원히 돈다.**
        if key in await _chain_keys(db, supersedes):
            return {"ok": False, "error": "cycle",
                    "detail": f"{supersedes!r} 의 앞줄에 이미 {key!r} 가 있다"}
    if marks:
        # 사람이 다시 잇는다 — 끊은 기록을 지운다(검사를 다 지난 뒤에 — 거절되면 기록이 남아야 한다). 같은 판의 기록을
        # 남겨 두면 아래 `_edge` 가 그 행을 되살리며 끊은 사람 · 때를 그대로 단 채 둔다.
        for m in marks:
            await db.delete(m)
        await db.flush()

    # ★판 이름 잠금(리포트 행 다음) — 같은 새 판을 다른 리포트가 지금 만들고 있으면 그것이 끝날 때까지 기다렸다가 그때의 판을
    #   읽는다(재검토 11-12 rr1 — 예전엔 둘째가 유일 제약에 걸렸다). 잠근 뒤 새로 읽는다(정체 맵의 옛 판 객체를 믿지 않는다).
    await lock_revision_names(db, [key])
    obj = (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_REVISION,
                                 OntoObject.key == key)
        .execution_options(populate_existing=True))).scalar_one_or_none()
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
        #   지나가며 `rev_source` 를 기계 출처(`eng_meta` · `rule`)로 되돌리면, 사람이 고친 사실이 사라진다.
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
    #   다 잡혀 판끼리 견준 숫자가 틀어진다(10-30 실측: dv1 → pv1 다시 확정 뒤 선 둘). **살아 있는 선만** 뗀다 — 끊은 기록
    #   (지운 표시를 단 선)은 위에서 사람이 이을 때만 지운다(R2).
    for old in live:
        if old.dst_key != key:
            await db.delete(old)
    # 리포트는 우리 1급 표다 — 행을 만들지 않고 **선의 끝점**으로만 쓴다. 선에 **누가 이었나**를 적는다(`link_source` —
    # manual 사람 · rule 이름이 정확 일치 규칙으로 허브 과제 하나에 풀렸다 · eng_meta 허브가 모르는 이름을 글자 그대로, 사람이면
    # `linked_by`) — 사람 판인지는 리포트마다 이것으로 가른다(판의 `rev_source` 는 판 하나에 하나라 여러 리포트가 나눠 쓴다). 사람이
    # 이은 선을 기계가 같은 판으로 다시 지나가면 사람 표시를 덮지 않는다.
    # ★여기서 **쓸 때** 찍는 표시다 — 이미 그 판에 있어 부르는 쪽이 쓰지 않고 지나간 선(`already`)은 옛 표시 그대로다. 판의
    # `rev_source` 는 그 판에 마지막으로 쓴 쪽의 값이다(사람 판은 기계가 덮지 않는다 — 재검토 11-14).
    stamp: dict[str, Any] = {"link_source": source, "linked_at": _now()}
    if source == "manual":
        stamp["linked_by"] = decided_by or ""
    row = (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
        OntoRelation.src_key == str(report.id), OntoRelation.dst_type == TYPE_REVISION,
        OntoRelation.dst_key == key).execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:
        db.add(OntoRelation(relation=REL_MEASURED, src_type=TYPE_REPORT, src_key=str(report.id),
                            dst_type=TYPE_REVISION, dst_key=key, source=SOURCE_SELF, properties=stamp, deleted=False))
    elif row.deleted:
        row.deleted, row.properties = False, stamp
    elif source == "manual" or not _human_link(row.properties, key, await _manual_revisions(db, [key])):
        row.properties = {**(row.properties or {}), **stamp}
    await db.flush()

    return {"ok": True, "key": key, "rev_seq": props["rev_seq"],
            "task_unverified": unverified,
            "detail": ("과제 거울이 없어 확인하지 못했다 — 허브 수신이 켜지면 확인된다"
                       if unverified else "")}


async def link_from_eng_meta(db, report: ImpactReport) -> dict:
    """인제스트·PATCH 가 부르는 자동 경로. 수동 메타(`eng_meta`)의 과제 · 개정 코드로 **찾거나 만들고** 잇는다.

    ★판정은 자동 잇기(`auto_link_tasks`)와 **하나다**(사용자 결정 11-12 「허브에 있으면 판정을 따른다」) — 과제 이름을 같은 정확 일치
    규칙(`exact_matches` · `_pick`)으로 본다. 예전엔 이 길만 글자 그대로 이어서 두 기계 길이 같은 리포트를 다른 판에 놓았다(반입마다
    「과제코드@판」 헛 판 · 값이 같은 메타 저장이 rule 선을 되돌림 · 엇갈린 이름을 조용히 이음 — 재검토 11-12).
    「허브가 아는 이름」 은 **거울에 있는 과제를 가리키는 원천이 하나라도 있는** 이름이다(`exact_matches` 가 낸 것 가운데
    `alias_missing` 이 아닌 것 — 과제명 · 과제코드 · 옛 과제명 · 끝이 거울에 있는 우리 별칭 · 허브 별칭 · 이름(label)). 셋으로 가른다.
      허브가 알고 과제 **하나로** 풀린다(과제명 · 과제코드 · 옛 과제명 · 별칭) — 그 과제의 판에 `rule` 로 잇는다. 이미 그 판에만
        이어져 있으면 **아무것도 쓰지 않는다**(`already` — 선의 표시(`link_source` · `linked_at`)도 판도 다시 찍지 않는다).
      허브가 아는데 하나로 정해지지 않는다(여러 과제에 걸린다 · 이름(label)만 같다 · 거울의 과제와 맞는데 우리 별칭은 거울에 없는
        과제를 가리킨다 · 그만 쓴 과제 여럿) — **잇지 않는다**(`undecided`). 아무것도 쓰지 않는다 — 있던 기계 선도 옮기거나 떼지
        않는다. 그 선이 메타 글자와 다른 판이면 `mismatch` 가 말한다 — 메타 글자 그대로의 판이면 `mismatch` 는 비어 있고(글자가
        같으면 먼저 None 이다), 개정 보기의 `ambiguous` · `task_candidates` 와 미리 보기의 그 이름 줄만 그 리포트를 가리킨다(재검토
        11-14 — 예전 글은 조건 없이 「어긋남은 `mismatch` 가 말한다」 였다).
      허브가 **모른다**(거울의 과제를 가리키는 원천이 없다) — 예전처럼 수동 메타 **글자 그대로** `eng_meta` 로 잇는다. 허브 없는
        박스(dev)와 허브에 아직 없는 과제는 동작이 그대로다. ★끝이 거울에 없는 우리 별칭**만** 맞는 이름도 허브가 모르는 이름이다 —
        거울이 빈 박스에도 별칭은 생길 수 있어서(`confirm_alias` 는 끝이 거울에 있는지 보지 않는다) 그것을 엇갈림으로 세면 그 박스의
        반입 동작이 바뀐다. 자동 잇기 · 미리 보기는 그대로다 — 그 이름을 `alias_missing` 으로 보이고, 글자 그대로 이은 선을 옮기지
        않는다(별칭의 끝이 거울에 오면 그때 옮긴다).
    그래서 선의 `link_source` 는 — `rule` 은 이름이 정확 일치 규칙으로 허브 과제 하나에 풀려 이은 것(반입 · 메타 고침 · 받기 뒤 ·
    일괄 적용 · 끊은 기록을 지운 뒤), `eng_meta` 는 허브가 모르는 이름을 글자 그대로 이은 것이다. ★선을 **쓸 때** 찍는 표시다 —
    `already` 로 지나간 선은 옛 표시(`eng_meta` · `manual` · 없음)가 그대로라, 지금은 허브 과제 하나로 풀리는 이름의 선이 `eng_meta`
    일 수 있다(과제가 허브에 오기 전에 글자 그대로 이은 선). 한 판의 리포트들이 서로 다른 표시를 가질 수 있고, 기계가 만든 판의
    `rev_source` 는 그 판에 **마지막으로 쓴** 쪽의 것이다(재검토 11-14 — 예전 글은 「판의 `rev_source` 도 같다」 였다).
    사람이 이미 정한 개정은 **건드리지 않는다**(`set_revision` 의 `kept_manual`). 사람이 끊은 리포트는 수동 메타를 고쳐도
    **다시 잇지 않는다** — `set_revision` 이 `unlinked` 로 거절하고, 메타 고침 자체는 그대로 저장된다(11-11).
    """
    task = report_free_task(report)
    code = str(((report.eng_meta or {}).get("dev_revision") or {}).get("code") or "").strip()
    if not task or not code:
        return {"ok": False, "error": "nothing_to_link",
                "detail": "eng_meta 에 과제와 dev_revision.code 가 둘 다 있어야 한다"}
    found = await exact_matches(db, task)
    if all(how == "alias_missing" for _, how in found):
        # 허브가 모르는 이름(맞는 데가 아예 없거나, 끝이 거울에 없는 우리 별칭만 맞는다) — 예전 그대로 글자 그대로 잇는다. 허브가 바꾼
        # 옛 과제명인데 바뀐 과제가 거울에 살아 있지 않을 때만 key 가 달라진다(지금 것으로 — 안 풀면 옛 key 로 개정이 새로 생겨 같은
        # 판이 둘이 된다, 층 2).
        task = await current_key(db, TYPE_TASK, task)
        return await set_revision(db, report, task_key=task, code=code, source="eng_meta")
    key, _how = _pick(found)
    if not key:
        return {"ok": False, "error": "undecided",
                "detail": f"수동 메타의 과제 {task!r} 는 허브 과제와 맞는 데가 있지만 하나로 정해지지 않는다(여러 과제에 걸린다 · "
                          "이름(label)만 같다 · 허브 과제와 맞는데 사람이 붙인 별칭은 거울에 없는 과제를 가리킨다) — 잇지 않았다(있던 "
                          "선은 그대로 둔다). 과제 잇기 미리 보기가 이 이름을 후보로 보인다 — 사람이 고른다. 후보가 없으면(그만 쓴 "
                          "과제만 맞는다) 못 붙임으로 보이고 고를 것이 없다 — 리포트의 개정 확정(손)으로 잇는다"}
    target = revision_key(key, code)
    # 리포트 행을 먼저 잠그고 그 뒤에 선을 읽는다(다른 모든 길과 같은 차례 — `lock_reports`). 이미 그 판에만 이어져 있으면 쓰지
    # 않는다 — 「이미 바르게 이은 선은 그대로 둔다」(자동 잇기의 `already` 와 같은 판정 · 같은 차례: 사람 선인지 보기 전에 가른다).
    await lock_reports(db, [report.id])
    live = set((await db.execute(select(OntoRelation.dst_key).where(
        OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
        OntoRelation.src_key == str(report.id), OntoRelation.deleted.is_(False)))).scalars().all())
    if live == {target}:
        return {"ok": True, "key": target, "already": True}
    return await set_revision(db, report, task_key=key, code=code, source=SOURCE_RULE)


# ── 어긋남 ─────────────────────────────────────────────────────────────────

async def mismatch(db, report: ImpactReport) -> dict | None:
    """`eng_meta` 와 이어진 개정이 다르면 그 사실을 돌려준다(없으면 `None`).

    ★**관계가 정본**이다. 그러나 조용히 맞추지 않는다 — 맞추면 사람이 넣은 값과 저장된
    값이 달라지고 그 차이는 아무 데도 안 뜬다. 화면이 보여 주고 사람이 고른다.
    「다르다」 는 글자가 아니라 **판정**으로 가른다(11-12) — 수동 메타의 이름(과제코드 · 별칭)이 기계 잇기와 같은 규칙으로 풀리는
    과제의 그 판에 이어져 있으면 어긋남이 아니다. 허브가 이름을 바꿨거나 합친 사실(`renamed` · `merged`)은 그보다 먼저 말한다.
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
    # 수동 메타의 이름이 과제코드 · 별칭이고, 기계 잇기와 같은 판정(`exact_matches` · `_pick`)으로 풀리는 과제의 그 판에 이어져 있다 —
    # 글자는 달라도 어긋남이 아니다(11-12 — 예전엔 글자만 견줘 바르게 이은 선에 「다르다」 경고가 떴다). 이름이 엇갈리면(하나로 안
    # 풀리면) 여기서 걸리지 않아 아래 「다르다」 로 말한다 — 사람이 고른다.
    key, _how = _pick(await exact_matches(db, task))
    if key and revision_key(key, code) == linked:
        return None
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
    # 이 리포트의 선을 누가 이었나(manual 사람 · rule 이름이 허브 과제 하나로 풀렸다 · eng_meta 허브가 모르는 이름을 글자 그대로). 판의
    # rev_source 와 다르다(판은 나눠 쓴다). ★누가 이었는지 적지 않던 때의 옛 선은 그 판이 사람 판이면 manual 로 답한다 — 서버가 그
    # 선을 사람 선으로 지키는 판정(`_human_link`)을 그대로 쓴다(재검토 11-14 F-15 — 화면의 ✓ 가 이 값을 본다. 예전엔 null 이라 손으로
    # 확정한 옛 리포트에서 ✓ 가 사라졌는데 기계는 그 선을 옮기지 못했다). 기계 판의 옛 선은 적힌 것이 없어 null 이다.
    # 선을 **쓸 때** 찍힌 값이다 — `already` 로 지나간 선은 옛 값 그대로다(`set_revision` 의 주석 — 재검토 11-14)
    src = (edge.properties or {}).get("link_source")
    if not src and _human_link(edge.properties, edge.dst_key,
                               {edge.dst_key} if props.get("rev_source") == "manual" else set()):
        src = "manual"
    return {"key": edge.dst_key, "task": str(props.get("task") or edge.dst_key.rsplit("@", 1)[0]),
            "code": props.get("code") or edge.dst_key.rsplit("@", 1)[-1], "source": src}


# ── 개정 줄 ────────────────────────────────────────────────────────────────

async def history(db, task_key: str, *, scope=None) -> list[dict]:
    """한 과제의 개정 줄 — `rev_seq` 순으로, 각 판에 달린 리포트와 함께.

    개정 자체는 전사 공용 축이라 다 보인다. ★그 안의 **리포트**는 `scope`(리포트 검색과 같은 술어 — 소유 · 같은 소속)로
    거른다 — 읽지 못하는 리포트의 id 가 새지 않게(사용자 결정 11-11). 비우면 전부(시스템 관리자).
    """
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
    if scope is not None and edges:
        seen = await visible_reports(db, [e.src_key for e in edges], scope)
        edges = [e for e in edges if e.src_key in seen]
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

    **짐작이 없는 길만** 여기서 푼다(`exact_matches`) —
      `exact`        과제명(plm_task.key)과 글자 그대로 같다
      `task_code`    과제코드(`properties.task_code`)와 글자 그대로 같다
      `previous_key` 허브가 바꾼 옛 과제명이다(`onto_previous_keys` — 같은 과제다)
      `alias`        사람이 이 플랫폼에서 이미 붙인 기록이 있다
      `hub_alias`    허브 행의 별칭(`properties.aliases`)과 글자 그대로 같다
    ★원천이 **모두 같은 과제 하나**를 가리킬 때만 푼다(검토 반영 11-11). 둘이 엇갈리면(사람이 붙인 별칭과 나중에 온 같은 글자의
      허브 과제 — R8), 과제코드 · 허브 별칭이 두 과제에 걸리면(R6), 이름(label)이 글자 그대로 같은 다른 과제가 있으면 풀지 않고
      **후보**로 낸다(`candidates_for`) — 사람이 고른다. 예전엔 원천 차례로 먼저 걸린 것이 조용히 이겼다. 그만 쓴 과제는 살아 있는
      과제가 하나도 안 맞을 때만 센다(사용자 결정 11-12 「살아 있는 객체가 정한다」 — `exact_matches`).
    ⚠ key 는 **과제명**이다(rootdesign plm_task.key). 과제코드는 `properties.task_code` 에 있다 —
      보고서에는 과제코드가 적혀 오므로 그 경로가 없으면 과제코드로는 영영 안 풀린다(KR-01, 2026-10-27).
    정규화해서 같아 보이는 것은 **여기서 풀지 않는다**(후보일 뿐이다 — `task_candidates`).
    """
    return _pick(await exact_matches(db, free))


# 글자 그대로 맞은 원천 → 후보에 보일 근거
_EXACT_WHY = {"exact": "과제명이 글자 그대로 같다", "task_code": "과제코드가 글자 그대로 같다",
              "previous_key": "허브가 바꾼 옛 과제명이다", "alias": "사람이 붙인 별칭이 가리킨다",
              "hub_alias": "허브 별칭이 글자 그대로 같다", "label": "이름(label)이 글자 그대로 같다",
              "alias_missing": "사람이 붙인 별칭이 거울에 없는 과제를 가리킨다"}


async def exact_matches(db, free: str) -> list[tuple[str, str]]:
    """자유 문자열과 **글자 그대로** 맞는 과제 — `(과제 key, 원천)` 목록. 원천 차례(과제명 · 과제코드 · 옛 과제명 · 우리 별칭 ·
    허브 별칭 · 이름), 같은 원천 안에서는 key 차례라 실행마다 같다(R6b — 예전 과제코드 고름은 차례 없는 `.first()` 였다).
    `label` 은 이것만으로는 잇지 않는다 — 다른 원천과 엇갈리는지 볼 때만 쓴다(정확 일치의 원천이 아니었다).
    ★살아 있는 과제가 정한다(사용자 결정 11-12 — SRC-08 다리와 같은 규칙) — 그만 쓴(deprecated) 과제는 살아 있는 과제가 하나도 안
    맞을 때만 센다. 그만 쓴 과제는 살아 있는 과제의 일치를 막지 못한다(재검토 rr2b — 그만 쓴 과제의 이름이 다른 과제의 과제코드와
    같아 엇갈림이 됐다). 살아 있는 과제가 안 맞으면 그만 쓴 과제 하나는 예전처럼 잇고, 여럿이면 못 붙임이다(후보로도 내지 않는다).
    ★사람이 붙인 별칭의 끝이 거울에 없으면(허브에서 지워짐 · 합쳐짐 · 받은 적 없음) `alias_missing` — 엇갈림이다. 다른 원천이 한 과제로
    맞아도 잇지 않고 후보로 낸다. 그 끝은 거울에 없어 고를 수 없으니 후보로 내지 않는다(SRC-08 다리와 같은 규칙 — 재검토 11-12, 예전엔
    거울에 없는 그 key 로 풀렸다). 그 별칭**만** 맞는 이름은 거울의 과제를 가리키는 원천이 없다 — 자동 잇기 · 미리 보기는 잇지 않고
    까닭(`alias_missing`)을 보이고, 인제스트 때 잇기(`link_from_eng_meta`)는 허브가 모르는 이름으로 보고 수동 메타 글자 그대로 잇는다.
    끝이 허브가 이름을 바꾼 **옛 과제명**이면 없는 것이 아니다 — 지금 이름의 과제로 본다(리포트의 이름을 풀 때와 같다. 재검토 11-14 F-05 —
    예전엔 끝이 없는 별칭으로 읽혀 잇지 못했다. 별칭 표는 다음 받기가 새 key 로 고쳐 쓴다). 합쳐 없어진 과제는 따라가지 않는다(알리고
    사람이 옮긴다 — 10-30).
    """
    free = (free or "").strip()
    if not free:
        return []
    live = (OntoObject.type_slug == TYPE_TASK, OntoObject.deleted.is_(False))
    out: list[tuple[str, str]] = [(k, "exact") for k in (await db.execute(
        select(OntoObject.key).where(*live, OntoObject.key == free))).scalars()]
    out += [(k, "task_code") for k in (await db.execute(select(OntoObject.key).where(
        *live, OntoObject.properties["task_code"].astext == free).order_by(OntoObject.key))).scalars()]
    now = await current_key(db, TYPE_TASK, free)
    if now != free and await task_exists(db, now):
        out.append((now, "previous_key"))
    al = (await db.execute(select(OntoAlias.key).where(
        OntoAlias.type_slug == TYPE_TASK, OntoAlias.alias == free))).scalar_one_or_none()
    if al is not None:
        al_now = await current_key(db, TYPE_TASK, al)      # 옛 과제명에 붙인 별칭 — 허브가 바꾼 지금 이름으로(F-05)
        out.append((al_now, "alias") if await task_exists(db, al_now) else (al, "alias_missing"))
    out += [(t.key, "hub_alias") for t in (await db.execute(select(OntoObject).where(
        *live, OntoObject.properties["aliases"].contains([free])).order_by(OntoObject.key))).scalars()
        if free in hub_aliases(t)]
    out += [(k, "label") for k in (await db.execute(select(OntoObject.key).where(
        *live, OntoObject.label == free).order_by(OntoObject.key))).scalars()]
    keys = sorted({k for k, _ in out})
    quiet = set((await db.execute(select(OntoObject.key).where(
        *live, OntoObject.status == "deprecated", OntoObject.key.in_(keys)))).scalars()) if keys else set()
    alive = [m for m in out if m[0] not in quiet]
    return alive if any(how != "alias_missing" for _, how in alive) else out


def missing_alias(found: list[tuple[str, str]]) -> str | None:
    """끝이 거울에 없는 사람의 별칭이 가리키는 key — 있으면 엇갈림이라 그 이름을 허브 과제에 잇지 않는다(그 끝은 후보로도 안 낸다)."""
    return next((k for k, how in found if how == "alias_missing"), None)


def _pick(found: list[tuple[str, str]]) -> tuple[str, str]:
    """원천들이 과제 하나로 모이고 이름 · 끝이 없는 별칭이 아닌 원천이 하나라도 있으면 그것(원천 차례 첫째) — 아니면 못 푼 것."""
    linkers = [m for m in found if m[1] not in ("label", "alias_missing")]
    return linkers[0] if linkers and len({k for k, _ in found}) == 1 else ("", "")


async def candidates_for(db, free: str, *, found: list[tuple[str, str]] | None = None,
                         rows: list[OntoObject] | None = None) -> tuple[list[dict], bool]:
    """못 푼 자유 문자열의 후보와 근거 — `(후보, 엇갈림)`. 글자 그대로 맞은 원천(엇갈려서 못 푼 것)을 먼저, 그다음 정규화해서
    같아 보이는 것(`task_candidates`). 엇갈림(`ambiguous`)은 글자 그대로 맞은 과제가 둘 이상이라는 뜻이다 — 사람이 고른다."""
    if found is None:
        found = await exact_matches(db, free)
    if rows is None:
        rows = await _live_tasks(db)
    labels = {t.key: t.label for t in rows}
    quiet = {t.key for t in rows if t.status == "deprecated"}
    stray = missing_alias(found)
    out: list[dict] = []
    for k, how in found:
        if how == "alias_missing" or k in quiet or any(c["key"] == k for c in out):
            continue        # 끝이 거울에 없는 별칭 · 그만 쓴 과제는 후보로 내지 않는다(고를 수 없다 · 새로 고르는 목록 — 다리와 같다)
        why = _EXACT_WHY[how] + (f" — 사람이 붙인 별칭은 거울에 없는 과제 {stray!r} 를 가리킨다" if stray else "")
        out.append({"key": k, "label": labels.get(k), "why": why, "rank": -1})
    seen = {c["key"] for c in out}
    out += [c for c in await task_candidates(db, free, rows=rows) if c["key"] not in seen]
    return out, len({k for k, _ in found}) > 1


def hub_aliases(obj: OntoObject) -> list[str]:
    """허브 행의 별칭 — SP 는 있으면 `properties.aliases` 에 배열로 준다(키트 10-21 §5.2). 모양이 어긋나면 없는 것으로 본다."""
    raw = (obj.properties or {}).get("aliases")
    return [str(a) for a in raw if str(a or "").strip()] if isinstance(raw, list) else []


async def _live_tasks(db) -> list[OntoObject]:
    return (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == TYPE_TASK,
                                 OntoObject.deleted.is_(False)))).scalars().all()


async def task_candidates(db, free: str, *, limit: int = 5,
                          rows: list[OntoObject] | None = None) -> list[dict]:
    """붙일 만한 과제 **후보와 근거**. 고르지 않는다.

    근거를 함께 내는 것이 요점이다 — 근거 없는 후보 목록은 사람이 검증할 수 없고,
    검증할 수 없는 목록은 결국 맨 위를 누르게 된다.
    `rows` 는 이미 읽은 과제 행(계획이 문자열마다 과제 전부를 다시 읽지 않게 넘긴다). 비우면 여기서 읽는다.
    """
    free = (free or "").strip()
    if not free:
        return []
    norm = normalize(free)
    if rows is None:
        rows = await _live_tasks(db)
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

    기계 잇기 둘(인제스트 · 메타 고침의 `link_from_eng_meta` · 자동 잇기의 계획)이 **이 하나**를 쓴다 — 두 벌이 되면 한쪽만 고쳐진다.
    """
    em = report.eng_meta or {}
    return str(em.get("project") or report.project_name or "").strip()


async def plan_task_links(db, *, limit: int | None = None, scope=None) -> dict:
    """★**계획이다 — 아무것도 쓰지 않는다.**

    자유 문자열별로 묶어서 「붙는 것」·「후보가 있는 것」·「못 붙인 것」 을 가른다.
    못 붙인 것을 **목록으로 돌려주는 것이 요점**이다 — 조용히 건너뛰면 "다 붙었다" 로 읽힌다.

    `scope` 는 볼 리포트를 좁히는 조건(`ImpactReport` 에 거는 WHERE)이다. 비우면 전부다. 일반 사용자에게는 라우트가
    리포트 검색과 같은 술어(소유 · 같은 소속)를 넘긴다 — 목록도 수도 그 사람이 읽을 수 있는 리포트만으로 센다(SRC-10).
    사람이 끊은 리포트(11-11)는 항목마다 `unlinked` 로, 수는 `counts.unlinked` 로 보인다 — 판정이 `links` 여도 적용 · 자동
    잇기가 건너뛴다.
    """
    # 칸 셋만 읽는다 — 리포트 행 통째(parts · findings · summary …)는 수천 건이면 수백 MB 이고, 받기마다 도는 자동 잇기
    # (SRC-09 — `auto_link_tasks`)가 이 길로 전부를 본다. 행은 `report_free_task` 가 읽는 칸(eng_meta · project_name)을 다 가졌다.
    stmt = select(ImpactReport.id, ImpactReport.eng_meta, ImpactReport.project_name)
    if scope is not None:
        stmt = stmt.where(scope)
    reps = (await db.execute(stmt)).all()
    groups: dict[str, list] = {}
    no_name: list[str] = []
    tasks: list[OntoObject] | None = None   # 후보를 볼 과제 행 — 못 푼 문자열이 처음 나올 때 한 번만 읽는다
    marks = await unlinked_reports(db)      # 사람이 끊은 리포트 — 기록은 적다(끊은 리포트 수만큼). 범위 안의 것만 아래에서 쓴다
    for r in reps:
        free = report_free_task(r)
        if not free:
            no_name.append(r.id)
            continue
        groups.setdefault(free, []).append(r)

    plan: list[dict] = []
    for free in sorted(groups):
        rows = groups[free]
        found = await exact_matches(db, free)
        key, how = _pick(found)
        codes = sorted({str((r.eng_meta or {}).get("dev_revision", {}).get("code") or "")
                        for r in rows} - {""})
        entry = {
            "free": free,
            "reports": sorted(r.id for r in rows),
            "n_reports": len(rows),
            "codes": codes,
            "task_key": key,
            "how": how or None,
            "unlinked": sorted(r.id for r in rows if r.id in marks),
        }
        if missing_alias(found):
            entry["alias_missing"] = missing_alias(found)    # 끝이 거울에 없는 사람의 별칭 — 그래서 잇지 않았다(떼고 다시 붙인다)
        if key:
            entry["verdict"] = "links"
        else:
            if tasks is None:
                tasks = await _live_tasks(db)
            cands, ambiguous = await candidates_for(db, free, found=found, rows=tasks)
            entry["candidates"] = cands
            entry["ambiguous"] = ambiguous      # 글자 그대로 맞은 과제가 둘 이상 — 잇지 않고 사람이 고른다(R8 · R6)
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
        "unlinked": sum(1 for r in reps if r.id in marks),
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


async def apply_task_links(db, *, only: list[str] | None = None) -> dict:
    """계획 중 **붙는 것만** 실제로 잇는다(후보·못 붙인 것은 건드리지 않는다) — 관리자 버튼(POST /ontology/task-links/apply).

    `only` 를 주면 그 자유 문자열만. ★받기 뒤 자동 잇기와 **같은 길 · 같은 기계 출처**(`rule`)로 잇는다(검토 반영 11-11 — 예전엔
    `manual` 이라 그새 끊은 기록을 지우고(R1) 주인이 확정한 판에서 옮기고(R4) 판에 관리자 이름을 찍었다). 버튼은 사람의 손이지만
    리포트마다 본 판단이 아니다 — 그래서 사람이 끊은 리포트는 건너뛰고(`skipped_unlinked`), 사람이 손으로 확정한 리포트는
    옮기지 않고(`kept_manual`), 판에 누가 정했다(`decided_by`)를 찍지 않는다. 결과는 자동 잇기와 같은 꼴에 고른 문자열 수(`strings`).
    받기 잠금 · 커밋은 부르는 쪽(라우트 — 그 잠금이 잡혀 있으면 409).
    """
    planned = await plan_task_links(db)
    picked = [e for e in planned["plan"] if e["verdict"] == "links" and (only is None or e["free"] in only)]
    got = await auto_link_tasks(db, report_ids=sorted({rid for e in picked for rid in e["reports"]}))
    got["strings"] = len(picked)
    return got


# ── 과거 붙이기 자동 (SRC-09) ──────────────────────────────────────────────
# 위 적용은 관리자 버튼이다. 받기(`plm_sync`) 뒤와 리포트 반입 뒤에는 「붙는 것」 만 **스스로** 잇는다 — 인제스트 때 잇기
# (`link_from_eng_meta`)도 같은 판정을 따르지만(11-12 — 예전엔 수동 메타 글자 그대로만 봤다) **그때의 거울**로 본 것이라, 뒤에 들어온
# 과제명 · 과제코드 · 별칭으로 늦게 풀리는 리포트가 남는다(허브가 모르던 이름은 글자 그대로의 판에 있다가 받기 뒤에 옮겨진다).
# 반입 뒤 잇기는 그래서 이름이 허브 과제 하나로 풀리면 대개 `already` 로 세기만 한다(허브가 모르는 이름은 글자 그대로 이어졌어도
# 후보 · 못 붙임으로 센다 — 재검토 11-14) — 응답 · 잡 경고에 실을 수(후보 · 못 붙임)를 내고, 인제스트 때 잇기가 깨졌을 때의 그물이다.

# 정확 일치 규칙으로 허브 과제 하나에 풀려 이은 선(`link_source`) · 기계가 만든 판(`rev_source`)의 출처 — 자동 잇기 · 일괄 적용과,
# 11-12 부터 인제스트 때 잇기 · 수동 메타 고침도 같은 값을 쓴다(코어와 잇기 뼈대 규칙 — 정확 일치만 `rule` 로 잇는다).
SOURCE_RULE = "rule"
_REFUSED_KEEP = 20          # 실행 기록에 남기는 거절 줄 상한 — 같은 결함이 수천 줄로 불어나지 않게


async def auto_link_tasks(db, *, report_ids: list[str] | None = None) -> dict:
    """계획 중 **붙는 것만** 스스로 잇는다(SRC-09). 후보 · 못 붙인 것은 **세기만** 한다 — 짐작으로 잇지 않는다.

    「붙는 것」 은 계획의 `links` 다 — 과제명 · 과제코드 · 옛 과제명 · 우리 별칭 · 하나뿐인 허브 별칭이 **글자 그대로** 같은 것
    (`resolve_task`). 리포트마다 다섯으로 가른다.
      `skipped_unlinked` ★사람이 이 리포트의 연결을 끊었다(끊은 기록) — 다시 잇지 않는다(11-11). 손으로 다시 잇거나 기록을
                        지우면 풀린다
      `linked`          이었다(새로 · 기계가 이은 다른 판에서 옮김) — `rev_source=rule`
      `already`         이미 그 판에 이어져 있다 — 쓰지 않는다(두 번째 실행은 아무것도 쓰지 않는다). 반입 뒤에는 대개 이것이다 —
                        인제스트 때 잇기(`link_from_eng_meta`)가 같은 판정으로 먼저 이었다(11-12)
      `kept_manual`     ★사람이 **이 리포트를** 손으로 확정해 두었다(선의 `link_source=manual`) — 옮기지 않는다. 리포트마다
                        가른다(남이 자기 리포트를 같은 판에 확정했다고 내 기계 선이 굳지 않는다 — 검토 R5). set_revision 도
                        기계 출처면 같은 까닭으로 거절한다
      `skipped_no_code` 과제는 풀렸는데 개정 코드가 없다 — 만들어 내지 않는다
    `report_ids` 를 주면 그 리포트만(반입 뒤 — 반입은 과제 · 별칭을 바꾸지 않아 다른 리포트의 판정은 그대로다), 비우면 전부
    (받기 뒤 — 과제 · 별칭이 바뀌면 어느 리포트든 새로 풀릴 수 있고, 지난번에 못 이은 것도 다시 본다). 받기 잠금 · 커밋은
    부르는 쪽, 리포트 행 잠금은 여기서 — 쓸 리포트만 id 차례로 잠그고 잠근 뒤 상태를 다시 읽어 가른다(`lock_reports`).

    수의 단위 — `linked` · `already` · `kept_manual` · `skipped_no_code` · `skipped_unlinked` · `reports` ·
    `reports_without_a_name` 은 리포트, `candidates` · `unmatched` 는 자유 문자열이다(미리 보기 `counts` 의 `proposal` ·
    `unmatched` 와 같은 단위).
    """
    scope = None if report_ids is None else ImpactReport.id.in_(list(report_ids))
    planned = await plan_task_links(db, scope=scope)
    c = planned["counts"]
    out: dict[str, Any] = {"scope": "all" if report_ids is None else "reports", "reports": c["reports"],
                           "linked": 0, "already": 0, "kept_manual": 0, "skipped_no_code": 0, "skipped_unlinked": 0,
                           "refused": [],
                           "candidates": c["proposal"], "unmatched": c["unmatched"],
                           "reports_without_a_name": c["reports_without_a_name"]}
    target = {rid: e["task_key"] for e in planned["plan"] if e["verdict"] == "links" for rid in e["reports"]}
    free_of = {rid: e["free"] for e in planned["plan"] if e["verdict"] == "links" for rid in e["reports"]}
    if not target:
        return out

    def decide(rid: str, s: dict) -> str:
        if s["marked"]:
            return "skipped_unlinked"
        if not s["code"]:
            return "skipped_no_code"
        key = revision_key(target[rid], s["code"])
        if s["live"] == {key}:
            return "already"
        if s["human"] - {key}:
            return "kept_manual"
        return "write"

    pending = []
    for rid, s in (await _link_state(db, sorted(target))).items():
        d = decide(rid, s)
        if d == "write":
            pending.append(rid)
        else:
            out[d] += 1
    if not pending:
        return out
    # ★쓸 리포트 행만 id 차례로 먼저 잠그고(다른 모든 길과 같은 차례) **다시 읽는다** — 계획을 읽은 뒤 사람이 끊었거나 손으로
    #   확정했거나 수동 메타를 고쳤으면 그것이 이긴다(검토 R1 · R2 · R11). 잠근 행은 이 트랜잭션이 끝날 때 풀린다.
    await lock_reports(db, pending)
    for rid, s in (await _link_state(db, pending)).items():
        if s["free"] != free_of[rid]:               # 그새 수동 메타가 바뀌었다(또는 리포트가 지워졌다) — 다음 잇기가 본다
            if len(out["refused"]) < _REFUSED_KEEP:
                out["refused"].append({"report": rid, "why": "changed"})
            continue
        d = decide(rid, s)
        if d != "write":
            out[d] += 1
            continue
        rep = await db.get(ImpactReport, rid)
        if rep is None:
            continue
        got = await set_revision(db, rep, task_key=target[rid], code=s["code"], source=SOURCE_RULE)
        if got.get("ok"):
            out["linked"] += 1
        elif got.get("error") == "unlinked":       # set_revision 이 잠근 뒤 다시 본 끊은 기록 — 여기까지 올 일은 없다
            out["skipped_unlinked"] += 1
        elif got.get("error") == "kept_manual":
            out["kept_manual"] += 1
        elif len(out["refused"]) < _REFUSED_KEEP:
            out["refused"].append({"report": rid, "why": got.get("error")})
    return out


async def _link_state(db, ids: list[str]) -> dict[str, dict]:
    """리포트들의 **지금** 선 상태 — `{"free", "code", "live", "marked", "human"}`. 잠그기 전에 고를 때와 잠근 뒤 다시 볼 때
    같은 함수를 쓴다(잠그기 전에 본 것으로 쓰지 않는다). `human` 은 사람이 정한 판으로 이어진 선의 판 key 들이다.
    """
    st = {rid: {"free": "", "code": "", "live": set(), "marked": False, "human": set()} for rid in ids}
    if not ids:
        return st
    for row in (await db.execute(select(ImpactReport.id, ImpactReport.eng_meta, ImpactReport.project_name)
                                 .where(ImpactReport.id.in_(ids)))).all():
        st[row.id]["free"] = report_free_task(row)
        st[row.id]["code"] = str(((row.eng_meta or {}).get("dev_revision") or {}).get("code") or "").strip()
    edges = (await db.execute(select(OntoRelation.src_key, OntoRelation.dst_key, OntoRelation.properties).where(
        OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
        OntoRelation.src_key.in_(ids), OntoRelation.deleted.is_(False)))).all()
    legacy = await _manual_revisions(db, [dst for _, dst, props in edges if not (props or {}).get("link_source")])
    for src, dst, props in edges:
        st[src]["live"].add(dst)
        if _human_link(props, dst, legacy):         # 리포트마다 — 이 리포트의 선을 사람이 이었나(R5)
            st[src]["human"].add(dst)
    for rid in await unlinked_reports(db, ids):
        st[rid]["marked"] = True
    return st


def _human_link(props: dict | None, key: str, legacy_manual: set[str]) -> bool:
    """이 리포트 선을 사람이 이었나 — 선에 적힌 `link_source` 로 가른다. 적지 않던 때의 옛 선은 그 판이 사람 판이면 사람 선으로
    본다(조심 쪽 — 사람이 정한 것일 수 있다)."""
    src = (props or {}).get("link_source")
    return src == "manual" if src else key in legacy_manual


async def _manual_revisions(db, keys) -> set[str]:
    """이 판 key 가운데 사람이 정한 판(`rev_source=manual`)."""
    keys = sorted(set(keys))
    if not keys:
        return set()
    return {k for k, props in (await db.execute(select(OntoObject.key, OntoObject.properties).where(
        OntoObject.type_slug == TYPE_REVISION, OntoObject.key.in_(keys)))).all()
        if (props or {}).get("rev_source") == "manual"}


async def link_report(db, report: ImpactReport) -> dict:
    """리포트 하나의 과제 잇기(붙는 것만)를 지금 돈다 — 반입을 **커밋한 뒤**(SRC-09 — 업로드 · 번들 · 7-1 반입이 모두
    `ingest_report` 를 지나므로 거기서 한 번)와 사람이 끊은 기록을 지운 뒤(11-11)에 부른다. 그 리포트만 본다.

    ★실패가 반입을 되돌리지 않는다 — 저장점 안에서 돌고, 깨지면 그 저장점만 되감고 `{"error": …}` 를 돌려준다(부르는 쪽이
    응답 · 잡 경고에 싣는다). 받기와 같은 잠금(`plm_sync.LOCK_HOLDERS` — 다른 리포트의 이 잇기도 쥔다)을 걸고, 쥐고 있으면 건너뛰고
    그렇게 말한다(허브 받기가 켜져 있으면 다음 받기 뒤 자동 잇기가 전부를 본다 — 꺼져 있으면 관리자 일괄 적용이 잇는다). 과제·개정 기능이 꺼져 있으면(`KOORM_ONTOLOGY=0` · 허브 설정 없음 — 라우트와
    같은 판정) 하지 않고 `skipped: off` 로 말한다.
    """
    from app.shared.features import ontology_state
    from app.worker import plm_sync

    rid = report.id
    st = ontology_state()
    if not st["enabled"]:
        # 기능이 꺼져 있으면 라우트처럼 하지 않는다(KOORM_ONTOLOGY=0 · 허브 설정 없음 — 검토 반영 11-11). 인제스트 때 잇기
        # (`_link_revision`)는 이 스위치와 따로 예전대로 돈다 — 거울이 아는 이름은 판정대로, 모르는 이름(허브 없는 박스)은 글자 그대로.
        return {"scope": "reports", "skipped": "off", "detail": f"과제·개정 기능이 꺼져 있다 — {st['reason']}"}
    try:
        if not await plm_sync.try_lock(db):
            await db.commit()          # 잠금 질의로 연 트랜잭션만 닫는다 — rollback 은 리포트 행을 만료시킨다
            return {"scope": "reports", "skipped": "busy",
                    "detail": f"{plm_sync.LOCK_HOLDERS} 가운데 하나가 잠금을 쥐고 있어 이번엔 잇지 않았다 — 허브 받기가 "
                              "켜져 있으면 다음 받기 뒤 자동 잇기가, 아니면 관리자 일괄 적용이 잇는다"}
        async with db.begin_nested():
            got = await auto_link_tasks(db, report_ids=[rid])
        await db.commit()
        return got
    except Exception as exc:           # noqa: BLE001 — 잇기 하나가 반입을 무르게 하면 안 된다
        logger.exception("과제 잇기 실패 — report %s", rid)
        try:
            await db.commit()          # 저장점은 이미 되감겼다 — 잠금만 푼다
        except Exception:              # noqa: BLE001
            await db.rollback()
            await db.refresh(report)   # rollback 은 모든 행을 만료시킨다 — 부르는 쪽이 리포트를 계속 읽는다
        return {"scope": "reports", "error": short_error(exc)}     # 짧은 꼴 — SQL 문 · 매개변수 없이 한 줄(전문은 위 로그)


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


async def unlink_revision(db, report: ImpactReport, *, by: str = "") -> dict:
    """리포트와 개정 사이의 선을 끊는다. **개정 객체는 지우지 않는다.**

    왜 객체를 남기나 — 그 판에 다른 리포트가 달려 있을 수 있고, `supersedes` 줄의 가운데일
    수도 있다. 지우면 줄이 끊기고 그것은 되돌릴 수 없다. 선만 끊으면 다시 이을 수 있다.

    ★선은 지우지 않고 **끊은 표시**(`deleted` + 끊은 사람 · 때)로 남긴다 — 이 표의 규약이고(끊은 선은 표시만 한다), 그것이
    「사람이 끊었다」 는 기록이다(사용자 결정 11-11). 기록이 있는 리포트는 기계(자동 잇기 · 인제스트 때 잇기 · 수동 메타 고침 ·
    관리자 일괄 적용)가 다시 잇지 않는다 — 사람이 손으로 다시 잇거나(`set_revision` manual) 기록을 지우면(`clear_unlink`) 풀린다.
    리포트 행을 먼저 잠그고 그 뒤에 선을 읽는다 — 커밋 전인 자동 잇기와 겹치면 그것이 끝날 때까지 기다렸다가 **그때 이어진 선**을
    끊는다(검토 R7 — 예전엔 다른 트랜잭션이 지운 선을 고치려다 500 이 났다). 잠근 뒤 이어진 선이 없으면 `not_linked` 다.
    """
    await lock_reports(db, [report.id])
    edges = (await db.execute(
        select(OntoRelation).where(OntoRelation.relation == REL_MEASURED,
                                   OntoRelation.src_type == TYPE_REPORT,
                                   OntoRelation.src_key == str(report.id),
                                   OntoRelation.deleted.is_(False))
        .execution_options(populate_existing=True))).scalars().all()
    if not edges:
        return {"ok": False, "error": "not_linked", "detail": "이어진 개정이 없다"}
    keys = sorted({e.dst_key for e in edges})
    at = _now()
    for e in edges:
        e.deleted = True
        e.properties = {**(e.properties or {}), "unlinked_by": by or "", UNLINK_MARK: at}
    await db.flush()
    return {"ok": True, "was": keys, "unlinked_by": by or "", "unlinked_at": at,
            "detail": "개정 객체는 남긴다 — 다른 리포트가 달려 있거나 줄의 가운데일 수 있다. 끊은 기록을 남겼다 — 자동 잇기 · "
                      "수동 메타 고침이 다시 잇지 않는다(손으로 다시 잇거나 끊은 기록을 지우면 다시 잇는다)"}


# ── 사람이 끊은 기록 (11-11 사용자 결정 「끊은 것을 기록해 자동이 건너뛴다」) ───────────
# 기록은 끊은 리포트 선 자체다 — `deleted` 와 `unlinked_at` · `unlinked_by` 를 단 `measured_at`. 리포트를 지우면 0019 트리거가
# 함께 지운다. 사람의 판단이 이긴다 — SRC-08 의 사람 선이 다시 반입해도 남는 것과 같은 자세다.

def _unlink_marks():
    return (OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
            OntoRelation.deleted.is_(True), OntoRelation.properties.has_key(UNLINK_MARK))


async def unlink_rows(db, report_id: str) -> list[OntoRelation]:
    """이 리포트의 끊은 기록(끊은 표시를 단 리포트 선) — 늘 새로 읽는다(잠근 뒤에 부르면 그때의 것이다)."""
    return (await db.execute(select(OntoRelation).where(
        *_unlink_marks(), OntoRelation.src_key == str(report_id))
        .execution_options(populate_existing=True))).scalars().all()


async def unlinked_reports(db, ids=None) -> dict[str, dict]:
    """사람이 끊은 리포트 → `{"by", "at", "was"}`(`ids` 를 주면 그 안에서만). 기록은 끊은 리포트 수만큼이라 적다."""
    stmt = select(OntoRelation.src_key, OntoRelation.dst_key, OntoRelation.properties).where(*_unlink_marks())
    if ids is not None:
        stmt = stmt.where(OntoRelation.src_key.in_(list(ids)))
    out: dict[str, dict] = {}
    for src, dst, props in (await db.execute(stmt)).all():
        p = props or {}
        rec = out.setdefault(src, {"by": p.get("unlinked_by") or "", "at": p.get(UNLINK_MARK), "was": []})
        rec["was"].append(dst)
    for rec in out.values():
        rec["was"].sort()
    return out


async def clear_unlink(db, report: ImpactReport) -> dict:
    """사람이 끊은 기록을 지운다 — 이 리포트를 기계(자동 잇기 · 인제스트 때 잇기 · 수동 메타 고침)가 다시 볼 수 있게 된다.
    없으면 **없다고 말한다**(조용히 성공하지 않는다). 리포트 행을 먼저 잠근다(다른 길과 같은 차례)."""
    await lock_reports(db, [report.id])
    marks = await unlink_rows(db, report.id)
    if not marks:
        return {"ok": False, "error": "not_unlinked", "detail": "끊은 기록이 없다"}
    was = sorted({m.dst_key for m in marks})
    for m in marks:
        await db.delete(m)
    await db.flush()
    return {"ok": True, "was": was, "detail": "끊은 기록을 지웠다 — 자동 잇기가 이 리포트를 다시 본다"}


# ── 개정 간 비교 ───────────────────────────────────────────────────────────

async def visible_reports(db, ids, scope) -> set[str]:
    """이 리포트 id 가운데 `scope`(리포트 검색과 같은 술어)로 읽을 수 있는 것. `scope` 가 비면 그대로 다(시스템 관리자)."""
    ids = sorted({str(i) for i in ids if i})
    if scope is None or not ids:
        return set(ids)
    return set((await db.execute(select(ImpactReport.id).where(ImpactReport.id.in_(ids), scope))).scalars())


async def compare(db, task_key: str, *, scope=None) -> dict:
    """한 과제의 개정을 **나란히** 놓는다 — 그것이 이 기능의 목적이다.

    숫자는 **리포트에 이미 승격된 칸**(`worst_stress`·`worst_g`·`max_severity`·`n_cases`)을
    그대로 쓴다. 다시 계산하지 않는다 — 같은 값을 두 곳에서 계산하면 반드시 갈린다.

    ★**판마다 리포트가 여럿일 수 있다.** 그때 하나를 골라 대표로 삼지 않는다 — 어느 것을
    골랐는지가 안 보이면 비교가 거짓이 된다. 최악값은 **그 판의 리포트 전부에서** 모으고,
    몇 건에서 모았는지를 함께 낸다.
    ★리포트 줄 · 수치는 `scope` 로 읽을 수 있는 리포트만으로 센다(사용자 결정 11-11 — 판은 다 보이고, 읽지 못하는 리포트의
    id · 최악값 · 심각도 · 케이스 수는 새지 않는다). 비우면 전부(시스템 관리자).
    """
    line = await history(db, task_key, scope=scope)
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


def _rev_code(key: str, props: dict | None) -> str:
    return str((props or {}).get("code") or key.rsplit("@", 1)[-1])


async def _task_revision_keys(db, tasks: list[str]) -> list[tuple[str, str]]:
    """이 과제들에 매달린 살아 있는 우리 개정의 `(key, 코드)`(key 차례) — **열만** 읽는다. 잠그기 전에 읽는 자리라 정체 맵에 판 객체를
    남기지 않는다(남기면 잠근 뒤에도 그 옛 칸으로 덮는다 — 재검토 11-12 rr6)."""
    if not tasks:
        return []
    return sorted((k, _rev_code(k, p)) for k, p in (await db.execute(select(OntoObject.key, OntoObject.properties).where(
        OntoObject.type_slug == TYPE_REVISION, OntoObject.source == SOURCE_SELF, OntoObject.deleted.is_(False),
        OntoObject.properties["task"].astext.in_(list(tasks))))).all())


async def _task_revisions(db, tasks: list[str]) -> list[OntoObject]:
    """이 과제들에 매달린 살아 있는 우리 개정 행(key 차례) — 늘 새로 읽는다(`populate_existing` — 잠근 뒤에 부르는 자리다)."""
    if not tasks:
        return []
    return (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == TYPE_REVISION, OntoObject.source == SOURCE_SELF, OntoObject.deleted.is_(False),
        OntoObject.properties["task"].astext.in_(list(tasks))).order_by(OntoObject.key)
        .execution_options(populate_existing=True))).scalars().all()


async def _reports_on(db, keys: list[str]) -> list[str]:
    """이 개정들에 살아 있는 선으로 이어진 리포트 id."""
    if not keys:
        return []
    return sorted(set((await db.execute(select(OntoRelation.src_key).where(
        OntoRelation.relation == REL_MEASURED, OntoRelation.src_type == TYPE_REPORT,
        OntoRelation.dst_type == TYPE_REVISION, OntoRelation.dst_key.in_(keys),
        OntoRelation.deleted.is_(False)))).scalars().all()))


async def _prev_of(db, key: str) -> str:
    """이 판의 앞 판 key(살아 있는 `supersedes` 선 — 없으면 빈 문자열). `_chain_keys` 와 같은 자리를 읽는다."""
    row = (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == REL_SUPERSEDES, OntoRelation.src_type == TYPE_REVISION,
        OntoRelation.src_key == key, OntoRelation.deleted.is_(False)))).scalars().first()
    return row.dst_key if row else ""


async def _stamp_old_machine_lines(db, key: str) -> None:
    """이 (기계) 판에 이어진 **옛 선**(누가 이었는지 `link_source` 가 없는 살아 있는 리포트 선)에 `eng_meta` 를 적는다 — 사람 판과
    접히면 남는 판이 사람 판이라, 표시 없는 선이 그때부터 사람 선으로 읽힌다(`_human_link` 의 옛 선 규칙 — 재검토 11-14 F-01 · F-02).

    표시를 안 적던 때(운영 main)의 기계 길은 인제스트 · 메타 고침의 글자 그대로 잇기 하나였고, 사람이 확정하면 그 판이 사람 판이
    됐다(기계가 다시 지나가도 사람 판 그대로다) — 기계 판에 남은 표시 없는 선은 그 기계 길이 이은 것이다. 언제 이었는지는 모른다
    (`linked_at` 은 적지 않는다). ★가리지 못하는 것 하나 — main 의 접기가 이미 기계 판으로 옮겨 놓은 사람 선은 여기서도 기계 선이다.
    부르는 쪽이 그 리포트 행을 잠가 둔다(`move_task_revisions` 의 잠금 차례 ①).
    """
    await db.flush()
    for e in (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == REL_MEASURED, OntoRelation.source == SOURCE_SELF,
            OntoRelation.src_type == TYPE_REPORT, OntoRelation.dst_type == TYPE_REVISION,
            OntoRelation.dst_key == key, OntoRelation.deleted.is_(False))
            .execution_options(populate_existing=True))).scalars().all():
        if not (e.properties or {}).get("link_source"):
            e.properties = {**(e.properties or {}), "link_source": "eng_meta"}
    await db.flush()


async def move_task_revisions(db, from_key: str, to_key: str, *, by: str = "", reason: str = "",
                              wait: bool = True) -> dict:
    """과제 A 에 매달린 **우리 것**(개정 · 별칭)을 과제 B 로 옮긴다 — 식별자 바뀜(저절로)과 합침(관리자)이 함께 쓴다.

    개정 key 는 `<과제>@<코드>` 라 과제가 바뀌면 key 도 바뀐다 — 같은 개정 행의 key 만 바꾸고 선의 끝을 따라 옮긴다.
    ★B 에 같은 코드 개정이 이미 있으면 A 쪽 리포트 선(`measured_at`)과 A 쪽을 앞 판으로 둔 선만 B 개정으로 옮기고,
    A 쪽 개정은 지우지 않고 비활성(`merged_into`)으로 둔다 — 지우면 되돌릴 수 없다. 옮긴 사람 · 까닭은 개정 칸에 남긴다.
    ★그렇게 접을 때 **사람이 정한 것은 남는다**(재검토 11-14 F-01 · F-02) — A 쪽만 사람 판이면 남는 B 판이 사람이 정한 칸
    (`rev_source` · `decided_by` · `decided_at` · `note`)을 받는다. 한쪽만 사람 판이면 기계 판 쪽의 옛 선(누가 이었는지 안 적힌 선)에
    기계가 이었다고 먼저 적는다(`_stamp_old_machine_lines`) — 안 적으면 그 기계 선이 사람 판에 얹혀 사람 선으로 굳는다. 예전엔 반대로
    사람의 옛 선이 기계 판에 얹혀 다음 자동 잇기가 옮겼다. A 쪽의 앞 판 선은 B 판에 앞 판이 없으면 B 판에 잇는다 — B 판에 다른 앞 판이
    있거나 이으면 줄이 돌 때는 잇지 않고 `dropped` 에 적어 돌려준다(끊은 줄과 같은 자리 — 남는 판의 줄에서 빠진 것이다). `model` 은 B 판이
    비어 있을 때만 받는다. 둘 다 사람 판이면 남는 판의 것이 남고, 접힌 판의 것은 그 판 행에 기록으로 남는다.
    ★잠금 차례(다른 모든 길과 같다) — ① 옮길 판과 **옮겨 갈 자리의 판**에 이어진 리포트 행(`lock_reports` — 접으면 그 자리 판의 옛
    선에도 적는다) ② 판 이름(옛 key · 새 key — `lock_revision_names`)
    ③ 이름을 쥔 뒤 판 행을 **새로 읽고**(기다리는 동안 사람이 판 칸을 고쳤을 수 있다 — 예전엔 잠그기 전에 읽은 판 객체로 덮어
    `rev_source` · `decided_by` · `note` 가 사라졌다, 재검토 11-12 rr6) 그새 이어진 리포트(늦게 온 선)도 잠근다. 판 이름을 쥔 뒤에는
    리포트를 기다리지 않는다(NOWAIT) — 늦게 온 리포트를 다른 트랜잭션이 쥐고 있거나 그새 옮길 판이 달라졌으면 **아무것도 쓰지 않고**
    `deferred` 로 돌려준다(이름 바뀜은 다음 받기가, 합침은 관리자가 다시 누른다 — rr5 의 교착 대신).
    `wait=False`(관리자가 누른 합침 옮기기)면 ① · ② 도 기다리지 않는다 — 그 과제의 리포트나 판을 다른 트랜잭션이 쥐고 있으면 바로
    `deferred` 다(재검토 11-14 F-08 — 누름이 그 트랜잭션이 끝날 때까지 답 없이 기다렸다). 까닭은 `detail` 에 일어난 그대로 적힌다.
    """
    from_key, to_key = (from_key or "").strip(), (to_key or "").strip()
    done: dict[str, Any] = {"from": from_key, "to": to_key, "revisions": 0, "collapsed": 0,
                            "reports": 0, "edges": 0, "aliases": 0, "dropped": [], "deferred": False}
    if not from_key or not to_key or from_key == to_key:
        return done
    first = await _task_revision_keys(db, [from_key])
    # 옛 key 와 새 key — 리포트 행도 판 이름도 이 둘을 다 잠근다(접으면 새 key 판의 칸 · 옛 선에도 쓴다)
    names = [k for k, _ in first] + [revision_key(to_key, c) for _, c in first]
    try:
        held = await lock_reports(db, await _reports_on(db, names), wait=wait)
        await lock_revision_names(db, names, wait=wait)
        revs = await _task_revisions(db, [from_key])
        if [r.key for r in revs] != [k for k, _ in first]:
            raise ReportsBusy("옮길 판이 그새 달라졌다")
        await lock_reports(db, set(await _reports_on(db, names)) - held)
    except ReportsBusy as exc:
        done["deferred"] = True
        done["detail"] = f"{exc} — 이번엔 옮기지 않았다"
        return done
    # 이번에 함께 옮겨 가는 판의 옛 key → 새 key — 앞 판이 아직 옛 이름이어도(key 차례로 옮긴다) 같은 판인지 가릴 수 있다
    going = {r.key: revision_key(to_key, _rev_code(r.key, r.properties)) for r in revs}
    for rev in revs:
        props = dict(rev.properties or {})
        code = _rev_code(rev.key, props)
        old, new = rev.key, revision_key(to_key, code)
        note = {"from": old, "to": new, "why": reason, "by": by, "at": _now()}
        props["moves"] = [*(props.get("moves") or []), note]
        there = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == TYPE_REVISION, OntoObject.key == new)
            .execution_options(populate_existing=True))).scalar_one_or_none()
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
            # ★사람이 정한 것은 남는다(재검토 11-14 F-01 · F-02). 차례가 요점이다 — 옛 선에 적기 → 남는 판의 칸 → 앞 판 선 → 선 옮기기.
            tp = dict(there.properties or {})
            mine_manual, there_manual = props.get("rev_source") == "manual", tp.get("rev_source") == "manual"
            if mine_manual != there_manual:
                # 한쪽만 사람 판 — 선이 섞이기 전에 기계 판 쪽의 옛 선에 기계가 이었다고 적는다. 남는 판은 어느 쪽이든 사람 판이 된다
                await _stamp_old_machine_lines(db, new if mine_manual else old)
            if mine_manual and not there_manual:
                for k in ("rev_source", "decided_by", "decided_at", "note"):
                    if props.get(k) is not None:
                        tp[k] = props[k]
            if props.get("model") and not tp.get("model"):
                tp["model"] = props["model"]
            there.properties = tp
            prev, own = await _prev_of(db, old), await _prev_of(db, new)
            if prev and going.get(prev, prev) != going.get(own, own):
                if own or prev == new or new in await _chain_keys(db, prev):
                    # 남는 판에 다른 앞 판이 있거나 이으면 줄이 돈다 — 잇지 않고 알린다(끊은 줄과 같은 자리로 돌려준다)
                    done["dropped"].append(f"{old} → {prev}")
                else:
                    await _edge(db, REL_SUPERSEDES, TYPE_REVISION, new, TYPE_REVISION, prev)
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
    누름은 **기다리지 않는다** — 그 과제의 리포트 · 판을 다른 트랜잭션이 쥐고 있거나 옮길 판이 그새 달라졌으면 아무것도 옮기지 않고
    `busy` 로 돌려준다(까닭은 `detail` 에 일어난 그대로 — 재검토 11-14 F-08, 예전엔 끝없이 기다리거나 일어나지 않은 까닭을 댔다).
    """
    row = await _hub_task(db, (key or "").strip())
    if row is None or not row.deleted or not row.merged_into or row.hidden:
        return {"ok": False, "error": "not_merged", "detail": f"{key!r} 는 허브에서 합쳐진 과제가 아니다"}
    into, end = await _merge_end(db, row.merged_into)
    if end is None or end.deleted:
        return {"ok": False, "error": "target_gone", "into": into,
                "detail": f"합쳐진 곳 {into!r} 도 허브에 살아 있지 않다 — 옮길 곳이 없다"}
    got = await move_task_revisions(db, row.key, into, by=by, reason=MOVE_MERGE + (f" — {note}" if note else ""),
                                    wait=False)
    if got["deferred"]:
        return {"ok": False, "error": "busy", "into": into,
                "detail": f"{got['detail']}. 잠시 뒤 다시 누른다"}
    return {"ok": True, **got}


async def reflect_after_sync(db) -> dict:
    """층 2 — 받은 사본만 읽고 이 플랫폼의 것에 반영한다(받기 한 번마다 `plm_sync.sync_once` 가 부른다).

    ① 과제 식별자 바뀜 — 우리 개정 · 별칭을 새 key 로 저절로 옮긴다. ② 모델 식별자 바뀜 — 개정의 `model` 칸.
    ③ 합쳐진 과제 — **옮기지 않고 센다**(실행 기록 · 관리 화면이 띄운다). 매번 전체 대조다(키트 §6 — 수만 건 이하면
    그것이 가장 단순하고 틀릴 일이 적다). 옮길 것이 없으면 아무것도 쓰지 않는다.
    """
    out: dict[str, Any] = {"renamed": 0, "revisions": 0, "collapsed": 0, "reports": 0, "aliases": 0,
                           "models": 0, "dropped": [], "merged_waiting": 0, "deferred": 0}
    renamed = sorted((await renamed_keys(db, TYPE_TASK)).items())
    if renamed:
        # 옮길 선이 달린 리포트 행을 **한꺼번에 · 한 번** 먼저 잠근다(아직 판 이름을 쥐지 않았다 — 기다려도 된다). 과제마다 옮기는 동안
        # 그새 새로 이어진 리포트는 기다리지 않고(판 이름을 쥐었다) 그 과제를 미룬다 — `deferred`, 다음 받기가 옮긴다(재검토 rr5).
        # 판은 열만 읽는다 — 정체 맵에 옛 판 객체를 남기지 않는다(옮기기가 잠근 뒤 새로 읽는다). 옮겨 갈 자리의 판(새 key)에 이어진
        # 리포트도 함께 잠근다 — 접으면 그 판의 옛 선에도 적는다(`move_task_revisions` 의 잠금 차례 ①과 같은 범위).
        names: list[str] = []
        for old, new in renamed:
            for k, code in await _task_revision_keys(db, [old]):
                names += [k, revision_key(new, code)]
        await lock_reports(db, await _reports_on(db, names))
    for old, new in renamed:
        got = await move_task_revisions(db, old, new, reason=MOVE_RENAME)
        if got["deferred"]:
            out["deferred"] += 1
            continue
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
