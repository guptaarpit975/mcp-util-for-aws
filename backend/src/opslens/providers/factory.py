from __future__ import annotations

from ..infrastructure.keychain import secret_store
from ..models import ModelProviderConfig
from .anthropic import AnthropicProvider
from .base import ModelProvider


class ProviderConfigurationError(RuntimeError):
    pass


def create_provider(config: ModelProviderConfig) -> ModelProvider:
    if not config.enabled:
        raise ProviderConfigurationError("The configured model provider is disabled.")
    if config.provider != "anthropic":
        raise ProviderConfigurationError(
            f"Provider '{config.provider}' is configurable but its adapter is not installed yet."
        )
    api_key = secret_store.resolve(config.api_key_reference, config.provider)
    if not api_key:
        raise ProviderConfigurationError(
            "Configure the Anthropic API key in Settings or export ANTHROPIC_API_KEY."
        )
    return AnthropicProvider(api_key=api_key, base_url=config.base_url)
