"""Initial Phase 0-3 schema.

Revision ID: 0001_phase_0_3
Revises:
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_phase_0_3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_provider_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("api_key_reference", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "aws_profile_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("expected_account_id", sa.String(length=12), nullable=True),
        sa.Column("regions_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
    )
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=True),
        sa.Column("result_summary_json", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
    )
    op.create_index("ix_tool_executions_agent_run_id", "tool_executions", ["agent_run_id"])
    op.create_table(
        "resource_inventory",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("arn", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "region",
            "service",
            "resource_id",
            name="uq_resource_identity",
        ),
    )
    op.create_index(
        "ix_resource_inventory_service_region",
        "resource_inventory",
        ["service", "region"],
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("resource_inventory")
    op.drop_table("tool_executions")
    op.drop_table("agent_runs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("aws_profile_configs")
    op.drop_table("model_provider_configs")
