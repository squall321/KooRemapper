# 후처리 예약(7-1) — 가짜 KooSlurm(httpx MockTransport)으로 예약 · 확인 · 반입 · 실패 · 토큰 수명을 고정한다
"""무엇을 지키나 (계획 docs/01-plan/features/postprocess-reservation-1028.plan.md).

이 경로의 위험은 둘이다.
  ① **안 된 것이 됐다고 남는다** — 매니페스트가 말하지 않은 성공, 까닭 없는 실패, 끝없이 기다리는 잡.
  ② **신원이 엇갈리거나 샌다** — 잡 소유자가 아닌 사람의 kst_ 로 부르거나, 토큰이 인자 · 오류문 · 번들에 남는다.
     토큰은 인자로 받지 않고 KooSlurm 위임 창구에서 그때그때 받는다(사용자 결정 10-29).

⚠ 시험 DB 는 **떠 있는 dev 워커의 DB** 다. 그래서
  · 워커용 시험은 잡을 `running` 으로 넣고, 만든 시각 · 확인 시각을 **먼 미래(2100년)** 로 둔다 — 떠 있는 워커가
    시험 잡을 집거나 진짜 대시보드로 확인하러 가지 않는다. `poll_one` 을 그 시각으로 직접 부른다.
  · 라우트 시험은 queued 잡이 생기므로 같은 세션에 `running` 로컬 잡을 하나 먼저 둔다 — 세션 직렬화 규칙
    (`_claim_one`) 때문에 워커가 그 세션의 queued 잡을 집지 않는다.
"""
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Job, Session, SessionFile, User
from app.runner.kooslurm_client import KooSlurmClient
from app.shared import diagnostics, security, storage
from app.worker import postprocess_return as pr

_aio = pytest.mark.asyncio(loop_scope="session")

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
needs_sphere = pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")

SSO_URL = "http://kooslurm.test/api/auth/sso"
SECRET = "sso-shared-secret"
KEY = "stcx:4242"
SID = "4242"
REPORT = "output/sphere_report.html"
FAR = datetime(2100, 1, 1, tzinfo=timezone.utc)


def _manifest(raw: bytes, **over) -> dict:
    m = {"schema": "smarttwin.return_manifest", "version": 1, "written_at": "2026-10-29T01:00:00+09:00",
         "stage": "complete", "driver_rc": 0,
         "job": {"slurm_job_id": SID, "job_name": "phone_fib162", "web_user": "kim",
                 "sim_type": "fullangle_drop", "result_dir": "/data/single/kim/drop_4242", "output_dir": "output"},
         "postprocess": {"by": "report_job", "rc": 0, "report_job": {"id": "4243", "state": "COMPLETED",
                                                                    "exit_code": "0:0"},
                         "postprocess_job_id": None},
         "reports": [{"kind": "sphere", "path": REPORT, "present": True, "size": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest(), "reason": None, "log_tail": None}],
         "ok": True}
    m.update(over)
    return m


class FakeSlurm:
    """KooSlurm 대역 — 위임 창구(`/auth/sso`)와 대시보드 REST. 받은 요청을 들고 있다.

    위임 창구는 게이트웨이 규격대로 같은 사람의 직전 토큰을 회수하고 새 토큰을 낸다 — REST 는 살아 있는 토큰만 받는다.
    """

    def __init__(self):
        self.manifest = None          # dict 면 200, None 이면 404
        self.prev = False
        self.info = {"state": "RUNNING", "exitCode": "0:0"}   # None 이면 404
        self.files: dict[str, bytes] = {}
        self.fail_with = None         # 401 · 403 · 500 이면 REST 모든 요청에 그 상태
        self.sso_status = 200
        self.sso_body = None          # 200 이 아닐 때 돌려줄 본문
        self.minted: list[dict] = []  # 위임 요청 헤더
        self.live: dict[str, str] = {}   # email → 살아 있는 토큰
        self.calls: list[tuple] = []
        self.clients: list[httpx.AsyncClient] = []

    def revoke(self, email):
        self.live.pop(email, None)

    def _sso(self, request: httpx.Request) -> httpx.Response:
        h = request.headers
        self.minted.append({k: h.get(k) for k in ("x-heax-gateway-secret", "x-heax-user-email",
                                                  "x-hwax-delegate-email", "x-heax-client")})
        if self.sso_status != 200:
            return httpx.Response(self.sso_status, json=self.sso_body or {"success": False, "error": "nope"})
        assert h.get("x-heax-gateway-secret") == SECRET
        tok = f"kst_minted_{len(self.minted):04d}_" + "z" * 12
        email = h.get("x-hwax-delegate-email")
        self.live[email] = tok
        # KooSlurm 33bd0da1 의 응답 꼴 — 봉투 없이 맨 위에 토큰 · 수명 · 푼 사용자 이름
        return httpx.Response(200, json={"access_token": tok, "token_type": "bearer", "expires_in": 3600,
                                         "username": email.split("@")[0], "client": h.get("x-heax-client")})

    def handler(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == SSO_URL:
            return self._sso(request)
        path = request.url.params.get("path")
        auth = request.headers.get("authorization")
        self.calls.append((request.url.path, path, auth))
        if self.fail_with:
            return httpx.Response(self.fail_with, json={"success": False, "error": f"nope {self.fail_with}"})
        if auth not in {f"Bearer {t}" for t in self.live.values()}:
            return httpx.Response(401, json={"success": False, "error": "Invalid token"})
        m = re.fullmatch(r"/api/jobs/(\d+)/(info|files/download)", request.url.path)
        assert m and m.group(1) == SID, request.url.path
        if m.group(2) == "info":
            if self.info is None:
                return httpx.Response(404, json={"success": False, "error": f"Job {SID} not found"})
            return httpx.Response(200, json={"success": True, "job": {"jobId": SID, **self.info}})
        if path == "output/return_manifest.json":
            if self.manifest is None:
                return httpx.Response(404, json={"success": False, "error": f"File not found: {path}"})
            return httpx.Response(200, content=json.dumps(self.manifest).encode())
        if path == "output/return_manifest.prev.json":
            return (httpx.Response(200, content=b"{}") if self.prev
                    else httpx.Response(404, json={"success": False, "error": "File not found"}))
        if path in self.files:
            return httpx.Response(200, content=self.files[path])
        return httpx.Response(404, json={"success": False, "error": f"File not found: {path}"})


@pytest.fixture()
async def slurm(monkeypatch):
    from app.config import settings
    from app.runner import kooslurm_client
    fake = FakeSlurm()
    monkeypatch.setattr(settings, "stcx_backend_url", "http://kooslurm.test/")
    monkeypatch.setattr(settings, "kooslurm_sso_secret", SECRET)

    def _client():
        c = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
        fake.clients.append(c)
        return c

    def factory(base, token, *, timeout=30.0):
        return KooSlurmClient(base, token, client=_client())

    async def mint(url, secret, email, *, timeout=30.0):
        return await kooslurm_client.mint_user_token(url, secret, email, client=_client())

    monkeypatch.setattr(pr, "KooSlurmClient", factory)
    monkeypatch.setattr(pr, "mint_user_token", mint)
    pr._TOKENS.clear()
    yield fake
    pr._TOKENS.clear()
    for c in fake.clients:
        await c.aclose()


@pytest.fixture()
async def owner(db):
    u = User(email=f"pp_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("pw123456"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="pp", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    yield u, s
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    await db.execute(delete(Job).where(Job.user_id == u.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    shutil.rmtree(storage.session_abs_dir(u.id, sid), ignore_errors=True)


def _args(**over):
    a = {"job_key": KEY, "sim_type": "fullangle_drop", "job_name": "phone_fib162",
         "project": "DEMO", "dev_rev": "dv1", "height": 2000, "floor": "concrete"}
    a.update(over)
    return a


async def _reserved(db, u, s, **over) -> Job:
    """라우트가 하는 일(소속 얼리기)을 거친 running 잡 + `start` — 먼 미래 시각으로."""
    job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id, operation="postprocess", args=_args(**over),
              status="running", external_ref={"affiliation": "team-a"}, created_at=FAR)
    db.add(job)
    await db.commit()
    await pr.start(db, job, now=FAR)
    return job


async def _poll(db, job, minutes=1):
    now = FAR + timedelta(minutes=minutes)
    await pr.poll_one(db, job, now)
    await db.commit()
    return job


def _kst_anywhere(job: Job) -> bool:
    blob = json.dumps([job.args, job.external_ref, job.resolved_cmd, job.error_summary, job.warnings],
                      default=str, ensure_ascii=False)
    return "kst_" in blob


# ── 판정(순수) ───────────────────────────────────────────────────────────────
def test_judge_refuses_an_unknown_manifest_shape():
    v = pr.judge(_manifest(b"x", version=2), sim_type="fullangle_drop")
    assert not v["ok"] and "v1 만 읽는다" in v["why"]


def test_judge_refuses_a_job_of_another_kind():
    v = pr.judge(_manifest(b"x"), sim_type="partial_impact")
    assert not v["ok"] and "partial_impact" in v["why"] and "fullangle_drop" in v["why"]


def test_judge_looks_at_present_before_ok():
    """후처리가 꺼진 잡은 `ok: true` 인데 리포트가 없다(KooSlurm `build`) — ok 만 보면 없는 것을 반입하러 간다."""
    m = _manifest(b"x", postprocess={"by": "disabled", "rc": None, "report_job": None, "postprocess_job_id": None})
    m["reports"][0].update(present=False, size=None, sha256=None,
                           reason="후처리 꺼짐(CHAIN_POSTPROCESS=false) — 리포트를 만들지 않았다")
    v = pr.judge(m, sim_type="fullangle_drop")
    assert not v["ok"] and "후처리 꺼짐" in v["why"]


def test_judge_refuses_a_report_outside_the_result_dir():
    m = _manifest(b"x")
    m["reports"][0]["path"] = "/data/elsewhere/sphere_report.html"
    v = pr.judge(m, sim_type="fullangle_drop")
    assert not v["ok"] and "결과 폴더 밖" in v["why"]


def test_judge_takes_the_present_report_and_names_the_missing_one():
    m = _manifest(b"x", ok=False)
    m["reports"].append({"kind": "impact", "path": "output/impact_report.html", "present": False,
                         "size": None, "sha256": None, "reason": "리포트 잡 9 가 FAILED", "log_tail": None})
    v = pr.judge(m, sim_type="fullangle_drop")
    assert v["ok"] and v["kind"] == "sphere"
    assert v["warnings"] and "impact" in v["warnings"][0] and "FAILED" in v["warnings"][0]


# ── 시작 ────────────────────────────────────────────────────────────────────
@_aio
async def test_without_the_dashboard_or_the_delegation_it_fails_plainly(db, owner, slurm, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "kooslurm_sso_secret", "")
    u, s = owner
    job = await _reserved(db, u, s)
    assert job.status == "failed" and "구성 안 됨" in job.error_summary
    assert "KOORM_KOOSLURM_SSO_SECRET" in job.error_summary and SECRET not in job.error_summary
    assert slurm.minted == [] and slurm.calls == []


@_aio
async def test_start_parks_the_job_without_the_token_in_its_args(db, owner, slurm):
    u, s = owner
    job = await _reserved(db, u, s)
    assert job.status == "running" and job.external_kind == pr.KIND
    assert job.external_ref["slurm_job_id"] == SID and job.resolved_cmd["job_key"] == KEY
    assert slurm.minted == [] and slurm.calls == [], "시작은 걸어 두기만 한다 — 첫 확인은 다음 스캔"


# ── 확인 · 반입 ─────────────────────────────────────────────────────────────
@_aio
async def test_404_keeps_waiting_with_the_owners_delegated_token(db, owner, slurm):
    u, s = owner
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "running" and job.external_ref["cluster_state"] == "RUNNING"
    assert job.external_poll_at > FAR
    assert slurm.minted == [{"x-heax-gateway-secret": SECRET, "x-heax-user-email": u.email,
                             "x-hwax-delegate-email": u.email, "x-heax-client": "dynaforge"}], "게이트웨이와 같은 위임 규격"
    assert {a for _, _, a in slurm.calls} == {f"Bearer {slurm.live[u.email]}"}, "잡 소유자 본인의 kst_ 로 불러야 한다"
    assert not _kst_anywhere(job), "받은 토큰이 잡 행에 남았다"


@_aio
async def test_the_delegated_token_is_reused_across_polls(db, owner, slurm):
    """발급은 같은 이름의 직전 토큰을 회수한다 — 확인마다 받으면 KooSlurm 에 회수된 토큰이 쌓인다."""
    u, s = owner
    job = await _reserved(db, u, s)
    for m in (1, 2, 4):
        await _poll(db, job, minutes=m)
    assert job.status == "running" and len(slurm.minted) == 1


@_aio
async def test_a_revoked_token_is_minted_again_instead_of_failing(db, owner, slurm):
    """들고 있던 토큰이 다른 곳의 발급으로 회수되면 401 이다 — 한 번은 버리고 새로 받는다."""
    u, s = owner
    job = await _reserved(db, u, s)
    await _poll(db, job, minutes=1)
    slurm.revoke(u.email)
    await _poll(db, job, minutes=2)
    assert job.status == "running" and "다음 확인에 새로 받는다" in job.external_ref["last_error"]
    await _poll(db, job, minutes=4)
    assert job.status == "running" and len(slurm.minted) == 2
    assert slurm.calls[-1][2] == f"Bearer {slurm.live[u.email]}"


@_aio
async def test_a_refused_delegation_fails_and_hides_any_token_it_echoes(db, owner, slurm):
    u, s = owner
    slurm.sso_status, slurm.sso_body = 403, {"success": False, "error": "client dynaforge 는 허용되지 않음 kst_leak_ABCDEFGH1234"}
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "failed" and "내주지 않았다(sso_403)" in job.error_summary
    assert "허용되지 않음" in job.error_summary and "kst_leak" not in job.error_summary
    assert slurm.calls == [], "위임이 안 되면 대시보드를 부르지 않는다"


@_aio
async def test_a_delegation_server_error_is_retried(db, owner, slurm):
    u, s = owner
    slurm.sso_status = 502
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "running" and job.external_ref["last_error"].startswith("sso sso_502")


@needs_sphere
@_aio
async def test_a_ready_manifest_is_ingested_under_the_reserver(db, owner, slurm):
    u, s = owner
    raw = _SPHERE.read_bytes()
    slurm.manifest, slurm.files[REPORT] = _manifest(raw), raw
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "succeeded", job.error_summary
    rid = job.external_ref["report_ids"][0]
    assert job.resolved_cmd["report_ids"] == [rid], "포털은 JobRead 의 resolved_cmd 로 리포트를 찾는다"
    rep = await db.get(ImpactReport, rid)
    assert rep.user_id == u.id and rep.session_id == s.id, "예약자 명의"
    assert rep.kind == "sphere" and rep.external_job_key == KEY
    assert rep.shared_affiliation == "team-a", "소속은 예약 때 얼린 값"
    assert rep.eng_meta["project"] == "DEMO"
    assert rep.reservation["conditions"] == {"height": 2000, "floor": "concrete"}
    assert rep.reservation["manifest"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert rep.drop_height == 1500.0, "리포트 자신의 높이를 예약 값으로 덮지 않는다"
    assert job.output_file_ids == [rep.source_file_id]
    assert not _kst_anywhere(job)
    from app.config import settings
    assert not (settings.storage_dir / ".incoming" / f"{job.id}.part").exists(), "임시 파일이 남았다"


@needs_sphere
@_aio
async def test_a_report_without_a_height_takes_the_reserved_one(db, owner, slurm):
    u, s = owner
    raw = _SPHERE.read_bytes().replace(b'"drop_height": 1500', b'"drop_heigh_": 1500')
    slurm.manifest, slurm.files[REPORT] = _manifest(raw), raw
    job = await _reserved(db, u, s)
    await _poll(db, job)
    rep = await db.get(ImpactReport, job.external_ref["report_ids"][0])
    assert rep.drop_height == 2000, "리포트에 높이가 없으면 예약 조건으로 채운다(7-5)"


@needs_sphere
@_aio
async def test_the_same_job_key_is_not_ingested_twice(db, owner, slurm):
    u, s = owner
    raw = _SPHERE.read_bytes()
    slurm.manifest, slurm.files[REPORT] = _manifest(raw), raw
    first = await _reserved(db, u, s)
    await _poll(db, first)
    calls = len(slurm.calls)
    second = await _reserved(db, u, s)
    assert second.status == "succeeded" and second.external_ref["already_ingested"] is True
    assert second.external_ref["report_ids"] == first.external_ref["report_ids"]
    assert len(slurm.calls) == calls, "이미 있는 키는 다시 받지 않는다"


@_aio
async def test_a_missing_report_fails_with_the_manifests_own_words(db, owner, slurm):
    u, s = owner
    m = _manifest(b"x", ok=False)
    m["reports"][0].update(present=False, size=None, sha256=None,
                           reason="리포트 잡 4243 가 FAILED(1:0) 로 끝남 — HTML 없음",
                           log_tail={"output/sphere_report.slurm.err": ["Traceback", "MemoryError"]})
    slurm.manifest = m
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "failed"
    assert "FAILED(1:0) 로 끝남" in job.error_summary and "MemoryError" in job.error_summary


@_aio
async def test_an_early_exit_fails(db, owner, slurm):
    u, s = owner
    m = _manifest(b"x", stage="early_exit", driver_rc=2, ok=False)
    m["reports"][0].update(present=False, reason="드라이버가 리포트 단계 전에 끝남(driver rc=2)")
    slurm.manifest = m
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "failed" and "early_exit" in job.error_summary and "driver_rc=2" in job.error_summary


@_aio
@pytest.mark.parametrize("code,word", [(401, "거절"), (403, "잡 소유자의 것이 아니다")])
async def test_a_refused_fresh_token_or_another_owner_fails_at_once(db, owner, slurm, code, word):
    u, s = owner
    slurm.fail_with = code
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "failed" and word in job.error_summary and not _kst_anywhere(job)
    assert job.external_ref["cluster_user"] == u.email.split("@")[0], "누구 명의로 불렀는지 남긴다"


@_aio
async def test_a_server_error_is_retried_not_failed(db, owner, slurm):
    u, s = owner
    slurm.fail_with = 500
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "running" and job.external_ref["last_error"].startswith("http_500")


@needs_sphere
@_aio
async def test_a_download_that_does_not_match_the_manifest_fails(db, owner, slurm):
    u, s = owner
    raw = _SPHERE.read_bytes()
    slurm.manifest, slurm.files[REPORT] = _manifest(raw), raw[:-10]
    job = await _reserved(db, u, s)
    await _poll(db, job)
    assert job.status == "failed" and "매니페스트와 다르다" in job.error_summary
    assert (await db.get(Job, job.id)).external_ref.get("report_ids") is None


@_aio
async def test_past_the_deadline_it_fails(db, owner, slurm):
    u, s = owner
    job = await _reserved(db, u, s)
    await _poll(db, job, minutes=60 * 24 * 8)
    assert job.status == "failed" and "기한(7일)" in job.error_summary


@_aio
async def test_a_job_that_ended_without_a_manifest_is_closed_after_a_grace(db, owner, slurm):
    """드라이버가 EXIT trap 전에 죽으면 매니페스트가 영영 안 온다(KooSlurm 10-28) — 7일을 기다리지 않는다.
    NFS 가 늦게 보여 줄 수 있으므로 처음 보고 2분은 기다린다."""
    u, s = owner
    slurm.info = {"state": "TIMEOUT", "exitCode": "0:15"}
    job = await _reserved(db, u, s)
    await _poll(db, job, minutes=1)
    await _poll(db, job, minutes=2)
    assert job.status == "running", "처음 본 지 2분 전에는 닫지 않는다"
    await _poll(db, job, minutes=4)
    assert job.status == "failed" and "TIMEOUT" in job.error_summary and "후처리 잡(C" in job.error_summary


@_aio
async def test_a_running_postprocess_job_keeps_the_wait(db, owner, slurm):
    """C 가 돌면 매니페스트는 .prev 로 옮겨져 있다 — 원 잡이 끝나 있어도 기다린다."""
    u, s = owner
    slurm.info, slurm.prev = {"state": "COMPLETED", "exitCode": "0:0"}, True
    job = await _reserved(db, u, s)
    for m in (1, 5, 30):
        await _poll(db, job, minutes=m)
    assert job.status == "running" and job.external_ref["postprocess_running"] is True


@_aio
async def test_a_job_the_cluster_does_not_know_fails_after_three_looks(db, owner, slurm):
    u, s = owner
    slurm.info = None
    job = await _reserved(db, u, s)
    await _poll(db, job, minutes=1)
    await _poll(db, job, minutes=2)
    assert job.status == "running", "sacct 가 5초 상한에 걸려도 404 다 — 한두 번으로 단정하지 않는다"
    await _poll(db, job, minutes=3)
    assert job.status == "failed" and "이 잡을 모른다" in job.error_summary


@_aio
async def test_the_diagnostics_bundle_hides_a_kst_token(db, owner, slurm):
    u, s = owner
    job = await _reserved(db, u, s)
    job.error_summary = "누군가 붙여 넣은 kst_pasted_ABCDEFGH12345678"
    await db.commit()
    blob = json.dumps(diagnostics.build(job, inputs=[], outputs=[], deck_lines=False), ensure_ascii=False)
    assert "kst_pasted" not in blob


# ── 라우트 ──────────────────────────────────────────────────────────────────
@pytest.fixture
async def api(db):
    from httpx import ASGITransport

    from app.config import settings
    from app.main import create_app
    settings.ratelimit_enabled = False
    async with httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


async def _login(api, u) -> dict:
    tok = (await api.post("/api/v1/auth/login", json={"email": u.email, "password": "pw123456"})
           ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {tok}"}


async def _hold_session(db, u, s) -> None:
    """같은 세션에 running 로컬 잡을 둔다 — 떠 있는 워커가 이 세션의 queued 잡을 집지 않는다(`_claim_one`)."""
    db.add(Job(id=ulid.new().str, session_id=s.id, user_id=u.id, operation="info",
               args={"input": "x.k"}, status="running"))
    await db.commit()


@_aio
async def test_the_route_freezes_the_affiliation_and_takes_no_token(db, owner, api):
    u, s = owner
    await _hold_session(db, u, s)
    h = await _login(api, u)
    r = await api.post(f"/api/v1/sessions/{s.id}/jobs", headers=h,
                       json={"operation": "postprocess", "args": _args(job_key="stcx:0")})
    assert r.status_code == 201, r.text
    job = await db.get(Job, r.json()["data"]["id"])
    await db.refresh(job)
    assert job.external_ref == {"affiliation": ""}, "게이트웨이 증명이 없으면 소속은 빈 값(소유자만 읽는다)"


@_aio
async def test_a_token_argument_is_refused_without_echoing_it(db, owner, api):
    """토큰을 인자로 나르면 포털 절차 원장 · 챗 문맥에 남는다 — 받지 않는다. 거절 문구도 값을 되풀이하지 않는다."""
    u, s = owner
    h = await _login(api, u)
    r = await api.post(f"/api/v1/sessions/{s.id}/jobs", headers=h,
                       json={"operation": "postprocess", "args": _args(kst_token="kst_should_not_be_echoed_1234")})
    assert r.status_code == 422 and "kst_token" in r.text
    assert "kst_should_not_be_echoed" not in r.text, "거절 문구가 토큰을 되풀이했다"


@_aio
async def test_a_reservation_can_be_canceled_and_drops_its_token(db, owner, api, slurm):
    u, s = owner
    job = await _reserved(db, u, s)
    h = await _login(api, u)
    r = await api.post(f"/api/v1/jobs/{job.id}/cancel", headers=h)
    assert r.status_code == 200, r.text
    await db.refresh(job)
    assert job.status == "canceled"
