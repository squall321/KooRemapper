from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("새 비밀번호가 비어 있습니다.")
        return v


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
