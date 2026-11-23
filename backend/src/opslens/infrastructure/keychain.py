from __future__ import annotations

import os

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "opslens"


class SecretStore:
    def set(self, reference: str, value: str) -> None:
        keyring.set_password(SERVICE_NAME, reference, value)

    def get(self, reference: str | None) -> str | None:
        if not reference:
            return None
        try:
            return keyring.get_password(SERVICE_NAME, reference)
        except KeyringError:
            return None

    def is_configured(self, reference: str | None) -> bool:
        return self.get(reference) is not None

    def environment_secret(self, provider: str) -> str | None:
        variable = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider)
        return os.getenv(variable) if variable else None

    def resolve(self, reference: str | None, provider: str) -> str | None:
        return self.get(reference) or self.environment_secret(provider)


secret_store = SecretStore()
