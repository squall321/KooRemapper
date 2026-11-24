# 낙하 파이프라인 ⑥ — 귀환 매니페스트의 이미지 출처를 원장에 옮기고 관측을 골라 get_job · system_status 에 낸다
"""계획 docs/01-plan/features/dropline-images-1124.plan.md.

픽스처 A · B · C · C2 는 KooSlurm `016a6109` 의 작성기(`dashboard/backend_5010/return_manifest.py`)를 그쪽 시험
(`ImagesProvenanceTest`)과 같은 대역(가짜 apptainer · sacct)으로 돌려 얻은 실물이다 — 노드 이름 · SIF 경로만 바꿨다.
손으로 지은 꼴이 실물과 달라 초록이던 전례가 있다(dropline (c), 11-15).
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import ulid
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ImpactReport, Session, User  # noqa: E402
from app.modules.jobs.schemas import JobRead  # noqa: E402
from app.modules.system.routes import _observed_images  # noqa: E402
from app.shared import security, storage  # noqa: E402
from app.worker import postprocess_return as pr  # noqa: E402

async_db = pytest.mark.asyncio(loop_scope="session")

PRE_SHA = "20ca3a82b27efecf9aac96d32f1d3c29e4323cdbc2a4000d6c67b65cbc597ae3"
POST_SHA = "72231043bc1807e6f740b235eb7511ecb33255a6a375435631196de8a9750d4b"
COMMIT = "e6407dcda8d02727c978c55143608878098d1acd"
PRE_PATH = "/opt/apptainers/SmartTwinPreprocessor.sif"
POST_PATH = "/opt/apptainers/SmartTwinPostprocessor.sif"

# a — 드라이버가 같은 노드에서 리포트를 만들었다(--postprocess driver)
A = {"manifest_node": {"node": "cn-a01",
                       "pre": {"path": PRE_PATH, "present": True, "size": 9, "sha256": PRE_SHA, "version": "v137",
                               "kooremapper_commit": COMMIT},
                       "post": {"path": POST_PATH, "present": True, "size": 4, "sha256": POST_SHA, "version": "226eca7"}},
     "report_node": "cn-a01", "report_images": None}
# b — pre SIF 없음 · apptainer 없음 · 후처리 꺼짐(--postprocess disabled)
B = {"manifest_node": {"node": "cn-a01", "pre": {"path": PRE_PATH, "present": False},
                       "post": {"path": POST_PATH, "present": True, "size": 4, "sha256": POST_SHA, "version": None}},
     "report_node": None, "report_images": None}
# c — 리포트 잡이 다른 노드에서 곁 파일을 남겼다(sacct NodeList)
C = {"manifest_node": {"node": "cn-a01", "pre": {"path": PRE_PATH, "present": False},
                       "post": {"path": POST_PATH, "present": False}},
     "report_node": "cn-b07",
     "report_images": {"sphere": {"node": "cn-b07", "post": {"present": True, "sha256": "ab" * 32, "version": "226eca7"}}}}
# c2 — 리포트 잡이 다른 노드인데 곁 파일이 없다
C2 = {**copy.deepcopy(C), "report_images": None}


def _manifest(images=None, **over) -> dict:
    m = {"schema": "smarttwin.return_manifest", "version": 1, "written_at": "2026-11-24T07:30:00+00:00",
         "stage": "complete", "driver_rc": 0,
         "job": {"slurm_job_id": "4242", "job_name": "phone", "web_user": "kim", "sim_type": "fullangle_drop",
                 "result_dir": "/data/single/kim/drop_4242", "output_dir": "output"},
         "postprocess": {"by": "driver", "rc": 0, "report_job": None, "postprocess_job_id": None},
         "reports": [{"kind": "sphere", "path": "output/sphere_report.html", "present": True, "size": 7,
                      "sha256": "cd" * 32, "reason": None, "log_tail": None}],
         "ok": True}
    if images is not None:
        m["images"] = images
    m.update(over)
    return m


def _digest(images) -> dict:
    return pr._digest(_manifest(copy.deepcopy(images)), "sphere")


# ── (가) 원장 · 관측 ─────────────────────────────────────────────

def test_a_driver_on_the_same_node_observes_its_own_post_and_pre():
    d = _digest(A)
    assert d["images"] == A, "아는 칸은 받은 그대로 옮긴다"
    assert d["images_observed"] == {
        "post": {"from": "manifest_node", "node": "cn-a01", "present": True, "size": 4, "sha256": POST_SHA,
                 "version": "226eca7"},
        "pre": {"node": "cn-a01", "present": True, "size": 9, "sha256": PRE_SHA, "version": "v137",
                "kooremapper_commit": COMMIT}}


def test_without_a_report_node_the_post_has_no_source_and_a_missing_pre_stays_unknown():
    obs = _digest(B)["images_observed"]
    assert obs["post"] == {"from": None, "node": None, "why": pr.NO_REPORT_NODE}, "매니페스트 노드 것을 리포트 것으로 짐작하지 않는다"
    assert obs["pre"] == {"node": "cn-a01", "present": False, "size": None, "sha256": None, "version": None,
                          "kooremapper_commit": None}


def test_a_report_jobs_sidecar_wins_over_the_manifest_node():
    obs = _digest(C)["images_observed"]
    assert obs["post"] == {"from": "report_images", "node": "cn-b07", "present": True, "size": None,
                           "sha256": "ab" * 32, "version": "226eca7"}
    assert obs["pre"]["node"] == "cn-a01" and obs["pre"]["present"] is False, "전처리는 드라이버 노드 것이다"


def test_another_report_node_without_a_sidecar_has_no_source():
    obs = _digest(C2)["images_observed"]
    assert obs["post"] == {"from": None, "node": "cn-b07", "why": pr.NO_REPORT_NODE}


def test_a_collection_failure_is_kept_as_its_error():
    err = "PermissionError: [Errno 13] Permission denied: '/opt/apptainers/SmartTwinPreprocessor.sif'"
    d = _digest({"manifest_node": {"node": "cn-a01", "error": err}, "report_node": "cn-a01", "report_images": None})
    assert d["images"]["manifest_node"] == {"node": "cn-a01", "error": err}
    assert d["images_observed"] == {"post": {"from": "manifest_node", "node": "cn-a01", "error": err},
                                    "pre": {"node": "cn-a01", "error": err}}


@pytest.mark.parametrize("images", [A, B, C, C2])
def test_images_do_not_change_the_verdict(images):
    """KooSlurm (d) 와 같은 뜻 — 이미지 칸은 판정 · ok 에 닿지 않는다(version 1 그대로라 모르는 칸을 건너뛴다)."""
    assert pr.judge(_manifest(images), sim_type="fullangle_drop") == pr.judge(_manifest(), sim_type="fullangle_drop")
    missing = {"reports": [{"kind": "sphere", "present": False, "reason": "리포트 없음"}], "ok": False}
    assert (pr.judge(_manifest(images, **missing), sim_type="fullangle_drop")
            == pr.judge(_manifest(**missing), sim_type="fullangle_drop"))


@pytest.mark.parametrize("raw", [None, "images", [], 3])
def test_without_an_images_dict_there_is_no_key(raw):
    m = _manifest()
    if raw is not None:
        m["images"] = raw
    d = pr._digest(m, "sphere")
    assert "images" not in d and "images_observed" not in d, "모르는 것을 없다고 하지 않는다"


def test_hostile_images_are_bounded_and_wrong_shapes_become_null():
    long = "v1\n\x1b[31m" + "x" * 100_000
    pre = {"path": "/opt/" + "p" * 10_000, "present": "true", "size": "9", "sha256": PRE_SHA.upper(),
           "version": long, "kooremapper_commit": "zz" * 10, "secret": "kst_abc"}
    post = {"present": True, "size": -1, "sha256": POST_SHA + "\n", "version": "226eca7"}
    side = {"../x": {"node": "evil"}, "Sphere": {"node": "evil"}, "sphere\n": {"node": "evil"}, "sphere": "not a dict"}
    side.update({f"k{i}": {"node": f"n{i}", "post": post} for i in range(10)})   # 이상한 열쇠가 앞에 — 상한이 가리지 않게
    raw = {"manifest_node": {"node": "n\n" * 1000, "pre": pre, "post": {"present": True, "size": True},
                             "extra": {"deep": [1, 2, 3]}},
           "report_node": "n " * 1000, "report_images": side, "unknown": "x" * 100_000}
    d = pr._digest(_manifest(raw), "sphere")
    img = d["images"]
    assert set(img) == {"manifest_node", "report_node", "report_images"}, "모르는 맨 위 칸은 옮기지 않는다"
    node = img["manifest_node"]
    assert set(node) == {"node", "pre", "post"} and "\n" not in node["node"] and len(node["node"]) <= pr.IMAGE_TEXT_MAX
    p = node["pre"]
    assert "secret" not in p
    assert (p["present"], p["size"], p["sha256"], p["kooremapper_commit"]) == (None, None, None, None), p
    assert len(p["version"]) <= pr.IMAGE_TEXT_MAX and "\n" not in p["version"] and "\x1b" not in p["version"]
    assert len(p["path"]) <= pr.IMAGE_LONG_MAX
    assert node["post"]["size"] is None, "참거짓은 크기가 아니다"
    assert len(img["report_node"]) <= pr.IMAGE_TEXT_MAX
    kinds = img["report_images"]
    assert list(kinds) == ["k0", "k1", "k2", "k3"], "종류 열쇠는 소문자 낱말 · 넷까지"
    assert kinds["k0"]["post"]["size"] is None and kinds["k0"]["post"]["sha256"] is None, "끝 줄바꿈이 붙은 sha 는 hex 가 아니다"
    assert len(json.dumps(d, ensure_ascii=False)) < 6000, "원장 한 줄의 상한"


# ── (나) get_job · system_status ──────────────────────────────────

def _job(**over):
    base = dict(id="J", session_id="S", operation="postprocess", args={}, resolved_cmd=None, status="succeeded",
                progress=100, exit_code=0, input_file_ids=[], output_file_ids=[], error_summary=None,
                warnings=None, created_at=datetime.now(timezone.utc), started_at=None, finished_at=None,
                external_kind="kooslurm_return", external_ref=None)
    base.update(over)
    return SimpleNamespace(**base)


def test_get_job_carries_the_observed_images_redacted_like_the_rest():
    err = f"OSError: {Path.home()}/x.sif — a@b.com"
    digest = _digest({"manifest_node": {"node": "cn-a01", "error": err}, "report_node": "cn-a01"})
    ext = JobRead.model_validate(_job(external_ref={"cluster_state": "COMPLETED", "manifest": digest})).model_dump()["external"]
    assert ext["images"]["post"]["from"] == "manifest_node"
    for e in (ext["images"]["post"]["error"], ext["images"]["pre"]["error"]):
        assert str(Path.home()) not in e and "<home>" in e and "<email>" in e
    ext = JobRead.model_validate(_job(external_ref={"manifest": _digest(A)})).model_dump()["external"]
    assert ext["images"] == _digest(A)["images_observed"]
    assert "manifest" not in ext, "원장 칸은 그대로 안 나간다"


def test_get_job_has_no_images_key_without_images():
    ext = JobRead.model_validate(_job(external_ref={"manifest": pr._digest(_manifest(), "sphere")})).model_dump()["external"]
    assert "images" not in ext


async def _owner(db):
    u = User(email=f"di_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="di", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    return u, s


@async_db
async def test_system_status_counts_observed_images_from_recent_7_1_reports(db):
    u, s = await _owner(db)
    try:
        tag = ulid.new().str[-8:].lower()                    # 공용 DB — 이 꼬리표의 판만 본다
        k = iter(range(100))

        def tagged(images, node=None):
            images = copy.deepcopy(images)
            mn = images["manifest_node"]
            mn["pre"]["version"] = f"p{tag}"
            mn["post"]["version"] = f"q{tag}"
            for side in (images.get("report_images") or {}).values():
                side["post"]["version"] = f"r{tag}"
            if node:
                mn["node"] = images["report_node"] = node
            return {"manifest": pr._digest(_manifest(images), "sphere")}

        async def report(reservation, keyed=True):
            r = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=u.id, kind="sphere", reservation=reservation,
                             external_job_key=f"stcx:{tag}{next(k)}" if keyed else None)
            db.add(r)
            await db.commit()

        await report(tagged(A))
        await report(tagged(A))
        await report(tagged(A, node="cn-a02"))
        await report(tagged(C))                               # 곁 파일 — 다른 post 판 · pre 는 SIF 가 없다
        await report(tagged(A), keyed=False)                  # 7-1 이 아니다 — 세지 않는다
        await report({"manifest": pr._digest(_manifest(), "sphere")})   # 이미지 칸이 없다 — 세지 않는다
        got = await _observed_images(db)
        pre = [r for r in got["pre"] if r["version"] == f"p{tag}"]
        post = {r["version"]: r for r in got["post"] if (r["version"] or "").endswith(tag)}
        assert pre == [{"sha256": PRE_SHA, "version": f"p{tag}", "kooremapper_commit": COMMIT, "n": 3, "nodes": 2,
                        "last_at": pre[0]["last_at"]}], pre
        assert set(post) == {f"q{tag}", f"r{tag}"}
        assert (post[f"q{tag}"]["sha256"], post[f"q{tag}"]["n"], post[f"q{tag}"]["nodes"]) == (POST_SHA, 3, 2)
        assert (post[f"r{tag}"]["sha256"], post[f"r{tag}"]["n"], post[f"r{tag}"]["nodes"]) == ("ab" * 32, 1, 1)
        assert all(r["last_at"] for r in pre + list(post.values()))
        assert len(got["pre"]) <= 10 and len(got["post"]) <= 10
    finally:
        await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
        await db.execute(delete(Session).where(Session.id == s.id))
        await db.execute(delete(User).where(User.id == u.id))
        await db.commit()
