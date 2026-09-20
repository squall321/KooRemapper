from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MCP_PUBLIC_URL_ENV, settings
from app.database import get_db
from app.models import User
from app.modules.users import pat
from app.modules.users.schemas import TokenCreateRequest, TokenRead
from app.shared.auth import get_current_user
from app.shared.ratelimit import rate_limit
from app.shared.responses import ok

router = APIRouter(tags=["tokens"])


def mcp_public_url(request: Request) -> str:
    """외부 클라이언트가 실제로 닿을 MCP 주소 — **설정에 없으면 빈 문자열이다(지어내지 않는다).**

    요청서 REQUEST-deploy-fixes-20260919 ④. 예전에는 셋을 차례로 시도했고 **셋 다 틀린 값을 냈다**
    (포털 쪽 dev 실측):

      · X-Forwarded-Host 파생 → 포털(:8088) 경유 시 **포트가 빠진다**(nginx 가 Host 를 포트 없이 넘긴다).
        HEAX Caddy(:4180) 경유면 `127.0.0.1:4180` 이라는 **내부 주소**가 나온다(trusted_proxies 가 없어
        Caddy 가 X-Forwarded-* 를 자기 Host 로 덮는다).
      · 루프백 폴백 → 원격 사용자에게 '틀렸는데 맞아 보이는' 주소다. 게다가 request.client 는 **TCP 상대**라,
        MCP 경유 호출은 사람이 어디 있든 늘 127.0.0.1 로 보인다 — 가드가 될 수 없다.

    그래서 **설정만 정본으로 삼는다.** 모르면 모른다고 말하고, 부르는 쪽이 무엇을 설정해야 하는지 알린다
    (형제 앱 StepForge D-272 와 같은 규율). 운영에서 증상을 없애려면 platform/.env 에
    `KOORM_MCP_PUBLIC_URL=https://<포털오리진:포트>/apps/kooremapper_mcp/mcp` 를 넣고 api 를 재기동한다.
    """
    return settings.mcp_public_url


MCP_URL_UNKNOWN = (
    f"# MCP 공개 주소를 서버가 모른다 — 운영자가 {MCP_PUBLIC_URL_ENV} 를 설정하면 "
    "여기에 붙여넣을 `claude mcp add` 명령이 나온다. (토큰은 이미 발급됐다)"
)


def mcp_add_command(request: Request, token: str) -> str:
    """`claude mcp add` 붙여넣기 명령 — 주소를 모르면 **명령을 만들지 않는다.**

    반쯤 맞는 명령을 주면 사용자가 그대로 붙여넣고 "연결이 안 된다" 로 돌아온다(cae00 실사고).
    URL 칸만 빈 명령도 같은 부류다 — claude 가 `--header` 값을 URL 로 먹는다.
    시스템 화면·토큰 화면·capabilities 가 **이 함수 하나**를 쓴다(요청서 ④ 고침 2).
    """
    url = mcp_public_url(request)
    if not url:
        return MCP_URL_UNKNOWN
    return (
        f"claude mcp add --transport http kooremapper "
        f"{url} "
        f'--header "Authorization: Bearer {token}"'
    )


def _mcp_add_snippet(plaintext: str, request: Request) -> str:
    """발급된 토큰이 박힌 붙여넣기 명령(토큰 화면 전용 이름 — 본체는 mcp_add_command)."""
    return mcp_add_command(request, plaintext)


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
