"""기준정보 주기 수신의 배선 — **꺼져 있는 것이 기본**이고, 꺼짐이 조용한 성공이 아니다.

허브가 아직 없다(계획서 §7 ②). 그래서 기본이 꺼짐이고, 꺼져 있을 때 **아무것도 부르지
않는다.** 없는 곳을 주기적으로 두드리면 로그가 실패로 가득 차고 **진짜 실패가 그 속에
묻힌다** — 그 상태가 가장 비싸다.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, func, select

from app.models import OntoCatalog, OntoObject, OntoRelation, OntoSyncRun, OntoSyncState, OntoType
from app.runner.sp_core import SpCoreClient
from app.worker import plm_sync

pytestmark = pytest.mark.asyncio(loop_scope="session")

_RUNNER = Path(__file__).resolve().parents[1] / "app" / "worker" / "runner_loop.py"


@pytest.fixture()
def on(monkeypatch):
    """설정 셋을 채워 켜 둔다."""
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_url", "http://hub.test/api")
    monkeypatch.setattr(settings, "sp_core_token", "tok")
    monkeypatch.setattr(settings, "sp_core_sync_sec", 600)
    # 이 픽스처의 시험들은 가짜 허브가 공개한 **그 타입**을 받기를 기대한다(커스텀 slug).
    # KR-06 기본(셋)으로 좁히면 그 slug 가 빠지므로, 여기서는 전부(None)로 둔다.
    monkeypatch.setattr(settings, "sp_core_types", "")
    return settings


async def _cat_mark(db) -> int:
    return int((await db.execute(select(func.coalesce(func.max(OntoCatalog.id), 0)))).scalar_one())


async def _forget(db, slug: str, got: dict | None, mark: int) -> None:
    """★`sync_once` 는 정말 커밋한다 — 실행 기록 · 카탈로그 줄 · 허브 타입 정의까지 치운다. 안 치우면 다음 실제 받기가
    시험 카탈로그(`r1`)와 견줘 「정의 판이 바뀌었다」 로 전부 처음부터 받고, 관리 화면의 최근 실행에 시험이 섞인다.
    (시험 카탈로그에 없는 허브 정의는 받을 때 지워진다 — 다음 실제 받기가 카탈로그로 다시 채운다.)"""
    if got and got.get("run_id"):
        await db.execute(delete(OntoSyncRun).where(OntoSyncRun.id == got["run_id"]))
    await db.execute(delete(OntoCatalog).where(OntoCatalog.id > mark, OntoCatalog.revision == "r1"))
    await db.execute(delete(OntoType).where(OntoType.slug == slug, OntoType.source == "hub"))
    await db.execute(delete(OntoRelation).where(OntoRelation.src_type == slug))
    await db.execute(delete(OntoObject).where(OntoObject.type_slug == slug))
    await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug == slug))
    await db.commit()


def _one_task_hub(slug: str):
    cat = {"system": "허브", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "과제", "count": 1, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": []}]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/core"):
            return httpx.Response(200, json=cat)
        return httpx.Response(200, json={"items": [
            {"key": "PRJ-1", "label": "과제 하나", "status": "active",
             "updated_at": "T1", "deleted": False}], "as_of": "T1", "next": None})

    return SpCoreClient("http://hub.test/api", "tok",
                        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_it_is_off_by_default():
    """허브 주소를 코드에 박지 않았으므로 **기본은 꺼짐**이다.

    ★2026-10-14 에 간격의 기본값이 0 → 3600 으로 바뀌었다. 꺼짐을 간격으로 만들지 않고
    **주소·토큰의 부재**로 만든다 — 주소·토큰을 넣은 사람이 간격까지 또 설정해야 하면
    그 둘째를 잊고, 그러면 "설정했는데 안 받는다" 가 된다. 간격 0 은 기능을 켜 둔 채
    주기 수신만 끄는 뜻이다(`test_clearing_the_interval_stops_only_the_scheduler`).
    """
    from app.config import settings
    assert settings.sp_core_url == "" and settings.sp_core_token == ""
    assert plm_sync.enabled() is False, "주소·토큰이 없으면 안 돌아야 한다"
    assert settings.sp_core_sync_sec > 0, "간격은 쓸 수 있는 기본값을 갖는다"


@pytest.mark.parametrize("blank", ["sp_core_url", "sp_core_token", "sp_core_sync_sec"])
async def test_one_blank_setting_turns_it_off(monkeypatch, on, blank):
    """셋 중 **하나라도** 비면 꺼진 것이다 — 반쪽으로 돌면 "받았는데 비어 있다" 가 된다."""
    monkeypatch.setattr(on, blank, 0 if blank.endswith("_sec") else "")
    assert plm_sync.enabled() is False


async def test_when_enabled_it_says_so(on):
    assert plm_sync.enabled() is True


async def test_being_off_is_an_explicit_failure_not_a_quiet_success():
    assert plm_sync.enabled() is False
    got = await plm_sync.sync_once()
    assert got["ok"] is False and got["error"] == "disabled"


async def test_the_type_list_comes_from_settings():
    """공개 35종을 다 받지 않는다 — 기본은 쓰는 것 셋, 설정으로 고친다(KR-06). 비우면 전부(None)."""
    from app.config import settings
    assert plm_sync.wanted_types() == ["plm_project", "plm_task", "plm_model"]
    old = settings.sp_core_types
    settings.sp_core_types = ""
    try:
        assert plm_sync.wanted_types() is None
    finally:
        settings.sp_core_types = old


async def test_sync_once_writes_and_commits(db, on):
    """받은 것은 **커밋한다** — 성공한 타입은 남아야 한다."""
    slug = f"t_{ulid.new().str[:12].lower()}"
    mark, got = await _cat_mark(db), None
    try:
        got = await plm_sync.sync_once(client=_one_task_hub(slug))
        assert got["ok"] and got["result"] == "ok", got
        # **다른 세션**에서 보인다 = 정말 커밋됐다
        rows = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == slug))).scalars().all()
        assert [r.key for r in rows] == ["PRJ-1"]
    finally:
        await _forget(db, slug, got, mark)


async def test_every_run_leaves_a_record_with_one_of_three_results(db, on):
    """규칙 16 — 결과는 셋(정상 · 확인 필요 · 실패)이고 실행마다 기록이 남는다(관리 화면의 「최근 실행」)."""
    slug = f"t_{ulid.new().str[:12].lower()}"
    mark, got = await _cat_mark(db), None
    try:
        got = await plm_sync.sync_once(client=_one_task_hub(slug), trigger="admin", requested_by="a@x")
        run = (await db.execute(select(OntoSyncRun).where(OntoSyncRun.id == got["run_id"])
                                .execution_options(populate_existing=True))).scalar_one()
        assert (run.result, run.trigger, run.requested_by, run.mode) == ("ok", "admin", "a@x", "normal")
        assert run.finished_at is not None and run.revision == "r1"
        assert run.counts["types"][slug]["rows"] == 1, run.counts
        assert "reflected" in run.counts, "층 2 반영 결과도 기록에 남는다"
    finally:
        await _forget(db, slug, got, mark)


async def test_a_run_does_not_start_while_another_holds_the_lock(db, on):
    """규칙 14 — 워커 주기와 관리자 버튼은 다른 프로세스다. 겹치면 기준 시각이 엇갈린다 — 시작하지 않고 「받는 중」."""
    slug = f"t_{ulid.new().str[:12].lower()}"
    from app.database import SessionLocal
    async with SessionLocal() as holder:
        assert await plm_sync.try_lock(holder)
        got = await plm_sync.sync_once(client=_one_task_hub(slug))
        await holder.rollback()          # 트랜잭션 잠금 — 끝나면 저절로 풀린다
    assert got["result"] == "busy" and "run_id" not in got, got
    rows = (await db.execute(select(OntoObject).where(OntoObject.type_slug == slug))).scalars().all()
    assert rows == [], "잠겨 있는데 받았다"


async def test_a_broken_reflect_keeps_what_was_received_and_says_so(db, on, monkeypatch):
    """층 2 결함 하나가 받기(층 1)를 영영 막으면 안 된다 — 받은 것은 남기고 「확인 필요」 로 알린다."""
    from app.modules.ontology import services as onto

    async def boom(_db):
        raise RuntimeError("반영 결함")

    monkeypatch.setattr(onto, "reflect_after_sync", boom)
    slug = f"t_{ulid.new().str[:12].lower()}"
    mark, got = await _cat_mark(db), None
    try:
        got = await plm_sync.sync_once(client=_one_task_hub(slug))
        assert got["result"] == "needs_check", got
        assert any("층 2 반영 실패" in p for p in got["problems"]), got["problems"]
        rows = (await db.execute(select(OntoObject).where(OntoObject.type_slug == slug))).scalars().all()
        assert [r.key for r in rows] == ["PRJ-1"], "반영이 깨졌다고 받은 것까지 되돌렸다"
    finally:
        await _forget(db, slug, got, mark)


async def test_the_weekly_full_comes_due(db, monkeypatch):
    """주 1회 처음부터(10-30 사용자 「권장」) — 마지막으로 **끝까지 돈** 처음부터 받기에서 따진다. 0 이면 끈다.

    살아 있는 dev DB 를 쓰므로 기록을 **미래**에 하나 두고 그 뒤로 시계를 돌린다 — 다른 기록이 있어도 최댓값은 그것이다."""
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_full_every_days", 7)
    at = datetime.now(timezone.utc) + timedelta(days=1)
    run = OntoSyncRun(mode="full", trigger="test", result="needs_check", started_at=at, finished_at=at)
    db.add(run)
    await db.commit()
    try:
        assert await plm_sync.full_due(at + timedelta(days=6)) is False
        assert await plm_sync.full_due(at + timedelta(days=7, minutes=1)) is True
        monkeypatch.setattr(settings, "sp_core_full_every_days", 0)
        assert await plm_sync.full_due(at + timedelta(days=30)) is False, "0 이면 끈다"
    finally:
        await db.execute(delete(OntoSyncRun).where(OntoSyncRun.id == run.id))
        await db.commit()


# ── 배선이 지워지지 않게 ───────────────────────────────────────────────────

async def test_the_worker_still_calls_it():
    """한 줄짜리 배선이라 조용히 사라질 수 있다 — 사라지면 수신이 **영원히 안 돈다.**"""
    text = _RUNNER.read_text(encoding="utf-8")
    assert "plm_sync.enabled()" in text, "게이트가 없다"
    assert "plm_sync.sync_once(full=await plm_sync.full_due())" in text, "호출이 없다(주 1회 처음부터 포함)"
    assert "max(60, settings.sp_core_sync_sec)" in text, "간격 하한이 없다 — 1초로 두드릴 수 있다"


# ── S1-7 — 부서는 **거울이 아니라 선의 끝점**이다 ──────────────────────────

async def test_a_relation_to_a_system_type_never_creates_an_object_row(db, on):
    """★부서를 `onto_objects` 에 복제하면 **두 벌이 되고 반드시 갈린다**(SP §3.6).

    DynaForge 의 소속 정본은 **포탈**이다 — 게이트웨이가 HMAC 로 서명한
    `X-Heax-User-Affiliation` 을 `shared/affiliation.py` 가 검증하고
    `shared/visibility.py` 가 판정한다. 그래서 받은 선의 **먼 끝은 행을 만들지 않는다**
    (SP 의 `object_links` 와 같은 자리 — 한쪽 끝이 `objects` 밖이다).
    """
    slug = f"t_{ulid.new().str[:12].lower()}"
    cat = {"system": "허브", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "과제", "count": 1, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": ["dept_in_charge"]}]}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/core"):
            return httpx.Response(200, json=cat)
        if path.endswith("/relations"):
            return httpx.Response(200, json={"items": [
                {"src": "PRJ-1", "relation": "dept_in_charge",
                 "dst": "CAEG", "dst_type": "workspace"}], "as_of": "T1", "next": None})
        return httpx.Response(200, json={"items": [
            {"key": "PRJ-1", "label": "과제 하나", "updated_at": "T1"}],
            "as_of": "T1", "next": None})

    client = SpCoreClient("http://hub.test/api", "tok",
                          client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    mark, got = await _cat_mark(db), None
    try:
        got = await plm_sync.sync_once(client=client)
        assert got["ok"], got
        edges = (await db.execute(select(OntoRelation).where(
            OntoRelation.src_type == slug))).scalars().all()
        assert len(edges) == 1 and edges[0].dst_key == "CAEG", "선이 안 들어왔다"
        assert edges[0].dst_type == "workspace"
        # ★행은 **없어야** 한다
        made = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == "workspace"))).scalars().all()
        assert made == [], f"부서를 행으로 복제했다: {[m.key for m in made]}"
    finally:
        await _forget(db, slug, got, mark)


async def test_sp_core_client_does_not_trust_proxy_env():
    """★core:read 토큰이 사내 프록시를 타지 않게 trust_env=False 다(KR-14)."""
    from app.runner.sp_core import SpCoreClient
    c = SpCoreClient("http://hub.test/api", "tok")
    h = c._http()
    try:
        assert getattr(h, "_trust_env", True) is False
    finally:
        await h.aclose()
