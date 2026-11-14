# SP 받는 쪽 층 2 — 허브 식별자 바뀜 · 합침을 우리 개정 · 별칭에 반영하고, 과제 검색이 별칭 · 순위를 안다(키트 10-21 §6)
"""층 1(사본)은 시험장 8단계가 채점한다(`test_sp_testbed.py`). 층 2 는 매핑이 플랫폼마다 달라 채점기가 없다 — 키트 §8.1 이
「SP key 로 적은 결과를 이 플랫폼의 표로 옮겨 시험에 넣는다」 고 한다. 우리 표는 개정(`<과제>@<코드>`) · 우리 선 · 별칭이다.

  식별자 바뀜 — 같은 것이다. **같은 개정 행**의 key 만 바뀌고 리포트 선 · 앞 판 선 · 별칭이 따라간다(새 행을 만들지 않는다).
  합침 — 저절로 옮기지 않는다(사용자 결정 10-30). 알리고, 관리자가 누르면 옮긴다.
  검색 — 순위를 매긴 **뒤** 자른다(포털 KR-16 다시) · 허브 별칭 · 우리 별칭도 본다(KR-01 다시).

층 1 은 실제 수신부(`sp_core.save_rows`)로 흉내 낸다 — 손으로 사본 행을 고치면 층 1 이 실제로 남기는 것(옛 → 새 표 등)과
어긋날 수 있다. 서비스 시험은 한 트랜잭션 안에서 돌리고 되돌린다. 라우트 시험만 커밋하고 치운다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, select

from app.models import (SOURCE_HUB, ImpactReport, OntoAlias, OntoObject, OntoPreviousKey, OntoRelation,
                        Session, User)
from app.modules.ontology import services as onto
from app.runner import sp_core

pytestmark = pytest.mark.asyncio(loop_scope="session")
P = "/api/v1"


def _tag() -> str:
    return ulid.new().str.lower()          # 통째로 — 앞자리는 시각이라 잘라 쓰면 1초 안에 겹친다(시험 격리)


def _report(*, project: str = "", code: str = "") -> ImpactReport:
    em = {"project": project, "dev_revision": {"code": code}} if project else None
    return ImpactReport(id=ulid.new().str, session_id="s", user_id=1, kind="sphere", eng_meta=em, n_cases=0)


async def _hub(db, type_slug: str, *rows: dict) -> dict:
    """허브 한 쪽을 실제 수신부로 받는다."""
    return await sp_core.save_rows(db, type_slug, [{"status": "active", "updated_at": "T1", **r} for r in rows])


async def _task(db, key: str, **props) -> None:
    await _hub(db, onto.TYPE_TASK, {"key": key, "label": f"과제 {key}", "properties": props})


async def _rev(db, rep: ImpactReport, task: str, code: str, **kw) -> str:
    got = await onto.set_revision(db, rep, task_key=task, code=code, source="manual", decided_by="t@x", **kw)
    assert got["ok"], got
    return got["key"]


async def _legacy(db, rep: ImpactReport) -> None:
    """이 리포트의 선을 **옛 꼴**로 — 운영 main 이 쓴 선에는 누가 이었는지(`link_source`)가 없다(`properties` null)."""
    edge = (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_type == onto.TYPE_REPORT,
        OntoRelation.src_key == rep.id, OntoRelation.deleted.is_(False)))).scalar_one()
    edge.properties = None
    await db.flush()


async def _machine(db, rep: ImpactReport, task: str, code: str, source: str = "eng_meta") -> dict:
    """기계 길(인제스트의 글자 그대로 잇기 · 자동 잇기)로 잇는다 — 결과를 그대로 돌려준다(거절도 값이다)."""
    return await onto.set_revision(db, rep, task_key=task, code=code, source=source)


async def _our_edges(db, relation: str, **where) -> list[OntoRelation]:
    stmt = select(OntoRelation).where(OntoRelation.relation == relation, OntoRelation.source == "dynaforge",
                                      OntoRelation.deleted.is_(False))
    for k, v in where.items():
        stmt = stmt.where(getattr(OntoRelation, k) == v)
    return (await db.execute(stmt)).scalars().all()


async def _rev_obj(db, key: str) -> OntoObject | None:
    return (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == onto.TYPE_REVISION, OntoObject.key == key))).scalar_one_or_none()


# ── 식별자 바뀜 — 저절로 옮긴다 ───────────────────────────────────────────────

async def test_a_renamed_task_carries_our_revisions_reports_and_aliases(db):
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        r1, r2 = _report(project=a, code="dv1"), _report(project=a, code="dv2")
        first = await _rev(db, r1, a, "dv1")
        await _rev(db, r2, a, "dv2", supersedes=first)
        assert (await onto.confirm_alias(db, alias=f"free-{t}", key=a))["ok"]

        await _hub(db, onto.TYPE_TASK, {"key": b, "label": f"과제 {b}", "renamed_from": a, "previous_keys": [a],
                                        "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["revisions"] >= 2 and got["aliases"] >= 1, got

        line = await onto.history(db, b)
        assert [(x["code"], x["reports"]) for x in line] == [("dv1", [r1.id]), ("dv2", [r2.id])], line
        assert line[1]["supersedes"] == f"{b}@dv1", "앞 판 선이 따라오지 않았다"
        assert await onto.history(db, a) == [], "옛 과제명에 개정이 남았다"
        # 같은 개정 행이다 — 새로 만든 것이 아니다(키트 §6)
        moved = await _rev_obj(db, f"{b}@dv1")
        assert moved is not None and f"{a}@dv1" in (moved.previous_keys or []), moved
        assert moved.properties["moves"][-1]["why"] == onto.MOVE_RENAME
        assert await _rev_obj(db, f"{a}@dv1") is None
        assert [e.dst_key for e in await _our_edges(db, onto.REL_OF, src_key=f"{b}@dv1")] == [b]
        assert (await db.execute(select(OntoAlias.key).where(OntoAlias.alias == f"free-{t}"))).scalar_one() == b

        # 옛 과제명으로 와도 지금 것으로 푼다 — 안 풀면 옛 key 로 같은 판이 하나 더 생긴다
        assert await onto.resolve_task(db, a) == (b, "previous_key")
        late = _report(project=a, code="dv1")
        assert (await onto.link_from_eng_meta(db, late))["key"] == f"{b}@dv1"
        assert await _rev_obj(db, f"{a}@dv1") is None
        mm = await onto.mismatch(db, r1)
        assert mm and mm["kind"] == "renamed", mm      # 「다르다」 가 아니라 그 사실을 말한다

        again = await onto.reflect_after_sync(db)       # 매번 전체 대조 — 두 번째는 옮길 것이 없다
        assert [x["code"] for x in await onto.history(db, b)] == ["dv1", "dv2"], again
    finally:
        await db.rollback()


async def test_a_rename_onto_a_revision_we_already_have_folds_into_it(db):
    """B 로 이미 받은 뒤에 「A 가 B 로 바뀜」 이 오면(오래 안 받았을 때) A 쪽 판은 B 쪽 같은 판으로 접힌다 — 지우지 않는다."""
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        ra, rb = _report(), _report()
        await _rev(db, ra, a, "dv1")
        await _rev(db, rb, b, "dv1")
        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["collapsed"] >= 1, got
        line = await onto.history(db, b)
        assert [(x["code"], sorted(x["reports"])) for x in line] == [("dv1", sorted([ra.id, rb.id]))], line
        old = await _rev_obj(db, f"{a}@dv1")
        assert old is not None and old.deleted and old.merged_into == f"{b}@dv1", "접힌 판은 비활성으로 남는다"
    finally:
        await db.rollback()


# ── 접을 때 사람이 정한 것은 남는다(재검토 11-14 F-01 · F-02 · F-15) ─────────────────────────

async def test_an_old_line_on_a_persons_revision_reads_as_a_persons_line(db):
    """운영 main 이 쓴 선에는 표시가 없다. 서버는 그 선을 「판이 사람 판이면 사람 선」 으로 지킨다(`_human_link`) — 패널이 읽는
    `linked.source` 도 같은 답을 해야 한다. 안 그러면 배포 직후 사람이 확정해 둔 리포트 전부에서 ✓ 가 사라진다(재검토 11-14 F-15)."""
    t = _tag()
    a = f"L2A-{t}"
    try:
        await _task(db, a)
        r_h, r_m = _report(), _report()
        await _rev(db, r_h, a, "dv1")
        assert (await _machine(db, r_m, a, "dv2"))["ok"]
        await _legacy(db, r_h)
        await _legacy(db, r_m)
        assert (await onto.linked_revision(db, r_h))["source"] == "manual"
        assert (await onto.linked_revision(db, r_m))["source"] is None, "기계 판의 옛 선은 누가 이었는지 적힌 것이 없다"
        # 서버의 판정과 같은 답이다 — 기계는 사람 선을 못 옮기고, 기계 선은 옮긴다
        assert (await _machine(db, r_h, a, "dv3", onto.SOURCE_RULE)).get("error") == "kept_manual"
        assert (await _machine(db, r_m, a, "dv3", onto.SOURCE_RULE))["ok"]
    finally:
        await db.rollback()


async def test_a_fold_keeps_what_a_person_decided(db):
    """A 가 B 로 바뀌었는데 B 에 같은 코드의 **기계 판**이 이미 있다(받기 전에 새 이름으로 반입이 왔다 · 미뤄진 옮기기 사이에 잇기가
    돌았다). 접을 때 남는 판이 사람이 정한 것(누가 · 언제 · 메모 · 앞 판)을 받고, 사람이 이은 옛 선은 사람 선으로 남는다 — 예전엔 남는
    판이 기계 판 그대로라 다음 자동 잇기가 사람의 옛 선을 옮겼다(재검토 11-14 F-01)."""
    t = _tag()
    a, b, c = f"L2A-{t}", f"L2B-{t}", f"L2C-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _task(db, c)
        r_prev, r_h, r_m = _report(), _report(), _report()
        prev = await _rev(db, r_prev, a, "pv1")
        await _rev(db, r_h, a, "dv1", supersedes=prev, note="사람이 정했다")
        assert (await _machine(db, r_m, b, "dv1"))["ok"]
        await _legacy(db, r_h)                           # 둘 다 운영 main 이 쓴 꼴 — 표시가 없다
        await _legacy(db, r_m)
        was = dict((await _rev_obj(db, f"{a}@dv1")).properties)

        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["collapsed"] >= 1 and not got["deferred"], got

        kept = (await _rev_obj(db, f"{b}@dv1")).properties
        assert [kept.get(k) for k in ("rev_source", "decided_by", "decided_at", "note")] == \
               ["manual", "t@x", was["decided_at"], "사람이 정했다"], kept
        line = {x["code"]: x for x in await onto.history(db, b)}
        assert line["dv1"]["supersedes"] == f"{b}@pv1", "앞 판 선이 접힌 판에 남았다"
        assert sorted(line["dv1"]["reports"]) == sorted([r_h.id, r_m.id]), line
        # 사람의 옛 선은 사람 선으로 읽히고, 남는 판에 있던 기계의 옛 선은 기계 선 그대로다
        assert (await onto.linked_revision(db, r_h))["source"] == "manual"
        assert (await onto.linked_revision(db, r_m))["source"] == "eng_meta"
        assert (await _machine(db, r_h, c, "dv2", onto.SOURCE_RULE)).get("error") == "kept_manual"
        assert (await _machine(db, r_m, c, "dv2", onto.SOURCE_RULE))["ok"], "기계 선이 사람 선으로 굳었다"
    finally:
        await db.rollback()


async def test_a_machine_revision_folding_into_a_persons_keeps_its_old_line_a_machines(db):
    """거꾸로 — A 쪽이 기계 판이고 B 쪽이 사람 판이다. 접으면 기계의 옛 선(표시 없음)이 사람 판에 얹힌다 — 예전엔 그때부터 사람 선으로
    읽혀 자동 잇기가 다시는 못 옮겼다. 접기 전에 그 선에 기계가 이었다고 적는다(재검토 11-14 F-01 · F-02 의 뒷면)."""
    t = _tag()
    a, b, c = f"L2A-{t}", f"L2B-{t}", f"L2C-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _task(db, c)
        r_m, r_h = _report(), _report()
        assert (await _machine(db, r_m, a, "dv1"))["ok"]
        await _rev(db, r_h, b, "dv1", note="B 쪽 사람")
        await _legacy(db, r_m)
        await _legacy(db, r_h)
        was = dict((await _rev_obj(db, f"{b}@dv1")).properties)

        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["collapsed"] >= 1 and not got["deferred"], got

        kept = (await _rev_obj(db, f"{b}@dv1")).properties
        assert [kept.get(k) for k in ("rev_source", "decided_by", "decided_at", "note")] == \
               ["manual", "t@x", was["decided_at"], "B 쪽 사람"], kept
        assert (await onto.linked_revision(db, r_m))["source"] == "eng_meta"
        assert (await onto.linked_revision(db, r_h))["source"] == "manual"
        assert (await _machine(db, r_h, c, "dv2", onto.SOURCE_RULE)).get("error") == "kept_manual"
        assert (await _machine(db, r_m, c, "dv2", onto.SOURCE_RULE))["ok"], "기계 선이 사람 선으로 굳었다"
    finally:
        await db.rollback()


async def test_a_fold_of_two_persons_revisions_keeps_the_one_that_stays(db):
    """둘 다 사람 판이면 남는 판의 것이 남는다(누가 · 메모 · 앞 판) — 접힌 판의 것은 그 판 행에 기록으로 남는다. 옛 선은 양쪽 다
    사람 선이라 적을 것이 없다."""
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        r_a1, r_a2, r_b1, r_b2 = _report(), _report(), _report(), _report()
        a1 = await _rev(db, r_a1, a, "dv1")
        assert (await onto.set_revision(db, r_a2, task_key=a, code="dv2", source="manual", decided_by="a@x",
                                        note="A 쪽", supersedes=a1))["ok"]
        b1 = await _rev(db, r_b1, b, "pv1")
        assert (await onto.set_revision(db, r_b2, task_key=b, code="dv2", source="manual", decided_by="b@x",
                                        note="B 쪽", supersedes=b1))["ok"]
        await _legacy(db, r_a2)
        await _legacy(db, r_b2)

        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["revisions"] >= 1 and got["collapsed"] >= 1 and not got["deferred"], got

        kept = (await _rev_obj(db, f"{b}@dv2")).properties
        assert (kept.get("rev_source"), kept.get("decided_by"), kept.get("note")) == ("manual", "b@x", "B 쪽"), kept
        folded = (await _rev_obj(db, f"{a}@dv2")).properties
        assert (folded.get("decided_by"), folded.get("note")) == ("a@x", "A 쪽"), folded
        line = {x["code"]: x for x in await onto.history(db, b)}
        assert line["dv2"]["supersedes"] == b1, "남는 판의 앞 판이 바뀌었다"
        ahead = [e.dst_key for e in await _our_edges(db, onto.REL_SUPERSEDES, src_key=f"{b}@dv2")]
        assert ahead == [b1], "남는 판에 앞 판 선이 둘이 됐다"
        assert f"{a}@dv2 → {b}@dv1" in got["dropped"], f"남는 판으로 못 옮긴 앞 판 선을 알리지 않았다: {got['dropped']}"
        for rep in (r_a2, r_b2):
            mine = await onto.linked_revision(db, rep)
            assert (mine["key"], mine["source"]) == (f"{b}@dv2", "manual"), mine
            assert (await _our_edges(db, onto.REL_MEASURED, src_key=rep.id))[0].properties is None, "옛 선에 뭔가 적었다"
    finally:
        await db.rollback()


async def test_a_fold_of_two_machine_revisions_writes_nothing_on_the_old_lines(db):
    """둘 다 기계 판이면 옛 선에 아무것도 적지 않는다 — 누가 이었는지 모르는 선은 모르는 채로 둔다(적는 것은 접어서 뜻이 바뀔
    때뿐이다)."""
    t = _tag()
    a, b, c = f"L2A-{t}", f"L2B-{t}", f"L2C-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _task(db, c)
        r1, r2 = _report(), _report()
        assert (await _machine(db, r1, a, "dv1"))["ok"]
        assert (await _machine(db, r2, b, "dv1"))["ok"]
        await _legacy(db, r1)
        await _legacy(db, r2)

        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["collapsed"] >= 1 and not got["deferred"], got

        assert (await _rev_obj(db, f"{b}@dv1")).properties.get("rev_source") == "eng_meta"
        for rep in (r1, r2):
            mine = await onto.linked_revision(db, rep)
            assert (mine["key"], mine["source"]) == (f"{b}@dv1", None), mine
            assert (await _machine(db, rep, c, "dv2", onto.SOURCE_RULE))["ok"]
    finally:
        await db.rollback()


async def test_a_fold_carries_the_line_to_a_previous_revision_that_already_moved(db):
    """앞 판이 먼저 옮겨진 차례(key 차례 — dv1 다음 dv2)에서도 앞 판 선이 남는 판으로 간다 — 그때 앞 판은 이미 새 이름이다."""
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        r1, r2, r_m = _report(), _report(), _report()
        first = await _rev(db, r1, a, "dv1")
        await _rev(db, r2, a, "dv2", supersedes=first)
        assert (await _machine(db, r_m, b, "dv2"))["ok"]

        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["revisions"] >= 1 and got["collapsed"] >= 1 and not got["deferred"], got
        assert not [d for d in got["dropped"] if t in d], got["dropped"]

        line = {x["code"]: x for x in await onto.history(db, b)}
        assert line["dv2"]["supersedes"] == f"{b}@dv1", line
        assert await onto._chain_keys(db, f"{b}@dv2") == [f"{b}@dv2", f"{b}@dv1"]
    finally:
        await db.rollback()


async def test_a_reused_old_key_is_not_resolved_away(db):
    """A→B 로 바뀐 뒤 허브가 A 라는 **새** 과제를 만들면 A 는 지금 key 다 — 옛 → 새 로 풀면 남의 개정을 옮긴다."""
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _hub(db, onto.TYPE_TASK, {"key": b, "renamed_from": a, "previous_keys": [a], "updated_at": "T2"})
        await _task(db, a)                              # 다시 쓰인 식별자
        assert a not in await onto.renamed_keys(db, onto.TYPE_TASK)
        assert await onto.current_key(db, onto.TYPE_TASK, a) == a
        rep = _report()
        await _rev(db, rep, a, "pv1")
        await onto.reflect_after_sync(db)
        assert [x["code"] for x in await onto.history(db, a)] == ["pv1"], "새 A 의 개정을 B 로 옮겼다"
    finally:
        await db.rollback()


async def test_a_renamed_model_is_followed_in_the_revision(db):
    t = _tag()
    task, m1, m2 = f"L2T-{t}", f"M1-{t}", f"M2-{t}"
    try:
        await _task(db, task)
        await _hub(db, onto.TYPE_MODEL, {"key": m1, "label": m1, "properties": {"task": task}})
        key = await _rev(db, _report(), task, "dv1", model_key=m1)
        await _hub(db, onto.TYPE_MODEL, {"key": m2, "label": m2, "renamed_from": m1, "previous_keys": [m1],
                                         "properties": {"task": task}, "updated_at": "T2"})
        got = await onto.reflect_after_sync(db)
        assert got["models"] >= 1, got
        assert (await _rev_obj(db, key)).properties["model"] == m2
    finally:
        await db.rollback()


# ── 합침 — 알리고 사람이 옮긴다 ──────────────────────────────────────────────

async def test_a_merged_task_is_announced_not_moved_then_moved_by_a_person(db):
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        rep = _report(project=a, code="dv1")
        await _rev(db, rep, a, "dv1")
        assert (await onto.confirm_alias(db, alias=f"free-{t}", key=a))["ok"]
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})

        got = await onto.reflect_after_sync(db)
        assert got["merged_waiting"] >= 1, got
        assert [x["code"] for x in await onto.history(db, a)] == ["dv1"], "합침을 저절로 옮겼다(사용자 결정 위반)"
        waiting = [m for m in await onto.merged_tasks(db) if m["key"] == a]
        assert waiting and waiting[0]["into"] == b and waiting[0]["revisions"] == [f"{a}@dv1"], waiting
        assert (waiting[0]["reports"], waiting[0]["aliases"], waiting[0]["into_active"]) == (1, 1, True)
        st = await onto.task_state(db, a)
        assert (st["state"], st["into"]) == ("merged", b), st

        moved = await onto.move_merged_task(db, a, by="admin@x", note="확인함")
        assert moved["ok"] and moved["revisions"] == 1 and moved["aliases"] == 1, moved
        assert [(x["code"], x["reports"]) for x in await onto.history(db, b)] == [("dv1", [rep.id])]
        assert not [m for m in await onto.merged_tasks(db) if m["key"] == a], "옮긴 뒤에도 목록에 남았다"
        obj = await _rev_obj(db, f"{b}@dv1")
        assert obj.properties["moves"][-1]["by"] == "admin@x" and onto.MOVE_MERGE in obj.properties["moves"][-1]["why"]
        mm = await onto.mismatch(db, rep)
        assert mm and mm["kind"] == "merged", mm       # 수동 메타는 고치지 않는다 — 옛 이름일 뿐이라고 말한다
    finally:
        await db.rollback()


async def test_only_a_merged_task_can_be_moved(db):
    t = _tag()
    a = f"L2A-{t}"
    try:
        await _task(db, a)
        got = await onto.move_merged_task(db, a)
        assert not got["ok"] and got["error"] == "not_merged", got
    finally:
        await db.rollback()


async def test_the_merge_target_is_followed_to_its_end(db):
    """A 를 B 로 합쳤는데 B 가 C 로 바뀌었으면 받는 곳은 C — 옛 B 로 옮기면 다음 반영이 또 옮겨야 한다."""
    t = _tag()
    a, b, c = f"L2A-{t}", f"L2B-{t}", f"L2C-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})
        await _hub(db, onto.TYPE_TASK, {"key": c, "renamed_from": b, "previous_keys": [b], "updated_at": "T3"})
        assert (await onto.task_state(db, a))["into"] == c
    finally:
        await db.rollback()


async def test_a_merge_into_a_gone_task_is_refused(db):
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _rev(db, _report(), a, "dv1")
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"},
                   {"key": b, "deleted": True, "updated_at": "T2"})
        got = await onto.move_merged_task(db, a)
        assert not got["ok"] and got["error"] == "target_gone", got
        assert [x["code"] for x in await onto.history(db, a)] == ["dv1"], "거절했는데 옮겼다"
    finally:
        await db.rollback()


async def test_moving_a_merged_task_keeps_a_persons_old_line_a_persons(db):
    """합친 과제를 관리자가 옮길 때도 같다 — 받는 과제에 같은 코드의 기계 판이 있으면 사람이 정한 것이 그 판으로 가고, 사람의 옛
    선은 사람 선으로 남는다. 예전엔 기계 판에 표시 없이 얹혀 다음 자동 잇기가 옮겼다(재검토 11-14 F-02)."""
    t = _tag()
    a, b, c = f"L2A-{t}", f"L2B-{t}", f"L2C-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        await _task(db, c)
        r_h, r_m = _report(), _report()
        await _rev(db, r_h, a, "dv1", note="사람이 정했다")
        assert (await _machine(db, r_m, b, "dv1"))["ok"]
        await _legacy(db, r_h)
        await _legacy(db, r_m)
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})

        got = await onto.move_merged_task(db, a, by="admin@x")
        assert got["ok"] and (got["collapsed"], got["reports"]) == (1, 1), got
        kept = (await _rev_obj(db, f"{b}@dv1")).properties
        assert (kept.get("rev_source"), kept.get("decided_by"), kept.get("note")) == ("manual", "t@x", "사람이 정했다"), kept
        mine = await onto.linked_revision(db, r_h)
        assert (mine["key"], mine["source"]) == (f"{b}@dv1", "manual"), mine
        assert (await onto.linked_revision(db, r_m))["source"] == "eng_meta"
        assert (await _machine(db, r_h, c, "dv2", onto.SOURCE_RULE)).get("error") == "kept_manual"
        assert (await _machine(db, r_m, c, "dv2", onto.SOURCE_RULE))["ok"], "기계 선이 사람 선으로 굳었다"
    finally:
        await db.rollback()


async def test_a_supersedes_line_that_would_loop_is_cut_not_moved(db):
    """옮긴 끝이 개정 줄을 돌게 만들면 옮기지 않고 끊는다(기록에 남긴다) — 줄을 따라가는 질의가 돈다."""
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    try:
        await _task(db, a)
        await _task(db, b)
        a2 = await _rev(db, _report(), a, "dv2")
        b1 = await _rev(db, _report(), b, "dv1", supersedes=a2)        # 과제를 건너 앞 판을 둔 줄
        b2 = await _rev(db, _report(), b, "dv2", supersedes=b1)
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})
        got = await onto.move_merged_task(db, a)
        assert got["ok"] and got["collapsed"] == 1, got
        assert got["dropped"] == [f"{b1} → {a2}"], got     # b1 → b2 로 옮기면 b2 → b1 → b2 가 돈다
        assert await onto._chain_keys(db, b2) == [b2, b1]
    finally:
        await db.rollback()


# ── 과제 검색(KR-01 · KR-16 다시) ────────────────────────────────────────────

async def test_ranking_happens_before_truncation(db):
    """예전에는 key 순으로 limit×5 개를 먼저 자르고 그 안에서만 순위를 매겼다 — 앞부분 일치가 창 밖으로 밀렸다."""
    q = f"zq{_tag()}"
    try:
        for i in range(12):
            await _task(db, f"a-{q}-{i:02d}")           # 낱말 경계 — key 순으로는 앞
        await _task(db, f"{q}-prime")                   # 앞부분 — key 순으로는 뒤
        got = await onto.search_tasks(db, q, limit=2)
        assert [i["key"] for i in got["items"]][0] == f"{q}-prime", got["items"]
        assert [i["match_kind"] for i in got["items"]] == ["prefix", "word"]
        assert (got["total"], got["truncated"]) == (13, True)
    finally:
        await db.rollback()


async def test_each_row_says_how_it_matched(db):
    q = f"kq{_tag()}"
    try:
        await _task(db, f"{q}x")
        await _task(db, f"x-{q}")
        await _task(db, f"x{q}y")
        await _task(db, f"T-{_tag()}", task_code=f"C/{q}")
        got = {i["key"]: (i["matched_by"], i["match_kind"]) for i in (await onto.search_tasks(db, q))["items"]}
        assert got[f"{q}x"] == ("task_name", "prefix")
        assert got[f"x-{q}"] == ("task_name", "word")
        assert got[f"x{q}y"] == ("task_name", "substring")
        assert ("task_code", "word") in got.values(), got
    finally:
        await db.rollback()


async def test_hub_and_our_aliases_are_searched_and_resolved(db):
    t = _tag()
    t1, t2, t3 = f"AL1-{t}", f"AL2-{t}", f"AL3-{t}"
    try:
        await _task(db, t1, aliases=[f"OLD-{t}", f"DUP-{t}"])
        await _task(db, t3, aliases=[f"DUP-{t}"])
        await _task(db, t2)
        assert (await onto.confirm_alias(db, alias=f"FREE-{t}", key=t2))["ok"]

        hub = (await onto.search_tasks(db, f"OLD-{t}"))["items"]
        assert [(i["key"], i["matched_by"], i["alias_source"], i["matched_alias"]) for i in hub] == \
            [(t1, "alias", "hub", f"OLD-{t}")], hub
        ours = (await onto.search_tasks(db, f"FREE-{t}"))["items"]
        assert [(i["key"], i["matched_by"], i["alias_source"]) for i in ours] == [(t2, "alias", "dynaforge")], ours

        assert await onto.resolve_task(db, f"OLD-{t}") == (t1, "hub_alias")
        assert await onto.resolve_task(db, f"DUP-{t}") == ("", ""), "두 과제가 가진 별칭으로 풀었다(짐작이다)"
        cands = {c["key"] for c in await onto.task_candidates(db, f"dup{t}")}
        assert {t1, t3} <= cands, cands                 # 풀지는 않고 후보로 둘 다 보인다
        # 사람이 이 플랫폼에서 정한 별칭과 허브 별칭이 엇갈리면 어느 쪽도 조용히 이기지 않는다 — 풀지 않고 둘 다 후보로 보인다
        # (검토 R8 · 11-11 — 예전엔 우리 별칭이 먼저였다. 정확 일치는 원천이 하나로 모일 때만이다)
        assert (await onto.confirm_alias(db, alias=f"OLD-{t}", key=t2))["ok"]
        assert await onto.resolve_task(db, f"OLD-{t}") == ("", "")
        cands, ambiguous = await onto.candidates_for(db, f"OLD-{t}")
        assert ambiguous and [(c["key"], c["why"]) for c in cands][:2] == \
            [(t2, "사람이 붙인 별칭이 가리킨다"), (t1, "허브 별칭이 글자 그대로 같다")], cands
    finally:
        await db.rollback()


async def test_deprecated_tasks_are_hidden_only_from_new_choices(db):
    """그만 씀 — 새로 고르는 목록(후보)에서만 숨긴다. 검색 · 풀기 · 이미 이은 것에는 그대로(사용자 결정 10-30)."""
    t = _tag()
    key = f"DEP-{t}"
    try:
        await _hub(db, onto.TYPE_TASK, {"key": key, "label": key, "status": "deprecated"})
        assert key not in {c["key"] for c in await onto.task_candidates(db, f"dep{t}")}
        found = (await onto.search_tasks(db, key))["items"]
        assert [(i["key"], i["status"]) for i in found] == [(key, "deprecated")]
        assert await onto.resolve_task(db, key) == (key, "exact")
        assert (await onto.task_state(db, key))["state"] == "deprecated"
    finally:
        await db.rollback()


# ── 라우트 — 보기 · 합친 과제 옮기기 · 개정 패널(커밋하고 치운다) ─────────────

async def _client():
    from httpx import ASGITransport

    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    app = create_app()
    app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
    return app, ASGITransport(app=app, raise_app_exceptions=False)


async def _user(db, *, admin: bool = False) -> User:
    from app.shared import security
    u = User(email=f"l2_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _wipe(db, t: str, *users: User, session_id: str = "") -> None:
    like = f"%{t}%"
    await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(like) | OntoRelation.dst_key.like(like)))
    await db.execute(delete(OntoObject).where(OntoObject.key.like(like)))
    await db.execute(delete(OntoPreviousKey).where(OntoPreviousKey.key.like(like)))
    await db.execute(delete(OntoAlias).where(OntoAlias.key.like(like)))
    if session_id:
        await db.execute(delete(OntoRelation).where(OntoRelation.src_key.in_(
            select(ImpactReport.id).where(ImpactReport.session_id == session_id))))
        await db.execute(delete(ImpactReport).where(ImpactReport.session_id == session_id))
        await db.execute(delete(Session).where(Session.id == session_id))
    for u in users:
        await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


async def test_the_browse_routes_show_states_edges_and_old_keys(db):
    import httpx

    from app.shared.auth import get_current_user
    t = _tag()
    ty, rel = f"t_{t}", f"r_{t}"
    u = await _user(db)
    try:
        await _hub(db, ty, {"key": f"X0-{t}", "label": "하나"},
                   {"key": f"X2-{t}", "label": "둘", "status": "deprecated"},
                   {"key": f"X3-{t}", "label": "셋"})
        await _hub(db, ty, {"key": f"X1-{t}", "label": "하나", "renamed_from": f"X0-{t}",
                            "previous_keys": [f"X0-{t}"], "updated_at": "T2"},
                   {"key": f"X3-{t}", "deleted": True, "updated_at": "T2"})
        await sp_core.save_relations(db, ty, [{"src": f"X1-{t}", "relation": rel, "dst": f"X2-{t}",
                                               "dst_type": ty, "evidence_note": "근거", "updated_at": "T2"}])
        await db.commit()
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            types = (await c.get(f"{P}/ontology/types")).json()["data"]["types"]
            mine = [x for x in types if x["slug"] == ty]
            assert mine and mine[0]["counts"] == {"total": 3, "active": 1, "deprecated": 1, "inactive": 1,
                                                  "hidden": 0}, mine
            for state, want in (("active", [f"X1-{t}"]), ("deprecated", [f"X2-{t}"]), ("inactive", [f"X3-{t}"])):
                r = await c.get(f"{P}/ontology/objects", params={"type": ty, "state": state})
                assert [i["key"] for i in r.json()["data"]["items"]] == want, (state, r.text[:300])
            one = (await c.get(f"{P}/ontology/objects/{ty}/X1-{t}")).json()["data"]
            assert one["object"]["properties"] == {} and one["previous"] == [f"X0-{t}"], one
            assert [(e["relation"], e["key"], e["label"], e["evidence_note"]) for e in one["out"]] == \
                [(rel, f"X2-{t}", "둘", "근거")], one["out"]
            old = (await c.get(f"{P}/ontology/objects/{ty}/X0-{t}")).json()["data"]
            assert old["renamed_to"] == f"X1-{t}", old          # 옛 식별자로 물으면 지금 것을 알려 준다
            assert (await c.get(f"{P}/ontology/objects", params={"type": ty, "state": "x"})).status_code == 422
    finally:
        await _wipe(db, t, u)


@pytest.mark.usefixtures("own_sync_lock")
async def test_the_panel_hears_of_a_merge_and_only_an_admin_moves_it(db):
    import httpx

    from app.shared import storage
    from app.shared.auth import get_current_user
    from app.worker import plm_sync
    # 옮기기 라우트는 받기 잠금을 잡는다 — 진짜 이름이면 dev DB 의 다른 실행과 엮여 409 로 빨개진다(재검토 11-14 F-17)
    assert plm_sync.LOCK_NAME.startswith("dynaforge.sp_core_sync.test."), plm_sync.LOCK_NAME
    t = _tag()
    a, b = f"L2A-{t}", f"L2B-{t}"
    owner, admin = await _user(db), await _user(db, admin=True)
    sid = ulid.new().str
    db.add(Session(id=sid, user_id=owner.id, name="l2", storage_path=storage.session_rel_dir(owner.id, sid)))
    await db.commit()
    try:
        await _task(db, a)
        await _task(db, b)
        rep = ImpactReport(id=ulid.new().str, session_id=sid, user_id=owner.id, kind="sphere",
                           eng_meta={"project": a, "dev_revision": {"code": "dv1"}}, n_cases=0)
        db.add(rep)
        await db.flush()
        await _rev(db, rep, a, "dv1")
        await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})
        await db.commit()
        app, transport = await _client()
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            app.dependency_overrides[get_current_user] = lambda: owner
            d = (await c.get(f"{P}/reports/{rep.id}/revision")).json()["data"]
            assert d["linked"] == {"key": f"{a}@dv1", "task": a, "code": "dv1", "source": "manual"}, d   # 선을 누가 이었나
            assert (d["task_state"]["state"], d["task_state"]["into"]) == ("merged", b), d["task_state"]
            refused = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={})
            assert refused.status_code == 403, refused.text[:200]      # 남의 리포트까지 옮기는 일 — 관리자만

            app.dependency_overrides[get_current_user] = lambda: admin
            listed = (await c.get(f"{P}/ontology/merged-tasks")).json()["data"]
            assert [m["into"] for m in listed if m["key"] == a] == [b], listed
            r = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={"note": "확인"})
            assert r.status_code == 200 and r.json()["data"]["revisions"] == 1, r.text[:300]
            runs = await c.get(f"{P}/ontology/sync/runs")
            assert runs.status_code == 200 and isinstance(runs.json()["data"], list)

            app.dependency_overrides[get_current_user] = lambda: owner
            d2 = (await c.get(f"{P}/reports/{rep.id}/revision")).json()["data"]
            assert d2["linked"]["key"] == f"{b}@dv1" and d2["mismatch"]["kind"] == "merged", d2
    finally:
        await _wipe(db, t, owner, admin, session_id=sid)


# ── 합친 과제 옮기기가 다른 트랜잭션과 겹칠 때(재검토 11-14 F-08) — 두 세션을 실제로 겹친다 ─────────────

async def _merged_case(db, t: str, users: list, sid: str):
    """합쳐진 과제 A(리포트 하나가 `A@dv1` 에 사람 선) · 살아 있는 B · 주인 · 관리자를 **커밋해** 둔다 — 치우는 것은 부른 쪽 `_wipe`.

    만든 사용자는 만드는 대로 `users` 에 담는다 — 중간에 깨져도 부른 쪽이 그때까지 만든 것을 치운다."""
    from app.shared import storage
    a, b = f"L2A-{t}", f"L2B-{t}"
    users.append(await _user(db))
    users.append(await _user(db, admin=True))
    owner, admin = users
    db.add(Session(id=sid, user_id=owner.id, name="l2", storage_path=storage.session_rel_dir(owner.id, sid)))
    await db.commit()
    await _task(db, a)
    await _task(db, b)
    rep = ImpactReport(id=ulid.new().str, session_id=sid, user_id=owner.id, kind="sphere",
                       eng_meta={"project": a, "dev_revision": {"code": "dv1"}}, n_cases=0)
    db.add(rep)
    await db.flush()
    await _rev(db, rep, a, "dv1")
    await _hub(db, onto.TYPE_TASK, {"key": a, "deleted": True, "merged_into": b, "updated_at": "T2"})
    await db.commit()
    return a, b, rep, admin


async def _late_report(db, sid: str, user_id: int) -> str:
    """그 세션에 아직 아무 판에도 안 이어진 리포트 하나를 커밋해 둔다(치우는 것은 `_wipe` — 세션째)."""
    rep = ImpactReport(id=ulid.new().str, session_id=sid, user_id=user_id, kind="sphere", n_cases=0)
    db.add(rep)
    await db.commit()
    return rep.id


@pytest.mark.usefixtures("own_sync_lock")
async def test_a_move_pressed_while_a_report_is_held_answers_busy_at_once(db):
    """합친 과제 옮기기는 그 과제의 리포트를 다른 트랜잭션이 쥐고 있으면 **기다리지 않고** 409 `busy` 다(아무것도 안 옮긴다) — 놓인 뒤
    다시 누르면 옮긴다. 예전엔 첫 리포트 잠금이 기다려서, 누름이 그 트랜잭션이 끝날 때까지 답이 없었다."""
    import asyncio

    import httpx

    from app.database import SessionLocal
    from app.shared.auth import get_current_user
    t, users, sid = _tag(), [], ulid.new().str
    try:
        a, _, rep, admin = await _merged_case(db, t, users, sid)
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: admin
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c, SessionLocal() as other:
            await onto.lock_reports(other, [rep.id])     # 메타 고침 · 손 확정 · 반입 때 잇기가 맨 먼저 하는 일 — 커밋 전이다
            press = asyncio.ensure_future(c.post(f"{P}/ontology/merged-tasks/{a}/move", json={}))
            try:
                done, _ = await asyncio.wait({press}, timeout=5.0)
            finally:
                await other.rollback()                   # 놓는다 — 기다리던 누름이 있으면 여기서 풀린다
            r = await asyncio.wait_for(press, 30)
            assert done, f"누름이 리포트 행을 기다렸다(놓인 뒤의 답 {r.status_code}) — 409 busy 로 바로 답해야 한다"
            msg = r.json()["message"]
            assert r.status_code == 409 and msg.startswith("busy: ") and "고치는 중인 리포트" in msg, (r.status_code, r.text[:300])
            listed = (await c.get(f"{P}/ontology/merged-tasks")).json()["data"]
            assert [m["revisions"] for m in listed if m["key"] == a] == [[f"{a}@dv1"]], "busy 로 답하고도 옮겼다"
            again = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={})
            assert again.status_code == 200 and again.json()["data"]["revisions"] == 1, again.text[:300]
    finally:
        await _wipe(db, t, *users, session_id=sid)


@pytest.mark.usefixtures("own_sync_lock")
async def test_a_move_pressed_while_a_revision_is_held_answers_busy_at_once_then_carries_the_late_line(db):
    """옮길 판의 **이름**을 다른 트랜잭션이 쥐고 있어도(새 리포트를 그 판에 손으로 확정하는 중 — 커밋 전) 누름은 기다리지 않고 409
    `busy` 다. 그 트랜잭션이 끝난 뒤 다시 누르면 그새 이어진 선까지 옮긴다."""
    import asyncio

    import httpx

    from app.database import SessionLocal
    from app.shared.auth import get_current_user
    t, users, sid = _tag(), [], ulid.new().str
    try:
        a, b, _, admin = await _merged_case(db, t, users, sid)
        late = await _late_report(db, sid, users[0].id)
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: admin
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c, SessionLocal() as other:
            await _rev(other, await other.get(ImpactReport, late), a, "dv1")     # 커밋 전 — 그 리포트 행과 판 이름 A@dv1 을 쥔다
            press = asyncio.ensure_future(c.post(f"{P}/ontology/merged-tasks/{a}/move", json={}))
            try:
                done, _ = await asyncio.wait({press}, timeout=5.0)
                await other.commit()                     # 손 확정이 끝난다 — 기다리던 누름이 있으면 여기서 풀린다
            finally:
                await other.rollback()
            r = await asyncio.wait_for(press, 30)
            assert done, f"누름이 판 이름을 기다렸다(놓인 뒤의 답 {r.status_code}) — 409 busy 로 바로 답해야 한다"
            msg = r.json()["message"]
            assert r.status_code == 409 and msg.startswith("busy: ") and "고치는 중인 판" in msg, (r.status_code, r.text[:300])
            again = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={})
            assert again.status_code == 200 and again.json()["data"]["revisions"] == 1, again.text[:300]
            app.dependency_overrides[get_current_user] = lambda: users[0]
            d = (await c.get(f"{P}/reports/{late}/revision")).json()["data"]
            assert d["linked"]["key"] == f"{b}@dv1", d["linked"]                 # 그새 이어진 선도 함께 옮겨 갔다
    finally:
        await _wipe(db, t, *users, session_id=sid)


@pytest.mark.usefixtures("own_sync_lock")
async def test_a_move_whose_revisions_changed_meanwhile_says_so_and_moves_on_the_next_press(db, monkeypatch):
    """누름이 옮길 판을 읽은 뒤 잠그기 전에 그 과제에 새 판이 생기면 아무것도 옮기지 않고 409 `busy` 다 — 까닭은 「옮길 판이 그새
    달라졌다」 이지 「누가 고치는 중」 이 아니다(예전엔 일어나지 않은 까닭을 댔다). 다시 누르면 새 판까지 옮긴다."""
    import httpx

    from app.database import SessionLocal
    from app.shared.auth import get_current_user
    t, users, sid = _tag(), [], ulid.new().str
    try:
        a, _, _, admin = await _merged_case(db, t, users, sid)
        late = await _late_report(db, sid, users[0].id)
        real, slipped = onto.lock_revision_names, []

        async def slip_in_a_new_revision(sdb, keys, **kw):
            """옮기기가 판 이름을 잠그려는 바로 그때 — 다른 트랜잭션이 그 과제의 새 판 A@dv2 를 만들어 커밋한다(한 번만)."""
            if not slipped:
                slipped.append(True)
                async with SessionLocal() as other:
                    await _rev(other, await other.get(ImpactReport, late), a, "dv2")
                    await other.commit()
            return await real(sdb, keys, **kw)

        monkeypatch.setattr(onto, "lock_revision_names", slip_in_a_new_revision)
        app, transport = await _client()
        app.dependency_overrides[get_current_user] = lambda: admin
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={})
            msg = r.json()["message"]
            assert slipped and r.status_code == 409 and msg.startswith("busy: ") and "달라졌다" in msg, (r.status_code, r.text[:300])
            assert "고치는 중" not in msg, f"일어나지 않은 까닭을 댔다: {msg}"
            again = await c.post(f"{P}/ontology/merged-tasks/{a}/move", json={})
            assert again.status_code == 200 and again.json()["data"]["revisions"] == 2, again.text[:300]
    finally:
        await _wipe(db, t, *users, session_id=sid)
