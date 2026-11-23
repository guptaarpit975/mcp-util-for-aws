from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ModelProviderConfig(TimestampMixin, Base):
    __tablename__ = "model_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    model: Mapped[str] = mapped_column(String(128), default="claude-sonnet-5-5")
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    options_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AwsProfileConfig(TimestampMixin, Base):
    __tablename__ = "aws_profile_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name: Mapped[str] = mapped_column(String(128), unique=True)
    expected_account_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    regions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    arguments_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResourceInventory(Base):
    __tablename__ = "resource_inventory"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "region",
            "service",
            "resource_id",
            name="uq_resource_identity",
        ),
        Index("ix_resource_inventory_service_region", "service", "region"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(12))
    region: Mapped[str] = mapped_column(String(32))
    service: Mapped[str] = mapped_column(String(32))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(512))
    arn: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="unknown")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        index=True,
    )


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"
    __table_args__ = (Index("ix_health_snapshots_account_service", "account_id", "service"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(12))
    region: Mapped[str] = mapped_column(String(32))
    service: Mapped[str] = mapped_column(String(32))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(512))
    resource_name: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32))
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_findings_fingerprint"),
        Index("ix_findings_status_severity", "status", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    fingerprint: Mapped[str] = mapped_column(String(64))
    account_id: Mapped[str] = mapped_column(String(12))
    region: Mapped[str] = mapped_column(String(32))
    service: Mapped[str] = mapped_column(String(32))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(512))
    resource_name: Mapped[str] = mapped_column(String(512))
    code: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="open")
    summary: Mapped[str] = mapped_column(String(1024))
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
