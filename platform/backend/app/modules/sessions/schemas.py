from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    # 공개 범위 — 소유자만 바꿀 수 있다(라우터가 _require_session 으로 이미 강제).
    visibility: str | None = Field(default=None, pattern="^(company|department|team|private)$")


class SessionRead(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    visibility: str = "private"
    created_at: datetime
    updated_at: datetime
    file_count: int | None = None

    model_config = {"from_attributes": True}


class FileRead(BaseModel):
    id: int
    session_id: str
    filename: str
    kind: str
    origin_job_id: str | None
    size_bytes: int
    sha256: str | None
    meta: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
