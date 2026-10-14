# 허브 코어 API 에서 기준정보를 **주기로 받는** 워커 쪽 — 설정이 비면 아무것도 하지 않는다
"""왜 잡이 아니라 주기 작업인가 — `Job` 은 세션에 매달린다(`session_id`·`user_id`). 기준정보
수신은 **세션의 일이 아니다.** 억지로 잡으로 만들면 "누구의 세션에서 돌린 동기화인가" 라는
답할 필요 없는 질문이 생기고, 세션을 지우면 이력이 함께 사라진다.

그래서 외부 잡 스캔(`runner_loop._poll_external_once`)과 **같은 자리·같은 모양**으로 둔다 —
시간 기준이고, 실패가 워커를 멈추지 않는다.

**기본은 꺼짐이다**(`sp_core_sync_sec=0`). 허브가 아직 없으므로 주기적으로 두드리면 로그가
실패로 가득 차고 **진짜 실패가 그 속에 묻힌다.**
"""
from __future__ import annotations

import logging

from app.config import settings
from app.database import SessionLocal
from app.runner.sp_core import SpCoreClient, sync_all

logger = logging.getLogger("koorm.worker")


def enabled() -> bool:
    """주소·토큰·간격이 **모두** 있어야 돈다. 하나라도 비면 꺼진 것이다."""
    return bool(settings.sp_core_url.strip() and settings.sp_core_token.strip()
                and settings.sp_core_sync_sec > 0)


def wanted_types() -> list[str] | None:
    """받을 타입. `None` 이면 **허브가 공개한 것 전부**다.

    목록을 코드에 박지 않는 것이 요점이다 — 허브에 타입이 늘어도 우리를 고치지 않는다
    (수신 규칙 5 와 같은 자세). 공개 안 된 것을 달라고 하면 `sync_all` 이 거절한다.
    """
    return None


async def sync_once(*, full: bool = False, client: SpCoreClient | None = None) -> dict:
    """한 번 받는다. 실패를 예외로 올리지 않는다 — 워커가 이것 때문에 멈추면 안 된다.

    `client` 는 시험이 넣는다(MockTransport 를 실은 것) — 이 리포가 `StcxClient`·
    `McpHttpClient` 에서 쓰는 것과 같은 구멍이다. 망 없이 계약을 고정하려면 필요하다.
    """
    if not enabled():
        return {"ok": False, "error": "disabled",
                "detail": "KOORM_SP_CORE_URL/TOKEN/SYNC_SEC 중 비어 있는 것이 있다"}
    owns = client is None
    client = client or SpCoreClient(settings.sp_core_url, settings.sp_core_token,
                                    page_size=settings.sp_core_page_size)
    try:
        async with SessionLocal() as db:
            got = await sync_all(db, client, types=wanted_types(), full=full)
            # 받은 것은 **커밋한다** — 중간에 실패한 타입이 있어도 성공한 타입은 남는다.
            # 전부-아니면-무로 묶으면 타입 하나가 막힐 때 나머지가 영영 안 들어온다.
            await db.commit()
    except Exception as exc:                       # noqa: BLE001
        logger.exception("plm sync failed")
        return {"ok": False, "error": "exception", "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        if owns:
            await client.close()
    if got.get("ok"):
        counts = {k: v.get("rows", 0) for k, v in (got.get("types") or {}).items()}
        logger.info("plm sync ok — 판 %s · %s", got.get("revision"), counts)
    else:
        logger.warning("plm sync 일부 실패 — %s", got.get("error") or got.get("types"))
    return got
