"""System-admin user management (require_system_admin)."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Session as SessionModel
from app.models import User
from app.modules.auth.schemas import UserRead, normalize_email, reject_blank_password
from app.shared.auth import require_system_admin
from app.shared.responses import ok
from app.shared.security import hash_password

router = APIRouter(tags=["admin"], dependencies=[Depends(require_system_admin)])


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    is_system_admin: bool = False

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def _pw_not_blank(cls, v: str) -> str:
        return reject_blank_password(v)


class UserPatch(BaseModel):
    is_active: bool | None = None
    is_system_admin: bool | None = None
    display_name: str | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _pw_not_blank(cls, v: str) -> str:
        return reject_blank_password(v)


async def _remaining_active_admins(db: AsyncSession, exclude_id: int) -> int:
    return (
        await db.execute(
            select(func.count(User.id)).where(
                User.is_system_admin.is_(True),
                User.is_active.is_(True),
                User.id != exclude_id,
            )
        )
    ).scalar_one()


@router.get("/admin/users")
async def list_users(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(User).order_by(User.id).limit(limit).offset(offset))
    ).scalars()
    out = []
    for u in rows:
        cnt = (
            await db.execute(
                select(func.count(SessionModel.id)).where(SessionModel.user_id == u.id)
            )
        ).scalar_one()
        d = UserRead.model_validate(u).model_dump()
        d["session_count"] = cnt
        out.append(d)
    return ok(out)


@router.post("/admin/users")
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 이메일입니다.")
    u = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
        is_system_admin=body.is_system_admin,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return ok(UserRead.model_validate(u).model_dump(), message="사용자 생성됨", status_code=201)


@router.patch("/admin/users/{user_id}")
async def patch_user(
    user_id: int, body: UserPatch,
    actor: User = Depends(require_system_admin), db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다.")
    # Removing this user's admin access (deactivate or demote) must not drop the
    # number of active system admins to zero — otherwise the /admin surface locks
    # out entirely. The self-guard above already covers the single-actor case;
    # this also covers concurrent mutual-demotion by two admins.
    removes_admin_access = (
        u.is_system_admin and u.is_active
        and (body.is_active is False or body.is_system_admin is False)
    )
    if removes_admin_access and await _remaining_active_admins(db, u.id) == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "마지막 시스템 관리자는 비활성화/권한 해제할 수 없습니다."
        )
    if body.is_active is not None:
        if u.id == actor.id and body.is_active is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "자기 계정은 비활성화할 수 없습니다.")
        u.is_active = body.is_active
    if body.is_system_admin is not None:
        if u.id == actor.id and body.is_system_admin is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "자기 관리자 권한은 해제할 수 없습니다.")
        u.is_system_admin = body.is_system_admin
    if body.display_name is not None:
        u.display_name = body.display_name
    await db.commit()
    await db.refresh(u)
    return ok(UserRead.model_validate(u).model_dump(), message="수정됨")


@router.post("/admin/users/{user_id}/password")
async def reset_password(
    user_id: int, body: PasswordReset, db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다.")
    u.password_hash = hash_password(body.new_password)
    await db.commit()
    return ok(message="비밀번호가 재설정되었습니다.")
