from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserRead
from app.modules.auth.services import authenticate
from app.shared.auth import get_current_user
from app.shared.responses import ok
from app.shared.security import create_access_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."
        )
    token = create_access_token(user.id)
    return ok(
        TokenResponse(access_token=token).model_dump(), message="로그인 성공"
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return ok(UserRead.model_validate(user).model_dump())
