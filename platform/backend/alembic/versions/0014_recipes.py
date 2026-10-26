"""레시피 — 빌드 없이 쌓이는 분석 함수의 판과 실행 기록

왜 필요한가. 비교 · 분석이 늘 때마다 C++ op 이나 백엔드 코드로 박아 빌드 · 배포하거나, 세션 스크래치에서
한 번 쓰고 버려졌다. 레시피는 파이썬 함수 하나와 메타를 DB 에 두고 샌드박스에서 돌린다. 판은 바뀌지 않는다.
실행 기록과 평가가 등록 관문의 근거라, 세션 · 잡 · 산출 파일이 지워져도 기록은 남는다(SET NULL).

계획 docs/01-plan/features/recipes-1026.plan.md

Revision ID: 0014_recipes
Revises: 0013_onto_aliases
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_recipes"
down_revision = "0013_onto_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=20), server_default="report", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(length=10), server_default="platform", nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_recipes_name"),
    )
    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="draft", nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("gate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "version", name="uq_recipe_versions_version"),
    )
    op.create_index("ix_recipe_versions_recipe_id", "recipe_versions", ["recipe_id"])
    op.create_index("ix_recipe_versions_status", "recipe_versions", ["status"])
    op.create_table(
        "recipe_runs",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=26), nullable=True),
        sa.Column("session_id", sa.String(length=26), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("report_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("report_kinds", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="queued", nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("output_file_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("stdout_tail", sa.Text(), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("sandbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("useful", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["recipe_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["output_file_id"], ["session_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipe_runs_recipe_id", "recipe_runs", ["recipe_id"])
    op.create_index("ix_recipe_runs_version_id", "recipe_runs", ["version_id"])
    op.create_index("ix_recipe_runs_job_id", "recipe_runs", ["job_id"])
    op.create_index("ix_recipe_runs_user_id", "recipe_runs", ["user_id"])
    op.create_index("ix_recipe_runs_created_at", "recipe_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("recipe_runs")
    op.drop_table("recipe_versions")
    op.drop_table("recipes")
