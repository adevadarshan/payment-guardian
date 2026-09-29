"""0003_users — application users, sessions, user scoping (Slice 4). Additive only."""

from alembic import op
import sqlalchemy as sa

revision = "0003_users"
down_revision = "0002_qr_seen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("is_demo", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("scans", sa.Column("user_id", sa.String(36), nullable=True))
    op.create_index("ix_scans_user_id", "scans", ["user_id"])
    op.add_column("audit_log", sa.Column("user_id", sa.String(36), nullable=True))
    op.create_index("ix_audit_user_id", "audit_log", ["user_id"])
    # Foreign keys need batch (copy-and-move) on SQLite; batch is a no-op
    # equivalent on PostgreSQL, so one path serves both.
    with op.batch_alter_table("scans") as batch_op:
        batch_op.create_foreign_key("fk_scans_user_id", "users", ["user_id"], ["id"],
                                    ondelete="SET NULL")
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.create_foreign_key("fk_audit_user_id", "users", ["user_id"], ["id"],
                                    ondelete="SET NULL")


def downgrade() -> None:
    # Batch mode: SQLite cannot ALTER constraints/columns outside copy-and-move.
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint("fk_audit_user_id", type_="foreignkey")
        batch_op.drop_index("ix_audit_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("scans") as batch_op:
        batch_op.drop_constraint("fk_scans_user_id", type_="foreignkey")
        batch_op.drop_index("ix_scans_user_id")
        batch_op.drop_column("user_id")
    op.drop_table("sessions")
    op.drop_table("users")
