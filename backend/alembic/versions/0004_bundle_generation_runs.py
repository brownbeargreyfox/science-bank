"""Allow a deterministic generation run to be associated with an imported SCDE bundle."""

import sqlalchemy as sa

from alembic import op

revision = "0004_bundle_generation_runs"
down_revision = "0003_roles_ownership_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("question_family_runs", sa.Column("bundle_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_question_family_runs_bundle_id",
        "question_family_runs",
        "bundles",
        ["bundle_id"],
        ["id"],
    )
    op.create_index("ix_question_family_runs_bundle_id", "question_family_runs", ["bundle_id"])


def downgrade() -> None:
    op.drop_index("ix_question_family_runs_bundle_id", table_name="question_family_runs")
    op.drop_constraint("fk_question_family_runs_bundle_id", "question_family_runs", type_="foreignkey")
    op.drop_column("question_family_runs", "bundle_id")
