"""0002_qr_seen — previously-seen QR payload store (Slice 3). Additive only."""

from alembic import op
import sqlalchemy as sa

revision = "0002_qr_seen"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qr_seen",
        sa.Column("payload_hash", sa.String(64), primary_key=True),
        sa.Column("payload_class", sa.String(16), nullable=False),
        sa.Column("normalized_preview", sa.String(280), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("times_seen", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_scan_id", sa.String(36),
                  sa.ForeignKey("scans.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("times_seen >= 1", name="ck_qr_seen_times_seen"),
    )


def downgrade() -> None:
    op.drop_table("qr_seen")
