"""SP 받는 쪽 — 키트 2026-10-21 판의 사본 표(이전 식별자 · 카탈로그 · 실행 기록 · 선의 근거와 갱신 시각)

왜 필요한가. 받는 쪽 규칙이 열하나에서 열여섯이 됐다(SP `kit/01-AI-GUIDE.md`@778db2f §4 · §5.6).
- 바뀐 식별자의 옛 → 새 짝을 남겨야 다른 곳에 남은 옛 값(우리 개정 · 별칭)을 푼다(규칙 5).
- 정의 판이 바뀌면 무엇이 달라졌는지 남기고 전부 다시 받는다 — 직전 카탈로그가 있어야 견준다(규칙 12).
- 결과는 정상 · 확인 필요 · 실패 셋이고(규칙 16), 관리 화면이 최근 실행과 사유를 보인다.
- 허브 선의 근거 메모(`evidence_note`)와 허브 갱신 시각을 사본에 담는다(§4 사본 표 꼴).
새 표 · null 허용 칸이라 옛 코드에 영향 없다.

계획 `docs/01-plan/features/sp-receive-1030.plan.md`

Revision ID: 0018_sp_receive
Revises: 0017_report_cad
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_sp_receive"
down_revision = "0017_report_cad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onto_relations", sa.Column("evidence_note", sa.Text(), nullable=True))
    op.add_column("onto_relations", sa.Column("updated_at", sa.String(40), nullable=True))
    op.create_table(
        "onto_previous_keys",
        sa.Column("type_slug", sa.String(80), primary_key=True),
        sa.Column("old_key", sa.String(300), primary_key=True),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_onto_previous_keys_key", "onto_previous_keys", ["key"])
    op.create_table(
        "onto_catalogs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("revision", sa.String(120), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_onto_catalogs_revision", "onto_catalogs", ["revision"])
    op.create_table(
        "onto_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("allow_shrink", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="worker"),
        sa.Column("requested_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("result", sa.String(20), nullable=False, server_default="running"),
        sa.Column("revision", sa.String(120), nullable=True),
        sa.Column("counts", postgresql.JSONB(), nullable=True),
        sa.Column("problems", postgresql.JSONB(), nullable=True),
        sa.Column("notes", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_onto_sync_runs_started_at", "onto_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_onto_sync_runs_started_at", table_name="onto_sync_runs")
    op.drop_table("onto_sync_runs")
    op.drop_index("ix_onto_catalogs_revision", table_name="onto_catalogs")
    op.drop_table("onto_catalogs")
    op.drop_index("ix_onto_previous_keys_key", table_name="onto_previous_keys")
    op.drop_table("onto_previous_keys")
    op.drop_column("onto_relations", "updated_at")
    op.drop_column("onto_relations", "evidence_note")
