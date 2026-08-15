"""ORM models for the KooRemapper Platform.

Kept in a single module (small schema) — users, PAT, sessions, files, jobs.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_system_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tokens: Mapped[list["PersonalAccessToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class PersonalAccessToken(Base):
    __tablename__ = "personal_access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)  # display: kr_ + 8
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="tokens")


class Session(Base):
    """A 'project' — a group of uploaded/generated LS-DYNA files."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # rel to storage_dir
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    files: Mapped[list["SessionFile"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class SessionFile(Base):
    __tablename__ = "session_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # rel to session dir
    kind: Mapped[str] = mapped_column(String(16), default="input", nullable=False)  # input|output|generated
    origin_job_id: Mapped[str | None] = mapped_column(String(26), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSONB)  # info parse: nodes/elems/parts/bbox/includes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="files")


class ImpactReport(Base):
    """A structured drop/impact study ingested from a koo_*_report HTML.

    kind ∈ {deep, sphere, impact}. Study-level fields live here; per-case metrics
    live in ``impact_cases`` (promoted rollup columns there enable cheap ranking).
    """

    __tablename__ = "impact_reports"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(12), index=True, nullable=False)  # deep|sphere|impact
    label: Mapped[str | None] = mapped_column(String(255))
    # 원본 HTML 을 담은 SessionFile — 온디맨드 시계열 재파싱용. 삭제돼도 리포트는 유지.
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_files.id", ondelete="SET NULL"), index=True
    )
    generator: Mapped[str | None] = mapped_column(String(40))
    generator_version: Mapped[str | None] = mapped_column(String(40))
    schema_str: Mapped[str | None] = mapped_column(String(64))
    project_name: Mapped[str | None] = mapped_column(String(255))
    doe_strategy: Mapped[str | None] = mapped_column(String(64))
    test_dir: Mapped[str | None] = mapped_column(String(1024))
    sim_params: Mapped[dict | None] = mapped_column(JSONB)
    parts: Mapped[list | None] = mapped_column(JSONB)  # [{part_id,name,group}]
    findings: Mapped[list | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)  # 전역 최악 롤업
    n_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    cases: Mapped[list["ImpactCase"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )


class ImpactCase(Base):
    """One case of a study: deep=single, sphere=per-angle, impact=per face×position."""

    __tablename__ = "impact_cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("impact_reports.id", ondelete="CASCADE"), index=True, nullable=False
    )
    case_key: Mapped[str] = mapped_column(String(255), nullable=False)
    identity: Mapped[dict | None] = mapped_column(JSONB)  # sphere: angle{}, impact: face+pos
    num_states: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool | None] = mapped_column(Boolean)
    parts_metrics: Mapped[dict | None] = mapped_column(JSONB)  # {pid: {peak_*}}
    # 랭킹 정렬용 승격 컬럼 (케이스 롤업).
    max_stress: Mapped[float | None] = mapped_column(Float)
    max_g: Mapped[float | None] = mapped_column(Float)
    max_disp: Mapped[float | None] = mapped_column(Float)
    min_safety_factor: Mapped[float | None] = mapped_column(Float)

    report: Mapped[ImpactReport] = relationship(back_populates="cases")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    args: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    resolved_cmd: Mapped[dict | None] = mapped_column(JSONB)  # argv + generated yaml
    status: Mapped[str] = mapped_column(
        String(12), default="queued", index=True, nullable=False
    )  # queued|running|succeeded|failed|canceled
    progress: Mapped[int | None] = mapped_column(SmallInteger)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout_path: Mapped[str | None] = mapped_column(String(1024))
    stderr_path: Mapped[str | None] = mapped_column(String(1024))
    input_file_ids: Mapped[list | None] = mapped_column(JSONB)
    output_file_ids: Mapped[list | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
