"""잡마다 어느 빌드·어느 환경에서 돌았는지를 남긴다 — 진단 번들의 근거

실패한 잡의 로그를 받아도 **그때 어느 바이너리였는지** 알 방법이 없었다. `buildinfo` 는
`/api/health` 전용이라 "지금" 만 말한다. 배포 자리 바이너리가 덱 계약 캠페인에서 다섯 번이나
다른 것으로 덮였으므로(context-notes 27), 빌드 정체가 없는 로그는 증거가 아니다.

칸을 하나로 두는 이유 — 이 값들은 **함께 읽힐 때만** 뜻이 있고 개별 질의 대상이 아니다.

Revision ID: 0009_job_env_snapshot
Revises: 0008_job_warnings
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_job_env_snapshot"
down_revision = "0008_job_warnings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("env_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "env_snapshot")
