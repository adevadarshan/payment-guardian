"""0001_initial — scans + audit_log (Slice 1). No users, no qr_seen yet."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_type", sa.String(16), nullable=False, index=True),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False, index=True),
        sa.Column("pipeline_version", sa.String(32), nullable=False),
        sa.Column("payment_amount", sa.Float, nullable=True),
        sa.Column("payment_currency", sa.String(3), nullable=True),
        sa.Column("payment_payee_id", sa.Text, nullable=True),
        sa.Column("payment_payee_name", sa.Text, nullable=True),
        sa.Column("payment_sender_balance", sa.Float, nullable=True),
        sa.Column("payment_note", sa.Text, nullable=True),
        sa.Column("payment_channel", sa.String(32), nullable=True),
        sa.Column("payment_merchant_category", sa.Text, nullable=True),
        sa.Column("result_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False, index=True),
        sa.Column("entity_id", sa.String(64), nullable=False, index=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at_str", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("scans")
