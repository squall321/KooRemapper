"""리포트에 **결과 이미지**를 붙인다 — 그림이 없으면 LLM 도 사람도 결과를 못 본다

왜 칸이 필요한가. 결과 이미지는 리포트 HTML 안에 임베드되지 **않는다** — 옆에 딸린 파일이다
(실측: impact `impact_report_data/set_media/pos_<POS>_s0_peak.png`, deep 은 형제
`custom_report/set_reports/<zone>/peak_*.png`). HTML 하나만 올리면 **애초에 들어오지 않는다.**

번들로 받은 미디어는 `SessionFile` 로 저장하면 되지만, **어느 리포트의 어느 케이스 그림인가**
를 적을 자리가 없었다. 세션에 리포트가 둘이면 파일만 보고는 가릴 수 없다.

칸을 하나(JSONB 목록)로 두는 이유 — 이 값들은 **함께 읽힐 때만** 뜻이 있다(경로·케이스·세트·
역할·파일id). 개별 질의 대상이 아니고, 리포트 한 건의 미디어는 수십 장 수준이다.

Revision ID: 0010_report_media
Revises: 0009_job_env_snapshot
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_report_media"
down_revision = "0009_job_env_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "impact_reports",
        sa.Column("media", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("impact_reports", "media")
