"""Health findings and conversation indexes.

Revision ID: 0002_health_and_chat
Revises: 0001_phase_0_3
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_health_and_chat"
down_revision = "0001_phase_0_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("resource_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_health_snapshots_account_service",
        "health_snapshots",
        ["account_id", "service"],
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("resource_name", sa.String(length=512), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=1024), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("fingerprint", name="uq_findings_fingerprint"),
    )
    op.create_index(
        "ix_findings_status_severity",
        "findings",
        ["status", "severity"],
    )
    op.execute(
        "UPDATE model_provider_configs SET model = 'claude-sonnet-5-5' "
        "WHERE model = 'claude-sonnet'"
    )


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_table("health_snapshots")
