from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    PasswordChange,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from app.modules.auth.services import authenticate
from app.shared.auth import get_current_user
from app.shared.ratelimit import rate_limit
from app.shared.responses import ok
from app.shared.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/login", dependencies=[Depends(rate_limit("login", settings.ratelimit_login_per_min))])
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


@router.get("/auth/config")
async def auth_config():
    """Public: lets the login screen know whether signup is enabled."""
    return ok({"allow_signup": settings.allow_signup})


@router.post("/auth/signup", dependencies=[Depends(rate_limit("signup", settings.ratelimit_signup_per_min))])
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    if not settings.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "회원가입이 비활성화되어 있습니다.")
    email = body.email.strip().lower()
    exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 이메일입니다.")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
        is_system_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return ok(
        {"access_token": token, "user": UserRead.model_validate(user).model_dump()},
        message="가입 완료", status_code=201,
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return ok(UserRead.model_validate(user).model_dump())


@router.post("/me/password")
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "비활성 계정입니다.")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "현재 비밀번호가 올바르지 않습니다.")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    # data carries the message too so unwrap()-based clients receive it
    return ok(data="비밀번호가 변경되었습니다.", message="비밀번호가 변경되었습니다.")
