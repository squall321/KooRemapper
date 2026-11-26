# 진행 중 올리기(multipart 본문을 받는 요청) 수를 세는 ASGI 미들웨어 — stop · 재기동 스크립트가 그 수가 0 이 될 때까지 기다린다
"""운영 11-26 — 재기동 때 올리던 파일 1건이 끊겼다(500). 사용자 결정 「수를 보이고 재기동이 기다린다」(포털 요청 1125 뒤따름).

API 는 내려갈 때 진행 중 요청을 5초만 기다린다(api.sif 의 uvicorn `--timeout-graceful-shutdown 5`) — 그보다 긴 올리기는 끊긴다.
그래서 이 수를 `/api/health` 의 `uploads_in_flight` 로 내고, stop 을 부르는 쪽(`_common.sh` 의 `wait_uploads_drained`)이 0 이 될
때까지 기다린다. uvicorn 일꾼이 하나라 프로세스 안의 수로 충분하다(이벤트 루프 하나 — 잠금이 필요 없다).

세는 것은 API 가 받고 있거나 처리하는 multipart 요청이다. 앞단 프록시가 본문을 다 받은 뒤에 넘기면(nginx 기본
`proxy_request_buffering on`) 그 전송 구간은 여기서 보이지 않는다.
"""
from __future__ import annotations

_count = 0


def uploads_in_flight() -> int:
    return _count


def _is_upload(scope) -> bool:
    if scope.get("method") not in ("POST", "PUT", "PATCH"):
        return False
    for name, value in scope.get("headers") or ():
        if name == b"content-type":
            return value[:10].lower() == b"multipart/"
    return False


class UploadCounter:
    """`app.add_middleware(UploadCounter)` — 요청이 끝나면(예외 · 끊김 포함) 줄인다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not _is_upload(scope):
            await self.app(scope, receive, send)
            return
        global _count
        _count += 1
        try:
            await self.app(scope, receive, send)
        finally:
            _count -= 1
