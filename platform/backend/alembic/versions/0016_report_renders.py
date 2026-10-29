"""리포트 렌더 기록 — SceneForge 렌더 결과(C-11)의 받은 · 실패한 이력

왜 필요한가. 렌더 결과(mp4 · 정지 화면)는 리포트 미디어에 **더한다** — 번들 반입처럼 통째로 바꾸지 않는다. 그런데
실패한 렌더(`ok: false`)는 붙일 미디어가 없어 그대로 두면 흔적이 사라진다. 화면이 「렌더 실패 — 까닭」 을 보이고,
같은 render_id 를 다시 받았을 때 멱등을 가르려면 렌더마다 한 줄의 기록이 있어야 한다. null 허용이라 옛 코드에 영향 없다.

계약 SceneForge `docs/contracts/c10-c11-render-request-result-draft-2026-10-29.md` · 반입 규칙(10-29 합의)

Revision ID: 0016_report_renders
Revises: 0015_report_reservation
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_report_renders"
down_revision = "0015_report_reservation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column("renders", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("impact_reports", "renders")
