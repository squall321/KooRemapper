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
    # 덱이 **정의되지 않은 것을 가리켜도** 강행한다.
    #
    # ⚠ 기본이 **통과**다(2026-09-27 캠페인 결정). 검사 자체는 P1-6 이 돌연변이까지 태워 정확하고
    # 추적 덱 489장 중 40장이 실제로 이 부류지만, 실사용 덱에 몇 장이 걸리는지 아직 안 세어 봤다.
    # 첫날부터 막으면 멀쩡한 운용이 멈추고, 그러면 사람은 게이트를 통째로 끈다 — 그 뒤엔 진짜를
    # 놓친다. 그래서 **경고로 시작한다**: 잡 기록(`warnings`)과 세션 화면에 남기고 막지는 않는다.
    #
    # `false` 로 주면 막는 쪽이 켜진다(단정 등급만, 422). 실사용 숫자를 센 뒤 기본값을 뒤집는 것이
    # 다음 결정이다 — 그때 이 주석과 `docs/requests/deck-contract-checklist.md` 를 같이 고친다.
    allow_dangling_refs: bool = True


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
