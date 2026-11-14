# 오류를 밖으로 내보내는 꼴 — 표준 봉투 예외 처리기 · 응답과 원장에 싣는 짧은 오류 글(short_error)
"""Centralized exception handlers — every error returns the standard envelope.

⚠ 상관자를 **contextvar 가 아니라 `request.state` 에서** 읽는다. 이유를 적어 둔다 —
`@app.exception_handler(Exception)` 은 Starlette 이 `ServerErrorMiddleware` 로 옮겨 달며, 그것은
사용자 미들웨어보다 **바깥**이다. 그래서 라우트가 터지면 (1) 상관자 미들웨어의 응답 후처리가
아예 실행되지 않아 `X-Request-Id` 헤더가 안 붙고, (2) 그 미들웨어의 `finally` 가 먼저 돌아
contextvar 가 이미 `-` 로 돌아간 뒤에 이 핸들러가 로그를 찍었다. 실측 — `/boom` 이 500 을 낼 때
헤더는 `None` 이고 로그는 `ERROR app.shared.errors [-] Unhandled error` 였다. **상관자가 필요한
바로 그 경우에 상관자가 없었다.** `request.state` 는 미들웨어가 요청 진입 때 채우므로 살아 있다.
"""
from __future__ import annotations

import logging
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import StatementError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.logctx import NONE
from app.shared.responses import fail

logger = logging.getLogger(__name__)


def correlator_of(req: Request) -> str:
    """이 요청의 상관자. 미들웨어가 `request.state` 에 넣어 둔다."""
    try:
        return getattr(req.state, "correlator", NONE) or NONE
    except Exception:
        return NONE


def _with_corr(headers: dict | None, corr: str) -> dict:
    """응답에 `X-Request-Id` 를 싣는다 — 사용자가 넘길 수 있는 유일한 끈이다."""
    out = dict(headers or {})
    out.setdefault("X-Request-Id", corr)
    return out


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(req: Request, exc: StarletteHTTPException):
        # preserve headers (e.g. Retry-After / X-RateLimit-* from 429, WWW-Authenticate from 401)
        corr = correlator_of(req)
        return fail(str(exc.detail), status_code=exc.status_code,
                    headers=_with_corr(getattr(exc, "headers", None), corr))

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(req: Request, exc: RequestValidationError):
        corr = correlator_of(req)
        return fail("요청 형식이 올바르지 않습니다.", status_code=422, errors=exc.errors(),
                    headers=_with_corr(None, corr))

    @app.exception_handler(Exception)
    async def _unhandled(req: Request, exc: Exception):
        corr = correlator_of(req)
        # ⚠ 상관자와 **경로·메서드**를 함께 적는다. 이 핸들러가 도는 경우에는 상관자 미들웨어의
        # 요청 줄이 찍히지 않으므로(위 주석), 이 한 줄이 그 실패의 유일한 기록이다.
        logger.exception("Unhandled error [%s] %s %s", corr, req.method, req.url.path)
        return fail(
            "서버 내부 오류가 발생했습니다. 진단 번호 %s 를 알려 주세요." % corr,
            status_code=500,
            headers=_with_corr(None, corr),
        )


# ── 응답 · 원장에 싣는 짧은 오류 글 ───────────────────────────────────────────────
# 코어 다리(reports/bridges.py)에서 처음 썼고, 과제 잇기(ontology) · 7-1 스캔이 두 번째 · 세 번째 소비자라 여기로 옮겼다(재검토 11-12).
# `bridges.short_error` 는 이것을 다시 내보낸다(부르는 쪽이 그대로 쓴다).

# 응답 · 원장에 싣지 않는 줄 — SQL 문 · 매개변수 · DETAIL(값이 든다) · 배경 링크 · autoflush 안내
_NOISE = ("[SQL", "[parameters", "DETAIL:", "(Background on this error", "(raised as a result of Query-invoked autoflush")


def short_error(exc: BaseException, limit: int = 300) -> str:
    """응답 · 원장에 싣는 오류의 짧은 꼴 — 「클래스: 한 줄」(`limit` 자 안). SQL 문 · 매개변수 · DETAIL · 배경 링크는 싣지 않는다 —
    전문은 서버 로그(`logger.exception`)에 남긴다. 예전에는 SQLAlchemy 오류 전문(약 1.6 KB — 문장과 값까지)이 API 응답 · 7-1 원장 ·
    받기 기록에 실렸다(검토 2차 11-11 항목 7 · 재검토 11-12)."""
    inner = exc.orig if isinstance(exc, StatementError) and exc.orig is not None else None   # 드라이버 오류 — 문장 없이 까닭만
    text = str(inner if inner is not None else exc)
    line = next((ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(_NOISE)), "")
    line = re.sub(r"\s*\(Background on this error at: [^)]*\)\s*$", "", line)
    m = re.match(r"<class '(?:[\w.]+\.)?(\w+)'>:\s*(.*)", line)     # asyncpg 어댑터 꼴 「<class 'asyncpg…Error'>: 까닭」
    if m:
        line = m.group(2) if m.group(1) == type(exc).__name__ else f"{m.group(1)}: {m.group(2)}"
    return (f"{type(exc).__name__}: {line}" if line else type(exc).__name__)[:limit]
