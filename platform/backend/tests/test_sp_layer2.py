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
    return ulid.new().str[:8].lower()


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
        # 사람이 이 플랫폼에서 정한 별칭이 허브 별칭보다 먼저다
        assert (await onto.confirm_alias(db, alias=f"OLD-{t}", key=t2))["ok"]
        assert await onto.resolve_task(db, f"OLD-{t}") == (t2, "alias")
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


async def test_the_panel_hears_of_a_merge_and_only_an_admin_moves_it(db):
    import httpx

    from app.shared import storage
    from app.shared.auth import get_current_user
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
            assert d["linked"] == {"key": f"{a}@dv1", "task": a, "code": "dv1"}, d
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
