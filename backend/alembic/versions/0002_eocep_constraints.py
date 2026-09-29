"""Add source-provenanced EOCEP constraints to standards."""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_eocep_constraints"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("standards", sa.Column("eocep_constraints", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("standards", "eocep_constraints")
