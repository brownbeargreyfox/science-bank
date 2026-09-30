"""Administrations, per-section item results, and question variant links."""

import sqlalchemy as sa

from alembic import op

revision = "0005_results_and_variants"
down_revision = "0004_bundle_generation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "administrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("administered_on", sa.Date(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_administrations_owner_date", "administrations", ["owner_id", "administered_on"])
    op.create_index("ix_administrations_assessment", "administrations", ["assessment_id", "deleted_at"])

    op.create_table(
        "administration_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "administration_id", sa.Integer(), sa.ForeignKey("administrations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_assessment_item_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("question_version_id", sa.Integer(), sa.ForeignKey("question_versions.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("administration_id", "position", name="uq_administration_items_position"),
    )
    op.create_index("ix_administration_items_question", "administration_items", ["question_id"])
    op.create_index("ix_administration_items_version", "administration_items", ["question_version_id"])

    op.create_table(
        "administration_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "administration_id", sa.Integer(), sa.ForeignKey("administrations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_index(
        "uq_administration_sections_name",
        "administration_sections",
        ["administration_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "item_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "section_id", sa.Integer(), sa.ForeignKey("administration_sections.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "administration_item_id",
            sa.Integer(),
            sa.ForeignKey("administration_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("attempted", sa.Integer(), nullable=False),
        sa.UniqueConstraint("section_id", "administration_item_id", name="uq_item_results_section_item"),
        sa.CheckConstraint("attempted >= 1", name="ck_item_results_attempted_positive"),
        sa.CheckConstraint("correct >= 0 AND correct <= attempted", name="ck_item_results_correct_range"),
    )
    op.create_index("ix_item_results_item", "item_results", ["administration_item_id"])

    op.add_column("questions", sa.Column("variant_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_questions_variant_of_id", "questions", "questions", ["variant_of_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_questions_variant_of_id", "questions", ["variant_of_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_variant_of_id", table_name="questions")
    op.drop_constraint("fk_questions_variant_of_id", "questions", type_="foreignkey")
    op.drop_column("questions", "variant_of_id")
    op.drop_index("ix_item_results_item", table_name="item_results")
    op.drop_table("item_results")
    op.drop_index("uq_administration_sections_name", table_name="administration_sections")
    op.drop_table("administration_sections")
    op.drop_index("ix_administration_items_version", table_name="administration_items")
    op.drop_index("ix_administration_items_question", table_name="administration_items")
    op.drop_table("administration_items")
    op.drop_index("ix_administrations_assessment", table_name="administrations")
    op.drop_index("ix_administrations_owner_date", table_name="administrations")
    op.drop_table("administrations")
