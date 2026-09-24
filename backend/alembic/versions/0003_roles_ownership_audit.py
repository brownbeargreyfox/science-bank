"""Roles, content ownership, actor columns, audit log, and DB-backed site settings."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003_roles_ownership_audit"
down_revision = "0002_eocep_constraints"
branch_labels = None
depends_on = None


def _user_fk(table: str, column: str) -> None:
    op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
    op.create_foreign_key(f"fk_{table}_{column}", table, "users", [column], ["id"], ondelete="RESTRICT")


def upgrade() -> None:
    from app.core.config import get_settings

    conn = op.get_bind()
    dupes = conn.execute(sa.text("select lower(username) from users group by 1 having count(*) > 1")).scalars().all()
    if dupes:
        raise RuntimeError(f"Resolve case-insensitive duplicate usernames before upgrading: {dupes}")

    op.add_column("users", sa.Column("role", sa.String(16), nullable=False, server_default="regular"))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_users_role", "users", "role in ('admin', 'power', 'regular')")
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)

    conn.execute(sa.text("update users set role = 'admin' where lower(username) = 'brandon'"))
    conn.execute(sa.text("update users set role = 'power' where lower(username) = 'nina' and role <> 'admin'"))
    # A non-empty install must always end up with an admin.
    conn.execute(
        sa.text(
            "update users set role = 'admin' where id = (select min(id) from users) "
            "and not exists (select 1 from users where role = 'admin')"
        )
    )

    admin_id = conn.scalar(sa.text("select min(id) from users where role = 'admin'"))
    for table in ("questions", "assessments"):
        _user_fk(table, "owner_id")
        has_rows = conn.scalar(sa.text(f"select exists (select 1 from {table})"))
        if has_rows and admin_id is None:
            raise RuntimeError(f"{table} has rows but no user exists to own them")
        if has_rows:
            conn.execute(sa.text(f"update {table} set owner_id = :uid"), {"uid": admin_id})
        op.alter_column(table, "owner_id", nullable=False)
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])
    op.add_column("assessments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    _user_fk("question_versions", "created_by")
    _user_fk("question_status_events", "actor_id")
    _user_fk("question_family_runs", "created_by")

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("actor_username", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("detail", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_audit_events_at", "audit_events", ["at"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])

    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_open", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_site_settings_singleton"),
    )
    conn.execute(
        sa.text("insert into site_settings (id, registration_open) values (1, :open)"),
        {"open": get_settings().registration_open},
    )


def downgrade() -> None:
    op.drop_table("site_settings")
    op.drop_index("ix_audit_events_actor_id", "audit_events")
    op.drop_index("ix_audit_events_at", "audit_events")
    op.drop_table("audit_events")
    for table, column in (
        ("question_family_runs", "created_by"),
        ("question_status_events", "actor_id"),
        ("question_versions", "created_by"),
    ):
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_column(table, column)
    op.drop_column("assessments", "deleted_at")
    for table in ("assessments", "questions"):
        op.drop_index(f"ix_{table}_owner_id", table)
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
    op.drop_index("uq_users_username_lower", "users")
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
