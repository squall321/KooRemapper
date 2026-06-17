"""Personal Access Token issuance / listing / revocation.

Plaintext (`kr_...`) is returned only once at creation; the DB stores a sha256
hash. The auth resolver (app.shared.auth) matches by prefix + hash.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PersonalAccessToken
from app.shared.security import hash_pat, new_pat_plaintext


async def create_token(
    db: AsyncSession,
    user_id: int,
    name: str,
    *,
    expires_days: int | None = None,
) -> tuple[PersonalAccessToken, str]:
    if expires_days is None:
        expires_days = settings.pat_default_expires_days
    plaintext = new_pat_plaintext()
    now = datetime.now(timezone.utc)
    row = PersonalAccessToken(
        user_id=user_id,
        name=(name or "MCP 토큰").strip()[:100],
        token_prefix=plaintext[:12],  # kr_ + 8 chars (display only)
        token_hash=hash_pat(plaintext),
        expires_at=(now + timedelta(days=expires_days)) if expires_days else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row, plaintext


async def list_tokens(db: AsyncSession, user_id: int) -> list[PersonalAccessToken]:
    return list(
        (
            await db.execute(
                select(PersonalAccessToken)
                .where(PersonalAccessToken.user_id == user_id)
                .order_by(PersonalAccessToken.id.desc())
            )
        ).scalars()
    )


async def revoke_token(db: AsyncSession, user_id: int, token_id: int) -> bool:
    row = await db.get(PersonalAccessToken, token_id)
    if row is None or row.user_id != user_id:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return True
