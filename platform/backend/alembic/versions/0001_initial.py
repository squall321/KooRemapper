"""initial schema: users, personal_access_tokens, sessions, session_files, jobs

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "personal_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_pat_user_id", "personal_access_tokens", ["user_id"])
    op.create_index("ix_pat_token_hash", "personal_access_tokens", ["token_hash"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "session_files",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.String(26), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("rel_path", sa.String(1024), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="input"),
        sa.Column("origin_job_id", sa.String(26)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64)),
        sa.Column("meta", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_session_files_session_id", "session_files", ["session_id"])
    op.create_index("ix_session_files_origin_job_id", "session_files", ["origin_job_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("session_id", sa.String(26), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("args", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("resolved_cmd", postgresql.JSONB()),
        sa.Column("status", sa.String(12), nullable=False, server_default="queued"),
        sa.Column("progress", sa.SmallInteger()),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("stdout_path", sa.String(1024)),
        sa.Column("stderr_path", sa.String(1024)),
        sa.Column("input_file_ids", postgresql.JSONB()),
        sa.Column("output_file_ids", postgresql.JSONB()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_jobs_session_id", "jobs", ["session_id"])
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("session_files")
    op.drop_table("sessions")
    op.drop_table("personal_access_tokens")
    op.drop_table("users")
