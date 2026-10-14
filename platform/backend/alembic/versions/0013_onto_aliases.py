"""별칭 표 — 자유 문자열을 정본 식별자에 **사람이** 붙인 기록

왜 필요한가. 과거 리포트의 과제는 자유 문자열(`eng_meta.project` · 리포트에 박힌
`project_name`)이다. 정본은 허브의 `plm_task.key`(과제코드)다. 둘을 잇는 일이 남는데,
**짐작으로 붙이면 안 된다** — 틀려도 그럴듯하고, 그럴듯한 오류는 몇 달 뒤 결과를 비교할 때
발견된다.

그래서 붙인 기록을 남긴다. 한 번 붙이면 다음 리포트는 자동으로 붙는다(같은 문자열이 계속
들어온다). 누가 언제 붙였는지도 남긴다 — 틀린 것을 되짚을 수 있어야 한다.

SP 가 같은 문제를 `ObjectAlias` + ADR 0025 「채울 곳과 별칭 후보」로 풀었다. 그 착상만 가져왔다
(엔진은 안 가져온다 — 계획서 §2).

★`(type_slug, alias)` 가 유일하다 — 한 문자열이 두 과제를 가리키면 그 데이터로는 아무
질문에도 답할 수 없다.

Revision ID: 0013_onto_aliases
Revises: 0012_relation_cardinality
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_onto_aliases"
down_revision = "0012_relation_cardinality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onto_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_slug", sa.String(length=80), nullable=False),
        sa.Column("alias", sa.String(length=500), nullable=False),
        sa.Column("key", sa.String(length=300), nullable=False),
        # manual — 사람이 골랐다. 그 밖의 값은 두지 않는다(자동 별칭은 별칭이 아니다).
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("confirmed_by", sa.String(length=200), server_default="", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_slug", "alias", name="uq_onto_aliases_alias"),
    )
    op.create_index("ix_onto_aliases_key", "onto_aliases", ["type_slug", "key"])


def downgrade() -> None:
    op.drop_table("onto_aliases")
