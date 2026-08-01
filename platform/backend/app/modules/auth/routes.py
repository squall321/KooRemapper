from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


@router.post("/auth/sso", dependencies=[Depends(rate_limit("sso", settings.ratelimit_login_per_min))])
async def sso_login(request: Request, db: AsyncSession = Depends(get_db)):
    """HEAX Portal 게이트웨이 SSO — 신뢰된 프록시 헤더로 자동 로그인(JIT 프로비저닝).

    신뢰 근거는 게이트웨이 공유 시크릿(X-Heax-Gateway-Secret)이다. 이 시크릿은
    HEAXHub Caddy 가 portal_auth 프록시 라우트에서만 주입하며, 직접 접근(:8700/:8443)
    경로는 값을 모르고, 프록시 경로에선 Caddy 의 header set 이 클라이언트 위조
    헤더를 덮어쓴다. KOORM_HEAX_GATEWAY_SECRET 미설정 시 이 엔드포인트는 닫힌다.
    """
    secret = settings.heax_gateway_secret
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO가 구성되어 있지 않습니다.")
    provided = request.headers.get("x-heax-gateway-secret", "")
    if not hmac.compare_digest(provided, secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "게이트웨이 검증 실패.")
    email = (request.headers.get("x-heax-user-email") or "").strip().lower()
    if not email or "@" not in email:
        # 익명 공개앱 통과(포탈 미로그인) — 자동 로그인 대상 아님.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "포탈 로그인 정보가 없습니다.")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        # JIT 프로비저닝 — 비밀번호 로그인 불가 계정(무작위 해시 placeholder).
        display = (request.headers.get("x-heax-user-name") or "").strip() or None
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            display_name=display,
            is_active=True,
            is_system_admin=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "비활성화된 계정입니다.")
    token = create_access_token(user.id)
    return ok(TokenResponse(access_token=token).model_dump(), message="SSO 로그인 성공")


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
    # get_current_user already rejects inactive users (401), so no is_active check here.
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "현재 비밀번호가 올바르지 않습니다.")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    # data carries the message too so unwrap()-based clients receive it
    return ok(data="비밀번호가 변경되었습니다.", message="비밀번호가 변경되었습니다.")
