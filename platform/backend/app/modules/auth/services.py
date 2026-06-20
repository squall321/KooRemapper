from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.shared.security import verify_password


async def authenticate(db: AsyncSession, email: str, password: str) -> Optional[User]:
    # match the normalization used at signup/create (case-insensitive email)
    user = (
        await db.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        # fall back to exact match for legacy/seeded mixed-case emails
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
