# SRC-09 — 과거 붙이기의 「붙는 것」 을 받기 뒤 · 반입 뒤에 스스로 잇는다: 정확 일치만 · 사람 판은 안 옮김 · 깨져도 반입 · 받기는 그대로
"""코어와 잇기 뼈대 규칙(포털 요청서 SRC-09) — 정확 일치(과제명 · 과제코드 · 옛 과제명 · 별칭)만 기계가 잇고 짐작(후보)은 세기만 한다.
지키는 것 넷.
  ① 붙는 것만 잇는다 — 후보 · 못 붙임 · 이름 없음 · 코드 없음은 **센다**(조용히 건너뛰면 "다 붙었다" 로 읽힌다).
  ② ★사람이 정한 판에 이어진 리포트는 옮기지 않는다 — `set_revision` 의 manual 보호는 판 칸만 지키고 리포트 선은 옮긴다.
  ③ 반입 · 받기를 **먼저 굳히고** 돈다 — 잇기가 깨져도 리포트 · 받은 행은 남고, 경고(반입 응답 · 잡) · 「확인 필요」(받기)로 알린다.
  ④ 받기 뒤 수는 리포트 전부를 센 것이라 관리자에게만 보인다(SRC-10 · 10-31 과 같은 까닭).

시험 DB 는 떠 있는 dev 워커의 DB 다 — 서비스 시험은 한 트랜잭션 안에서 돌리고 되돌린다. 커밋하는 시험(반입 · 받기)은 고유한
과제명 · 과제코드를 쓰고 치운다. 받기 시험은 전부를 보는 호출(report_ids=None)이 나가는지만 잡고 실제로는 이 시험의 리포트만 잇는다
(공유 DB 의 남의 리포트에 개정을 쓰지 않게).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (ImpactReport, OntoAlias, OntoObject, OntoRelation, OntoSyncRun, Session, SessionFile,
                        User)
from app.modules.ontology import services as onto
from app.runner import sp_core
from app.shared import security, storage
from app.worker import plm_sync

pytestmark = pytest.mark.asyncio(loop_scope="session")

P = "/api/v1"
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")


def _tag() -> str:
    return ulid.new().str[:8].lower()


async def _owner(db, *, admin: bool = False, commit: bool = False):
    u = User(email=f"al_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.flush()
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="autolink", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.flush()
    if commit:
        await db.commit()
        storage.ensure_session_dir(u.id, sid)
    return u, s


async def _rep(db, s, *, project: str = "", code: str = "", commit: bool = False) -> ImpactReport:
    em: dict = {}
    if project:
        em["project"] = project
    if code:
        em["dev_revision"] = {"code": code}
    r = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=s.user_id, kind="sphere", n_cases=0,
                     eng_meta=em or None)
    db.add(r)
    await db.flush()
    if commit:
        await db.commit()
    return r


async def _task(db, key: str, **props) -> None:
    """허브 한 쪽을 실제 수신부로 받는다(층 1 이 실제로 남기는 꼴 그대로)."""
    await sp_core.save_rows(db, onto.TYPE_TASK, [{"key": key, "label": f"과제 {key}", "status": "active",
                                                  "updated_at": "T1", "properties": props}])


async def _linked(db, rid: str) -> list[str]:
    return sorted((await db.execute(select(OntoRelation.dst_key).where(
        OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_type == onto.TYPE_REPORT,
        OntoRelation.src_key == rid, OntoRelation.deleted.is_(False)))).scalars().all())


async def _rev(db, key: str) -> OntoObject | None:
    return (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == onto.TYPE_REVISION, OntoObject.key == key)
        .execution_options(populate_existing=True))).scalar_one_or_none()


async def _drop(db, u, s, keys=(), runs=()) -> None:
    """커밋한 시험의 뒷정리 — 이 시험의 리포트 · 과제 · 개정 · 실행 기록만 지운다."""
    uid, sid = u.id, s.id               # rollback 이 행을 만료시키기 전에 읽어 둔다
    await db.rollback()
    mine = (await db.execute(select(ImpactReport.id).where(ImpactReport.session_id == sid))).scalars().all()
    if mine:
        await db.execute(delete(OntoRelation).where(OntoRelation.src_type == onto.TYPE_REPORT,
                                                    OntoRelation.src_key.in_(mine)))
    for k in keys:
        await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{k}@%")))
        await db.execute(delete(OntoRelation).where(OntoRelation.dst_key.like(f"{k}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{k}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key == k))
        await db.execute(delete(OntoAlias).where(OntoAlias.key == k))
    for rid in runs:
        await db.execute(delete(OntoSyncRun).where(OntoSyncRun.id == rid))
    await db.execute(delete(ImpactReport).where(ImpactReport.session_id == sid))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()
    shutil.rmtree(storage.session_abs_dir(uid, sid), ignore_errors=True)


# ── ① 붙는 것만 잇고 나머지는 센다 ─────────────────────────────────────────────

async def test_only_exact_matches_are_linked_and_the_rest_is_counted(db):
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task, task_code=code)
        assert (await onto.confirm_alias(db, alias=f"별칭-{t}", key=task, by="kim@x"))["ok"]
        r_exact = await _rep(db, s, project=task, code="dv1")          # 과제명 그대로
        r_code = await _rep(db, s, project=code, code="dv2")           # 과제코드 그대로
        r_alias = await _rep(db, s, project=f"별칭-{t}", code="pv1")   # 사람이 붙인 별칭
        r_nocode = await _rep(db, s, project=task)                     # 과제는 아는데 판을 모른다
        r_cand = await _rep(db, s, project=f"al {t}", code="dv1")      # 구분기호만 다르다 — 후보일 뿐
        r_none = await _rep(db, s, project=f"없는것-{t}", code="dv1")
        r_noname = await _rep(db, s)
        ids = [r.id for r in (r_exact, r_code, r_alias, r_nocode, r_cand, r_none, r_noname)]

        got = await onto.auto_link_tasks(db, report_ids=ids)
        assert got["scope"] == "reports" and got["reports"] == 7, got
        assert (got["linked"], got["already"], got["kept_manual"], got["skipped_no_code"]) == (3, 0, 0, 1), got
        assert (got["candidates"], got["unmatched"], got["reports_without_a_name"]) == (1, 1, 1), got
        assert got["refused"] == []
        line = {x["code"]: (x["reports"], x["rev_source"]) for x in await onto.history(db, task)}
        assert line == {"dv1": ([r_exact.id], "rule"), "dv2": ([r_code.id], "rule"),
                        "pv1": ([r_alias.id], "rule")}, line
        for r in (r_nocode, r_cand, r_none, r_noname):
            assert await _linked(db, r.id) == [], "짐작 · 판 없는 것을 이었다"

        again = await onto.auto_link_tasks(db, report_ids=ids)
        assert (again["linked"], again["already"]) == (0, 3), "두 번째 실행은 아무것도 쓰지 않아야 한다"
    finally:
        await db.rollback()


# ── ② 사람이 정한 판 ──────────────────────────────────────────────────────────

async def test_a_report_on_a_human_revision_is_never_moved(db):
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        # 사람이 이 리포트를 pv1 로 확정했다 — 수동 메타(dv1)와 다르다. 관계가 정본이다
        assert (await onto.set_revision(db, r, task_key=task, code="pv1", decided_by="kim@x",
                                        note="사람이 봤다", source="manual"))["ok"]
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert (got["kept_manual"], got["linked"]) == (1, 0), got
        assert await _linked(db, r.id) == [f"{task}@pv1"], "사람이 정한 판에서 옮겼다"
        assert await _rev(db, f"{task}@dv1") is None, "쓰지 않을 판을 만들었다"

        # 사람이 확정한 판을 **가리키는** 것은 막지 않는다 — 판 칸(누가 · 언제 · 메모)은 그대로다
        r2 = await _rep(db, s, project=task, code="pv1")
        got2 = await onto.auto_link_tasks(db, report_ids=[r2.id])
        assert got2["linked"] == 1, got2
        p = (await _rev(db, f"{task}@pv1")).properties
        assert (p["rev_source"], p["decided_by"], p["note"]) == ("manual", "kim@x", "사람이 봤다"), p
        assert await _linked(db, r2.id) == [f"{task}@pv1"]
    finally:
        await db.rollback()


async def test_a_machine_link_moves_to_the_task_it_now_resolves_to(db):
    """인제스트 때 잇기는 수동 메타 글자 그대로다 — 과제코드로 적힌 리포트는 「없는 과제」 에 붙어 있다가, 허브가 그 코드의 과제를
    내면 받기 뒤 자동 잇기가 정본 과제로 옮긴다(SRC-09 의 까닭). 옛 판 객체는 지우지 않는다(set_revision 과 같다)."""
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    try:
        _, s = await _owner(db)
        r = await _rep(db, s, project=code, code="dv1")
        first = await onto.link_from_eng_meta(db, r)
        assert first["key"] == f"{code}@dv1" and first["task_unverified"], first
        await _task(db, task, task_code=code)
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert got["linked"] == 1, got
        assert await _linked(db, r.id) == [f"{task}@dv1"]
        assert (await _rev(db, f"{task}@dv1")).properties["rev_source"] == onto.SOURCE_RULE
        assert await _rev(db, f"{code}@dv1") is not None, "옛 판 객체는 남는다"
    finally:
        await db.rollback()


# ── ③ 반입 뒤 — 굳힌 뒤에 돌고, 깨져도 반입은 그대로 ────────────────────────────

async def test_after_import_links_only_that_report_and_commits(db):
    t = _tag()
    task = f"AL-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await db.commit()
        r = await _rep(db, s, project=task, code="dv1", commit=True)
        other = await _rep(db, s, project=task, code="dv2", commit=True)   # 같은 과제의 다른 리포트 — 이번 반입이 아니다
        got = await onto.link_after_import(db, r)
        assert (got["scope"], got["reports"], got["linked"]) == ("reports", 1, 1), got
        async with SessionLocal() as fresh:                               # 다른 세션에서 보인다 = 굳었다
            assert await _linked(fresh, r.id) == [f"{task}@dv1"]
            assert await _linked(fresh, other.id) == [], "반입한 리포트만 봐야 한다"
        assert r.kind == "sphere", "부르는 쪽의 리포트 행이 만료되면 안 된다"
    finally:
        await _drop(db, u, s, keys=[task])


async def test_a_broken_link_after_import_keeps_the_report_and_says_why(db, monkeypatch):
    async def boom(_db, **_kw):
        raise RuntimeError("잇기 결함")

    monkeypatch.setattr(onto, "auto_link_tasks", boom)
    u, s = await _owner(db, commit=True)
    try:
        r = await _rep(db, s, project=f"AL-{_tag()}", code="dv1", commit=True)
        got = await onto.link_after_import(db, r)
        assert "잇기 결함" in got["error"], got
        assert r.kind == "sphere" and r.id, "실패 뒤에도 부르는 쪽이 리포트를 읽는다"
        async with SessionLocal() as fresh:
            assert await fresh.get(ImpactReport, r.id) is not None
    finally:
        await _drop(db, u, s)


async def test_a_busy_lock_skips_the_link_and_says_so(db):
    u, s = await _owner(db, commit=True)
    try:
        r = await _rep(db, s, project=f"AL-{_tag()}", code="dv1", commit=True)
        async with SessionLocal() as holder:
            assert await plm_sync.try_lock(holder)            # 받기가 도는 중이다
            got = await onto.link_after_import(db, r)
            await holder.rollback()
        assert got["skipped"] == "busy" and "받기 뒤" in got["detail"], got
        assert r.kind == "sphere"
    finally:
        await _drop(db, u, s)


@needs_sphere
async def test_an_import_links_the_report_through_its_task_code(db):
    """종단 — `ingest_report` 가 굳힌 뒤 과제 잇기가 돈다(업로드 · 번들 · 7-1 반입이 모두 이 자리를 지난다)."""
    from app.modules.reports import services as rsvc
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task, task_code=code)
        await db.commit()
        rep = await rsvc.ingest_report(db, s, filename="Test_001_report.html", raw=_SPHERE.read_bytes(),
                                       project=code, dev_rev="dv1")
        links = rep.auto_task_links
        assert (links["scope"], links["reports"], links["linked"]) == ("reports", 1, 1), links
        assert [(x["code"], x["reports"], x["rev_source"]) for x in await onto.history(db, task)] == \
            [("dv1", [rep.id], "rule")]
        # 인제스트 때 잇기(글자 그대로)가 먼저 만든 판에서 옮겨졌다 — 옛 판은 빈 채로 남는다
        assert [(x["code"], x["reports"]) for x in await onto.history(db, code)] == [("dv1", [])]
    finally:
        await _drop(db, u, s, keys=[task, code])


@needs_sphere
async def test_a_broken_link_never_undoes_the_ingest(db, monkeypatch):
    from app.modules.reports import services as rsvc

    async def boom(_db, **_kw):
        raise RuntimeError("잇기 결함")

    monkeypatch.setattr(onto, "auto_link_tasks", boom)
    task = f"AL-{_tag()}"
    u, s = await _owner(db, commit=True)
    try:
        rep = await rsvc.ingest_report(db, s, filename="Test_001_report.html", raw=_SPHERE.read_bytes(),
                                       project=task, dev_rev="dv1")
        assert "잇기 결함" in rep.auto_task_links["error"]
        assert rep.n_cases > 0
        async with SessionLocal() as fresh:
            assert await fresh.get(ImpactReport, rep.id) is not None, "잇기 결함이 반입을 되감았다"
        # 인제스트 때 잇기(수동 메타 글자 그대로)는 반입과 함께 굳었다
        line = await onto.history(db, task)
        assert [(x["code"], x["reports"]) for x in line] == [("dv1", [rep.id])], line
    finally:
        await _drop(db, u, s, keys=[task])


@needs_sphere
async def test_both_import_routes_return_the_task_links(db):
    """업로드(POST /sessions/{id}/reports)와 한 번에 반입(POST /reports/intake) — 응답에 `task_links` 가 실린다."""
    from app.main import create_app
    t = _tag()
    task = f"AL-{t}"
    u, s = await _owner(db, commit=True)
    created: list[str] = []
    try:
        await _task(db, task)
        await db.commit()
        app = create_app()
        hdr = {"authorization": f"Bearer {security.create_access_token(u.id)}"}
        raw = _SPHERE.read_bytes()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test", timeout=120) as c:
            up = await c.post(f"{P}/sessions/{s.id}/reports", headers=hdr,
                              files={"file": ("Test_001_report.html", raw, "text/html")},
                              data={"project": task, "dev_rev": "dv1"})
            one = await c.post(f"{P}/reports/intake", headers=hdr,
                               files={"file": ("Test_001_report.html", raw, "text/html")},
                               data={"session_id": s.id, "project": task, "dev_rev": "dv2"})
        assert up.status_code == 201, up.text[:300]
        assert one.status_code == 201, one.text[:300]
        a, b = up.json()["data"], one.json()["data"]
        created += [a["id"], b["report_id"]]
        assert a["task_links"]["already"] == 1, a["task_links"]   # 과제명 그대로 — 인제스트 때 잇기가 이미 같은 판에 이었다
        assert b["task_links"]["already"] == 1, b["task_links"]
        assert {x["code"] for x in await onto.history(db, task)} == {"dv1", "dv2"}
    finally:
        await _drop(db, u, s, keys=[task])


# ── ③ 받기 뒤 — 받은 것을 굳힌 뒤 전부를 보고, 수를 실행 기록에 남긴다 ─────────────

@pytest.fixture()
def hub_on(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_url", "http://hub.test/api")
    monkeypatch.setattr(settings, "sp_core_token", "tok")
    monkeypatch.setattr(settings, "sp_core_sync_sec", 600)
    return settings


def _fake_receive(task: str, code: str):
    """허브에서 과제 하나를 받은 것처럼 — 층 1 의 실제 수신부(`save_rows`)로 쓰고 sync_all 의 결과 꼴을 돌려준다."""
    async def fake(sdb, client, *, types=None, full=False, allow_shrink=False):
        rows = await sp_core.save_rows(sdb, onto.TYPE_TASK, [{"key": task, "label": f"과제 {task}", "status": "active",
                                                               "updated_at": "T1", "properties": {"task_code": code}}])
        return {"ok": True, "result": "ok", "revision": "r-src09", "types": {onto.TYPE_TASK: rows},
                "relations": {}, "skipped": [], "problems": [], "notes": [], "error": None}
    return fake


async def test_a_receive_links_what_now_resolves_and_records_the_counts(db, hub_on, monkeypatch):
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    u, s = await _owner(db, commit=True)
    r = await _rep(db, s, project=code, code="dv1", commit=True)     # 과제코드로 적힌 리포트 — 아직 과제가 없다
    calls: list = []
    real = onto.auto_link_tasks

    async def mine_only(sdb, *, report_ids=None):
        calls.append(report_ids)
        return await real(sdb, report_ids=[r.id])        # 공유 DB 의 남의 리포트는 건드리지 않는다

    monkeypatch.setattr(plm_sync, "sync_all", _fake_receive(task, code))
    monkeypatch.setattr(onto, "auto_link_tasks", mine_only)
    runs: list[int] = []
    try:
        got = await plm_sync.sync_once(client=object())
        runs.append(got["run_id"])
        assert got["result"] == "ok", got
        assert calls == [None], "받기 뒤에는 리포트 전부를 봐야 한다(과제 · 별칭이 바뀌면 어느 리포트든 풀린다)"
        links = got["task_links"]
        assert links["linked"] == 1 and {"candidates", "unmatched", "reports_without_a_name"} <= set(links), links
        assert await _linked(db, r.id) == [f"{task}@dv1"]
        run = (await db.execute(select(OntoSyncRun).where(OntoSyncRun.id == got["run_id"])
                                .execution_options(populate_existing=True))).scalar_one()
        assert run.counts["task_links"] == links, "받기 결과 줄(실행 기록)에 수가 없다"

        again = await plm_sync.sync_once(client=object())
        runs.append(again["run_id"])
        assert (again["task_links"]["linked"], again["task_links"]["already"]) == (0, 1), again["task_links"]
    finally:
        await _drop(db, u, s, keys=[task, code], runs=runs)


async def test_a_broken_link_after_a_receive_keeps_what_was_received(db, hub_on, monkeypatch):
    async def boom(_db, **_kw):
        raise RuntimeError("잇기 결함")

    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    u, s = await _owner(db, commit=True)
    monkeypatch.setattr(plm_sync, "sync_all", _fake_receive(task, code))
    monkeypatch.setattr(onto, "auto_link_tasks", boom)
    runs: list[int] = []
    try:
        got = await plm_sync.sync_once(client=object())
        runs.append(got["run_id"])
        assert got["result"] == "needs_check", got
        assert any("과제 잇기 실패" in p and "잇기 결함" in p for p in got["problems"]), got["problems"]
        async with SessionLocal() as fresh:
            row = (await fresh.execute(select(OntoObject).where(OntoObject.type_slug == onto.TYPE_TASK,
                                                                OntoObject.key == task))).scalar_one_or_none()
        assert row is not None, "잇기가 깨졌다고 받은 것까지 되돌렸다"
        run = (await db.execute(select(OntoSyncRun).where(OntoSyncRun.id == got["run_id"])
                                .execution_options(populate_existing=True))).scalar_one()
        assert run.result == "needs_check" and "잇기 결함" in run.counts["task_links"]["error"]
    finally:
        await _drop(db, u, s, keys=[task, code], runs=runs)


# ── ④ 받기 뒤 수는 관리자에게만 ──────────────────────────────────────────────

async def test_the_fleet_wide_counts_reach_only_a_system_admin(db):
    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    u, s = await _owner(db, commit=True)
    a, sa = await _owner(db, admin=True, commit=True)
    run = OntoSyncRun(mode="normal", trigger="test", result="ok", counts={
        "types": {}, "task_links": {"scope": "all", "linked": 2, "candidates": 3, "unmatched": 4,
                                    "reports_without_a_name": 5}})
    db.add(run)
    await db.commit()
    try:
        app = create_app()
        app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as c:
            plain = await c.get(f"{P}/ontology/sync",
                                headers={"authorization": f"Bearer {security.create_access_token(u.id)}"})
            boss = await c.get(f"{P}/ontology/sync",
                               headers={"authorization": f"Bearer {security.create_access_token(a.id)}"})
        assert plain.status_code == 200 and boss.status_code == 200
        p, b = plain.json()["data"]["last_run"], boss.json()["data"]["last_run"]
        assert p["id"] == b["id"] == run.id
        assert "task_links" not in p["counts"], "리포트 전부를 센 수가 일반 사용자에게 샜다"
        assert b["counts"]["task_links"]["linked"] == 2
    finally:
        await db.execute(delete(OntoSyncRun).where(OntoSyncRun.id == run.id))
        await db.commit()
        await _drop(db, a, sa)
        await _drop(db, u, s)
