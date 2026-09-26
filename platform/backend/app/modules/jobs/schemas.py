from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobCreate(BaseModel):
    operation: str
    args: dict = {}
    # 덱이 참조하는 `*INCLUDE` 가 세션에 없어도 강행한다. 기본은 막는 쪽이다 — op 은 인클루드를
    # 읽지 않아 성공하지만 산출물에 그 줄이 보존돼, LS-DYNA 에 넣을 때야 깨진 것이 드러난다.
    # 인클루드를 클러스터에 따로 두는 운용을 위해 남겨 둔 탈출구다.
    allow_missing_includes: bool = False
    # 덱이 **정의되지 않은 것을 가리켜도** 강행한다. 기본은 막는 쪽이다 — `info` 는 그것을
    # 보고만 하고 rc=0 으로 끝내므로(그 rc 는 계약이다) 하류는 알 방법이 없고 LS-DYNA 가
    # 키워드 단계에서 죽는다. 단정 등급만 막는다(인클루드를 못 읽었으면 단정하지 않는다).
    allow_dangling_refs: bool = False


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
    warnings: list | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
