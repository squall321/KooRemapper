# gmsh 가 진짜로 돌아가나 — 큐에 넣기 전 확인과 /api/health 노출 (P1-9)
"""왜 이 시험이 있나 (2026-09-25).

`meshfix` 는 `requires_gmsh` 인 유일한 op 인데 플랫폼은 그것을 **보지 않고** 큐에 넣었다.
gmsh 가 없거나 망가져 있으면 잡이 한참 돌다 `Gmsh failed (exit 32512)` 로 죽고, 사람은
자기 덱이 잘못된 줄 안다.

⚠ 탐지기의 탐색 순서는 `src/commands/meshfix.cpp` 의 `findGmshExe` 를 따라간다. 두 구현이
갈리면 한쪽이 틀린 채로 초록이 된다 — 그래서 **둘이 같은 답을 내는지** 여기서 못 박는다.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.runner import gmsh_probe

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _clear():
    gmsh_probe.reset_cache()
    yield
    gmsh_probe.reset_cache()


def _fake_tree(tmp_path, *, kind):
    """바이너리 옆 `gmsh/gmsh` 를 만든다. kind: 'good' | 'broken' | 'none'."""
    b = tmp_path / "KooRemapper"
    b.write_text("#!/bin/sh\nexit 0\n")
    b.chmod(0o755)
    if kind != "none":
        (tmp_path / "gmsh").mkdir()
        g = tmp_path / "gmsh" / "gmsh"
        if kind == "good":
            g.write_text("#!/bin/sh\necho 4.14.1\n")
        else:
            # 깨진 파이썬 래퍼를 흉내낸다 — 파일은 있고 실행도 되지만 rc≠0 이다.
            g.write_text("#!/bin/sh\necho 'Traceback (most recent call last):' >&2\nexit 1\n")
        g.chmod(0o755)
    return b


def test_a_working_gmsh_is_found_with_its_version(tmp_path, monkeypatch):
    monkeypatch.delenv("KOOREMAPPER_GMSH", raising=False)
    b = _fake_tree(tmp_path, kind="good")
    info = gmsh_probe.probe(b)
    assert info["available"] is True
    assert info["version"] == "4.14.1"
    assert info["path"].endswith("gmsh/gmsh")


def test_a_broken_wrapper_is_not_accepted(tmp_path, monkeypatch):
    """⚠ 핵심이다. 파일이 있고 실행도 되지만 gmsh 가 아니다 — 예전 탐색은 이것을 집었다."""
    monkeypatch.delenv("KOOREMAPPER_GMSH", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-for-test")
    b = _fake_tree(tmp_path, kind="broken")
    info = gmsh_probe.probe(b)
    assert info["available"] is False, info
    assert info["rejected"], "무엇을 왜 건너뛰었는지 말하지 않는다"
    assert "--version" in info["rejected"][0]


def test_a_nonzero_exit_is_rejected_even_if_it_prints_a_version(tmp_path, monkeypatch):
    """gmsh 가 뜨긴 하는데 실패하는 경우 — 버전 비슷한 줄을 찍고 rc≠0 이다.

    ⚠ 이 갈래가 없으면 "rc 를 안 본다" 는 변이가 살아남는다(실제로 살아남았다) — 깨진 래퍼가
    stdout 을 비우는 바람에 다른 검사에 우연히 걸렸을 뿐이었다.
    """
    monkeypatch.delenv("KOOREMAPPER_GMSH", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-for-test")
    b = _fake_tree(tmp_path, kind="none")
    (tmp_path / "gmsh").mkdir()
    g = tmp_path / "gmsh" / "gmsh"
    g.write_text("#!/bin/sh\necho 4.14.1\nexit 3\n")
    g.chmod(0o755)
    info = gmsh_probe.probe(b)
    assert info["available"] is False, info


def test_a_newly_installed_gmsh_is_seen_without_restarting(tmp_path, monkeypatch):
    """⚠ **못 찾은 답을 캐시하면 안 된다.** 운영자가 gmsh 를 깔아도 프로세스를 재기동하기
    전까지 계속 "없다" 고 말하게 된다 — 이 기능이 막으려던 종류의 거짓말이다.
    바이너리는 **건드리지 않는다**(그것이 이 시험의 핵심이다).
    """
    monkeypatch.delenv("KOOREMAPPER_GMSH", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-for-test")
    b = _fake_tree(tmp_path, kind="none")
    assert gmsh_probe.probe(b)["available"] is False
    (tmp_path / "gmsh").mkdir()
    g = tmp_path / "gmsh" / "gmsh"
    g.write_text("#!/bin/sh\necho 4.14.1\n")
    g.chmod(0o755)
    info = gmsh_probe.probe(b)          # 바이너리는 그대로다
    assert info["available"] is True, "깔았는데도 '없다' 고 한다 — 못 찾은 답을 캐시했다"
    assert info["version"] == "4.14.1"


def test_an_explicit_path_is_not_silently_swapped(tmp_path, monkeypatch):
    """명시 지정이 망가졌으면 **다른 것으로 갈아타지 않는다** — 바이너리와 같은 규율이다."""
    b = _fake_tree(tmp_path, kind="good")          # 옆에 멀쩡한 것이 있어도
    bad = tmp_path / "bad"
    bad.write_text("#!/bin/sh\nexit 1\n")
    bad.chmod(0o755)
    monkeypatch.setenv("KOOREMAPPER_GMSH", str(bad))
    info = gmsh_probe.probe(b)
    assert info["available"] is False, info
    assert info["path"] is None


def test_the_cache_refreshes_when_the_binary_changes(tmp_path, monkeypatch):
    """배포가 바이너리를 갈면 옆 gmsh 번들도 함께 갈린다(`bin/` 통째) — 옛 답을 내면 안 된다."""
    monkeypatch.delenv("KOOREMAPPER_GMSH", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-for-test")
    b = _fake_tree(tmp_path, kind="broken")
    assert gmsh_probe.probe(b)["available"] is False
    g = tmp_path / "gmsh" / "gmsh"
    g.write_text("#!/bin/sh\necho 9.9.9\n")
    g.chmod(0o755)
    b.write_text("#!/bin/sh\nexit 0\n# changed\n")   # 바이너리가 갈렸다
    info = gmsh_probe.probe(b)
    assert info["available"] is True and info["version"] == "9.9.9", info


@pytest.mark.skipif(not (REPO / "platform" / "backend" / "bin" / "KooRemapper").exists(),
                    reason="배포 바이너리가 없다")
def test_the_probe_agrees_with_the_binary_on_this_box():
    """⚠ 두 구현이 갈리지 않는지 **실제로** 확인한다. 갈리면 한쪽이 틀린 채 초록이 된다.

    바이너리는 `meshfix` 를 돌릴 때만 자기가 고른 gmsh 를 찍는다 — 그 한 줄을 뽑아 비교한다.
    """
    binary = REPO / "platform" / "backend" / "bin" / "KooRemapper"
    info = gmsh_probe.probe(binary)
    if not info["available"]:
        pytest.skip("이 박스에 gmsh 가 없다 — 비교할 것이 없다")
    # ⚠ 설정 파싱이 먼저라, yaml 이 없으면 gmsh 단계에 **도달하지 못하고** 끝난다
    #    (처음에 그렇게 써서 이 시험이 조용히 skip 됐다). 설정은 멀쩡하게 주고 모델만 없게 한다 —
    #    gmsh 탐색은 모델 적재보다 **앞**이다(meshfix.cpp: 탐색 2032 → 적재 2039).
    import tempfile as _tf
    d = _tf.mkdtemp(prefix="gmshagree_")
    Path(d, "m.yaml").write_text("model: __nonexistent__.k\noutput: o.k\npid: 1\n", encoding="utf-8")
    p = subprocess.run([str(binary), "meshfix", "m.yaml"],
                       capture_output=True, text=True, timeout=120, cwd=d)
    out = p.stdout + p.stderr
    assert "Gmsh" in out, (
        "gmsh 선택을 찍지 않는 경로로 끝났다 — 이 시험이 조용히 지나가면 두 구현이 갈려도 모른다: %s"
        % out[-300:])
    assert info["path"] in out, (
        "탐지기와 바이너리가 다른 gmsh 를 골랐다 — probe=%s / binary 출력=%s"
        % (info["path"], out[-300:]))


# ── 잡을 큐에 넣기 전에 거절하나 (실 DB + 실제 엔드포인트) ────────────────────
_aio = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def api(db):
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    transport = ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(api, db):
    import ulid
    from app.config import settings
    from app.models import User
    from app.shared import security

    settings.ratelimit_enabled = False
    email = "gmshgate_%s@kooremapper.test" % ulid.new().str
    u = User(email=email, password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    tok = (await api.post("/api/v1/auth/login",
                          json={"email": email, "password": "pw123456"})).json()["data"]["access_token"]
    h = {"Authorization": "Bearer %s" % tok}
    sid = (await api.post("/api/v1/sessions", json={"name": "gmsh-gate"},
                          headers=h)).json()["data"]["id"]
    return h, sid, u


async def _cleanup(db, u, sid):
    from sqlalchemy import delete
    from app.models import Job, Session, SessionFile, User
    await db.execute(delete(Job).where(Job.session_id == sid))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


@_aio
async def test_a_gmsh_job_is_refused_before_it_is_queued(api, db, monkeypatch):
    """⚠ 예전에는 그냥 큐에 넣었다. 잡이 한참 돌다 `Gmsh failed (exit 32512)` 로 죽고,
    사람은 자기 덱이 잘못된 줄 안다. 큐에 **넣기 전에** 사람이 읽을 한 줄로 거절한다."""
    from app.runner import gmsh_probe as gp

    h, sid, u = await _login(api, db)
    try:
        monkeypatch.setattr(gp, "probe", lambda _b: {
            "available": False, "version": None, "path": None,
            "rejected": ["/usr/bin/gmsh (--version 이 실패했다 — gmsh 가 아니거나 망가졌다)"]})
        await api.post("/api/v1/sessions/%s/files" % sid,
                       files={"files": ("m.k", b"*KEYWORD\n*END\n", "text/plain")}, headers=h)
        r = await api.post("/api/v1/sessions/%s/jobs" % sid,
                           json={"operation": "meshfix",
                                 "args": {"model": "m.k", "output": "o.k", "pid": 1}},
                           headers=h)
        assert r.status_code == 422, r.text
        assert "gmsh" in r.text
        assert "건너뛴 후보" in r.text, "무엇을 왜 못 썼는지 안 알려 준다 — %s" % r.text[:300]

        # gmsh 가 있으면 그대로 통과한다(관문이 길을 막아서는 안 된다)
        monkeypatch.setattr(gp, "probe", lambda _b: {
            "available": True, "version": "4.14.1", "path": "/x/gmsh", "rejected": []})
        r2 = await api.post("/api/v1/sessions/%s/jobs" % sid,
                            json={"operation": "meshfix",
                                  "args": {"model": "m.k", "output": "o.k", "pid": 1}},
                            headers=h)
        assert r2.status_code == 201, r2.text
    finally:
        await _cleanup(db, u, sid)


@_aio
async def test_health_reports_gmsh_without_leaking_the_path(api):
    """운영에서 "이 서버가 meshfix 를 돌릴 수 있나" 를 밖에서 볼 수 있어야 한다.
    ⚠ 다만 `/api/health` 는 인증 없이 열린다 — 경로와 거절 목록은 싣지 않는다."""
    d = (await api.get("/api/health")).json()["data"]
    assert "gmsh" in d and set(d["gmsh"]) == {"available", "version"}, d.get("gmsh")
    assert isinstance(d["gmsh"]["available"], bool)
