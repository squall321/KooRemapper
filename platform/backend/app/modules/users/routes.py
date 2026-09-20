from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.users import pat
from app.modules.users.schemas import TokenCreateRequest, TokenRead
from app.shared.auth import get_current_user
from app.shared.ratelimit import rate_limit
from app.shared.responses import ok

router = APIRouter(tags=["tokens"])


def mcp_public_url(request: Request) -> str:
    """외부 클라이언트가 실제로 닿을 MCP 주소 — **모르면 빈 문자열이다(지어내지 않는다).**

    포털/허브 프록시 경유 요청(X-Forwarded-* 존재)이면 그 오리진의 고정 라우트
    /apps/kooremapper_mcp/mcp 가 정답이다 — raw host:port(8701)는 사외 PC 에서
    안 닿는다(cae00 실사고: 힌트대로 등록하면 연결 불가). 설정이 있으면 그것이 정본.

    ⚠ 예전에는 마지막 폴백이 `http://127.0.0.1:<port>/mcp` 였다. 그 주소는 **이 서버에서 볼 때만**
    참이라, 프록시를 안 거치고 직접 붙은 **원격** 사용자에게는 '틀렸는데 맞아 보이는' 주소가 된다
    (붙여넣으면 자기 PC 의 8701 을 찌른다). 그래서 호출자가 루프백일 때만 그 값을 주고, 그 밖에는
    **모른다고 말한다** — 부르는 쪽이 빈 값을 보고 "운영자가 MCP_PUBLIC_URL 을 설정해야 한다" 고
    안내한다. 주소를 지어내는 것보다 모른다고 하는 편이 언제나 낫다.
    """
    if settings.mcp_public_url:
        return settings.mcp_public_url
    fwd_host = request.headers.get("x-forwarded-host")
    if fwd_host:
        proto = request.headers.get("x-forwarded-proto") or "http"
        return f"{proto}://{fwd_host}/apps/kooremapper_mcp/mcp"
    client = (request.client.host if request.client else "") or ""
    if client in {"127.0.0.1", "::1", "localhost"}:
        return f"http://127.0.0.1:{settings.mcp_port}/mcp"
    return ""


MCP_URL_UNKNOWN = (
    "# MCP 공개 주소를 서버가 모른다 — 운영자가 MCP_PUBLIC_URL 을 설정하면 "
    "여기에 붙여넣을 `claude mcp add` 명령이 나온다. (토큰은 이미 발급됐다)"
)


def _mcp_add_snippet(plaintext: str, request: Request) -> str:
    """Ready-to-paste `claude mcp add` command for the issued token.

    주소를 모르면 **명령을 만들지 않는다** — 반쯤 맞는 명령을 주면 사용자가 그대로 붙여넣고
    "연결이 안 된다" 로 돌아온다(cae00 실사고가 그 모양이었다)."""
    url = mcp_public_url(request)
    if not url:
        return MCP_URL_UNKNOWN
    return (
        f"claude mcp add --transport http kooremapper "
        f"{url} "
        f'--header "Authorization: Bearer {plaintext}"'
    )


@router.get("/me/tokens")
async def list_my_tokens(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await pat.list_tokens(db, user.id)
    return ok([TokenRead.model_validate(r).to_dict() for r in rows])


@router.post(
    "/me/tokens",
    dependencies=[Depends(rate_limit("token", settings.ratelimit_token_per_min))],
)
async def create_my_token(
    body: TokenCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """발급. 평문(`token`)은 이 응답에서 **1회만** 노출된다(이후 조회 불가)."""
    row, plaintext = await pat.create_token(
        db, user.id, body.name, expires_days=body.expires_days
    )
    return ok(
        {
            "token": plaintext,
            "info": TokenRead.model_validate(row).to_dict(),
            "mcp_add": _mcp_add_snippet(plaintext, request),
        },
        message="토큰이 발급되었습니다. 이 값은 다시 표시되지 않습니다.",
        status_code=201,
    )


@router.delete("/me/tokens/{token_id}")
async def revoke_my_token(
    token_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await pat.revoke_token(db, user.id, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "토큰을 찾을 수 없습니다.")
    return ok(message="토큰이 취소되었습니다.")
