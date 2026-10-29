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
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
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
    # 소속 — 세션 가시성의 department/team 판정에 쓴다. 포털/SSO 가 주는 값을 그대로 받고
    # 정규화는 값이 쌓인 뒤에. 빈 값끼리는 매칭되지 않는다(미설정끼리 보이면 사고다).
    department: Mapped[str | None] = mapped_column(String(120))
    team: Mapped[str | None] = mapped_column(String(120))
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
    # 공개 범위 — company|department|team|private (HEAX Hub 와 같은 4단).
    # 기본 private: 만들어 두기만 한 세션이 조직에 노출되지 않는다. 넓히는 것은 소유자의 명시 행위.
    visibility: Mapped[str] = mapped_column(
        String(16), default="private", server_default="private", index=True, nullable=False
    )
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
    rel_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # rel to the storage root, not the session dir
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
    # 읽기 공유 범위 — 반입(예약) 시점에 검증한 소속 id 를 **얼려서** 적는다.
    # 소유자가 나중에 소속을 옮겨도 과거 리포트의 공유 범위가 따라 움직이면, 그 리포트를 근거로 한
    # 비교·보고가 조용히 달라진다(요청서 §8). 읽는 사람의 소속은 요청마다 새로 검증한다.
    shared_affiliation: Mapped[str | None] = mapped_column(String(120), index=True)
    label: Mapped[str | None] = mapped_column(String(255))
    # 원본 HTML 을 담은 SessionFile — 온디맨드 시계열 재파싱용. 삭제돼도 리포트는 유지.
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_files.id", ondelete="SET NULL"), index=True
    )
    # 이 결과를 만든 원본 K파일(SessionFile) — 한 K에 여러 리포트가 매달린다(1:N).
    # scenario.json 의 template 파일명으로 자동 매칭되거나 수동 지정.
    source_kfile_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_files.id", ondelete="SET NULL"), index=True
    )
    # 시뮬레이션 조건 — 원본 scenario.json 은 SessionFile(kind=scenario)로 보관하고,
    # 여기엔 조건 요약(angle_source/tolerance/height 등)만 캐시한다.
    scenario_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_files.id", ondelete="SET NULL")
    )
    scenario: Mapped[dict | None] = mapped_column(JSONB)
    # 결과 이미지 — 번들로 함께 반입한 그림·영상. `[{path, file_id, kind, role, case_key,
    # set_name, bytes, can_llm_view}]`. ★`can_llm_view` 로 png/jpeg/gif/webp 와 mp4 를 가른다:
    # 모델은 영상을 못 본다. 매핑 정본은 리포트 자신(`set_report.media`)이고, 선언이 없는 종류
    # (deep)는 케이스에 묶지 않고 목록으로만 둔다 — 파일명으로 추측한 매핑은 틀려도 그럴듯하다.
    media: Mapped[list | None] = mapped_column(JSONB)
    # 렌더 기록 — SceneForge 렌더 결과(C-11)마다 한 줄(render_id · ok · 까닭 · 경고 · 받은 시각 · 출력 sha).
    # 성공한 렌더의 그림은 위 `media` 에 **더하고**(role render · render_id), 실패는 여기에만 남긴다.
    renders: Mapped[list | None] = mapped_column(JSONB)
    # 과제/개발단계 수동 메타 — {project, dev_revision:{phase,round?}, design_variation?, doe?}.
    # DataHub 등재 폼의 기본값으로도 쓰인다.
    eng_meta: Mapped[dict | None] = mapped_column(JSONB)
    # 리포트 초점/변형 라벨(수동) — 같은 전각도라도 "카메라 디테일"·"코너 정밀" 등 초점이
    # 다른 리포트를 구분·검색하기 위한 자유 태그. doe_strategy(방향 컨셉)와 직교한다.
    focus: Mapped[str | None] = mapped_column(String(64), index=True)
    # 외부 잡 키(`stcx:<slurm id>`) — 후처리 예약(7-1)이 반입한 리포트에만 있다. **잡 하나에 리포트 하나**(7-2):
    # 같은 키를 다시 반입하려 하면 새로 만들지 않고 이 행을 알린다. 손으로 올린 리포트는 비어 있다.
    external_job_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    # 예약 원장 — 예약 때 받은 잡 이름 · sim_type · 해석 조건(높이 · 바닥 · 프리셋 · 위치 DOE) · 예약 잡 id.
    # 리포트 자신이 가진 값(sim_params 등)을 덮지 않으려고 따로 둔다(7-5 — 같은 조건끼리 묶는 근거).
    reservation: Mapped[dict | None] = mapped_column(JSONB)
    # 검색·정렬용 승격 컬럼(JSONB 대신 컬럼으로 빠른 필터). 인제스트 시 채운다.
    worst_stress: Mapped[float | None] = mapped_column(Float, index=True)
    worst_g: Mapped[float | None] = mapped_column(Float)
    max_severity: Mapped[str | None] = mapped_column(String(12), index=True)  # CRITICAL|WARNING|INFO
    drop_height: Mapped[float | None] = mapped_column(Float, index=True)
    scenario_type: Mapped[str | None] = mapped_column(String(32), index=True)  # cuboid_geometry 등
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
    # 성공한 잡에도 남기는 경고(개행 왕복 등). `error_summary` 는 실패 자리라 여기가 따로 있어야
    # 한다 — rc=0 인데 산출 덱이 상한 경우가 실제 사고의 모양이었다(캠페인 사건 1·7).
    warnings: Mapped[list | None] = mapped_column(JSONB)
    # 이 잡이 **어느 빌드·어느 환경**에서 돌았나 — 진단 번들의 근거다.
    # {binary:{revision,binary_sha256,…}, gmsh:{available,version}, platform:{app_env}, host:{nodename}}
    # ⚠ `/api/health` 는 "지금" 만 말한다. 배포 자리 바이너리가 이 캠페인에서 다섯 번 덮였으므로
    # (context-notes 27) 사흘 전 로그를 받아도 그때의 빌드를 알 방법이 없었다.
    env_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ── 외부 잡(다른 클러스터에 던진 것) ───────────────────────────────────
    # 로컬 잡은 워커의 자식 프로세스라 워커가 죽으면 같이 죽는다. 외부 잡은 아니다 —
    # stcx 에 던진 4시간짜리는 API 를 재기동해도 계속 돈다. 그래서 수명 판정을
    # **프로세스가 아니라 이 칸들로** 한다. 이걸 안 두면 재기동 한 번에 running 이
    # 전부 failed 로 지워지고(reconcile_orphans), 잡은 멀쩡히 도는 채로 화면에서 사라진다.
    external_kind: Mapped[str | None] = mapped_column(String(40), index=True)   # 예: "stcx_mcp"
    external_ref: Mapped[dict | None] = mapped_column(JSONB)   # {registry_id, slurm_job_ids, work_dir, ...}
    external_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


# ── 온톨로지 — 허브 거울과 자체 정의를 **한 꼴로** ─────────────────────────
# 표 이름·칸·타입을 StepForge 와 **같게** 둔다(계획서 §4). 둘을 맞댈 날이 오는데 이름이
# 다르면 그 일부터 해야 한다. `properties` 는 양쪽 다 **JSONB** 다(§2-b).
#
# `source` 가 「누가 이것의 정본인가」 다 — `hub` 는 받은 것이라 **우리가 고치지 않는다**
# (SP `managed_by` 와 같은 뜻 · `objects/routes.py:2268` 이 허브 쪽에서 만들기까지 거절한다).
# `dynaforge` 는 우리 것이다.

SOURCE_HUB = "hub"
SOURCE_SELF = "dynaforge"


class OntoType(Base):
    """객체 타입 정의 — 허브 카탈로그 스냅샷(`plm_task` 등)과 자체 정의(`dev_revision`)."""

    __tablename__ = "onto_types"
    __table_args__ = (UniqueConstraint("slug", name="uq_onto_types_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # `CorePropertyOut` 목록 그대로 — key·label·data_type·unit·required·multi·enum_options·
    # ref_type_slug·help. **우리가 해석해서 줄이지 않는다**(규칙 5: 모르는 칸은 무시한다).
    properties: Mapped[list | None] = mapped_column(JSONB)
    relations: Mapped[list | None] = mapped_column(JSONB)      # 이 타입에 걸리는 관계 slug 들
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_SELF, nullable=False)
    # 허브 카탈로그의 `revision` 지문. 바뀌면 정의가 바뀐 것이다 — 알린다(계획서 §6).
    catalog_revision: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OntoRelationType(Base):
    """관계 종류 정의 — 방향·전이·순환 금지·끝점 제약이 **데이터**로 있어야 한다."""

    __tablename__ = "onto_relation_types"
    __table_args__ = (UniqueConstraint("slug", name="uq_onto_relation_types_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    inverse_label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    directed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    transitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acyclic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # `many_to_one`·`one_to_many`·`many_to_many`·`one_to_one`. **정의 파일에만 있고 코어 API
    # 응답에는 없다** — 그래서 받은 것은 비어 있고, 자체 정의에서만 채워진다(0012).
    cardinality: Mapped[str | None] = mapped_column(String(20))
    src: Mapped[list | None] = mapped_column(JSONB)            # 허용 출발 타입(비면 제약 없음)
    dst: Mapped[list | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_SELF, nullable=False)
    catalog_revision: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OntoObject(Base):
    """객체 — 허브 거울과 자체 객체가 **한 표**에 산다.

    ★`key` 가 정체성이다(uuid 가 아니다 — 받는 쪽의 id 는 허브 것과 다르다). 그래서
    `(type_slug, key)` 가 유일하고, 선도 `key` 로 잇는다.

    ⚠**지우지 않는다** — 허브에서 사라진 것은 `deleted` 로 표시만 한다(규칙 4). 우리 선이
    그것을 가리키고 있을 수 있고, 지우면 그 선이 끊긴 채 조용히 남는다.
    """

    __tablename__ = "onto_objects"
    __table_args__ = (
        UniqueConstraint("type_slug", "key", name="uq_onto_objects_type_key"),
        Index("ix_onto_objects_label", "label"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    label: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSONB)
    # ★`renamed_from` 이 올 때 옮긴 옛 식별자들. **키트에는 이 처리가 없다**(ENVELOPE 에도
    #   없다) — 규칙 4 가 요구하므로 우리가 채웠다. 없으면 개명 뒤 같은 것이 둘이 된다.
    previous_keys: Mapped[list | None] = mapped_column(JSONB)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # 지운 것이 아니라 **이 자격으로 더 이상 안 보이는 것**(소유 부서가 옮겨 갔다). 이름·칸이
    # 안 오므로 가진 값은 두고 비활성만 한다 — 없던 것은 만들지 않는다(규칙 4).
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_into: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_SELF, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String(40))   # 허브가 준 ISO 문자열 그대로
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OntoRelation(Base):
    """선 — **끝점은 `key` 로** 잇는다(`CoreRelationOut` 이 그렇게 생겼다)."""

    __tablename__ = "onto_relations"
    __table_args__ = (
        UniqueConstraint("relation", "src_type", "src_key", "dst_type", "dst_key",
                         name="uq_onto_relations_edge"),
        Index("ix_onto_relations_dst", "dst_type", "dst_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    relation: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    src_type: Mapped[str] = mapped_column(String(80), nullable=False)
    src_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    dst_type: Mapped[str] = mapped_column(String(80), nullable=False)
    dst_key: Mapped[str] = mapped_column(String(300), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSONB)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_SELF, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OntoSyncState(Base):
    """타입별 수신 시계. ★**규칙 1·2 가 사는 자리다.**

    `as_of` 는 **서버가 준 값을 그대로** 둔다(우리 시계로 만들면 몇 초 차이로 그 사이 행이
    샌다). 그리고 쪽이 남아 있는 동안(`next` 가 있는 동안)에는 **옮기지 않는다** — 중간에서
    멈춘 쪽이 남은 쪽을 영영 안 받는다.
    """

    __tablename__ = "onto_sync_state"

    type_slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    objects_as_of: Mapped[str | None] = mapped_column(String(40))
    relations_as_of: Mapped[str | None] = mapped_column(String(40))
    catalog_revision: Mapped[str | None] = mapped_column(String(120))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ok | reset | stopped | error — `stopped` 는 규칙 11 의 `APP-CORE-0001`(공개 안 된 타입)
    # 이다. 그때는 **그 타입 수신을 멈추고 알린다** — 계속 두드리지 않는다.
    last_status: Mapped[str | None] = mapped_column(String(20))
    last_error: Mapped[str | None] = mapped_column(Text)


class OntoAlias(Base):
    """자유 문자열 → 정본 식별자. **사람이 붙인 기록**이다.

    ★`(type_slug, alias)` 가 유일하다 — 한 문자열이 두 과제를 가리키면 그 데이터로는 아무
    질문에도 답할 수 없다(SP §4.1 이 `key_scope` 에서 같은 말을 한다).

    누가 언제 붙였는지 남긴다 — 틀린 것을 되짚을 수 있어야 한다. 자동으로 붙인 것은 여기
    안 적는다(그것은 별칭이 아니라 그냥 일치다).
    """

    __tablename__ = "onto_aliases"
    __table_args__ = (
        UniqueConstraint("type_slug", "alias", name="uq_onto_aliases_alias"),
        Index("ix_onto_aliases_key", "type_slug", "key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    confirmed_by: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


# ── 레시피 — 빌드 없이 쌓이는 분석 함수(docs/01-plan/features/recipes-1026.plan.md) ──────
# 레시피는 이름 · 소유만 들고, 코드 · 메타는 **판**에 있다. 판은 바뀌지 않는다 — 고치면 새 판이다.
# 실행 기록은 근거다. 세션 · 잡 · 산출 파일이 지워져도 기록은 남아야 하므로 그 칸들은 SET NULL 이다.

RECIPE_VERSION_STATUSES = ("draft", "candidate", "registered", "superseded")


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(20), default="report", nullable=False)
    # 처음 올린 사람. git 에서 읽어 들인 레시피는 비어 있다(사용자 id 는 박스마다 다르다).
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    origin: Mapped[str] = mapped_column(String(10), default="platform", nullable=False)  # platform | git
    # 지금 등록된 판 — 다른 사용자가 검색 · 실행하는 판이다. 없으면 아직 등록 전이다.
    current_version: Mapped[int | None] = mapped_column(Integer)
    # 사람이 내린 것 — 검색 · 남의 실행에서 빠진다. 판의 상태는 그대로 둔다(기록이다).
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versions: Mapped[list["RecipeVersion"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", passive_deletes=True
    )


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"
    __table_args__ = (UniqueConstraint("recipe_id", "version", name="uq_recipe_versions_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # {title, question, when_to_use, kinds, needs, inputs:{min_reports,max_reports}, params, tags}
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True, nullable=False)
    # 정적 검사 · 자기 시험 · 앞 판 시험의 결과 — 왜 draft 인지 여기서 읽는다.
    checks: Mapped[dict | None] = mapped_column(JSONB)
    # 등록 관문을 지날 때의 판정(근거 실행 · 평가) — 등록 전에는 비어 있다.
    gate: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipe: Mapped[Recipe] = relationship(back_populates="versions")


class RecipeRun(Base):
    __tablename__ = "recipe_runs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("recipe_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    report_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    report_kinds: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="queued", nullable=False)
    # 결과 — 상한(설정)을 넘으면 앞부분만 두고 `result_truncated` 를 켠다. 전체는 산출 파일에 있다.
    result: Mapped[dict | None] = mapped_column(JSONB)
    result_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    output_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_files.id", ondelete="SET NULL")
    )
    error: Mapped[str | None] = mapped_column(Text)
    stdout_tail: Mapped[str | None] = mapped_column(Text)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    # 어느 격리 층이 켜졌나 — {landlock, seccomp, audit, limits}. 커널 층이 없는 박스가 있다.
    sandbox: Mapped[dict | None] = mapped_column(JSONB)
    # 평가 — 돌린 사람이 붙인다. useful 과 글(무엇을 보였나)이 등록 관문의 근거다.
    useful: Mapped[bool | None] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
