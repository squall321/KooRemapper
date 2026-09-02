# 리포트 인제스트/조회 API의 Pydantic 응답 스키마.
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: str
    session_id: str
    kind: str
    label: str | None
    focus: str | None = None             # 초점 라벨(camera-detail 등)
    source_file_id: int | None
    source_kfile_id: int | None = None   # 원본 K파일(1 K : N 리포트)
    scenario_file_id: int | None = None  # 원본 scenario.json
    scenario: dict | None = None         # 시뮬 조건 요약
    scenario_type: str | None = None     # 방향 조건 종류(cuboid_geometry 등)
    eng_meta: dict | None = None         # 과제/rev 수동 메타
    doe_strategy: str | None = None      # 방향 컨셉(cuboid_26 등)
    drop_height: float | None = None
    worst_stress: float | None = None
    worst_g: float | None = None
    max_severity: str | None = None
    generator: str | None
    generator_version: str | None
    project_name: str | None
    doe_strategy: str | None
    test_dir: str | None
    sim_params: dict | None
    parts: list | None
    findings: list | None
    summary: dict | None
    n_cases: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListItem(BaseModel):
    id: str
    kind: str
    label: str | None
    focus: str | None = None
    project_name: str | None
    doe_strategy: str | None = None
    scenario_type: str | None = None
    drop_height: float | None = None
    worst_stress: float | None = None
    max_severity: str | None = None
    source_kfile_id: int | None = None
    eng_meta: dict | None = None
    n_cases: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseRead(BaseModel):
    id: int
    report_id: str
    case_key: str
    identity: dict | None
    num_states: int | None
    success: bool | None
    parts_metrics: dict | None
    max_stress: float | None
    max_g: float | None
    max_disp: float | None
    min_safety_factor: float | None

    model_config = {"from_attributes": True}
