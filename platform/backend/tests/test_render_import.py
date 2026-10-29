# SceneForge 렌더 결과(C-11) 반입 — 더하기 · 멱등 · 전부 아니면 전무 · 실패 기록 · 소유자만을 고정한다
"""반입 규칙 다섯(10-29 SceneForge 와 합의) — 렌더마다 항목 더하기(render_id 멱등) · case_key 로 붙이기 ·
전부 아니면 전무 검증 · ok:false 는 렌더 기록으로만 · manifest sha 는 경고(C-3 을 아직 안 냈다).

실제 sphere 리포트(Test_001, 26각도)를 반입해 진짜 각도 키로 시험한다. 잡을 만들지 않으므로 떠 있는 워커와 엮이지 않는다.
"""
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.models import ImpactCase, ImpactReport, Job, Session, SessionFile, User
from app.modules.reports import services as svc
from app.shared import security, storage

_aio = pytest.mark.asyncio(loop_scope="session")
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
pytestmark = [pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")]

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"y" * 120


def _out(kind: str, name: str, data: bytes, **extra) -> dict:
    return {"kind": kind, "file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), **extra}


def _result(report_id: str, case_key: str, outputs: list, *, rid="r1", ok=True, reason=None, version=1) -> dict:
    return {"format": "sceneforge.render_result", "version": version, "render_id": rid, "request_id": "q1",
            "ok": ok, "reason": reason, "warnings": [],
            "run": {"report_id": report_id, "case_key": case_key, "run_id": f"{report_id}:{case_key}"},
            "outputs": outputs,
            "meta": {"mode": "report", "deform_scale": 10, "deform_label": "변형 ×10",
                     "notice": "보기 전용 — 판정은 해석 결과(정본)", "frame": "level",
                     "template": {"id": "report-iso", "sha256": "t"},
                     "inputs": {"c3_manifest_sha256": "abc", "s1_sha256": "def"},
                     "created_at": "2026-10-29T12:00:00+09:00"}}


def _zip(result: dict | None, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        if result is not None:
            z.writestr("render_result.json", json.dumps(result, ensure_ascii=False))
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


@pytest.fixture
async def api(db):
    from httpx import ASGITransport

    from app.config import settings
    from app.main import create_app
    settings.ratelimit_enabled = False
    async with httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


async def _mk_user(db, tag="rnd"):
    u = User(email=f"{tag}_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def owned(db, api):
    """소유자 · 세션 · 반입한 sphere 리포트 · 로그인 헤더 · 각도 키 하나."""
    u = await _mk_user(db)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="rnd", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    rep = await svc.ingest_report(db, s, filename="Test_001_report.html", raw=_SPHERE.read_bytes())
    key = (await db.execute(select(ImpactCase.case_key).where(ImpactCase.report_id == rep.id))).scalars().first()
    tok = (await api.post("/api/v1/auth/login", json={"email": u.email, "password": "pw123456"})).json()["data"]["access_token"]
    # id 는 값으로 들고 있는다 — 시험이 객체를 만료시켜도 비동기에서 지연 조회가 일어나지 않게
    uid, rid = u.id, rep.id
    yield {"uid": uid, "sid": sid, "rid": rid, "key": key, "h": {"Authorization": f"Bearer {tok}"}}
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == uid))
    await db.execute(delete(Job).where(Job.user_id == uid))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()
    shutil.rmtree(storage.session_abs_dir(uid, sid), ignore_errors=True)


async def _post(api, o, raw: bytes, report_id: str | None = None, h: dict | None = None):
    return await api.post(f"/api/v1/reports/{report_id or o['rid']}/renders", headers=h or o["h"],
                          files={"file": ("render.zip", raw, "application/zip")})


async def _fresh(db, report_id: str) -> ImpactReport:
    """라우트가 다른 세션에서 쓴 것을 본다 — 리포트 하나만 다시 읽는다."""
    rep = await db.get(ImpactReport, report_id)
    await db.refresh(rep)
    return rep


async def _render_files(db, o) -> list[str]:
    rows = (await db.execute(select(SessionFile.filename).where(
        SessionFile.session_id == o["sid"], SessionFile.filename.like("renders/%")))).scalars().all()
    return sorted(rows)


@_aio
async def test_a_render_is_added_and_existing_media_is_kept(db, api, owned):
    o = owned
    rep = await _fresh(db, o["rid"])
    rep.media = [{"path": "bundle/fig.png", "kind": "image", "can_llm_view": True, "role": "figure"}]
    await db.commit()
    res = _result(rep.id, o["key"], [_out("mp4", "render.mp4", MP4, fps=30, frames=300, time_window_ms=[0.0, 5.0]),
                                     _out("still", "still_0.500ms.png", PNG, time_ms=0.5)])
    r = await _post(api, o, _zip(res, {"render.mp4": MP4, "still_0.500ms.png": PNG}))
    assert r.status_code == 200, r.text
    rep = await _fresh(db, rep.id)
    paths = [m["path"] for m in rep.media]
    assert paths[0] == "bundle/fig.png", "번들 그림이 지워졌다 — 렌더는 더해야 한다"
    added = [m for m in rep.media if m.get("render_id") == "r1"]
    assert {m["kind"] for m in added} == {"video", "image"} and all(m["case_key"] == o["key"] for m in added)
    assert [m["can_llm_view"] for m in sorted(added, key=lambda m: m["kind"])] == [True, False], "모델은 영상을 못 본다"
    assert added[0]["render"]["deform_scale"] == 10 and added[0]["set_title"] == "변형 ×10"
    assert await _render_files(db, o) == ["renders/r1/render.mp4", "renders/r1/render_result.json",
                                          "renders/r1/still_0.500ms.png"]
    log = rep.renders[0]
    assert log["ok"] is True and log["render_id"] == "r1" and len(log["outputs"]) == 2
    assert any("대조하지 못했다" in w for w in log["warnings"]), "C-3 를 아직 안 냈다 — 지어내지 않고 말한다"


@_aio
async def test_the_same_render_twice_changes_nothing(db, api, owned):
    o = owned
    res = _result(o["rid"], o["key"], [_out("mp4", "render.mp4", MP4)])
    raw = _zip(res, {"render.mp4": MP4})
    assert (await _post(api, o, raw)).status_code == 200
    r = await _post(api, o, raw)
    assert r.status_code == 200 and r.json()["data"]["already"] is True
    rep = await _fresh(db, o["rid"])
    assert len([m for m in rep.media if m.get("render_id") == "r1"]) == 1 and len(rep.renders) == 1
    assert await _render_files(db, o) == ["renders/r1/render.mp4", "renders/r1/render_result.json"], "_1 이 쌓였다"


@_aio
async def test_a_changed_render_replaces_only_its_own_files(db, api, owned):
    o = owned
    keep = _result(o["rid"], o["key"], [_out("still", "a.png", PNG)], rid="other")
    assert (await _post(api, o, _zip(keep, {"a.png": PNG}))).status_code == 200
    assert (await _post(api, o, _zip(_result(o["rid"], o["key"], [_out("mp4", "render.mp4", MP4)]),
                                     {"render.mp4": MP4}))).status_code == 200
    mp4b = MP4 + b"z"
    r = await _post(api, o, _zip(_result(o["rid"], o["key"], [_out("mp4", "render.mp4", mp4b)]), {"render.mp4": mp4b}))
    assert r.status_code == 200 and r.json()["data"]["already"] is False
    rep = await _fresh(db, o["rid"])
    r1 = [m for m in rep.media if m.get("render_id") == "r1"]
    assert len(r1) == 1 and r1[0]["sha256"] == hashlib.sha256(mp4b).hexdigest()
    assert [m for m in rep.media if m.get("render_id") == "other"], "다른 렌더를 건드렸다"
    assert "renders/r1/render_1.mp4" not in await _render_files(db, o)


@_aio
async def test_a_failed_render_is_logged_without_media(db, api, owned):
    o = owned
    res = _result(o["rid"], o["key"], [], ok=False, reason="S1 처음 움직임이 법선과 3.2° 어긋남")
    r = await _post(api, o, _zip(res, {}))
    assert r.status_code == 200 and r.json()["data"]["ok"] is False
    rep = await _fresh(db, o["rid"])
    assert not [m for m in (rep.media or []) if m.get("render_id")], "실패한 렌더에 그림이 붙었다"
    assert rep.renders[0]["ok"] is False and "3.2°" in rep.renders[0]["reason"]
    assert await _render_files(db, o) == []


@_aio
@pytest.mark.parametrize("case,word", [
    ("sha", "sha256 이 다르다"), ("bytes", "크기가 다르다"), ("extra", "outputs 에 없는 파일"),
    ("folder", "폴더 없는 이름"), ("missing", "묶음에 없다"), ("ext", "확장자가 다르다"),
    ("version", "v1 만 받는다"), ("nojson", "render_result.json 이 맨 위에 없다"),
])
async def test_a_broken_result_stores_nothing(db, api, owned, case, word):
    o = owned
    out = _out("mp4", "render.mp4", MP4)
    files = {"render.mp4": MP4}
    res = _result(o["rid"], o["key"], [out])
    if case == "sha":
        out["sha256"] = "0" * 64
    elif case == "bytes":
        out["bytes"] = 1
    elif case == "extra":
        files["notes.txt"] = b"x"
    elif case == "folder":
        files = {"sub/render.mp4": MP4}
    elif case == "missing":
        files = {}
    elif case == "ext":
        out["file"] = "render.png"
        files = {"render.png": MP4}
        out["sha256"] = hashlib.sha256(MP4).hexdigest()
    elif case == "version":
        res = _result(o["rid"], o["key"], [out], version=2)
    r = await _post(api, o, _zip(None if case == "nojson" else res, files))
    assert r.status_code == 422 and word in r.json().get("message", r.text), r.text
    rep = await _fresh(db, o["rid"])
    assert not rep.renders and not [m for m in (rep.media or []) if m.get("render_id")]
    assert await _render_files(db, o) == [], "거절했는데 파일이 남았다"


@_aio
async def test_an_unknown_angle_or_another_reports_result_is_refused(db, api, owned):
    o = owned
    r = await _post(api, o, _zip(_result(o["rid"], "no_such_angle", [_out("mp4", "render.mp4", MP4)]),
                                 {"render.mp4": MP4}))
    assert r.status_code == 422 and "없는 각도" in r.text
    r = await _post(api, o, _zip(_result("01OTHERREPORT", o["key"], [_out("mp4", "render.mp4", MP4)]),
                                 {"render.mp4": MP4}))
    assert r.status_code == 422 and "다른 리포트" in r.text


@_aio
async def test_the_same_render_id_with_a_flipped_outcome_is_refused(db, api, owned):
    o = owned
    assert (await _post(api, o, _zip(_result(o["rid"], o["key"], [_out("mp4", "render.mp4", MP4)]),
                                     {"render.mp4": MP4}))).status_code == 200
    r = await _post(api, o, _zip(_result(o["rid"], o["key"], [], ok=False, reason="x"), {}))
    assert r.status_code == 422 and "다른 결과" in r.text


@_aio
async def test_only_the_owner_can_attach(db, api, owned):
    o = owned
    other = await _mk_user(db, tag="rndother")
    try:
        tok = (await api.post("/api/v1/auth/login", json={"email": other.email, "password": "pw123456"})
               ).json()["data"]["access_token"]
        r = await _post(api, o, _zip(_result(o["rid"], o["key"], [_out("mp4", "render.mp4", MP4)]),
                                     {"render.mp4": MP4}), h={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 404, "남의 리포트에 붙일 수 있었다"
    finally:
        await db.execute(delete(User).where(User.id == other.id))
        await db.commit()
