from __future__ import annotations

from typing import Any

import httpx


class ProviderError(RuntimeError):
    """A provider call failed. `code` is a stable category the UI and the event log can explain."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "upstream",
        status: int | None = None,
        retryable: bool = False,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable
        self.detail = detail


def error_payload(response: httpx.Response) -> tuple[str | None, str]:
    try:
        payload: Any = response.json()
    except ValueError:
        return None, response.text[:500]
    if isinstance(payload, dict):
        error = payload.get("error", payload)
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
            message = error.get("message") or error.get("detail") or str(payload)
            inner = error.get("innererror") or {}
            if isinstance(inner, dict) and inner.get("code"):
                code = f"{code}:{inner['code']}" if code else inner["code"]
            return (str(code) if code else None), str(message)[:800]
        return None, str(error)[:800]
    return None, str(payload)[:800]


def classify(response: httpx.Response, service: str) -> ProviderError:
    code, message = error_payload(response)
    lower = f"{code} {message}".lower()
    status = response.status_code
    if status in (401, 403):
        return ProviderError(
            f"{service} refused the credentials (HTTP {status}). Sign in again (az login) or check the role assignment.",
            code="auth", status=status, detail=message,
        )
    if "too many running tasks" in lower:
        return ProviderError(f"{service}: too many running tasks; waiting for a slot.", code="too_many_tasks",
                             status=status, retryable=True, detail=message)
    if status == 429 or "ratelimit" in lower or "rate limit" in lower:
        return ProviderError(f"{service} is rate-limiting requests.", code="rate_limit", status=status,
                             retryable=True, detail=message)
    if any(term in lower for term in ("content_safety", "content_filter", "contentfilter", "bingblocklist",
                                      "moderation", "responsibleai", "safety system", "content policy")):
        label = "BingBlockList" if "bingblocklist" in lower else (code or "content filter")
        return ProviderError(f"{service}'s content filter blocked this request ({label}).", code="content_filter",
                             status=status, detail=message)
    if status in (408, 500, 502, 503, 504):
        return ProviderError(f"{service} had a temporary error (HTTP {status}).", code="upstream", status=status,
                             retryable=True, detail=message)
    if status == 404:
        return ProviderError(f"{service}: deployment or job not found (HTTP 404).", code="not_found", status=status,
                             detail=message)
    return ProviderError(f"{service} returned HTTP {status}: {message}", code="bad_request", status=status,
                         detail=message)
