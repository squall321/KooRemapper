# 인클루드·설정 파일이 저장·추적되나 — 조용히 깨지는 셋을 막는다
"""*INCLUDE 하위 경로 보존 · 인클루드 정합성 관문 · 설정 파일 등록.

왜 이 셋이 한 파일에 있나 — 실측으로 확인한 하나의 사고 사슬이다(context-notes 2026-09-23):

  1. KooRemapper 는 `*INCLUDE` 를 **읽지 않는다**(있으나 없으나 노드 수가 같다).
  2. 그런데 출력 덱에는 그 `*INCLUDE` 줄을 **보존한다**(indent 산출물 4-5행에서 확인).
  3. 업로드가 경로를 눕히면 `sub/part.k` 가 `part.k` 가 된다.

  → 셋이 겹치면: op 은 성공하고, 산출물은 존재하지 않는 `sub/part.k` 를 가리키며,
    LS-DYNA 는 인클루드를 따라가므로 거기서 깨진다. **도구는 끝까지 아무 말도 하지 않는다.**

실 DB(dev postgres)에 붙는다(conftest 참조). 각 시험은 자기 뒷정리를 한다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import pytest_asyncio
import ulid
from sqlalchemy import delete

from app.models import Session, SessionFile, User
from app.modules.sessions import services as svc
from app.shared import security, storage

# ⚠ 전역 asyncio 마크를 쓰지 않는다 — 이 파일은 동기(경로 정제)와 비동기(DB) 시험이 섞여 있어
# 전역으로 걸면 동기 시험마다 경고가 난다. DB 시험에만 개별로 붙인다.
_aio = pytest.mark.asyncio(loop_scope="session")


# ── 경로 보존·트래버설 (DB 없이) ────────────────────────────────────────────
def test_subdirectories_survive_upload_naming():
    """`sub/part.k` 가 눕혀지면 산출물의 `*INCLUDE sub/part.k` 가 가리킬 곳이 없어진다."""
    assert storage.safe_relpath("sub/part.k") == "sub/part.k"
    assert storage.safe_relpath("sub\\part.k") == "sub/part.k"   # 윈도 클라이언트
    assert storage.safe_relpath("deep/a/b/part.k") == "deep/a/b/part.k"


@pytest.mark.parametrize("hostile,expect_no", [
    ("../../etc/passwd", ".."),
    ("/etc/passwd", "/etc"),
    ("a/../../b.k", ".."),
    ("C:\\Windows\\system32\\x.k", ":"),
])
def test_traversal_never_escapes(hostile, expect_no):
    """`..`·절대경로·드라이브 문자는 남으면 안 된다 — 남으면 세션 밖에 쓴다."""
    out = storage.safe_relpath(hostile)
    assert expect_no not in out, f"{hostile!r} → {out!r}"
    assert not out.startswith("/")


def test_write_guard_rejects_escape(tmp_path):
    """이름 정제를 뚫더라도 쓰기 직전에 한 번 더 막는다(방어 두 겹)."""
    assert storage.resolve_within(tmp_path, "sub/ok.k").is_relative_to(tmp_path)
    with pytest.raises(ValueError):
        storage.resolve_within(tmp_path, "../escape.k")


def test_long_names_keep_their_extension():
    """꼬리를 그냥 자르면 `.k` 가 날아가 파일 형식 판정이 달라진다."""
    out = storage.safe_relpath("x" * 300 + ".k")
    assert out.endswith(".k") and len(out) <= 255


# ── DB 를 쓰는 시험 ────────────────────────────────────────────────────────
async def _mk_session(db):
    u = User(email=f"inc_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="inc-test",
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _cleanup(db, u, s):
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    d = storage.session_abs_dir(u.id, s.id)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
async def sess(db):
    u, s = await _mk_session(db)
    try:
        yield u, s
    finally:
        await _cleanup(db, u, s)


_MASTER = (b"*KEYWORD\n*INCLUDE\nsub/part.k\n"
           b"*NODE\n       1     0.0     0.0     0.0\n*END\n")
_PART = b"*KEYWORD\n*NODE\n       2    10.0     0.0     0.0\n*END\n"


@_aio
async def test_uploaded_subpath_lands_on_disk_and_in_db(db, sess):
    """올린 그대로의 경로에 저장돼야 산출물의 `*INCLUDE` 가 가리킬 곳이 생긴다."""
    _u, s = sess
    row = await svc.add_uploaded_file(db, s, filename="sub/part.k", raw=_PART)
    assert row.filename == "sub/part.k"
    assert storage.abs_path(row.rel_path).is_file()
    assert storage.abs_path(row.rel_path).parent.name == "sub"


@_aio
async def test_dedup_counts_inside_the_subdirectory(db, sess):
    """같은 이름을 또 올리면 그 하위 폴더 안에서 비켜 간다(다른 폴더와 안 섞인다)."""
    _u, s = sess
    a = await svc.add_uploaded_file(db, s, filename="sub/part.k", raw=_PART)
    b = await svc.add_uploaded_file(db, s, filename="sub/part.k", raw=_PART)
    assert a.filename == "sub/part.k"
    assert b.filename == "sub/part_1.k", b.filename


@_aio
async def test_missing_include_is_reported(db, sess):
    """마스터만 올리면 — op 은 성공할 것이므로 — 여기서 말해 주지 않으면 아무도 모른다."""
    _u, s = sess
    await svc.add_uploaded_file(db, s, filename="master.k", raw=_MASTER)
    st = await svc.include_status(db, s.id)
    assert "master.k" in st, st
    assert st["master.k"]["missing"] == ["sub/part.k"]


@_aio
async def test_satisfied_include_is_not_reported(db, sess):
    """인클루드를 경로째로 올리면 조용해야 한다 — 거짓 경보는 경고를 무시하게 만든다."""
    _u, s = sess
    await svc.add_uploaded_file(db, s, filename="master.k", raw=_MASTER)
    await svc.add_uploaded_file(db, s, filename="sub/part.k", raw=_PART)
    assert await svc.include_status(db, s.id) == {}


@_aio
async def test_flattened_legacy_upload_still_counts_as_satisfied(db, sess):
    """옛 세션은 평탄화돼 있다 — 이름만 맞아도 만족으로 본다(거짓 경보를 내지 않는다)."""
    _u, s = sess
    await svc.add_uploaded_file(db, s, filename="master.k", raw=_MASTER)
    await svc.add_uploaded_file(db, s, filename="part.k", raw=_PART)
    assert await svc.include_status(db, s.id) == {}


# ── 실행 직전 관문 (API 수준) ──────────────────────────────────────────────
# 여기서 막지 않으면 아무도 못 막는다 — op 은 인클루드를 읽지 않아 성공하고,
# 깨진 산출물은 LS-DYNA 에 넣고 나서야 드러난다.
@pytest_asyncio.fixture(loop_scope="session")
async def api(db):
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    transport = ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(api, db):
    """세션 하나를 가진 사용자를 만들고 (토큰, session_id) 를 준다."""
    from app.config import settings
    settings.ratelimit_enabled = False
    email = f"incapi_{ulid.new().str}@kooremapper.test"
    u = User(email=email, password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    r = await api.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
    tok = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = (await api.post("/api/v1/sessions", json={"name": "inc-api"}, headers=h)).json()["data"]["id"]
    return h, sid, u


@_aio
async def test_run_is_blocked_when_an_include_is_missing(api, db):
    h, sid, u = await _login(api, db)
    try:
        await api.post(f"/api/v1/sessions/{sid}/files",
                       files={"files": ("master.k", _MASTER, "text/plain")}, headers=h)

        st = (await api.get(f"/api/v1/sessions/{sid}/includes", headers=h)).json()["data"]
        assert st["ok"] is False and "master.k" in st["missing_by_file"]

        # unfold 는 bent_mesh 가 file 타입 파라미터라 관문의 '쓰이는 파일' 경로를 그대로 탄다
        payload = {"operation": "unfold", "args": {"bent_mesh": "master.k", "output_flat": "flat"}}
        r = await api.post(f"/api/v1/sessions/{sid}/jobs", json=payload, headers=h)
        assert r.status_code == 422, r.text
        assert "*INCLUDE" in r.text and "sub/part.k" in r.text

        # 탈출구 — 인클루드를 클러스터에 따로 두는 운용을 막아서는 안 된다.
        r2 = await api.post(f"/api/v1/sessions/{sid}/jobs",
                            json={**payload, "allow_missing_includes": True}, headers=h)
        assert r2.status_code == 201, r2.text
    finally:
        await _cleanup_user(db, u, sid)


@_aio
async def test_run_passes_once_the_include_is_uploaded(api, db):
    h, sid, u = await _login(api, db)
    try:
        await api.post(f"/api/v1/sessions/{sid}/files",
                       files={"files": ("master.k", _MASTER, "text/plain")}, headers=h)
        await api.post(f"/api/v1/sessions/{sid}/files",
                       files={"files": ("sub/part.k", _PART, "text/plain")}, headers=h)

        st = (await api.get(f"/api/v1/sessions/{sid}/includes", headers=h)).json()["data"]
        assert st["ok"] is True, st

        r = await api.post(f"/api/v1/sessions/{sid}/jobs",
                           json={"operation": "unfold",
                                 "args": {"bent_mesh": "master.k", "output_flat": "flat"}}, headers=h)
        assert r.status_code == 201, r.text
    finally:
        await _cleanup_user(db, u, sid)


async def _cleanup_user(db, u, sid):
    from app.models import Job
    await db.execute(delete(Job).where(Job.session_id == sid))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    d = storage.session_abs_dir(u.id, sid)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ── ① 플랫폼이 만든 설정 파일이 파일 목록에 뜨나 ───────────────────────────
@_aio
async def test_generated_config_is_registered_and_not_double_counted(db, sess):
    """`config.yaml` 은 디스크에만 있고 목록·다운로드에는 **영영 안 보였다.**

    원인은 순서였다 — `build_command` 가 먼저 쓰고 산출물 스냅샷은 그 뒤라, '새로 생긴 파일'
    판정에서 빠졌다. 그래서 워커가 **명시적으로** 등록한다. kind 는 output 이 아니라 generated 다
    (바이너리의 산출물이 아니라 플랫폼이 만든 입력이다).
    """
    from sqlalchemy import select

    from app.models import SessionFile as SF
    from app.worker.runner_loop import _register_file

    _u, s = sess
    work = storage.session_abs_dir(_u.id, s.id)
    cfg = work / "config.yaml"
    cfg.write_text("base_model: master.k\noutput: out\n", encoding="utf-8")

    fid = await _register_file(db, s, "config.yaml", cfg, kind="generated",
                               job_id="01JOBFAKE0000000000000000", inspect=False)
    await db.commit()

    row = (await db.execute(select(SF).where(SF.id == fid))).scalar_one()
    assert row.kind == "generated", row.kind
    assert row.filename == "config.yaml"
    assert row.origin_job_id == "01JOBFAKE0000000000000000"
    assert row.sha256 and row.size_bytes == cfg.stat().st_size
    assert storage.abs_path(row.rel_path).is_file()          # 내려받을 수 있다
    # K파일이 아니므로 `info` 를 돌리지 않는다(돌리면 오류 메타만 남는다)
    assert row.meta is None

    # 같은 이름을 산출물로 다시 등록해도 행이 하나여야 한다(중복 등록 금지)
    again = await _register_file(db, s, "config.yaml", cfg, kind="output",
                                 job_id="01JOBFAKE0000000000000000")
    await db.commit()
    assert again == fid
    n = len((await db.execute(select(SF).where(SF.session_id == s.id))).scalars().all())
    assert n == 1, f"중복 등록됐다({n}행)"
