"""Phase 10 endpoint tests — signup / login / password change, admin guard +
user management, system status/capabilities, and rate-limit headers.

The rate-limit test is pure (no DB). The rest hit the real ASGI app over an
in-process httpx transport against the live dev postgres; they skip themselves
if the DB is unreachable and clean up every row they create (email prefix
`phase10_…@test.local`).
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import ulid  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402
from app.shared import security  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")

API = "/api/v1"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── DB-free: rate-limit dependency raises 429 with Retry-After (RL-001) ──────
async def test_rate_limit_dependency_emits_429_with_headers():
    from fastapi import Depends, FastAPI

    from app.shared import ratelimit
    from app.shared.ratelimit import rate_limit

    ratelimit._hits.clear()
    prev = settings.ratelimit_enabled
    settings.ratelimit_enabled = True
    app = FastAPI()

    @app.get("/ping", dependencies=[Depends(rate_limit("unittest", 3))])
    async def ping():
        return {"ok": True}

    # Constant bearer token → constant rate-limit key regardless of client host.
    hdr = {"Authorization": "Bearer kr_unittest_constant_token"}
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as c:
            for _ in range(3):
                assert (await c.get("/ping", headers=hdr)).status_code == 200
            r = await c.get("/ping", headers=hdr)
            assert r.status_code == 429
            assert int(r.headers["Retry-After"]) >= 1
            assert r.headers["X-RateLimit-Limit"] == "3"
    finally:
        settings.ratelimit_enabled = prev
        ratelimit._hits.clear()


# ── DB-free: _client_key must not be spoofable via X-Forwarded-For ──────────
def _fake_request(headers: dict, peer: str | None):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


async def test_client_key_ignores_untrusted_xff():
    from app.shared.ratelimit import _client_key

    # Untrusted peer (direct hit) → XFF ignored, keyed on the real peer.
    k1 = _client_key(_fake_request({"x-forwarded-for": "9.9.9.9"}, "8.8.8.8"), None, "login")
    k2 = _client_key(_fake_request({"x-forwarded-for": "1.1.1.1"}, "8.8.8.8"), None, "login")
    assert k1 == k2 == "login:8.8.8.8", (k1, k2)

    # Trusted proxy peer (loopback) → use the LAST hop nginx appended, not the
    # client-controlled first hop. Two different spoofed first hops, same real
    # client → same bucket (bypass closed).
    t1 = _client_key(_fake_request({"x-forwarded-for": "9.9.9.9, 5.5.5.5"}, "127.0.0.1"), None, "login")
    t2 = _client_key(_fake_request({"x-forwarded-for": "1.1.1.1, 5.5.5.5"}, "127.0.0.1"), None, "login")
    assert t1 == t2 == "login:5.5.5.5", (t1, t2)

    # No XFF → fall back to the peer.
    assert _client_key(_fake_request({}, "127.0.0.1"), None, "login") == "login:127.0.0.1"


# ── Shared fixtures for the DB-backed endpoint tests ────────────────────────
@pytest_asyncio.fixture(loop_scope="session")
async def db_up():
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DB unavailable: {exc}")


@pytest.fixture(autouse=True)
def _no_ratelimit():
    # Many tests log in repeatedly; keep the limiter out of their way.
    prev = settings.ratelimit_enabled
    settings.ratelimit_enabled = False
    yield
    settings.ratelimit_enabled = prev


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_up):
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _uniq_email() -> str:
    return f"phase10_{ulid.new().str.lower()}@test.local"


@pytest_asyncio.fixture(loop_scope="session")
async def make_user(db_up):
    """Factory creating real users; everything prefixed phase10_ is purged after."""

    async def _make(is_admin: bool = False, password: str = "password123", active: bool = True):
        email = _uniq_email()
        async with SessionLocal() as s:
            u = User(
                email=email,
                password_hash=security.hash_password(password),
                display_name="P10",
                is_active=active,
                is_system_admin=is_admin,
            )
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return {"id": u.id, "email": email, "password": password,
                    "token": security.create_access_token(u.id)}

    yield _make
    async with SessionLocal() as s:
        await s.execute(delete(User).where(User.email.like("phase10_%@test.local")))
        await s.commit()


# ── login / me / password ───────────────────────────────────────────────────
async def test_login_me_and_wrong_password(client, make_user):
    u = await make_user()
    r = await client.post(f"{API}/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]

    me = await client.get(f"{API}/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["data"]["email"] == u["email"]

    bad = await client.post(f"{API}/auth/login", json={"email": u["email"], "password": "nope"})
    assert bad.status_code == 401


async def test_password_change_flow(client, make_user):
    u = await make_user(password="oldpassword1")
    h = _auth(u["token"])

    short = await client.post(f"{API}/me/password",
                              json={"current_password": "oldpassword1", "new_password": "short"}, headers=h)
    assert short.status_code == 422  # min_length=8

    wrong = await client.post(f"{API}/me/password",
                              json={"current_password": "WRONGWRONG", "new_password": "newpassword1"}, headers=h)
    assert wrong.status_code == 400

    okr = await client.post(f"{API}/me/password",
                            json={"current_password": "oldpassword1", "new_password": "newpassword1"}, headers=h)
    assert okr.status_code == 200
    # PWD-001 fix: data carries the message so unwrap()-based clients see it
    assert "변경" in okr.json()["data"]

    assert (await client.post(f"{API}/auth/login",
            json={"email": u["email"], "password": "newpassword1"})).status_code == 200
    assert (await client.post(f"{API}/auth/login",
            json={"email": u["email"], "password": "oldpassword1"})).status_code == 401


# ── admin guard + management ────────────────────────────────────────────────
async def test_admin_routes_require_admin(client, make_user):
    normal = await make_user()
    admin = await make_user(is_admin=True)

    forbidden = await client.get(f"{API}/admin/users", headers=_auth(normal["token"]))
    assert forbidden.status_code == 403

    listed = await client.get(f"{API}/admin/users", headers=_auth(admin["token"]))
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()["data"]}
    assert normal["email"] in emails and admin["email"] in emails


async def test_admin_create_patch_and_self_guards(client, make_user):
    admin = await make_user(is_admin=True)
    h = _auth(admin["token"])
    new_email = _uniq_email()

    created = await client.post(f"{API}/admin/users",
                                json={"email": new_email, "password": "createduser1"}, headers=h)
    assert created.status_code == 201, created.text
    new_id = created.json()["data"]["id"]

    dup = await client.post(f"{API}/admin/users",
                            json={"email": new_email, "password": "createduser1"}, headers=h)
    assert dup.status_code == 409

    short = await client.post(f"{API}/admin/users",
                              json={"email": _uniq_email(), "password": "short"}, headers=h)
    assert short.status_code == 422

    deact = await client.patch(f"{API}/admin/users/{new_id}", json={"is_active": False}, headers=h)
    assert deact.status_code == 200 and deact.json()["data"]["is_active"] is False

    self_deact = await client.patch(f"{API}/admin/users/{admin['id']}", json={"is_active": False}, headers=h)
    assert self_deact.status_code == 400

    self_demote = await client.patch(f"{API}/admin/users/{admin['id']}", json={"is_system_admin": False}, headers=h)
    assert self_demote.status_code == 400


# ── signup gate ─────────────────────────────────────────────────────────────
async def test_signup_gate_and_validation(client):
    prev = settings.allow_signup
    try:
        settings.allow_signup = False
        off = await client.post(f"{API}/auth/signup",
                                json={"email": _uniq_email(), "password": "signuptest1"})
        assert off.status_code == 403

        settings.allow_signup = True
        email = _uniq_email()
        ok_r = await client.post(f"{API}/auth/signup", json={"email": email, "password": "signuptest1"})
        assert ok_r.status_code == 201, ok_r.text
        assert ok_r.json()["data"]["access_token"]

        dup = await client.post(f"{API}/auth/signup", json={"email": email, "password": "signuptest1"})
        assert dup.status_code == 409

        short = await client.post(f"{API}/auth/signup",
                                  json={"email": _uniq_email(), "password": "short"})
        assert short.status_code == 422

        # blank (all-whitespace) password is rejected like PasswordChange (#5)
        blank = await client.post(f"{API}/auth/signup",
                                  json={"email": _uniq_email(), "password": " " * 10})
        assert blank.status_code == 422

        # malformed email is rejected at registration (#5)
        bad_email = await client.post(f"{API}/auth/signup",
                                      json={"email": "notanemail", "password": "signuptest1"})
        assert bad_email.status_code == 422
    finally:
        settings.allow_signup = prev
        async with SessionLocal() as s:
            await s.execute(delete(User).where(User.email.like("phase10_%@test.local")))
            await s.commit()


# ── system status / capabilities ────────────────────────────────────────────
async def test_system_status_and_capabilities(client, make_user):
    u = await make_user()
    h = _auth(u["token"])

    st = await client.get(f"{API}/system/status", headers=h)
    assert st.status_code == 200, st.text
    d = st.json()["data"]
    assert d["operations"] >= 45
    for key in ("api", "database", "worker", "binary", "gmsh", "rate_limit", "signup", "mcp"):
        assert key in d, f"system/status missing {key}"
    # SYS-004: no absolute binary path leaked
    assert set(d["binary"].keys()) == {"present"}

    caps = await client.get(f"{API}/system/capabilities", headers=h)
    assert caps.status_code == 200
    cd = caps.json()["data"]
    assert cd["operations"] >= 45 and cd["mcp_tools"] >= 20
    assert isinstance(cd["parity"], list) and len(cd["parity"]) >= 1
    assert all("web" in p and "mcp" in p for p in cd["parity"])


async def test_file_lifecycle_and_cross_user_isolation(client, make_user):
    """File upload/list/inspect/download/delete + a non-owner is denied (M15)."""
    owner = await make_user()
    other = await make_user()
    sid = (await client.post(f"{API}/sessions", json={"name": "files"},
                             headers=_auth(owner["token"]))).json()["data"]["id"]
    kf = b"*KEYWORD\n*NODE\n       1     0.0     0.0     0.0\n*END\n"
    up = await client.post(f"{API}/sessions/{sid}/files",
                           files={"files": ("t.k", kf, "text/plain")}, headers=_auth(owner["token"]))
    assert up.status_code == 201, up.text
    fid = up.json()["data"][0]["id"]

    lst = await client.get(f"{API}/sessions/{sid}/files", headers=_auth(owner["token"]))
    assert any(f["id"] == fid for f in lst.json()["data"])
    assert (await client.get(f"{API}/sessions/{sid}/files/{fid}/inspect",
                             headers=_auth(owner["token"]))).status_code == 200
    dl = await client.get(f"{API}/sessions/{sid}/files/{fid}/download", headers=_auth(owner["token"]))
    assert dl.status_code == 200 and b"*NODE" in dl.content

    # a different user cannot reach the session or its file
    assert (await client.get(f"{API}/sessions/{sid}", headers=_auth(other["token"]))).status_code in (403, 404)
    assert (await client.get(f"{API}/sessions/{sid}/files/{fid}/download",
                             headers=_auth(other["token"]))).status_code in (403, 404)

    assert (await client.delete(f"{API}/sessions/{sid}/files/{fid}",
                                headers=_auth(owner["token"]))).status_code == 200


async def test_token_lifecycle(client, make_user):
    """PAT create → authenticates → list → revoke → rejected (M15)."""
    u = await make_user()
    h = _auth(u["token"])
    cr = await client.post(f"{API}/me/tokens", json={"name": "test-pat"}, headers=h)
    assert cr.status_code == 201, cr.text
    pat = cr.json()["data"]["token"]
    tid = cr.json()["data"]["info"]["id"]
    assert pat.startswith("kr_")

    me = await client.get(f"{API}/me", headers=_auth(pat))
    assert me.status_code == 200 and me.json()["data"]["email"] == u["email"]
    assert any(t["id"] == tid for t in (await client.get(f"{API}/me/tokens", headers=h)).json()["data"])

    assert (await client.delete(f"{API}/me/tokens/{tid}", headers=h)).status_code == 200
    assert (await client.get(f"{API}/me", headers=_auth(pat))).status_code == 401


# ── 리포트 원샷 인테이크 (세션+K파일+리포트 한 호출) ─────────────────────────────
_SPHERE_INTAKE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


@pytest.mark.skipif(not _SPHERE_INTAKE.exists(), reason="sphere 샘플 없음")
async def test_report_intake_one_shot_with_kfile(client, make_user):
    import gzip
    u = await make_user()
    h = _auth(u["token"])
    html = _SPHERE_INTAKE.read_bytes()
    # ① 세션 없이 리포트+K파일 한 호출 → 세션 자동 생성 + K 링크
    r = await client.post(
        f"{API}/reports/intake", headers=h,
        files={"file": ("Test_001_report.html", html, "text/html"),
               "kfile": ("model.k", b"*KEYWORD\n*TITLE\nintake test\n*END\n", "text/plain")},
        data={"project": "INTAKE-TEST", "kind": "sphere"},
    )
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["session_id"] and d["report_id"] and d["kfile_id"]
    assert d["kind"] == "sphere" and d["n_cases"] == 26
    assert d["source_kfile_id"] == d["kfile_id"]   # K파일이 리포트에 링크됨
    # ② .gz 리포트를 기존 세션에 한 호출로(전송량↓)
    rz = await client.post(
        f"{API}/reports/intake", headers=h,
        files={"file": ("Test_001_report.html.gz", gzip.compress(html), "application/gzip")},
        data={"session_id": d["session_id"], "kind": "sphere"},
    )
    assert rz.status_code == 201, rz.text
    assert rz.json()["data"]["session_id"] == d["session_id"]   # 기존 세션 재사용
    await client.delete(f"{API}/sessions/{d['session_id']}", headers=h)
