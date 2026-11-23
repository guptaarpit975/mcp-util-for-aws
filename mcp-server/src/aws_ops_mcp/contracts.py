from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResourceRecord(BaseModel):
    service: str
    resource_type: str
    resource_id: str
    name: str
    region: str
    arn: str | None = None
    status: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class InventoryResult(BaseModel):
    account_id: str
    profile: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resources: list[ResourceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceEnvelope(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    tool: str
    account_id: str
    profile: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["ok", "partial", "error"] = "ok"
    facts: dict[str, Any] = Field(default_factory=dict)
    resources: list[ResourceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HealthFinding(BaseModel):
    fingerprint: str
    account_id: str
    region: str
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    code: str
    severity: Literal["info", "warning", "critical"]
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)
