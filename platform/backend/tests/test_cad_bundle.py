# StepForge fe_cad 묶음(C-6 · C-7) 붙이기 — 받는 쪽 검사 · 전부 아니면 전무 · 멱등 · 갈아 끼우기 · 소유자만을 고정한다
"""뷰어 1단계(`docs/01-plan/features/deform-viewer-1030.plan.md`, 사용자 결정 10-30 — 리포트에 묶음 붙이기).

검사 시험은 작은 합성 묶음으로 한다 — 실패 하나만 골라 만들 수 있게 manifest 의 sha 는 늘 만든 파일로 다시 센다.
붙이기 시험은 실제 sphere 리포트(Test_001, 파트 1–23)를 반입해 진짜 파트 id 로 한다. 잡을 만들지 않는다.
"""
from __future__ import annotations

import array
import hashlib
import io
import json
import shutil
import struct
import zipfile
from pathlib import Path

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.models import ImpactReport, Job, Session, SessionFile, User
from app.modules.reports import services as svc
from app.reports import cad_bundle as cb
from app.shared import security, storage

_aio = pytest.mark.asyncio(loop_scope="session")
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
KEY = "a" * 64
KEY2 = "b" * 64


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _glb(vertices: list[int]) -> bytes:
    """노드 i → mesh i → primitive 0 의 POSITION 정점 vertices[i] 개. 검사는 JSON 덩이만 읽으므로 바이너리 덩이는 없다."""
    doc = {"asset": {"version": "2.0"},
           "nodes": [{"mesh": i} for i in range(len(vertices))],
           "meshes": [{"primitives": [{"attributes": {"POSITION": i}}]} for i in range(len(vertices))],
           "accessors": [{"count": n, "type": "VEC3", "componentType": 5126} for n in vertices]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(js)) + struct.pack("<II", len(js), 0x4E4F534A) + js


def _bundle(parts=((1, 3), (2, 4)), *, key=KEY, w=(0.2, 0.3, 0.5), glb_vertices=None, weights_key=None,
            pad=8, glb_name="model.step.glb") -> tuple[dict, dict[str, bytes]]:
    """합성 fe_cad 묶음 — (manifest, {이름: 바이트}). 인자 하나로 검사 하나만 깨지게 만든다."""
    binary = bytearray()

    def put(data: bytes, count: int, dtype: str) -> dict:
        off = len(binary)
        binary.extend(data)
        binary.extend(b"\0" * (-len(binary) % pad))
        return {"offset": off, "count": count, "dtype": dtype}

    wparts = []
    for i, (pid, rows) in enumerate(parts):
        arrays = {"row_ptr": put(array.array("I", range(0, 3 * rows + 1, 3)).tobytes(), rows + 1, "uint32"),
                  "col": put(array.array("I", range(1, 3 * rows + 1)).tobytes(), 3 * rows, "uint32"),
                  "w": put(array.array("f", list(w) * rows).tobytes(), 3 * rows, "float32"),
                  "dist": put(array.array("f", [0.0] * rows).tobytes(), rows, "float32")}
        wparts.append({"part_key": f"/m/P{pid}", "pid": pid,
                       "glb": {"file": glb_name, "node": i, "mesh": i,
                               "primitives": [{"primitive": 0, "vertices": rows}], "vertices": rows},
                       "rows": rows, "nnz": 3 * rows, "arrays": arrays, "dist_mm": {"max": 0.0}})
    binary = bytes(binary)
    weights = {"format": cb.FORMATS["weights"], "version": 1, "key": weights_key or key, "byte_order": "little",
               "align_bytes": 8, "nnz_per_row": 3, "units": {"glb": "m", "deck": "mm", "weights_dist": "mm"},
               "bin": {"file": "weights.bin", "bytes": len(binary), "sha256": _sha(binary)},
               "parts": wparts, "unmapped": []}
    parts_json = {"format": cb.FORMATS["parts"], "version": 1, "key": key,
                  "parts": [{"part_key": f"/m/P{pid}", "name": f"Part {pid}", "pid": pid, "color": None}
                            for pid, _ in parts]}
    pairs_json = {"format": cb.FORMATS["pairs"], "version": 1, "key": key,
                  "deck": {"file": "model.k", "sha256": "0" * 64},
                  "cad_project": {"id": "p1", "name": "test", "facet_body": True},
                  "pairs": [{"pid": pid, "part_key": f"/m/P{pid}"} for pid, _ in parts]}
    files = {glb_name: _glb(glb_vertices or [r for _, r in parts]), "weights.bin": binary,
             "weights.json": json.dumps(weights).encode(), "parts.json": json.dumps(parts_json).encode(),
             "pairs.json": json.dumps(pairs_json).encode()}
    manifest = {"format": cb.FORMATS["manifest"], "version": 1, "key": key,
                "variants": {"view": {"glb": [glb_name], "weights": "weights.json", "key": key}},
                "files": [{"file": n, "bytes": len(b), "sha256": _sha(b)} for n, b in files.items()]}
    return manifest, files


def _zip(manifest: dict | None, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if manifest is not None:
            zf.writestr(cb.MANIFEST_NAME, json.dumps(manifest))
        for n, b in files.items():
            zf.writestr(n, b)
    return buf.getvalue()


def _check(manifest, files, part_ids=frozenset(range(1, 24))):
    return cb.check(manifest, {**files, cb.MANIFEST_NAME: json.dumps(manifest).encode()},
                    report_part_ids=set(part_ids))


# ── 검사(순수) ───────────────────────────────────────────────────────────────
def test_a_good_bundle_passes_with_a_summary_the_viewer_can_use():
    out = _check(*_bundle())
    assert out["key"] == KEY and out["n_parts"] == 2 and out["rows"] == 7 and out["nnz"] == 21
    assert [(p["pid"], p["name"], p["glb"]["node"]) for p in out["parts"]] == [(1, "Part 1", 0), (2, "Part 2", 1)]
    assert out["pids_matched"] == 2 and out["warnings"] == [] and out["view"]["bin"] == "weights.bin"


def test_unzip_keeps_the_manifest_bytes_and_refuses_folders():
    m, f = _bundle()
    got_m, got_f = cb.unzip(_zip(m, f))
    assert got_m == m and cb.MANIFEST_NAME in got_f and set(got_f) - {cb.MANIFEST_NAME} == set(f)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("fe_cad/manifest.json", "{}")
    with pytest.raises(cb.CadBundleError, match="폴더 없는 이름"):
        cb.unzip(buf.getvalue())
    with pytest.raises(cb.CadBundleError, match="manifest.json"):
        cb.unzip(_zip(None, f))


def test_a_korean_glb_name_is_taken():
    out = _check(*_bundle(glb_name="기기 모델 v2.step.glb"))
    assert out["view"]["glb"] == ["기기 모델 v2.step.glb"]


@pytest.mark.parametrize("breaks, word", [
    ("sha", "sha256 이 manifest 와 다르다"),
    ("missing", "묶음에 없다"),
    ("extra", "manifest 에 없는 파일"),
])
def test_files_must_match_the_manifest_exactly(breaks, word):
    m, f = _bundle()
    if breaks == "sha":
        f["parts.json"] = f["parts.json"][:-1] + b" "
    elif breaks == "missing":
        del f["pairs.json"]
    else:
        f["notes.txt"] = b"x"
    with pytest.raises(cb.CadBundleError, match=word):
        _check(m, f)


def test_every_header_must_carry_the_manifest_key():
    with pytest.raises(cb.CadBundleError, match="weights.json 열쇠가 manifest 와 다르다"):
        _check(*_bundle(weights_key=KEY2))


def test_an_offset_off_the_eight_byte_grid_is_refused():
    # 행 2 의 row_ptr 는 12 바이트 — 8 이 아니라 4 로만 맞추면 col 이 12 에서 시작한다
    with pytest.raises(cb.CadBundleError, match="8 의 배수"):
        _check(*_bundle(parts=((1, 2),), pad=4))


def test_weights_that_do_not_sum_to_one_are_refused():
    with pytest.raises(cb.CadBundleError, match="무게 합"):
        _check(*_bundle(w=(0.2, 0.3, 0.6)))


def test_rows_must_equal_the_glb_vertices():
    with pytest.raises(cb.CadBundleError, match="정점"):
        _check(*_bundle(glb_vertices=[3, 5]))


def test_a_file_that_is_not_a_glb_is_refused():
    m, f = _bundle()
    f["model.step.glb"] = b"not a glb at all, just bytes"
    m["files"] = [{"file": n, "bytes": len(b), "sha256": _sha(b)} for n, b in f.items()]
    with pytest.raises(cb.CadBundleError, match="glb"):
        _check(m, f)


def test_a_bundle_of_another_device_is_refused_and_a_partial_one_warns():
    with pytest.raises(cb.CadBundleError, match="이 리포트의 기기가 아니다"):
        _check(*_bundle(parts=((101, 3),)))
    with pytest.raises(cb.CadBundleError, match="파트 표가 없어"):
        _check(*_bundle(), part_ids=set())
    out = _check(*_bundle(parts=((1, 3), (99, 3))))
    assert out["pids_bundle_only"] == [99] and "리포트에 없다" in out["warnings"][0]


_REAL = Path("/data/appdata/step_forge/projects/001a184fed0639fc4477054/export/fe_cad/2b8061b6990f")


@pytest.mark.skipif(not (_REAL / "manifest.json").exists(), reason="StepForge 실제 묶음 없음(이 박스 전용)")
def test_the_real_stepforge_bundle_passes():
    """합성 묶음만으로는 StepForge 산출 꼴이 바뀐 것을 못 본다 — P2 기준 묶음(10-29)을 그대로 검사한다."""
    files = {f.name: f.read_bytes() for f in _REAL.iterdir() if f.is_file()}
    out = cb.check(json.loads(files[cb.MANIFEST_NAME]), files, report_part_ids=set(range(1, 24)))
    assert out["n_parts"] == 22 and out["rows"] == 1232 and out["nnz"] == 3696 and out["pids_matched"] == 22
    assert out["warnings"] == [] and out["units"]["glb"] == "m"


# ── 붙이기(서비스 · 라우트) ───────────────────────────────────────────────────
needs_sample = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")


@pytest.fixture
async def api(db):
    from httpx import ASGITransport

    from app.config import settings
    from app.main import create_app
    settings.ratelimit_enabled = False
    async with httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


async def _mk_user(db, tag):
    u = User(email=f"{tag}_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def owned(db, api):
    """소유자 · 세션 · 반입한 sphere 리포트 · 로그인 헤더."""
    u = await _mk_user(db, "cad")
    sid = ulid.new().str
    db.add(Session(id=sid, user_id=u.id, name="cad", storage_path=storage.session_rel_dir(u.id, sid)))
    await db.commit()
    storage.ensure_session_dir(u.id, sid)
    s = await db.get(Session, sid)
    rep = await svc.ingest_report(db, s, filename="Test_001_report.html", raw=_SPHERE.read_bytes())
    tok = (await api.post("/api/v1/auth/login", json={"email": u.email, "password": "pw123456"})).json()["data"]["access_token"]
    uid, rid = u.id, rep.id    # 값으로 든다 — 객체가 만료돼도 비동기 지연 조회가 일어나지 않게
    yield {"uid": uid, "sid": sid, "rid": rid, "h": {"Authorization": f"Bearer {tok}"}}
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == uid))
    await db.execute(delete(Job).where(Job.user_id == uid))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()
    shutil.rmtree(storage.session_abs_dir(uid, sid), ignore_errors=True)


async def _post(api, o, raw: bytes, h: dict | None = None):
    return await api.post(f"/api/v1/reports/{o['rid']}/cad", headers=h or o["h"],
                          files={"file": ("fe_cad.zip", raw, "application/zip")})


async def _fresh(db, report_id: str) -> ImpactReport:
    rep = await db.get(ImpactReport, report_id)
    await db.refresh(rep)
    return rep


async def _cad_files(db, o) -> list[str]:
    return sorted((await db.execute(select(SessionFile.filename).where(
        SessionFile.session_id == o["sid"], SessionFile.filename.like("cad/%")))).scalars().all())


@needs_sample
@_aio
async def test_a_bundle_is_attached_once_and_the_viewer_gets_file_ids(db, api, owned):
    o = owned
    r = await _post(api, o, _zip(*_bundle()))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["stored"] == 6 and r.json()["data"]["already"] is False
    rep = await _fresh(db, o["rid"])
    assert rep.cad["key"] == KEY and rep.cad["n_parts"] == 2
    ids = [rep.cad["view"]["glb"][0]["file_id"], rep.cad["view"]["weights"]["file_id"], rep.cad["view"]["bin"]["file_id"],
           rep.cad["manifest_file_id"], rep.cad["parts_file_id"], rep.cad["pairs_file_id"]]
    assert all(isinstance(i, int) for i in ids)
    names = await _cad_files(db, o)
    assert len(names) == 6 and all(n.startswith(f"cad/{o['rid']}/{KEY[:12]}/") for n in names)
    # 같은 묶음을 다시 — 바꾼 것이 없다
    r = await _post(api, o, _zip(*_bundle()))
    assert r.status_code == 200 and r.json()["data"]["already"] is True
    assert await _cad_files(db, o) == names


@needs_sample
@_aio
async def test_another_key_replaces_the_bundle_and_its_old_files(db, api, owned):
    o = owned
    assert (await _post(api, o, _zip(*_bundle()))).status_code == 200
    r = await _post(api, o, _zip(*_bundle(key=KEY2, parts=((3, 3),))))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["replaced"] == KEY
    rep = await _fresh(db, o["rid"])
    assert rep.cad["key"] == KEY2 and [p["pid"] for p in rep.cad["parts"]] == [3]
    names = await _cad_files(db, o)
    assert names and all(n.startswith(f"cad/{o['rid']}/{KEY2[:12]}/") for n in names), names


@needs_sample
@_aio
async def test_a_bad_bundle_is_refused_whole_and_keeps_the_old_one(db, api, owned):
    o = owned
    assert (await _post(api, o, _zip(*_bundle()))).status_code == 200
    before = await _cad_files(db, o)
    r = await _post(api, o, _zip(*_bundle(key=KEY2, w=(0.5, 0.5, 0.5))))
    assert r.status_code == 422 and "CAD 묶음을 받지 않았다" in r.text and "무게 합" in r.text, r.text
    assert await _cad_files(db, o) == before
    assert (await _fresh(db, o["rid"])).cad["key"] == KEY
    # 같은 열쇠에 다른 파일 — StepForge 는 같은 열쇠면 같은 바이트다
    m, f = _bundle()
    f["parts.json"] = f["parts.json"].replace(b"Part 1", b"Part X")
    m["files"] = [{"file": n, "bytes": len(b), "sha256": _sha(b)} for n, b in f.items()]
    r = await _post(api, o, _zip(m, f))
    assert r.status_code == 422 and "같은 열쇠" in r.text, r.text


@needs_sample
@_aio
async def test_only_the_owner_attaches(db, api, owned):
    o = owned
    other = await _mk_user(db, "cad_other")
    try:
        tok = (await api.post("/api/v1/auth/login", json={"email": other.email, "password": "pw123456"})
               ).json()["data"]["access_token"]
        r = await _post(api, o, _zip(*_bundle()), h={"Authorization": f"Bearer {tok}"})
        assert r.status_code in (403, 404), r.text
        assert await _cad_files(db, o) == []
    finally:
        await db.execute(delete(User).where(User.id == other.id))
        await db.commit()
