from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.users import pat
from app.modules.users.schemas import TokenCreateRequest, TokenRead
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["tokens"])


def _mcp_add_snippet(plaintext: str) -> str:
    """Ready-to-paste `claude mcp add` command for the issued token."""
    port = settings.mcp_port
    return (
        f"claude mcp add --transport http kooremapper "
        f"http://127.0.0.1:{port}/mcp "
        f'--header "Authorization: Bearer {plaintext}"'
    )


@router.get("/me/tokens")
async def list_my_tokens(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await pat.list_tokens(db, user.id)
    return ok([TokenRead.model_validate(r).to_dict() for r in rows])


@router.post("/me/tokens")
async def create_my_token(
    body: TokenCreateRequest,
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
            "mcp_add": _mcp_add_snippet(plaintext),
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
