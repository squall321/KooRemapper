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
    # 덱 판 라벨 · 연결된 CAD(DF-15) — 보낸 칸만 맞춘다(null 은 지운다)
    deck_revision_label: str | None = Field(default=None, min_length=1, max_length=64)
    linked_cad: "LinkedCad | None" = None
    # 허브 과제 · 개발 단계(자동 파이프라인 KR-AP1 · 사용자 결정 11-27) — 보낸 칸만 맞춘다(null 은 지운다). 과제는 과제명 · 과제코드 ·
    # 옛 과제명 · 별칭 무엇이든 — 판 확정과 같은 규칙으로 풀어 과제명을 남기고 못 풀면 거절한다. 개발 단계는 dev_rev 꼴
    task_key: str | None = Field(default=None, min_length=1, max_length=300)
    dev_rev: str | None = Field(default=None, min_length=1, max_length=8)


class LinkedCad(BaseModel):
    """연결된 CAD — StepForge 과제 id · 판(DF-15)."""

    model_config = {"extra": "forbid"}
    project_id: str = Field(min_length=1, max_length=128)
    revision: str | None = Field(default=None, min_length=1, max_length=64)


class PartRename(BaseModel):
    """덱 파일의 *PART 제목 바꾸기(DF-15)."""

    model_config = {"extra": "forbid"}
    file_id: int = Field(gt=0)
    title: str = Field(max_length=70)


class SessionRead(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    visibility: str = "private"
    deck_revision_label: str | None = None
    linked_cad: dict | None = None
    task_key: str | None = None
    dev_rev: str | None = None
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


SessionUpdate.model_rebuild()
