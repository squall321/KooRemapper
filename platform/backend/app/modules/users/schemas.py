from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TokenCreateRequest(BaseModel):
    name: str = Field(default="MCP 토큰", max_length=100)
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class TokenRead(BaseModel):
    id: int
    name: str
    token_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None

    @property
    def status(self) -> str:
        from datetime import timezone

        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc):
            return "expired"
        return "active"

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["status"] = self.status
        return d

    model_config = {"from_attributes": True}
