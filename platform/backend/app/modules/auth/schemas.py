from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Shared field validators (reused by signup + admin user-create) ──────────
def normalize_email(v: str) -> str:
    """Strip + lowercase + reject obviously-malformed values. Permits internal
    reserved TLDs (e.g. `.local`); only enforces a basic local@domain.tld shape."""
    v = v.strip().lower()
    local, _, domain = v.partition("@")
    if not local or "." not in domain or " " in v:
        raise ValueError("유효한 이메일 형식이 아닙니다.")
    return v


def reject_blank_password(v: str) -> str:
    if not v.strip():
        raise ValueError("비밀번호는 공백만으로 구성할 수 없습니다.")
    return v


class LoginRequest(BaseModel):
    # Plain str (not EmailStr): login matches stored credentials; deliverability
    # validation belongs on registration, and internal accounts may use
    # reserved TLDs like `.local`.
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def _pw_not_blank(cls, v: str) -> str:
        return reject_blank_password(v)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        return reject_blank_password(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_active: bool = True
    is_system_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
