import asyncio
import base64
from typing import Any, Protocol

import httpx

from .config import Settings


class AccessTokenProvider(Protocol):
    async def token(self) -> str: ...


class MediaProviderError(RuntimeError):
    """Raised when the upstream Foundry media service returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_code: str | None = None,
        retryable: bool = False,
        content_filter: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_code = provider_code
        self.retryable = retryable
        self.content_filter = content_filter


class TokenProvider:
    def __init__(self, scope: str) -> None:
        self.scope = scope
        self._credential: Any | None = None

    async def token(self) -> str:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        access_token = await asyncio.to_thread(self._credential.get_token, self.scope)
        return access_token.token


class FoundryImageClient:
    def __init__(
        self,
        settings: Settings,
        *,
        token_provider: AccessTokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.tokens = token_provider or TokenProvider(settings.azure_scope)
        self.transport = transport

    async def generate(self, prompt: str) -> str:
        payload = {
            "model": self.settings.image_deployment,
            "prompt": prompt,
            "width": self.settings.image_width,
            "height": self.settings.image_height,
            "response_format": "b64_json",
        }
        result = await self._post_json_with_retries(self.settings.image_endpoint, payload)
        return _extract_image_b64(result)

    async def edit(self, prompt: str, image_b64: str) -> str:
        files = [
            ("image", ("source.png", base64.b64decode(image_b64), "image/png")),
        ]
        data = {
            "model": self.settings.image_deployment,
            "prompt": prompt,
            "width": str(self.settings.image_width),
            "height": str(self.settings.image_height),
            "response_format": "b64_json",
        }
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await self._send_image_request_with_retries(
                client,
                "POST",
                self.settings.image_edit_endpoint,
                data=data,
                files=files,
                headers={"Authorization": f"Bearer {token}"},
            )
        return _extract_image_b64(response.json())

    async def _post_json_with_retries(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await self._send_image_request_with_retries(
                client,
                "POST",
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        return response.json()

    async def _send_image_request_with_retries(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        attempts = max(self.settings.image_retry_attempts, 1)
        for attempt in range(attempts):
            response = await client.request(method, url, **kwargs)
            if response.status_code < 400:
                return response
            error = _provider_error(response)
            if error.retryable and attempt < attempts - 1:
                await asyncio.sleep(self.settings.image_retry_backoff_seconds * (2**attempt))
                continue
            raise error
        raise MediaProviderError("Image provider request failed before a response was returned.")


class SoraVideoClient:
    def __init__(
        self,
        settings: Settings,
        *,
        token_provider: AccessTokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.tokens = token_provider or TokenProvider(settings.azure_scope)
        self.transport = transport

    async def create(self, prompt: str, input_reference_b64: str | None = None) -> dict[str, Any]:
        payload = {
            "model": self.settings.video_model,
            "prompt": prompt,
            "size": self.settings.video_size,
            "seconds": self.settings.video_seconds,
        }
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            if input_reference_b64:
                files = [
                    (
                        "input_reference",
                        ("reference.png", base64.b64decode(input_reference_b64), "image/png"),
                    )
                ]
                response = await client.post(
                    self.settings.video_endpoint,
                    data={key: str(value) for key, value in payload.items()},
                    files=files,
                    headers={"Authorization": f"Bearer {token}"},
                )
            else:
                response = await client.post(
                    self.settings.video_endpoint,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                )
        if response.status_code >= 400:
            raise _provider_error(response)
        return response.json()

    async def get(self, video_id: str) -> dict[str, Any]:
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
            response = await client.get(
                f"{self.settings.video_endpoint}/{video_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise _provider_error(response)
        return response.json()

    async def download(self, video_id: str) -> bytes:
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=180, transport=self.transport) as client:
            response = await client.get(
                f"{self.settings.video_endpoint}/{video_id}/content",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise _provider_error(response)
        return response.content


def _extract_image_b64(payload: dict[str, Any]) -> str:
    try:
        image_b64 = payload["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError) as error:
        raise MediaProviderError("Image provider response did not include data[0].b64_json.") from error
    if not isinstance(image_b64, str) or not image_b64:
        raise MediaProviderError("Image provider returned an empty image payload.")
    return image_b64


def _provider_error(response: httpx.Response) -> MediaProviderError:
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text
    code, message = _provider_code_and_message(payload)
    message = message or str(payload)
    lower_message = message.lower()
    content_filter = code == "content_safety_violation" or "bingblocklist" in lower_message
    rate_limit = response.status_code == 429 or code == "RateLimitReached"
    if content_filter:
        label = "BingBlockList" if "bingblocklist" in lower_message else code or "content filter"
        detail = (
            "The vendor's filter blocked the generated response "
            f"({label}). Treat this as classroom evidence that automated guardrails can create "
            "false positives; use recorded mode or adjust the allowed options."
        )
    elif rate_limit:
        detail = (
            "The image provider is rate-limiting live generation right now "
            "(MAI-Image-2.6 allows a small burst per minute). Wait briefly or use recorded mode."
        )
    else:
        detail = f"Provider returned HTTP {response.status_code}: {message}"
    return MediaProviderError(
        detail,
        status_code=response.status_code,
        provider_code=code,
        retryable=rate_limit,
        content_filter=content_filter,
    )


def _provider_code_and_message(payload: Any) -> tuple[str | None, str | None]:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
        else:
            code = payload.get("code")
            message = payload.get("message") or payload.get("detail")
        return (
            code if isinstance(code, str) else None,
            message if isinstance(message, str) else None,
        )
    if isinstance(payload, str):
        return None, payload
    return None, None
