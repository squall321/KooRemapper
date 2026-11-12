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


@pytest.fixture(autouse=True)
def ontology_on(monkeypatch):
    """반입 뒤 잇기는 과제·개정 기능이 켜져 있을 때만 돈다(라우트와 같은 판정). 이 박스는 허브 설정이 없어 꺼져 있다 — 켠다."""
    from app.config import settings
    monkeypatch.setattr(settings, "ontology", "1")


def _tag() -> str:
    return ulid.new().str.lower()          # 통째로 — 앞자리는 시각이라 잘라 쓰면 1초 안에 겹친다(시험 격리)


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


async def test_someone_elses_confirm_does_not_freeze_my_machine_link(db):
    """검토 R5 — 판의 rev_source 는 판 하나에 하나라 여러 리포트가 나눠 쓴다. 남이 자기 리포트를 같은 판에 손으로 확정해도
    기계가 이은 내 리포트는 옮겨진다 — 사람 판인지는 **리포트마다**(선의 link_source) 가른다."""
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    try:
        _, s1 = await _owner(db)
        _, s2 = await _owner(db)
        mine = await _rep(db, s1, project=code, code="dv1")
        assert (await onto.link_from_eng_meta(db, mine))["ok"]                 # 기계 — 글자 그대로의 판
        theirs = await _rep(db, s2, project=code, code="dv1")
        assert (await onto.set_revision(db, theirs, task_key=code, code="dv1", decided_by="lee@x",
                                        source="manual"))["ok"]                  # 남이 같은 판에 손으로
        await _task(db, task, task_code=code)
        got = await onto.auto_link_tasks(db, report_ids=[mine.id, theirs.id])
        assert (got["linked"], got["kept_manual"]) == (1, 1), got
        assert await _linked(db, mine.id) == [f"{task}@dv1"], "남의 확정 때문에 내 기계 선이 옛 판에 굳었다"
        assert await _linked(db, theirs.id) == [f"{code}@dv1"], "사람이 확정한 리포트를 옮겼다"
    finally:
        await db.rollback()


async def test_a_machine_path_never_moves_or_restamps_a_link_a_person_made(db):
    """기계 경로(여기선 인제스트 때 잇기)는 사람이 이 리포트를 확정한 선을 옮기지 않고(`kept_manual`), 같은 판을 다시 지나가도
    선의 「사람이 이었다」 표시를 덮지 않는다."""
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        assert (await onto.set_revision(db, r, task_key=task, code="dv1", decided_by="kim@x", source="manual"))["ok"]
        assert (await onto.link_from_eng_meta(db, r))["ok"]                    # 같은 판 — 지나가기만
        edge = (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_key == r.id)
            .execution_options(populate_existing=True))).scalar_one()
        assert (edge.properties["link_source"], edge.properties["linked_by"]) == ("manual", "kim@x"), edge.properties
        r.eng_meta = {"project": task, "dev_revision": {"code": "dv2"}}        # 수동 메타가 다른 판을 말한다
        await db.flush()
        refused = await onto.link_from_eng_meta(db, r)
        assert refused["ok"] is False and refused["error"] == "kept_manual", refused
        assert await _linked(db, r.id) == [f"{task}@dv1"]
        assert (await onto.linked_revision(db, r))["source"] == "manual"
    finally:
        await db.rollback()


async def test_an_old_link_without_a_source_on_a_human_revision_is_kept(db):
    """누가 이었나를 적지 않던 때의 옛 선은 그 판이 사람 판이면 사람 선으로 본다(조심 쪽) — 기계가 옮기지 않는다."""
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    try:
        _, s = await _owner(db)
        r = await _rep(db, s, project=code, code="dv1")
        assert (await onto.set_revision(db, r, task_key=code, code="dv1", decided_by="kim@x", source="manual"))["ok"]
        edge = (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_key == r.id))).scalar_one()
        edge.properties = None                                                 # 옛 선 — 표시가 없다
        await db.flush()
        await _task(db, task, task_code=code)
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert (got["kept_manual"], got["linked"]) == (1, 0), got
        assert await _linked(db, r.id) == [f"{code}@dv1"]
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
        got = await onto.link_report(db, r)
        assert (got["scope"], got["reports"], got["linked"]) == ("reports", 1, 1), got
        async with SessionLocal() as fresh:                               # 다른 세션에서 보인다 = 굳었다
            assert await _linked(fresh, r.id) == [f"{task}@dv1"]
            assert await _linked(fresh, other.id) == [], "반입한 리포트만 봐야 한다"
        assert r.kind == "sphere", "부르는 쪽의 리포트 행이 만료되면 안 된다"
    finally:
        await _drop(db, u, s, keys=[task])


async def test_a_broken_link_report_keeps_the_report_and_says_why(db, monkeypatch):
    async def boom(_db, **_kw):
        raise RuntimeError("잇기 결함")

    monkeypatch.setattr(onto, "auto_link_tasks", boom)
    u, s = await _owner(db, commit=True)
    try:
        r = await _rep(db, s, project=f"AL-{_tag()}", code="dv1", commit=True)
        got = await onto.link_report(db, r)
        assert "잇기 결함" in got["error"], got
        assert r.kind == "sphere" and r.id, "실패 뒤에도 부르는 쪽이 리포트를 읽는다"
        async with SessionLocal() as fresh:
            assert await fresh.get(ImpactReport, r.id) is not None
    finally:
        await _drop(db, u, s)


async def test_with_the_feature_off_the_import_does_not_link(db, monkeypatch):
    """과제·개정 기능이 꺼져 있으면(KOORM_ONTOLOGY=0) 반입 뒤 잇기를 하지 않고 그렇게 말한다 — 라우트가 거절하는 것과 같은 판정."""
    from app.config import settings
    monkeypatch.setattr(settings, "ontology", "0")
    t = _tag()
    task = f"AL-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await db.commit()
        r = await _rep(db, s, project=task, code="dv1", commit=True)
        got = await onto.link_report(db, r)
        assert got["skipped"] == "off" and "KOORM_ONTOLOGY=0" in got["detail"], got
        assert await _linked(db, r.id) == [], "기능이 꺼져 있는데 이었다"
    finally:
        await _drop(db, u, s, keys=[task])


async def test_a_busy_lock_skips_the_link_and_says_so(db):
    u, s = await _owner(db, commit=True)
    try:
        r = await _rep(db, s, project=f"AL-{_tag()}", code="dv1", commit=True)
        async with SessionLocal() as holder:
            assert await plm_sync.try_lock(holder)            # 받기가 도는 중이다
            got = await onto.link_report(db, r)
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


async def test_a_busy_lock_after_a_receive_skips_the_link_and_logs_it(db, caplog):
    """받기를 커밋한 뒤 다시 잠금을 걸 때 다른 받기 · 일괄 적용이 쥐고 있으면 건너뛰고 — 로그에 한 줄 남긴다(예전엔 말없이 건너뛰었다)."""
    import logging
    async with SessionLocal() as holder:
        assert await plm_sync.try_lock(holder)
        with caplog.at_level(logging.WARNING, logger="koorm.worker"):
            got = await plm_sync._link_tasks(db)
        await holder.rollback()
    assert got["skipped"] == "busy", got
    assert any("plm task links skipped" in r.getMessage() for r in caplog.records), caplog.text


async def test_with_the_feature_off_a_receive_does_not_link(db, monkeypatch):
    """받기는 허브 설정만 보고 돈다(`plm_sync.enabled`). 과제·개정 기능을 끄면(KOORM_ONTOLOGY=0) 받기 뒤 자동 잇기도 하지 않고 그렇게
    말한다 — 반입 뒤 잇기 · 라우트와 같은 판정(재검토 11-12 — 예전엔 꺼도 리포트 전부를 이었고, 라우트는 409 라 끊지도 못했다)."""
    from app.config import settings
    monkeypatch.setattr(settings, "ontology", "0")
    called = []

    async def spy(_db, **kw):
        called.append(kw)
        return {"scope": "all", "linked": 0}

    async def yes(_db):
        return True

    monkeypatch.setattr(onto, "auto_link_tasks", spy)
    monkeypatch.setattr(plm_sync, "try_lock", yes)
    got = await plm_sync._link_tasks(db)
    await db.rollback()
    assert called == [], "기능이 꺼져 있는데 받기 뒤 자동 잇기를 불렀다"
    assert got["skipped"] == "off" and "KOORM_ONTOLOGY=0" in got["detail"], got


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
    run = OntoSyncRun(mode="normal", trigger="test", result="needs_check", counts={
        "types": {}, "task_links": {"scope": "all", "linked": 2, "candidates": 3, "unmatched": 4,
                                    "reports_without_a_name": 5},
        "reflected": {"renamed": 1, "revisions": 1, "reports": 7, "dropped": []}},
        problems=["과제 잇기 실패 — RuntimeError: 원문에 남의 리포트 01ABC"], error="exception: 원문")
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
        # 예외 원문(사유 줄 · 오류 글)과 층 2 가 옮긴 리포트 수도 관리자에게만 — 일반 사용자는 「문제가 있었다」(수)까지만
        assert (p["problems"], p["error"], p["problem_count"]) == ([], None, 1), p
        assert "reports" not in p["counts"]["reflected"] and p["counts"]["reflected"]["renamed"] == 1, p["counts"]
        assert (b["problems"][0].startswith("과제 잇기 실패"), b["error"], b["problem_count"]) == (True, "exception: 원문", 1)
        assert b["counts"]["reflected"]["reports"] == 7
    finally:
        await db.execute(delete(OntoSyncRun).where(OntoSyncRun.id == run.id))
        await db.commit()
        await _drop(db, a, sa)
        await _drop(db, u, s)


# ── ⑤ 사람이 끊은 것 — 기록이 이긴다(사용자 결정 11-11 「끊은 것을 기록해 자동이 건너뛴다」) ──────────────
# 끊기는 선을 지우지 않고 끊은 표시(deleted + 끊은 사람 · 때)로 남긴다. 기계 경로(받기 뒤 · 반입 뒤 자동 잇기 · 관리자 일괄 적용 ·
# 수동 메타 고침)는 그 리포트를 다시 잇지 않고 센다. 사람이 손으로 다시 잇거나 기록을 지우면 풀린다.

async def _tombstones(db, rid: str) -> list[OntoRelation]:
    return (await db.execute(select(OntoRelation).where(
        OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_type == onto.TYPE_REPORT,
        OntoRelation.src_key == rid, OntoRelation.deleted.is_(True))
        .execution_options(populate_existing=True))).scalars().all()


async def test_an_unlink_records_who_and_when_and_keeps_the_line_marked(db):
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        assert (await onto.auto_link_tasks(db, report_ids=[r.id]))["linked"] == 1
        got = await onto.unlink_revision(db, r, by="kim@x")
        assert got["ok"] and got["was"] == [f"{task}@dv1"] and got["unlinked_by"] == "kim@x", got
        marks = await _tombstones(db, r.id)
        assert [(m.dst_key, m.properties["unlinked_by"]) for m in marks] == [(f"{task}@dv1", "kim@x")], "끊은 선을 지웠다"
        assert marks[0].properties.get(onto.UNLINK_MARK), "끊은 때가 없다"
        assert await onto.linked_revision(db, r) is None and await _linked(db, r.id) == []
        assert [x["reports"] for x in await onto.history(db, task)] == [[]], "끊은 리포트가 개정 줄에 남았다"
        rec = (await onto.unlinked_reports(db, [r.id]))[r.id]
        assert (rec["by"], rec["was"]) == ("kim@x", [f"{task}@dv1"]) and rec["at"]
    finally:
        await db.rollback()


async def test_the_auto_link_and_the_admin_apply_skip_an_unlinked_report_and_the_preview_shows_it(db):
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        assert (await onto.auto_link_tasks(db, report_ids=[r.id]))["linked"] == 1
        assert (await onto.unlink_revision(db, r, by="kim@x"))["ok"]

        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert (got["skipped_unlinked"], got["linked"], got["already"]) == (1, 0, 0), got
        plan = await onto.plan_task_links(db, scope=ImpactReport.id.in_([r.id]))
        entry = plan["plan"][0]
        assert entry["verdict"] == "links" and entry["unlinked"] == [r.id], entry
        assert plan["counts"]["unlinked"] == 1, plan["counts"]
        done = await onto.apply_task_links(db, only=[task])
        assert (done["skipped_unlinked"], done["linked"]) == (1, 0), done
        assert await _linked(db, r.id) == [] and len(await _tombstones(db, r.id)) == 1, "일괄 적용이 사람의 끊음을 덮었다"
    finally:
        await db.rollback()


async def test_relinking_by_hand_clears_the_record(db):
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        assert (await onto.auto_link_tasks(db, report_ids=[r.id]))["linked"] == 1
        assert (await onto.unlink_revision(db, r, by="kim@x"))["ok"]
        # 기계는 막힌다 — 인제스트 때 잇기(수동 메타 글자 그대로)도
        refused = await onto.link_from_eng_meta(db, r)
        assert refused["ok"] is False and refused["error"] == "unlinked", refused
        # 사람이 손으로 같은 판에 다시 잇는다 — 기록이 지워지고, 되살린 선에 끊은 사람 · 때가 남지 않는다
        assert (await onto.set_revision(db, r, task_key=task, code="dv1", decided_by="kim@x", source="manual"))["ok"]
        assert await _tombstones(db, r.id) == [] and await onto.unlinked_reports(db, [r.id]) == {}
        live = (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == onto.REL_MEASURED, OntoRelation.src_key == r.id)
            .execution_options(populate_existing=True))).scalars().all()
        assert [(e.dst_key, e.deleted, (e.properties or {}).get(onto.UNLINK_MARK)) for e in live] == \
            [(f"{task}@dv1", False, None)], [(e.dst_key, e.deleted, e.properties) for e in live]
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert (got["skipped_unlinked"], got["already"]) == (0, 1), got
    finally:
        await db.rollback()


async def test_clearing_the_record_makes_the_report_eligible_again(db):
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        r = await _rep(db, s, project=task, code="dv1")
        assert (await onto.auto_link_tasks(db, report_ids=[r.id]))["linked"] == 1
        assert (await onto.unlink_revision(db, r, by="kim@x"))["ok"]
        cleared = await onto.clear_unlink(db, r)
        assert cleared["ok"] and cleared["was"] == [f"{task}@dv1"], cleared
        assert await _tombstones(db, r.id) == []
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert (got["linked"], got["skipped_unlinked"]) == (1, 0), got
        assert await _linked(db, r.id) == [f"{task}@dv1"]
        again = await onto.clear_unlink(db, r)
        assert again["ok"] is False and again["error"] == "not_unlinked", "없는 기록을 지운 척했다"
    finally:
        await db.rollback()


async def test_a_metadata_edit_does_not_relink_an_unlinked_report(db):
    """열린 점 2 — 수동 메타 고침(PATCH)은 인제스트 때 잇기를 다시 부른다. 끊은 리포트는 다시 잇지 않고 메타만 저장한다."""
    from app.modules.reports import services as rsvc
    t = _tag()
    task, other = f"AL-{t}", f"AL2-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await _task(db, other)
        await db.commit()
        r = await _rep(db, s, project=task, code="dv1", commit=True)
        assert (await onto.link_from_eng_meta(db, r))["ok"]
        await db.commit()
        assert (await onto.unlink_revision(db, r, by="kim@x"))["ok"]
        await db.commit()
        r = await rsvc.update_report_meta(db, r, dev_rev="pv1")
        assert r.eng_meta["dev_revision"]["code"] == "pv1", "메타 고침 자체는 저장된다"
        r = await rsvc.update_report_meta(db, r, project=other)
        assert r.eng_meta["project"] == other
        assert await _linked(db, r.id) == [], "메타 고침이 끊은 리포트를 다시 이었다"
        assert [m.dst_key for m in await _tombstones(db, r.id)] == [f"{task}@dv1"], "기록이 지워졌다"
    finally:
        await _drop(db, u, s, keys=[task, other])


async def test_a_metadata_edit_moves_only_a_machine_link_and_only_on_project_or_stage(db, monkeypatch):
    """검토 R3 — 수동 메타 고침은 과제 · 개발단계가 바뀔 때만 선을 보고, 그때도 **기계가 이은** 선만 따라간다. 사람이 손으로
    확정한 선은 그대로다. 설계안 · DOE 만 고치면 선을 아예 보지 않는다."""
    from app.modules.reports import services as rsvc
    t = _tag()
    task, other = f"AL-{t}", f"AL2-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await _task(db, other)
        await db.commit()
        human = await _rep(db, s, project=task, code="dv1", commit=True)
        assert (await onto.set_revision(db, human, task_key=task, code="pv1", decided_by="kim@x", source="manual"))["ok"]
        machine = await _rep(db, s, project=task, code="dv1", commit=True)
        assert (await onto.link_from_eng_meta(db, machine))["ok"]
        await db.commit()

        calls = []
        real = onto.link_from_eng_meta

        async def counted(sdb, rep):
            calls.append(rep.id)
            return await real(sdb, rep)

        monkeypatch.setattr(onto, "link_from_eng_meta", counted)
        human = await rsvc.update_report_meta(db, human, variation="A", doe="S1:c3")
        assert calls == [], "설계안 · DOE 만 고쳤는데 선을 다시 봤다"
        assert await _linked(db, human.id) == [f"{task}@pv1"]
        human = await rsvc.update_report_meta(db, human, project=other)
        assert await _linked(db, human.id) == [f"{task}@pv1"], "메타 고침이 사람이 확정한 판에서 리포트를 옮겼다"
        machine = await rsvc.update_report_meta(db, machine, project=other)
        assert await _linked(db, machine.id) == [f"{other}@dv1"], "기계가 이은 선이 바뀐 과제를 따라가지 않았다"
    finally:
        await _drop(db, u, s, keys=[task, other])


async def test_a_link_that_breaks_in_the_database_never_drops_the_metadata_save(db, monkeypatch):
    """인제스트 때 잇기(`_link_revision`)가 DB 쪽에서 깨져도(세션이 되감김 대기가 되는 오류) 메타 저장은 굳는다 — 잇기만 저장점에서
    되감긴다(재검토 11-12 rr1 — 예전엔 예외를 삼키고도 부르는 쪽의 커밋이 PendingRollbackError 로 깨져 인제스트는 리포트째 잃었다)."""
    from sqlalchemy import text as sql

    from app.modules.reports import services as rsvc
    t = _tag()
    task, other = f"AL-{t}", f"AL2-{t}"
    u, s = await _owner(db, commit=True)
    try:
        r = await _rep(db, s, project=task, code="dv1", commit=True)

        async def broken(sdb, rep):
            await sdb.execute(sql("select 1/0"))           # 바깥 트랜잭션에서 나면 세션째 되감김 대기가 되는 DB 오류
            return {"ok": True}

        monkeypatch.setattr(onto, "link_from_eng_meta", broken)
        r = await rsvc.update_report_meta(db, r, project=other)
        async with SessionLocal() as f:
            saved = await f.get(ImpactReport, r.id)
            assert (saved.eng_meta or {}).get("project") == other, f"잇기가 깨져 메타 저장까지 잃었다: {saved.eng_meta}"
    finally:
        await _drop(db, u, s, keys=[task, other])


async def test_a_receive_leaves_an_unlinked_report_unlinked_and_counts_it(db, hub_on, monkeypatch):
    t = _tag()
    task, code = f"AL-{t}", f"ALC-{t}"
    u, s = await _owner(db, commit=True)
    r = await _rep(db, s, project=code, code="dv1", commit=True)
    real = onto.auto_link_tasks

    async def mine_only(sdb, *, report_ids=None):
        assert report_ids is None
        return await real(sdb, report_ids=[r.id])

    monkeypatch.setattr(plm_sync, "sync_all", _fake_receive(task, code))
    monkeypatch.setattr(onto, "auto_link_tasks", mine_only)
    runs: list[int] = []
    try:
        first = await plm_sync.sync_once(client=object())
        runs.append(first["run_id"])
        assert first["task_links"]["linked"] == 1, first["task_links"]
        assert (await onto.unlink_revision(db, r, by="kim@x"))["ok"]       # 사람이 끊는다
        await db.commit()
        second = await plm_sync.sync_once(client=object())
        runs.append(second["run_id"])
        links = second["task_links"]
        assert (links["skipped_unlinked"], links["linked"]) == (1, 0), links
        assert second["result"] == "ok", "끊은 리포트를 건너뛴 것은 문제가 아니다"
        assert await _linked(db, r.id) == [], "받기 뒤 자동 잇기가 사람이 끊은 리포트를 다시 이었다"
        run = (await db.execute(select(OntoSyncRun).where(OntoSyncRun.id == second["run_id"])
                                .execution_options(populate_existing=True))).scalar_one()
        assert run.counts["task_links"]["skipped_unlinked"] == 1
    finally:
        await _drop(db, u, s, keys=[task, code], runs=runs)


async def test_the_unlink_routes_record_show_and_clear(db):
    """REST — 끊기는 끊은 사람(로그인한 소유자)을 적고, 개정 보기가 기록을 보이고, 기록 지우기는 소유자만 · 지운 뒤 바로 한 번 잇는다."""
    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    t = _tag()
    task = f"AL-{t}"
    u, s = await _owner(db, commit=True)
    o, so = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await db.commit()
        r = await _rep(db, s, project=task, code="dv1", commit=True)
        assert (await onto.link_from_eng_meta(db, r))["ok"]
        await db.commit()
        app = create_app()
        app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
        mine = {"authorization": f"Bearer {security.create_access_token(u.id)}"}
        theirs = {"authorization": f"Bearer {security.create_access_token(o.id)}"}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as c:
            cut = await c.delete(f"{P}/reports/{r.id}/revision", headers=mine)
            view = await c.get(f"{P}/reports/{r.id}/revision", headers=mine)
            nope = await c.delete(f"{P}/reports/{r.id}/revision/unlinked", headers=theirs)
            clear = await c.delete(f"{P}/reports/{r.id}/revision/unlinked", headers=mine)
            after = await c.get(f"{P}/reports/{r.id}/revision", headers=mine)
            twice = await c.delete(f"{P}/reports/{r.id}/revision/unlinked", headers=mine)
        assert cut.status_code == 200 and cut.json()["data"]["unlinked_by"] == u.email, cut.text[:300]
        v = view.json()["data"]
        assert v["linked"] is None and v["unlinked"]["by"] == u.email and v["unlinked"]["was"] == [f"{task}@dv1"], v
        assert nope.status_code == 404, "남의 리포트의 기록을 지웠다"
        assert clear.status_code == 200, clear.text[:300]
        cd = clear.json()["data"]
        assert cd["was"] == [f"{task}@dv1"] and cd["task_links"]["linked"] == 1, cd
        a = after.json()["data"]
        assert a["unlinked"] is None and a["linked"]["key"] == f"{task}@dv1", a
        assert twice.status_code == 409, "없는 기록을 지운 척했다"
    finally:
        await _drop(db, o, so)
        await _drop(db, u, s, keys=[task])


# ── ⑥ 관리자 일괄 적용 — 자동 잇기와 같은 길 · 같은 기계 출처(검토 반영 11-11) ─────────────────────────
# 예전엔 manual 로 이어서 그새 끊은 기록을 지우고(R1) 주인이 확정한 판에서 옮기고(R4) 판에 관리자 이름을 찍었다.

async def test_the_admin_apply_respects_an_unlink_that_lands_after_it_read_its_plan(db, monkeypatch):
    """R1 — 적용이 계획을 읽은 직후 주인이 끊고 커밋해도, 적용은 그 끊음을 보고 건너뛴다(기록은 남는다)."""
    t = _tag()
    task = f"AL-{t}"
    u, s = await _owner(db, commit=True)
    try:
        await _task(db, task)
        await db.commit()
        r = await _rep(db, s, project=task, code="dv1", commit=True)
        assert (await onto.link_from_eng_meta(db, r))["ok"]
        await db.commit()
        real = onto.plan_task_links
        fired = []

        async def plan_then_owner_unlinks(sdb, **kw):
            got = await real(sdb, **kw)
            if not fired:
                fired.append(1)
                async with SessionLocal() as other:
                    rep = await other.get(ImpactReport, r.id)
                    assert (await onto.unlink_revision(other, rep, by="kim@x"))["ok"]
                    await other.commit()
            return got

        monkeypatch.setattr(onto, "plan_task_links", plan_then_owner_unlinks)
        done = await onto.apply_task_links(db, only=[task])
        await db.commit()
        monkeypatch.undo()
        assert fired and (done["skipped_unlinked"], done["linked"]) == (1, 0), done
        assert await _linked(db, r.id) == [] and [m.dst_key for m in await _tombstones(db, r.id)] == [f"{task}@dv1"], \
            "일괄 적용이 그새 끊은 기록을 지우고 다시 이었다"
    finally:
        await _drop(db, u, s, keys=[task])


async def test_the_admin_apply_keeps_an_owner_confirmed_report_and_stamps_no_admin(db):
    """R4 — 주인이 손으로 확정한 리포트는 일괄 적용이 옮기지 않고 `kept_manual` 로 센다. 이은 판에 관리자 이름이 없다."""
    t = _tag()
    task = f"AL-{t}"
    try:
        _, s = await _owner(db)
        await _task(db, task)
        mine = await _rep(db, s, project=task, code="dv1")
        assert (await onto.set_revision(db, mine, task_key=task, code="pv1", decided_by="kim@x", source="manual"))["ok"]
        other = await _rep(db, s, project=task, code="dv2")                     # 손대지 않은 리포트 — 이어져야 한다
        done = await onto.apply_task_links(db, only=[task])
        assert (done["kept_manual"], done["linked"], done["strings"]) == (1, 1, 1), done
        assert await _linked(db, mine.id) == [f"{task}@pv1"], "일괄 적용이 사람이 확정한 판에서 옮겼다"
        p = (await _rev(db, f"{task}@dv2")).properties
        assert p["rev_source"] == onto.SOURCE_RULE and "decided_by" not in p, p
        assert await _rev(db, f"{task}@dv1") is None, "옮기지도 않을 판을 만들었다"
    finally:
        await db.rollback()


async def test_the_admin_apply_is_refused_while_a_receive_holds_the_lock(db):
    """일괄 적용은 받기 뒤 자동 잇기와 같은 잠금을 건다 — 받는 중이면 409 busy(겹쳐 돌지 않는다)."""
    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    a, sa = await _owner(db, admin=True, commit=True)
    try:
        app = create_app()
        app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
        async with SessionLocal() as holder:
            assert await plm_sync.try_lock(holder)                              # 받는 중이다
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                         base_url="http://test") as c:
                r = await c.post(f"{P}/ontology/task-links/apply", json={"only": ["없는-문자열"]},
                                 headers={"authorization": f"Bearer {security.create_access_token(a.id)}"})
            await holder.rollback()
        assert r.status_code == 409 and "busy" in r.json()["message"], (r.status_code, r.text[:200])
    finally:
        await _drop(db, a, sa)
