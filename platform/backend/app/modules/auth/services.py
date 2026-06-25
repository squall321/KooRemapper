from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.shared.security import hash_password, verify_password

# Precomputed once at import: when no (active) user is found we still run a real
# argon2 verify against this so response time does not reveal whether the account
# exists / is active (CWE-208 user-enumeration via login timing).
_DUMMY_HASH = hash_password("constant-time-placeholder")


async def authenticate(db: AsyncSession, email: str, password: str) -> Optional[User]:
    # match the normalization used at signup/create (case-insensitive email)
    norm = email.strip().lower()
    user = (await db.execute(select(User).where(User.email == norm))).scalar_one_or_none()
    if user is None and norm != email:
        # fall back to exact match for legacy/seeded mixed-case emails — only when
        # normalization changed the value, to avoid a redundant query (and the
        # extra timing variance it would add).
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        verify_password(password, _DUMMY_HASH)  # constant-time: don't leak existence
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
