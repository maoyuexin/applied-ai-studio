from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol

from .base import ProviderError


class TokenSource(Protocol):
    async def token(self) -> str: ...


class AzureTokenProvider:
    """Entra ID tokens via DefaultAzureCredential (az login on a Mac, a service principal on a server).

    Tokens are cached until five minutes before expiry; Azure CLI token calls take about a second.
    """

    def __init__(self, scope: str) -> None:
        self.scope = scope
        self._credential: Any | None = None
        self._token: str | None = None
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if self._token and time.time() < self._expires - 300:
                return self._token
            if self._credential is None:
                from azure.identity import DefaultAzureCredential

                self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            try:
                access = await asyncio.to_thread(self._credential.get_token, self.scope)
            except Exception as error:  # noqa: BLE001 - azure-identity raises several credential errors
                raise ProviderError(
                    "No Azure sign-in found. On a Mac run `az login`; on a server set the service principal "
                    "variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET).",
                    code="auth",
                ) from error
            self._token, self._expires = access.token, float(access.expires_on)
            return self._token

    @property
    def mode(self) -> str:
        import os

        if os.environ.get("AZURE_CLIENT_ID") and os.environ.get("AZURE_CLIENT_SECRET"):
            return "Service principal"
        return "Azure CLI (az login)"


class StaticTokenProvider:
    def __init__(self, value: str = "test-token") -> None:
        self.value = value

    async def token(self) -> str:
        return self.value

    mode = "static"
