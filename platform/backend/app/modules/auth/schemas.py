from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    # Plain str (not EmailStr): login matches stored credentials; deliverability
    # validation belongs on registration, and internal accounts may use
    # reserved TLDs like `.local`.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_system_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
