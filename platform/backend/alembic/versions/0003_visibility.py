"""session visibility (company|department|team|private) + user org fields

세션은 지금까지 user_id 하나로만 스코프됐다. 그래서 게이트웨이 서비스 계정으로 조회하는
심의가 실제 모델을 하나도 못 봤다(세션 12·K파일 25건이 있는데 0건 조회, 2026-08-17 실측).
공개 범위를 HEAX Hub 와 같은 4단으로 두고, 부서·팀 판정을 위해 users 에 소속을 받는다.

기본값은 private — 마이그레이션이 기존 세션의 노출 범위를 넓히지 않는다.

Revision ID: 0003_visibility
Revises: 0002_impact_reports
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_visibility"
down_revision = "0002_impact_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 조직 — 포털/SSO 가 주는 값을 그대로 받아 적는다. 정규화는 값이 쌓인 뒤에.
    op.add_column("users", sa.Column("department", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("team", sa.String(120), nullable=True))

    # 가시성 — private 기본. 서버 기본값도 함께 걸어 기존 행이 NULL 로 남지 않게 한다.
    op.add_column(
        "sessions",
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
    )
    op.create_index("ix_sessions_visibility", "sessions", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_sessions_visibility", table_name="sessions")
    op.drop_column("sessions", "visibility")
    op.drop_column("users", "team")
    op.drop_column("users", "department")
