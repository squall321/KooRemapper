"""Centralized exception handlers — every error returns the standard envelope."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.responses import fail

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_req: Request, exc: StarletteHTTPException):
        return fail(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_req: Request, exc: RequestValidationError):
        return fail("요청 형식이 올바르지 않습니다.", status_code=422, errors=exc.errors())

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        logger.exception("Unhandled error")
        return fail("서버 내부 오류가 발생했습니다.", status_code=500)
