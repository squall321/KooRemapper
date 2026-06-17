from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobCreate(BaseModel):
    operation: str
    args: dict = {}


class JobRead(BaseModel):
    id: str
    session_id: str
    operation: str
    args: dict
    resolved_cmd: dict | None
    status: str
    progress: int | None
    exit_code: int | None
    input_file_ids: list | None
    output_file_ids: list | None
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
