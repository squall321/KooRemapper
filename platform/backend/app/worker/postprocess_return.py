# 후처리 예약(7-1) — KooSlurm 귀환 매니페스트를 기다려 리포트를 예약자 명의로 반입하는 외부 잡
"""흐름 (계획 docs/01-plan/features/postprocess-reservation-1028.plan.md)

1. 잡 생성(`app.modules.jobs.routes.create_job`) — 소속을 검증해 `external_ref.affiliation` 에 얼린다(반입 때는
   요청이 없다). **토큰은 받지 않는다** — 도구 인자로 나르면 포털 절차 원장 · 챗 문맥에 평문으로 남는다(포털 확인,
   사용자 결정 10-29). 확인할 때마다 KooSlurm 위임 창구에서 잡 소유자의 kst_ 를 받는다(`_owner_token`).
2. 시작(`start`, 워커가 잡을 집은 직후) — 주소 · 위임 창구가 없으면 「구성 안 됨」. 같은 잡 키의 리포트가 이미 있으면
   그것으로 끝낸다(7-2). 아니면 외부 잡으로 걸어 두고 다음 스캔(≤15초)에 첫 확인을 한다.
3. 확인(`poll_due`) — 매니페스트 404 는 아직이다. 200 이면 판정(`judge`) → 받기 → 반입.
   404 가 이어지는데 클러스터 잡이 끝나 있으면 매니페스트가 영영 안 올 수 있다 — 드라이버가 EXIT trap
   전에 죽었거나(SIGKILL · 시간 초과), 매니페스트를 쓰기 전 판의 드라이버다(KooSlurm 10-28). 처음 보고 2분이
   지나도 그대로면 닫는다(NFS 지연). C(후처리 잡)가 도는 중이면(.prev 가 있다) 기다린다.

지키는 것 — **지어내지 않는다.** 성공 · 실패는 매니페스트가 말하는 대로이고, 까닭은 원문 그대로 옮긴다.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models import ImpactReport, Job, Session, User
from app.modules.reports import services as report_svc
from app.runner.kooslurm_client import MANIFEST_PATH, SSO_PATH, KooSlurmClient, mint_user_token
from app.runner.stcx_client import STATES_BAD, STATES_OK
from app.worker.runner_loop import _POLL_BATCH, _next_poll_delay

logger = logging.getLogger("koorm.worker")

OPERATION = "postprocess"
KIND = "kooslurm_return"
# sim_type → 받을 리포트 종류. 매니페스트 `reports[].kind` 와 같은 낱말이다.
REPORT_KIND = {"fullangle_drop": "sphere", "partial_impact": "impact"}
MANIFEST_SCHEMA = "smarttwin.return_manifest"
MANIFEST_VERSION = 1
JOB_KEY = re.compile(r"^stcx:([0-9]+)$")
# 예약 원장에 옮겨 적는 해석 조건(7-5). 리포트 자신의 값을 덮지 않고 `reservation.conditions` 에 둔다.
CONDITION_KEYS = ("height", "floor", "preset", "position_doe")
# 매니페스트 없이 잡이 끝난 것을 처음 보고 얼마 뒤에 닫나. 결과 폴더가 NFS 라 끝난 직후의 파일이 늦게 보일 수 있다 —
# 다시 볼 때 1분 이상 띄우라는 것이 KooSlurm 의 답이다(10-29). 횟수가 아니라 시각으로 잰다(첫 두 확인은 30초 간격이다).
_ENDED_GRACE = timedelta(minutes=2)
# 클러스터가 잡을 모른다(`/info` 404)를 몇 번 연달아 보면 닫나. 대시보드는 sacct 가 5초 상한에 걸려도 404 다.
_UNKNOWN_LIMIT = 3
_TERMINAL = STATES_OK | STATES_BAD
# 위임 창구에서 받은 토큰을 사람별로 잠깐 들고 있는다. 발급은 같은 사람 · 같은 이름의 직전 토큰을 회수하므로 확인마다
# 받으면 KooSlurm 에 회수된 토큰이 쌓인다. **프로세스 안에만** 있다(DB · 로그 · 번들에 없다) — 게이트웨이와 같은 까닭 ·
# 같은 꼴이다(만료 2분 전까지, 만료를 안 주면 10분).
_TOKEN_TTL_S = 600
_TOKENS: dict[str, tuple[str, float, str | None]] = {}


def _missing_config() -> list[str]:
    return [name for name, value in (
        ("KOORM_STCX_BACKEND_URL", settings.stcx_backend_url),
        ("KOORM_KOOSLURM_SSO_SECRET", settings.kooslurm_sso_secret),
    ) if not str(value or "").strip()]


async def _owner_token(email: str) -> dict:
    """잡 소유자의 kst_ — 들고 있는 것이 살아 있으면 그것(`fresh: False`), 아니면 위임 창구에서 새로(`fresh: True`)."""
    hit = _TOKENS.get(email)
    if hit and hit[1] > time.monotonic():
        return {"ok": True, "token": hit[0], "fresh": False, "username": hit[2]}
    got = await mint_user_token(str(settings.stcx_backend_url).rstrip("/") + SSO_PATH,
                                settings.kooslurm_sso_secret, email, timeout=settings.kooslurm_timeout_sec)
    if not got.get("ok"):
        return got
    ttl = _TOKEN_TTL_S
    if got.get("expires_in"):
        ttl = max(0, min(ttl, int(got["expires_in"]) - 120))
    _TOKENS[email] = (got["token"], time.monotonic() + ttl, got.get("username"))
    return {"ok": True, "token": got["token"], "fresh": True, "username": got.get("username")}


def _close(job: Job, *, status: str, now: datetime, why: str | None = None, **extra) -> None:
    """잡을 끝낸다."""
    if extra:
        job.external_ref = {**(job.external_ref or {}), **extra}
    job.status = status
    job.finished_at = now
    job.external_poll_at = None
    if why:
        job.error_summary = why[:2000]


def cancel(job: Job) -> None:
    """사용자 취소 — 이 종류는 클러스터에 손대지 않으므로 기다림만 멈춘다."""
    _close(job, status="canceled", now=datetime.now(timezone.utc))


def _succeed(job: Job, report: ImpactReport, now: datetime, *, already: bool = False) -> None:
    _close(job, status="succeeded", now=now, report_ids=[report.id], already_ingested=already)
    job.progress = 100
    job.resolved_cmd = {**(job.resolved_cmd or {}), "report_ids": [report.id]}
    if already:
        job.warnings = [*(job.warnings or []),
                        f"같은 잡 키({report.external_job_key})의 리포트가 이미 있어 새로 반입하지 않았다 — 리포트 {report.id}"]
    elif report.source_file_id:
        job.output_file_ids = [report.source_file_id]


async def _report_by_key(db, job_key: str) -> ImpactReport | None:
    return (await db.execute(
        select(ImpactReport).where(ImpactReport.external_job_key == job_key)
    )).scalar_one_or_none()


def _tail_text(log_tail) -> str:
    """`log_tail{파일: [끝 20줄]}` → 사람이 읽는 글."""
    if not isinstance(log_tail, dict):
        return ""
    out = []
    for name, lines in log_tail.items():
        text = "\n".join(map(str, lines)) if isinstance(lines, list) else str(lines or "")
        if text.strip():
            out.append(f"[{name}]\n{text.strip()}")
    return "\n".join(out)


def judge(manifest: dict, *, sim_type: str) -> dict:
    """매니페스트 → `{"ok": True, "entry": …, "kind": …, "warnings": […]}` 또는 `{"ok": False, "why": …}`.

    ⚠ `ok` 보다 **`present` 를 먼저** 본다 — 후처리가 꺼진 잡은 `ok: true` 인데 리포트가 없다(작성기 `build`).
    """
    def no(why: str) -> dict:
        return {"ok": False, "why": why}

    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("version") != MANIFEST_VERSION:
        return no(f"모르는 매니페스트 꼴이다(schema={manifest.get('schema')!r}, version={manifest.get('version')!r})"
                  f" — {MANIFEST_SCHEMA} v{MANIFEST_VERSION} 만 읽는다")
    job = manifest.get("job") if isinstance(manifest.get("job"), dict) else {}
    if job.get("sim_type") and job["sim_type"] != sim_type:
        return no(f"예약한 종류({sim_type})와 클러스터 잡의 종류({job['sim_type']})가 다르다 — job_key 를 확인하라")
    kind = REPORT_KIND[sim_type]
    entries = [r for r in manifest.get("reports") or [] if isinstance(r, dict)]
    entry = next((r for r in entries if r.get("kind") == kind), None)
    if manifest.get("stage") == "early_exit":
        why = f"드라이버가 일찍 끝났다(stage=early_exit, driver_rc={manifest.get('driver_rc')})"
        if entry and entry.get("reason"):
            why += f" — {entry['reason']}"
        return no(why)
    if entry is None:
        by = (manifest.get("postprocess") or {}).get("by")
        return no(f"매니페스트에 {kind} 리포트 항목이 없다(postprocess.by={by!r})")
    if not entry.get("present"):
        why = f"{kind} 리포트가 없다 — {entry.get('reason') or '까닭이 적혀 있지 않다'}"
        tail = _tail_text(entry.get("log_tail"))
        return no(why + (f"\n{tail}" if tail else ""))
    path = str(entry.get("path") or "")
    parts = PurePosixPath(path).parts
    if not path or path.startswith("/") or ".." in parts:
        return no(f"리포트가 결과 폴더 밖에 있다(path={path!r}) — 파일 REST 로 받을 수 없다")
    if not isinstance(entry.get("size"), int) or not entry.get("sha256"):
        return no("매니페스트의 리포트 항목에 크기 · sha256 이 없다")
    warnings = [f"{r.get('kind')} 리포트는 없다 — {r.get('reason') or '까닭 없음'}"
                for r in entries if r is not entry and not r.get("present")]
    return {"ok": True, "entry": entry, "kind": kind, "warnings": warnings}


def _digest(manifest: dict) -> dict:
    """매니페스트에서 원장에 남길 것만 — 판정을 다시 짚을 때 필요한 칸."""
    job = manifest.get("job") if isinstance(manifest.get("job"), dict) else {}
    pp = manifest.get("postprocess") if isinstance(manifest.get("postprocess"), dict) else {}
    return {"written_at": manifest.get("written_at"), "stage": manifest.get("stage"),
            "driver_rc": manifest.get("driver_rc"), "ok": manifest.get("ok"),
            "slurm_job_id": job.get("slurm_job_id"), "job_name": job.get("job_name"),
            "web_user": job.get("web_user"), "result_dir": job.get("result_dir"),
            "postprocess_by": pp.get("by"), "postprocess_rc": pp.get("rc"),
            "postprocess_job_id": pp.get("postprocess_job_id")}


async def start(db, job: Job, now: datetime | None = None) -> None:
    """워커가 잡을 집은 직후 — 걸어 두기만 한다. 첫 확인은 다음 스캔이 한다."""
    now = now or datetime.now(timezone.utc)
    if job.status != "running":       # 집는 사이에 취소됐다
        return
    args = dict(job.args or {})
    ref = dict(job.external_ref or {})
    missing = _missing_config()
    if missing:
        _close(job, status="failed", now=now,
               why="구성 안 됨 — " + " · ".join(missing) + " 이(가) 비었다. 후처리 예약은 KooSlurm 대시보드 주소와 "
                   "위임 창구가 있어야 귀환 매니페스트를 본다(값을 지어내지 않는다)")
        await db.commit()
        return
    key = str(args.get("job_key") or "")
    m = JOB_KEY.match(key)
    sim_type = str(args.get("sim_type") or "")
    if not m or sim_type not in REPORT_KIND:
        _close(job, status="failed", now=now, why=f"인자가 맞지 않다(job_key={key!r}, sim_type={sim_type!r})")
        await db.commit()
        return
    existing = await _report_by_key(db, key)
    if existing is not None:
        _succeed(job, existing, now, already=True)
        await db.commit()
        return
    deadline = (job.created_at or now) + timedelta(days=settings.postprocess_wait_days)
    ref.update({"job_key": key, "slurm_job_id": m.group(1), "sim_type": sim_type,
                "report_kind": REPORT_KIND[sim_type], "deadline": deadline.isoformat(), "polls": 0})
    job.external_kind = KIND
    job.external_ref = ref
    job.external_poll_at = now
    job.progress = 5
    job.resolved_cmd = {"external": KIND, "job_key": key, "manifest": MANIFEST_PATH}
    await db.commit()
    logger.info("postprocess job %s reserved → %s (%s)", job.id, key, sim_type)


async def poll_due(now: datetime | None = None) -> int:
    """기한이 된 예약을 하나씩 본다. 잡마다 따로 커밋한다 — 하나가 깨져도 나머지는 간다."""
    now = now or datetime.now(timezone.utc)
    async with SessionLocal() as db:
        due = (await db.execute(
            select(Job).where(Job.status == "running", Job.external_kind == KIND,
                              Job.external_poll_at.is_not(None), Job.external_poll_at <= now)
            .order_by(Job.external_poll_at).limit(_POLL_BATCH)
        )).scalars().all()
        for job in due:
            jid = job.id
            try:
                await poll_one(db, job, now)
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — 잡 하나의 실패가 스캔을 멈추면 나머지가 선다
                logger.exception("postprocess job %s poll crashed", jid)
                await db.rollback()
                j = await db.get(Job, jid)
                if j is not None and j.status == "running":
                    _close(j, status="failed", now=now,
                           why=f"worker exception: {type(exc).__name__}: {exc}")
                    await db.commit()
        return len(due)


async def poll_one(db, job: Job, now: datetime) -> None:
    ref = dict(job.external_ref or {})
    existing = await _report_by_key(db, str(ref.get("job_key") or ""))
    if existing is not None:          # 같은 키를 다른 예약이 먼저 반입했다(7-2)
        _succeed(job, existing, now, already=True)
        return
    owner = await db.get(User, job.user_id)
    if owner is None or not owner.email:
        _close(job, status="failed", now=now, why="잡 소유자를 찾을 수 없다")
        return
    tok = await _owner_token(owner.email)
    if not tok.get("ok"):
        err = str(tok.get("error") or "")
        if err.startswith("sso_") and not err.startswith("sso_5"):
            # 4xx · 토큰 없는 응답 — 비밀 · 허용 클라이언트 · 사용자 매핑 문제다. 기다려도 안 바뀐다.
            _close(job, status="failed", now=now,
                   why=f"KooSlurm 위임 창구가 잡 소유자의 토큰을 내주지 않았다({err}): {tok.get('detail') or ''}"
                       .rstrip(": "))
            return
        ref["last_error"] = f"sso {err}: {tok.get('detail') or ''}"[:500]
        _wait(job, ref, now)
        return
    ref["cluster_user"] = tok.get("username")     # KooSlurm 이 이메일에서 푼 이름 — 403 이면 이 사람의 잡이 아니다
    client = KooSlurmClient(settings.stcx_backend_url, tok["token"], timeout=settings.kooslurm_timeout_sec)
    try:
        await _step(db, job, ref, client, now, fresh=tok["fresh"], email=owner.email)
    finally:
        await client.close()


def _wait(job: Job, ref: dict, now: datetime) -> None:
    """다시 볼 시각을 잡는다 — 기한이 지났으면 닫는다."""
    deadline = datetime.fromisoformat(ref["deadline"])
    if now >= deadline:
        last = f" — 마지막 오류: {ref['last_error']}" if ref.get("last_error") else ""
        job.external_ref = ref
        _close(job, status="failed", now=now,
               why=f"기한({settings.postprocess_wait_days}일) 안에 귀환 매니페스트가 오지 않았다{last}")
        return
    delay = _next_poll_delay(ref.get("poll_interval"))
    ref["poll_interval"] = delay
    job.external_ref = ref
    job.external_poll_at = now + timedelta(seconds=delay)


async def _step(db, job: Job, ref: dict, client: KooSlurmClient, now: datetime, *,
                fresh: bool, email: str) -> None:
    sid = str(ref["slurm_job_id"])
    ref["polls"] = int(ref.get("polls") or 0) + 1
    ref["last_poll_at"] = now.isoformat()
    got = await client.manifest(sid)
    if not got.get("ok"):
        err = got.get("error")
        if err == "http_401" and not fresh:
            # 들고 있던 토큰이 회수됐을 수 있다(같은 이름으로 다시 받은 곳이 있다) — 버리고 다음 확인에 새로 받는다.
            _TOKENS.pop(email, None)
            ref["last_error"] = "http_401: 들고 있던 위임 토큰이 거절됐다 — 다음 확인에 새로 받는다"
            _wait(job, ref, now)
            return
        if err in ("http_401", "http_403"):
            why = ("KooSlurm 이 위임받은 잡 소유자의 토큰을 거절했다(401)"
                   if err == "http_401" else
                   f"이 잡은 잡 소유자의 것이 아니다(403 — KooSlurm 소유 검사, {ref['job_key']}, "
                   f"KooSlurm 사용자 {ref.get('cluster_user') or '?'})")
            job.external_ref = ref
            _close(job, status="failed", now=now, why=f"{why}: {got.get('detail') or ''}".rstrip(": "))
            return
        # 시간 초과 · 연결 · 5xx · 깨진 매니페스트는 다시 본다 — 기한이 상한이다.
        ref["last_error"] = f"{err}: {got.get('detail') or ''}"[:500]
        _wait(job, ref, now)
        return
    if not got.get("found"):
        ended = await _ended_without_manifest(client, sid, ref, now)
        if ended:
            job.external_ref = ref
            _close(job, status="failed", now=now, why=ended)
            return
        _wait(job, ref, now)
        return

    manifest = got["manifest"]
    ref["manifest"] = _digest(manifest)
    verdict = judge(manifest, sim_type=ref["sim_type"])
    if not verdict["ok"]:
        job.external_ref = ref
        _close(job, status="failed", now=now, why=verdict["why"])
        return
    await _fetch_and_ingest(db, job, ref, client, verdict, manifest, now)


async def _ended_without_manifest(client: KooSlurmClient, sid: str, ref: dict,
                                  now: datetime) -> str | None:
    """매니페스트가 404 일 때 — 영영 안 올 잡이면 까닭을, 아니면 None. **모르면 접지 않는다.**"""
    info = await client.job_info(sid)
    if not info.get("ok"):
        ref["last_error"] = f"info {info.get('error')}: {info.get('detail') or ''}"[:500]
        return None
    if info.get("found") and info.get("state") not in _TERMINAL:
        ref["cluster_state"] = info.get("state")
        ref["unknown_seen"] = 0
        ref.pop("ended_since", None)
        return None
    prev = await client.has_prev_manifest(sid)
    if not prev.get("ok"):
        ref["last_error"] = f"prev {prev.get('error')}: {prev.get('detail') or ''}"[:500]
        return None
    if prev.get("found"):             # C 가 도는 중 — 끝나면 매니페스트가 다시 생긴다
        ref["cluster_state"] = info.get("state") if info.get("found") else None
        ref["postprocess_running"] = True
        ref["unknown_seen"] = 0
        ref.pop("ended_since", None)
        return None
    ref.pop("postprocess_running", None)
    if not info.get("found"):
        ref.pop("ended_since", None)
        n = ref["unknown_seen"] = int(ref.get("unknown_seen") or 0) + 1
        if n < _UNKNOWN_LIMIT:
            return None
        return (f"클러스터가 이 잡을 모른다(`/info` 404 를 {n}번 연달아 받았다) — job_key({ref['job_key']}) 를"
                " 확인하라")
    state = info.get("state")
    ref["cluster_state"] = state
    ref["unknown_seen"] = 0
    since = ref.setdefault("ended_since", now.isoformat())
    if now - datetime.fromisoformat(since) < _ENDED_GRACE:
        return None
    return (f"클러스터 잡이 {state}(exit {info.get('exit_code') or '?'}) 로 끝났는데 귀환 매니페스트가 없다 — "
            "드라이버가 매니페스트를 쓰기 전에 죽었거나(SIGKILL · 시간 초과) 매니페스트를 쓰기 전 판의 드라이버다. "
            "KooSlurm 후처리 잡(C, POST /api/jobs/<id>/postprocess)으로 다시 걸면 매니페스트가 생긴다 — 그 뒤 다시 예약하라")


async def _fetch_and_ingest(db, job: Job, ref: dict, client: KooSlurmClient, verdict: dict,
                            manifest: dict, now: datetime) -> None:
    entry = verdict["entry"]
    size = int(entry["size"])
    cap = settings.max_upload_mb * 1024 * 1024
    if size > cap:
        job.external_ref = ref
        _close(job, status="failed", now=now,
               why=f"리포트가 반입 상한({settings.max_upload_mb} MB)보다 크다({size} 바이트) — 손으로 올릴 때와 같은 상한이다")
        return
    session = await db.get(Session, job.session_id)
    if session is None:
        job.external_ref = ref
        _close(job, status="failed", now=now, why="세션을 찾을 수 없다")
        return

    # 세션 폴더 밖에 받는다 — 안에 두면 같은 세션의 로컬 잡이 이 파일을 자기 산출물로 잘못 등록할 수 있다.
    incoming = settings.storage_dir / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    part = incoming / f"{job.id}.part"
    try:
        got = await client.download(str(ref["slurm_job_id"]), str(entry["path"]), part, max_bytes=cap)
        if not got.get("ok"):
            # 매니페스트는 있으니 다음 확인에서 다시 받는다 — 기한이 상한이다.
            ref["last_error"] = f"download {got.get('error')}: {got.get('detail') or ''}"[:500]
            _wait(job, ref, now)
            return
        if got["bytes"] != size or got["sha256"] != entry["sha256"]:
            job.external_ref = ref
            _close(job, status="failed", now=now,
                   why=(f"내려받은 리포트가 매니페스트와 다르다(크기 {got['bytes']}/{size} · sha256 "
                        f"{got['sha256'][:12]}/{str(entry['sha256'])[:12]}) — 그사이 C 가 리포트를 다시 썼을 수 있다."
                        " 다시 예약하라"))
            return
        raw = await asyncio.to_thread(part.read_bytes)
    finally:
        part.unlink(missing_ok=True)

    args = dict(job.args or {})
    reservation = {
        "job_key": ref["job_key"], "job_id": job.id, "job_name": args.get("job_name"),
        "sim_type": ref["sim_type"],
        "reserved_at": (job.created_at or now).isoformat(),
        "conditions": {k: args[k] for k in CONDITION_KEYS if args.get(k) not in (None, "")},
        "manifest": {**ref["manifest"], "report_path": entry["path"], "sha256": entry["sha256"]},
    }
    job.external_ref = ref
    try:
        report = await report_svc.ingest_report(
            db, session, filename=PurePosixPath(str(entry["path"])).name, raw=raw,
            kind_hint=verdict["kind"], label=args.get("label") or args.get("job_name") or None,
            project=args.get("project"), dev_rev=args.get("dev_rev"),
            variation=args.get("variation"), doe=args.get("doe"),
            # 소속은 예약 때 검증해 얼린 값이다 — 반입 때는 요청(헤더)이 없다.
            shared_affiliation=str(ref.get("affiliation") or ""),
            reservation=reservation,
        )
    except ValueError as exc:
        _close(job, status="failed", now=now, why=f"리포트 반입 실패: {exc}")
        return
    except IntegrityError:
        # 같은 키를 다른 예약이 그사이 반입했다 — 유일 제약(7-2)이 막은 것이다.
        await db.rollback()
        j = await db.get(Job, job.id)
        existing = await _report_by_key(db, ref["job_key"])
        if j is None:
            return
        if existing is None:
            _close(j, status="failed", now=now, why="리포트 반입이 유일 제약에 걸렸는데 기존 리포트를 못 찾았다")
            return
        logger.warning("postprocess job %s: %s 는 이미 반입됐다 — 이번에 쓴 HTML 은 세션 폴더에 남았을 수 있다",
                       job.id, ref["job_key"])
        _succeed(j, existing, now, already=True)
        return
    finally:
        del raw
    _succeed(job, report, now)
    if verdict["warnings"]:
        job.warnings = [*(job.warnings or []), *verdict["warnings"]]
    logger.info("postprocess job %s ingested %s → report %s", job.id, ref["job_key"], report.id)
