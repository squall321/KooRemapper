# 허브 코어 API 에서 기준정보를 **주기로 받는** 워커 쪽 — 설정이 비면 아무것도 하지 않는다
"""왜 잡이 아니라 주기 작업인가 — `Job` 은 세션에 매달린다(`session_id`·`user_id`). 기준정보
수신은 **세션의 일이 아니다.** 억지로 잡으로 만들면 "누구의 세션에서 돌린 동기화인가" 라는
답할 필요 없는 질문이 생기고, 세션을 지우면 이력이 함께 사라진다.

그래서 외부 잡 스캔(`runner_loop._poll_external_once`)과 **같은 자리·같은 모양**으로 둔다 —
시간 기준이고, 실패가 워커를 멈추지 않는다.

**켜짐은 주소·토큰이 정한다**(`enabled()` = `sp_core_url` · `sp_core_token` · `sp_core_sync_sec>0`).
주기 기본은 `sp_core_sync_sec=3600`(1시간)이고, 주소·토큰이 비어 있으면 어차피 안 돈다 —
그래서 주소·토큰만 넣으면 켜진다(간격까지 또 설정하지 않아도 된다). 받을 타입은
`KOORM_SP_CORE_TYPES`(기본 plm_project,plm_task,plm_model)로 고른다(KR-06).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text

from app.config import settings
from app.database import SessionLocal
from app.models import OntoSyncRun
from app.runner.sp_core import SpCoreClient, sync_all

logger = logging.getLogger("koorm.worker")


def enabled() -> bool:
    """주소·토큰·간격이 **모두** 있어야 돈다. 하나라도 비면 꺼진 것이다."""
    return bool(settings.sp_core_url.strip() and settings.sp_core_token.strip()
                and settings.sp_core_sync_sec > 0)


def wanted_types() -> list[str] | None:
    """받을 타입. 설정 `KOORM_SP_CORE_TYPES`(쉼표)로 고른다 — 기본은 **쓰는 것 셋**이다(KR-06).

    공개 35종을 다 받으면 약 1만 9천 건 + 관계 13종이 들어온다. 쓰는 것은 셋뿐이라 기본을 좁혔다.
    설정이 비면 `None` — 공개된 것 전부. 고른 타입 중 공개 안 된 것이 있어도 `sync_all` 이
    **거절하지 않고 건너뛰며 알린다**(응답 `skipped`).
    """
    raw = [t.strip() for t in (settings.sp_core_types or "").split(",") if t.strip()]
    return raw or None


# 규칙 14 — 두 실행이 겹치지 않게(워커 주기와 관리자 버튼은 다른 프로세스다). 트랜잭션 advisory 잠금이라 커밋 ·
# 실패 때 저절로 풀린다 — 세션 잠금은 풀에서 연결이 바뀌면 다른 연결로 풀려 남는다.
LOCK_NAME = "dynaforge.sp_core_sync"


async def try_lock(db) -> bool:
    """이 트랜잭션에 받기 잠금을 건다(못 걸면 `False` — 누가 받는 중이다). 층 2 를 손으로 고치는 길(합친 과제 옮기기)도 건다."""
    return bool((await db.execute(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": LOCK_NAME})).scalar())


async def _open_run(*, mode: str, allow_shrink: bool, trigger: str, requested_by: str) -> int:
    """실행 기록을 **따로** 연다 — 본 트랜잭션이 깨져도 기록은 남는다."""
    async with SessionLocal() as db:
        run = OntoSyncRun(mode=mode, allow_shrink=allow_shrink, trigger=trigger, requested_by=requested_by)
        db.add(run)
        await db.commit()
        return run.id


async def _close_run(run_id: int, got: dict) -> None:
    async with SessionLocal() as db:
        run = await db.get(OntoSyncRun, run_id)
        if run is None:
            return
        run.finished_at = datetime.now(timezone.utc)
        run.result = str(got.get("result") or "failed")
        run.revision = got.get("revision")
        run.counts = {"types": got.get("types") or {}, "relations": got.get("relations") or {},
                      "skipped": got.get("skipped") or [], "reflected": got.get("reflected")}
        run.problems = list(got.get("problems") or [])
        run.notes = list(got.get("notes") or [])
        run.error = got.get("error")
        await db.commit()


async def full_due(now: datetime | None = None) -> bool:
    """주 1회 처음부터 받을 때가 됐나 — 마지막으로 **끝까지 돈** 처음부터 받기(정상 · 확인 필요)에서 따진다."""
    days = int(settings.sp_core_full_every_days or 0)
    if days <= 0:
        return False
    async with SessionLocal() as db:
        last = (await db.execute(select(func.max(OntoSyncRun.finished_at)).where(
            OntoSyncRun.mode == "full", OntoSyncRun.result.in_(["ok", "needs_check"])))).scalar_one()
    return last is None or (now or datetime.now(timezone.utc)) - last >= timedelta(days=days)


async def sync_once(*, full: bool = False, allow_shrink: bool = False, client: SpCoreClient | None = None,
                    trigger: str = "worker", requested_by: str = "") -> dict:
    """한 번 받는다(층 1 → 층 2 반영 → 커밋). 실패를 예외로 올리지 않는다 — 워커가 이것 때문에 멈추면 안 된다.

    결과는 셋이다(규칙 16) — ok · needs_check · failed. 이미 받는 중이면 시작하지 않고 `busy` 를 돌려준다(규칙 14).
    `client` 는 시험이 넣는다(MockTransport 를 실은 것) — 망 없이 계약을 고정하려면 필요하다.
    """
    if not enabled():
        return {"ok": False, "result": "failed", "error": "disabled",
                "detail": "KOORM_SP_CORE_URL/TOKEN/SYNC_SEC 중 비어 있는 것이 있다"}
    owns = client is None
    client = client or SpCoreClient(settings.sp_core_url, settings.sp_core_token,
                                    page_size=settings.sp_core_page_size)
    mode = "full" if full else "normal"
    try:
        async with SessionLocal() as db:
            if not await try_lock(db):
                await db.rollback()
                return {"ok": False, "result": "busy", "error": "busy",
                        "detail": "이미 받는 중이다 — 끝난 뒤 다시 한다"}
            run_id = await _open_run(mode=mode, allow_shrink=allow_shrink, trigger=trigger,
                                     requested_by=requested_by)
            try:
                got = await sync_all(db, client, types=wanted_types(), full=full, allow_shrink=allow_shrink)
                # 층 2 — 사본 표만 읽어 이 플랫폼에 반영한다(식별자 바뀜 → 우리 개정 · 별칭). 멈춘 실행도 끝까지
                # 받은 흐름은 이미 사본에 있으므로 반영한다. ★저장점 안에서 — 반영이 깨져도 받은 것(층 1)은 남기고
                # 「확인 필요」 로 알린다(반영 결함 하나가 받기를 영영 막으면 안 된다).
                from app.modules.ontology import services as onto
                try:
                    async with db.begin_nested():
                        got["reflected"] = await onto.reflect_after_sync(db)
                except Exception as exc:               # noqa: BLE001
                    logger.exception("plm reflect failed")
                    got["reflected"] = {"error": f"{type(exc).__name__}: {exc}"}
                    got["problems"] = [*(got.get("problems") or []),
                                       f"층 2 반영 실패 — {type(exc).__name__}: {exc}"]
                    if got.get("result") == "ok":
                        got["result"] = "needs_check"      # ok 는 그대로 — 받기는 끝까지 돌았다(sync_all 과 같은 뜻)
                # 받은 것은 **커밋한다** — 멈춘 실행도 끝까지 받은 흐름의 기준 시각은 옮겨 둔다(다음 실행이 거기서 잇는다).
                await db.commit()
            except Exception as exc:                   # noqa: BLE001
                await db.rollback()
                logger.exception("plm sync failed")
                got = {"ok": False, "result": "failed", "error": "exception",
                       "detail": f"{type(exc).__name__}: {exc}"}
            await _close_run(run_id, got)
            got["run_id"] = run_id
    except Exception as exc:                           # noqa: BLE001 — 잠금 · 기록을 못 열었다
        logger.exception("plm sync could not start")
        return {"ok": False, "result": "failed", "error": "exception", "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        if owns:
            await client.close()
    if got.get("result") == "ok":
        counts = {k: v.get("rows", 0) for k, v in (got.get("types") or {}).items()}
        logger.info("plm sync ok — 판 %s · %s", got.get("revision"), counts)
    else:
        logger.warning("plm sync %s — %s", got.get("result"), got.get("error") or got.get("problems"))
    return got
