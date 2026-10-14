"""온톨로지 표 다섯 — 허브 거울과 자체 정의를 **한 꼴로** 담는다

왜 다섯인가. 받은 것(과제·개발모델·프로젝트·시험주체와 그 선)과 우리 것(개발 개정)을
**같은 표**에 둔다. 두 벌로 두면 질의가 두 벌이 되고, 두 벌은 한쪽만 고쳐진다.

★**표 이름·칸·타입을 StepForge 와 같게 둔다**(계획서 §4 · StepForge `docs/STANDARD_PLATFORM.md`
§4). 두 쌍둥이가 같은 허브에서 같은 것을 받으므로, 맞댈 날이 오는데 이름이 다르면 그 일부터
해야 한다. `properties` 는 양쪽 다 **JSONB** 다(§2-b — StepForge 도 PG 로 온다).

★**끝점은 `key` 로 잇는다**(uuid 가 아니다). 받는 쪽의 id 는 허브 것과 다르다 —
`CoreRelationOut` 이 그렇게 생겼다. 그래서 `(type_slug, key)` 가 유일하다.

★**지우지 않는다.** 허브에서 사라진 것은 `deleted` 로 표시만 한다(수신 규칙 4). 우리 선이
그것을 가리키고 있을 수 있고, 지우면 그 선이 끊긴 채 조용히 남는다.

`onto_sync_state` 가 **수신 규칙 1·2 가 사는 자리**다 — 서버가 준 `as_of` 를 그대로 두고,
쪽이 남아 있는 동안에는 옮기지 않는다.

Revision ID: 0011_ontology
Revises: 0010_report_media
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_ontology"
down_revision = "0010_report_media"
branch_labels = None
depends_on = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "onto_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("properties", _JSONB, nullable=True),
        sa.Column("relations", _JSONB, nullable=True),
        sa.Column("source", sa.String(length=20), server_default="dynaforge", nullable=False),
        sa.Column("catalog_revision", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_onto_types_slug"),
    )
    op.create_index("ix_onto_types_slug", "onto_types", ["slug"])

    op.create_table(
        "onto_relation_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), server_default="", nullable=False),
        sa.Column("inverse_label", sa.String(length=200), server_default="", nullable=False),
        sa.Column("directed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("transitive", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("acyclic", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("src", _JSONB, nullable=True),
        sa.Column("dst", _JSONB, nullable=True),
        sa.Column("source", sa.String(length=20), server_default="dynaforge", nullable=False),
        sa.Column("catalog_revision", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_onto_relation_types_slug"),
    )
    op.create_index("ix_onto_relation_types_slug", "onto_relation_types", ["slug"])

    op.create_table(
        "onto_objects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type_slug", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("label", sa.String(length=500), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("properties", _JSONB, nullable=True),
        # ★`renamed_from` 으로 옮긴 옛 식별자들. 수신 키트에는 이 처리가 **없지만**
        #   수신 규칙 4 가 요구한다 — 없으면 개명 뒤 같은 것이 둘이 된다.
        sa.Column("previous_keys", _JSONB, nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("merged_into", sa.String(length=300), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="dynaforge", nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_slug", "key", name="uq_onto_objects_type_key"),
    )
    op.create_index("ix_onto_objects_type_slug", "onto_objects", ["type_slug"])
    op.create_index("ix_onto_objects_deleted", "onto_objects", ["deleted"])
    op.create_index("ix_onto_objects_label", "onto_objects", ["label"])

    op.create_table(
        "onto_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("src_type", sa.String(length=80), nullable=False),
        sa.Column("src_key", sa.String(length=300), nullable=False),
        sa.Column("dst_type", sa.String(length=80), nullable=False),
        sa.Column("dst_key", sa.String(length=300), nullable=False),
        sa.Column("properties", _JSONB, nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="dynaforge", nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relation", "src_type", "src_key", "dst_type", "dst_key",
                            name="uq_onto_relations_edge"),
    )
    op.create_index("ix_onto_relations_relation", "onto_relations", ["relation"])
    op.create_index("ix_onto_relations_src_key", "onto_relations", ["src_key"])
    op.create_index("ix_onto_relations_deleted", "onto_relations", ["deleted"])
    op.create_index("ix_onto_relations_dst", "onto_relations", ["dst_type", "dst_key"])

    op.create_table(
        "onto_sync_state",
        sa.Column("type_slug", sa.String(length=80), nullable=False),
        sa.Column("objects_as_of", sa.String(length=40), nullable=True),
        sa.Column("relations_as_of", sa.String(length=40), nullable=True),
        sa.Column("catalog_revision", sa.String(length=120), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("type_slug"),
    )


def downgrade() -> None:
    op.drop_table("onto_sync_state")
    op.drop_table("onto_relations")
    op.drop_table("onto_objects")
    op.drop_table("onto_relation_types")
    op.drop_table("onto_types")
