"""Idempotent seed — ensures a system-admin user exists.

Run inside the api image: `python -m app.seed`.
Credentials from KOORM_ADMIN_EMAIL / KOORM_ADMIN_PASSWORD (default admin@local / admin).
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.shared.security import hash_password


async def _seed() -> None:
    email = os.environ.get("KOORM_ADMIN_EMAIL", "admin@kooremapper.local")
    password = os.environ.get("KOORM_ADMIN_PASSWORD", "admin")
    async with SessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing:
            print(f"✓ admin already exists: {email}")
            return
        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                display_name="Administrator",
                is_active=True,
                is_system_admin=True,
            )
        )
        await db.commit()
        print(f"✓ created system-admin: {email}")


if __name__ == "__main__":
    asyncio.run(_seed())
