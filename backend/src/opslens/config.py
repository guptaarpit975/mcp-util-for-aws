from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSLENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpsLens"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origin: str = "http://127.0.0.1:5173"
    database_url: str = "mysql+asyncmy://opslens:opslens@127.0.0.1:3307/opslens"
    auto_create_schema: bool = False
    default_aws_profile: str = ""
    default_aws_regions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["ap-south-1", "us-east-1"]
    )
    mcp_tool_timeout_seconds: float = 30
    inventory_page_limit: int = 10
    max_agent_iterations: int = 6
    max_tool_result_chars: int = 50_000
    model_max_tokens: int = 2_048

    @field_validator("default_aws_regions", mode="before")
    @classmethod
    def parse_regions(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]


@lru_cache
def get_settings() -> Settings:
    return Settings()
