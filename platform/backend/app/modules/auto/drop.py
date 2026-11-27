# 자동 파이프라인 전각도 낙하 해석 — profile · 확인 · 제출(idem_key) · 사슬 나아가기 · 상태 다섯 낱말 · 결과 봉투(KR-AP2)
"""포털 계약 v1.1 §2 · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md · 사용자 결정 11-27(맥락 1 · 3절).

사슬 — 원천 세션의 덱 → 실행 세션(제출 계정 소유)에 복사 → op `stcx_fullangle_drop` 잡 → 그 잡이 Slurm 잡 번호를 얻으면 op
`postprocess` 예약(job_key `stcx:<번호>`) → 예약이 sphere 리포트를 반입하면 done. 사슬은 `auto_status` · `auto_result` 를 부를 때
앞으로 민다(포털이 상태를 묻는다). 제출 잡 · 예약 잡은 워커가 평소처럼 돌린다.

판정 — 기준이 없다(사용자 결정 「기준 없이 수치만」). verdict 는 늘 unknown 이고 metrics 에 limit 이 없다. 수치의 단위는 sphere
리포트의 단위계에서 읽는다 — KooD3plotReader `koo_deep_report/ontology/package.py` 의 환산표와 같다(ton-mm-s · g-mm-ms 는 MPa,
SI 는 Pa 를 MPa 로, ton-mm-ms 는 일관 단위계가 아니라 모름). 단위계를 모르거나 검출되지 않았으면 응력 · G 는 싣지 않고 notes 에 까닭.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone

import ulid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import AutoRun, ImpactReport, Job, Session, SessionFile, User
from app.modules.auto import services as src
from app.modules.auto.services import AutoError
from app.runner import catalog
from app.shared import storage, visibility

STCX_OP = "stcx_fullangle_drop"
POSTPROCESS_OP = "postprocess"
NCPU_DEFAULT = 2                       # stcx 는 각도마다 Slurm 잡 하나 — ncpu 기본 2(SmartTwinMCP)
PROFILES = {
    "fullangle_162": {"num_directions": 162, "title": "전각도 낙하 — Fibonacci 162 방향"},
    "fullangle_26": {"num_directions": 26, "title": "전각도 낙하 — Fibonacci 26 방향"},
}
_IDEM = re.compile(r"[0-9a-f]{64}")
_JOB_FAILED = {"failed", "error", "timeout"}
_JOB_CANCELLED = {"canceled", "cancelled"}
TERMINAL = {"done", "failed", "cancelled"}
# 단위계(sphere summary.unit_system.id) → 응력 단위 · 배수(MPa 로) — KooD3plotReader ontology/package.py 의 환산표
_STRESS = {"ton-mm-s": ("MPa", 1.0), "g-mm-ms": ("MPa", 1.0), "SI": ("MPa", 1e-6), "si": ("MPa", 1e-6)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def app_version() -> str | None:
    from app.shared.buildinfo import build_info
    commit = (build_info(settings.kooremapper_bin) or {}).get("revision")
    return str(commit)[:8] if commit else None


async def submit_user(db) -> User | None:
    email = (settings.auto_submit_email or "").strip().lower()
    if not email:
        return None
    return (await db.execute(select(User).where(User.email.ilike(email), User.is_active.is_(True)))).scalar_one_or_none()


async def profiles(db) -> dict:
    return {
        "app_version": app_version(),
        "service_identity": await submit_user(db) is not None,
        "profiles": [{"id": pid, "title": p["title"], "inputs": [{"kind": "deck", "required": True}],
                      "cost": {"cores": p["num_directions"] * NCPU_DEFAULT, "minutes": None, "cluster": "stcx"},
                      "sync": False, "criteria_source": None, "outputs": ["metrics", "artifacts"]}
                     for pid, p in PROFILES.items()],
    }


def _profile(profile: str) -> dict:
    if profile not in PROFILES:
        raise AutoError("bad_profile", f"모르는 profile 이다: {profile!r} — {', '.join(PROFILES)} 가운데 하나")
    return PROFILES[profile]


async def _source_session(db, user: User, subject: dict) -> Session | None:
    sid = ((subject or {}).get("refs") or {}).get("dynaforge")
    if not sid:
        return None
    s = await db.get(Session, str(sid))
    if s is None:
        return None
    if src.is_service(user) or s.user_id == user.id:
        return s
    owner = await db.get(User, s.user_id)
    return s if visibility.can_view(user, s, owner) else None


def _has_include(path) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return any(line.lstrip().upper().startswith("*INCLUDE") for line in fh)
    except OSError:
        return False


async def _stcx_off() -> list[str]:
    from app.worker.runner_loop import _stcx_disabled
    return _stcx_disabled()


async def check(db, user: User, subject: dict, profile: str) -> dict:
    """제출하지 않는다 — 읽기만(계약 §2 · §4-2). 빠진 것을 모두 모아 한 번에 말한다."""
    _profile(profile)
    missing: list[dict] = []
    subject = subject or {}
    if not subject.get("project"):
        missing.append({"kind": "project_key", "why": "이 세션의 허브 과제가 비었다 — update_session 의 task_key 로 넣는다"})
    if not subject.get("revision"):
        missing.append({"kind": "revision", "why": "이 세션의 개발 단계가 비었다 — update_session 의 dev_rev 로 넣는다"})
    s = await _source_session(db, user, subject)
    deck = None
    if s is None:
        missing.append({"kind": "input", "name": "session", "why": "subject.refs.dynaforge 의 세션을 찾을 수 없거나 볼 수 없다"})
    else:
        decks = [f for f in await src.session_inputs(db, s) if src.is_deck(f.filename)]
        if len(decks) != 1:
            names = ", ".join(f.filename for f in decks) or "없음"
            missing.append({"kind": "input", "name": "deck",
                            "why": f"낼 덱이 하나여야 한다(지금 {len(decks)}개 — {names})"})
        else:
            deck = decks[0]
            if _has_include(storage.abs_path(deck.rel_path)):
                missing.append({"kind": "input", "name": "deck_include",
                                "why": f"{deck.filename} 에 *INCLUDE 가 있다 — stcx 는 덱 파일 하나만 받는다(extract-parts 로 펼친 덱을 올린다)"})
    off = await _stcx_off()
    if off:
        missing.append({"kind": "infra", "why": "stcx 제출이 꺼져 있다 — " + " · ".join(off) + " 가 비었다"})
    if not settings.auto_drop_infra_ready:
        missing.append({"kind": "infra", "why": "클러스터 공유 폴더(KooSlurm SH-01 · 02) 전이다 — 업로드한 덱을 계산 노드가 못 읽는다"
                                               "(풀리면 KOORM_AUTO_DROP_INFRA_READY 를 켠다)"})
    if await submit_user(db) is None:
        missing.append({"kind": "permission", "why": "제출 계정이 정해지지 않았다(KOORM_AUTO_SUBMIT_EMAIL — 운영이 정한다)"})
    # 빈 sha 는 재서 답에 싣되 남기지 않는다 — 확인은 아무것도 바꾸지 않는다(계약 §4-2 · 커밋하지 않으면 세션이 닫힐 때 버린다)
    inputs = [src.input_item(deck)] if deck is not None else []
    return {"ready": not missing, "missing": missing, "inputs": inputs}


async def _run(db, user: User, run_ref: str) -> AutoRun:
    run = await db.get(AutoRun, str(run_ref))
    if run is None or not (src.is_service(user) or run.created_by == user.id):
        raise AutoError("not_found", f"실행을 찾을 수 없다: {run_ref!r}")
    return run


async def submit(db, user: User, subject: dict, profile: str, idem_key: str) -> dict:
    p = _profile(profile)
    if not isinstance(idem_key, str) or not _IDEM.fullmatch(idem_key):
        raise AutoError("bad_idem_key", "idem_key 는 64자 소문자 16진수다(계약 §2)")
    old = (await db.execute(select(AutoRun).where(AutoRun.idem_key == idem_key))).scalar_one_or_none()
    if old is not None:
        if not (src.is_service(user) or old.created_by == user.id):
            raise AutoError("not_found", "이 idem_key 의 실행을 볼 수 없다")
        await advance(db, old)
        return {"run_ref": old.run_ref, "state": state_of(old, await _jobs(db, old))["state"], "created": False}
    got = await check(db, user, subject, profile)
    if not got["ready"]:
        raise AutoError("not_ready", "입력이 갖춰지지 않았다 — missing 을 본다", missing=got["missing"])
    owner = await submit_user(db)
    source = await _source_session(db, user, subject)
    deck = next(f for f in await src.session_inputs(db, source) if src.is_deck(f.filename))
    run_ref = ulid.new().str
    sid = ulid.new().str
    run_session = Session(id=sid, user_id=owner.id, name=f"자동 실행 {run_ref}", visibility="private",
                          storage_path=storage.session_rel_dir(owner.id, sid),
                          description=f"자동 파이프라인 — 원천 세션 {source.id} · profile {profile}",
                          task_key=subject.get("project"), dev_rev=subject.get("revision"))
    db.add(run_session)
    await db.flush()
    rel = f"{run_session.storage_path}/{deck.filename}"
    dest = storage.abs_path(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(storage.abs_path(deck.rel_path), dest)
    db.add(SessionFile(session_id=sid, filename=deck.filename, rel_path=rel, kind="input",
                       size_bytes=deck.size_bytes, sha256=src.file_sha256(deck)))
    args = {"model": deck.filename, "num_directions": p["num_directions"], "job_name": f"auto-{run_ref}",
            "postprocess_enabled": True, "auto_sphere": True}
    errs = catalog.validate_args(STCX_OP, args)
    if errs:
        raise AutoError("bad_args", "; ".join(errs))
    job = Job(id=ulid.new().str, session_id=sid, user_id=owner.id, operation=STCX_OP, args=args, status="queued")
    db.add(job)
    run = AutoRun(run_ref=run_ref, idem_key=idem_key, profile=profile, subject=subject, inputs=got["inputs"],
                  source_session_id=source.id, run_session_id=sid, stcx_job_id=job.id, stage="stcx", created_by=user.id)
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:                       # 같은 idem_key 를 그사이 다른 호출이 냈다 — 그 실행을 돌려준다
        await db.rollback()
        dest.unlink(missing_ok=True)
        old = (await db.execute(select(AutoRun).where(AutoRun.idem_key == idem_key))).scalar_one()
        return {"run_ref": old.run_ref, "state": state_of(old, await _jobs(db, old))["state"], "created": False}
    return {"run_ref": run_ref, "state": "queued", "created": True}


async def _jobs(db, run: AutoRun) -> tuple[Job | None, Job | None]:
    a = await db.get(Job, run.stcx_job_id) if run.stcx_job_id else None
    b = await db.get(Job, run.postprocess_job_id) if run.postprocess_job_id else None
    return a, b


def _close(run: AutoRun, stage: str, detail: str | None = None) -> None:
    run.stage, run.detail, run.finished_at = stage, detail, _now()


async def advance(db, run: AutoRun) -> None:
    """사슬을 한 걸음씩 민다 — 여러 번 불러도 같다. 끝난 실행은 그대로."""
    if run.stage in TERMINAL:
        return
    stcx, pp = await _jobs(db, run)
    if run.stage == "stcx":
        if stcx is None:
            _close(run, "failed", "stcx 잡이 없다")
        elif stcx.status in _JOB_FAILED:
            _close(run, "failed", f"stcx 제출 · 해석 실패 — {stcx.error_summary or stcx.status}")
        elif stcx.status in _JOB_CANCELLED:
            _close(run, "cancelled", "stcx 잡이 취소됐다")
        else:
            slurm = (stcx.external_ref or {}).get("slurm_job_id")
            if slurm:
                # 잡 만들기 라우트와 같은 검사 — 인자 · 과제 메타(dev_rev 는 parse_stage). 소속은 서비스 계정이라 비운다.
                from app.modules.reports.services import build_eng_meta
                args = {k: v for k, v in {"job_key": f"stcx:{slurm}", "sim_type": "fullangle_drop",
                                          "job_name": f"auto-{run.run_ref}", "project": run.subject.get("project"),
                                          "dev_rev": run.subject.get("revision")}.items() if v}
                errs = catalog.validate_args(POSTPROCESS_OP, args)
                try:
                    build_eng_meta(args.get("project"), args.get("dev_rev"))
                except ValueError as exc:
                    errs.append(f"과제 메타 — {exc}")
                if errs:
                    _close(run, "failed", "후처리 예약 인자가 틀렸다 — " + "; ".join(errs))
                else:
                    pp = Job(id=ulid.new().str, session_id=stcx.session_id, user_id=stcx.user_id, operation=POSTPROCESS_OP,
                             status="queued", external_ref={"affiliation": ""}, args=args)
                    db.add(pp)
                    run.postprocess_job_id, run.stage = pp.id, "postprocess"
            elif stcx.status == "succeeded":
                _close(run, "failed", "stcx 잡은 끝났는데 Slurm 잡 번호가 없다 — 후처리 예약을 걸 수 없다")
    if run.stage == "postprocess":
        if pp is None:
            pp = await db.get(Job, run.postprocess_job_id)
        if pp is None:
            _close(run, "failed", "후처리 예약 잡이 없다")
        elif pp.status == "succeeded":
            ids = (pp.external_ref or {}).get("report_ids") or (pp.resolved_cmd or {}).get("report_ids") or []
            if ids:
                run.report_id = str(ids[0])
                _close(run, "done")
            else:
                _close(run, "failed", "후처리 예약은 끝났는데 반입한 리포트가 없다")
        elif pp.status in _JOB_FAILED:
            _close(run, "failed", f"후처리 반입 실패 — {pp.error_summary or pp.status}")
        elif pp.status in _JOB_CANCELLED:
            _close(run, "cancelled", "후처리 예약이 취소됐다")
    await db.commit()
    await db.refresh(run)               # updated_at 은 DB 가 고친다(onupdate) — 읽기 전에 다시 받는다


def state_of(run: AutoRun, jobs: tuple[Job | None, Job | None]) -> dict:
    """안의 걸음 → 계약의 다섯 낱말(queued · running · done · failed · cancelled)과 사람 글."""
    stcx, _ = jobs
    if run.stage in TERMINAL:
        return {"state": run.stage, "detail": run.detail or {"done": "끝났다", "cancelled": "취소됐다"}.get(run.stage, "")}
    slurm = (stcx.external_ref or {}).get("slurm_job_id") if stcx is not None else None
    if run.stage == "stcx":
        if stcx is not None and stcx.status == "queued":
            return {"state": "queued", "detail": "stcx 제출을 기다린다"}
        return {"state": "running", "detail": f"stcx 해석 중(Slurm {slurm})" if slurm else "stcx 에 제출하는 중"}
    return {"state": "running", "detail": f"sphere 리포트 반입을 기다린다(Slurm {slurm})"}


async def status(db, user: User, run_ref: str) -> dict:
    run = await _run(db, user, run_ref)
    await advance(db, run)
    st = state_of(run, await _jobs(db, run))
    return {**st, "progress": None, "updated_at": src.zulu(run.updated_at)}


def _metrics(report: ImpactReport) -> tuple[list[dict], list[str]]:
    summ = report.summary or {}
    us = summ.get("unit_system") if isinstance(summ.get("unit_system"), dict) else None
    out, notes = [], []
    if us is None:
        notes.append("이 리포트에 단위계 기록이 없다(옛 산출물) — 최대 응력 · 최대 가속도는 단위를 몰라 싣지 않았다")
    elif not us.get("detected"):
        notes.append(f"생성기가 단위계를 검출하지 못했다({us.get('note') or '사유 없음'}) — 최대 응력 · 최대 가속도는 싣지 않았다")
    else:
        stress = (summ.get("worst_stress") or {}).get("value")
        unit = _STRESS.get(str(us.get("id")))
        if stress is not None and unit:
            out.append({"name": "peak_stress", "label": "최대 응력(전 각도)", "unit": unit[0],
                        "value": float(f"{float(stress) * unit[1]:.9g}"), "limit": None, "limit_source": None,
                        "verdict": "unknown"})
        elif stress is not None:
            notes.append(f"단위계 {us.get('id')!r} 의 응력 단위를 정할 수 없다 — 최대 응력은 싣지 않았다")
        g = (summ.get("worst_g") or {}).get("value")
        if g is not None:
            out.append({"name": "peak_acceleration", "label": "최대 가속도(전 각도)", "unit": "G", "value": float(g),
                        "limit": None, "limit_source": None, "verdict": "unknown"})
    for key, label in (("successful_runs", "끝난 각도"), ("failed_runs", "실패한 각도")):
        v = summ.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append({"name": key, "label": label, "unit": "runs", "value": float(v), "limit": None,
                        "limit_source": None, "verdict": "unknown"})
    notes.append("판정 기준이 정해지지 않았다 — verdict 는 unknown 이다(사용자 결정 11-27 「기준 없이 수치만」)")
    if report.max_severity:
        notes.append(f"리포트 생성기의 최고 심각도 표시: {report.max_severity}(공학 합부가 아니다)")
    return out, notes


async def result(db, user: User, run_ref: str) -> dict:
    run = await _run(db, user, run_ref)
    await advance(db, run)
    if run.stage != "done":
        st = state_of(run, await _jobs(db, run))
        raise AutoError("not_done", f"실행이 끝나지 않았다({st['state']} — {st['detail']})")
    report = await db.get(ImpactReport, run.report_id)
    if report is None:
        raise AutoError("not_found", "반입된 리포트가 이 박스에 없다(지워졌을 수 있다)")
    metrics, notes = _metrics(report)
    manifest = (report.reservation or {}).get("manifest") or {}
    artifacts = [{"kind": "result_dir", "location": manifest["result_dir"]}] if manifest.get("result_dir") else []
    if not metrics:
        notes.append("실을 수 있는 수치가 없다 — 값이 없는 것이지 박스에 리포트가 없는 것이 아니다(report_summary 로 본다)")
    return {"run_ref": run.run_ref, "subject": run.subject, "profile": run.profile, "app_version": app_version(),
            "verdict": "unknown", "metrics": metrics, "figures": [], "artifacts": artifacts,
            "inputs": run.inputs or [], "notes": notes, "finished_at": src.zulu(run.finished_at),
            "report_id": run.report_id}


async def cancel(db, user: User, run_ref: str) -> dict:
    run = await _run(db, user, run_ref)
    await advance(db, run)
    if run.stage in TERMINAL:
        raise AutoError("not_cancellable", f"이미 끝난 실행이다({run.stage})")
    stcx, _ = await _jobs(db, run)
    if run.stage != "stcx" or stcx is None or stcx.status != "queued":
        raise AutoError("not_cancellable", "이미 stcx 에 냈다 — 클러스터 잡은 여기서 취소하지 않는다(KooSlurm 에서)")
    stcx.status, stcx.error_summary = "canceled", "자동 파이프라인 취소"
    _close(run, "cancelled", "내기 전에 취소했다")
    await db.commit()
    return {"run_ref": run.run_ref, "state": "cancelled"}
