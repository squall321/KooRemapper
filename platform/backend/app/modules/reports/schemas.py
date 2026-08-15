# 리포트 인제스트/조회 API의 Pydantic 응답 스키마.
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: str
    session_id: str
    kind: str
    label: str | None
    source_file_id: int | None
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
    project_name: str | None
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
