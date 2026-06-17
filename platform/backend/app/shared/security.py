"""Password hashing (argon2) + JWT encode/decode + PAT helpers."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt

from app.config import settings

_ph = PasswordHasher()

PAT_PREFIX = "kr_"  # KooRemapper token — distinguishes PAT from JWT


# ── passwords ───────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# ── JWT ─────────────────────────────────────────────────────────────
def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ── PAT ─────────────────────────────────────────────────────────────
def new_pat_plaintext() -> str:
    return PAT_PREFIX + secrets.token_urlsafe(32)


def hash_pat(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
