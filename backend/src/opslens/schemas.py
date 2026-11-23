from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    application: str
    environment: str
    database: str


class ModelProviderView(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    api_key_reference: str | None = None
    api_key_configured: bool = False
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class ModelProviderUpdate(BaseModel):
    provider: Literal["anthropic", "openai", "local"]
    model: str = Field(min_length=1, max_length=128)
    base_url: str | None = Field(default=None, max_length=512)
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class ModelSecretUpdate(BaseModel):
    api_key: str = Field(min_length=8)


class AwsProfileView(BaseModel):
    profile_name: str
    expected_account_id: str | None = None
    regions: list[str]
    enabled: bool = True


class AwsProfileUpdate(BaseModel):
    profile_name: str = Field(min_length=1, max_length=128)
    expected_account_id: str | None = Field(default=None, pattern=r"^\d{12}$")
    regions: list[str] = Field(min_length=1)
    enabled: bool = True

    @field_validator("regions")
    @classmethod
    def normalize_regions(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class SettingsView(BaseModel):
    model_provider: ModelProviderView
    aws_profile: AwsProfileView | None


class ValidationResponse(BaseModel):
    ok: bool
    message: str


class AwsConnectionResponse(BaseModel):
    connected: bool
    profile: str
    account_id: str | None = None
    arn: str | None = None
    user_id: str | None = None
    message: str


class InventoryRefreshRequest(BaseModel):
    services: list[str] | None = None


class InventoryRefreshResponse(BaseModel):
    account_id: str
    resource_count: int
    warning_count: int
    warnings: list[str]
    collected_at: datetime


class ResourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    region: str
    service: str
    resource_type: str
    resource_id: str
    name: str
    arn: str | None = None
    status: str
    metadata_json: dict[str, Any]
    collected_at: datetime


class ResourceListResponse(BaseModel):
    items: list[ResourceView]
    total: int


class McpToolView(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any]


class McpStatusResponse(BaseModel):
    connected: bool
    server_name: str | None = None
    protocol_version: str | None = None
    tools: list[McpToolView] = Field(default_factory=list)
    message: str


class FindingView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    region: str
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    code: str
    severity: str
    status: str
    summary: str
    evidence_json: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class FindingListResponse(BaseModel):
    items: list[FindingView]
    total: int


class HealthSummaryResponse(BaseModel):
    total_resources: int
    healthy_resources: int
    open_findings: int
    critical_findings: int
    warning_findings: int
    last_evaluated_at: datetime | None = None


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=255)


class ConversationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    provider: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    content_json: dict[str, Any] | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
