"""Live Foundry / Azure clients: text (chat completions), MAI-Image, Sora video, Speech (MAI-Voice + STT)."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape, quoteattr

import httpx

from .auth import TokenSource
from .base import ProviderError, classify

MAX_IMAGE_PIXELS = 2_359_296
MIN_IMAGE_SIDE = 768


@dataclass
class TextResult:
    text: str
    seconds: float
    deployment: str
    usage: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        raw = self.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{"):] if "{" in raw else raw
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise ProviderError("The text model did not return JSON.", code="bad_output", detail=self.text[:400])
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError as error:
            raise ProviderError("The text model returned malformed JSON.", code="bad_output",
                                detail=self.text[:400]) from error


async def _send(
    client: httpx.AsyncClient, service: str, method: str, url: str, *, attempts: int = 3, backoff: float = 2.0,
    retry_codes: tuple[str, ...] = ("rate_limit", "upstream"), **kwargs: Any,
) -> httpx.Response:
    last: ProviderError | None = None
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            last = ProviderError(f"{service} timed out.", code="timeout", retryable=True)
            if attempt < attempts - 1:
                await asyncio.sleep(backoff * (attempt + 1))
                continue
            raise last from error
        except httpx.HTTPError as error:
            raise ProviderError(f"Could not reach {service}: {error.__class__.__name__}.", code="network",
                                retryable=True) from error
        if response.status_code < 400:
            return response
        last = classify(response, service)
        if last.code in retry_codes and attempt < attempts - 1:
            await asyncio.sleep(backoff * (attempt + 1))
            continue
        raise last
    raise last or ProviderError(f"{service} request failed.")


class TextClient:
    service = "Text model"

    def __init__(self, endpoint: str, tokens: TokenSource, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.tokens = tokens
        self.transport = transport

    async def complete(
        self, deployment: str, system: str, user: str, *, json_mode: bool = True, max_tokens: int = 6000,
        purpose: str = "", context: dict[str, Any] | None = None,
    ) -> TextResult:
        del purpose, context  # used by the fake provider only
        body: dict[str, Any] = {
            "model": deployment,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_completion_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=180, transport=self.transport) as client:
            response = await _send(client, self.service, "POST", f"{self.endpoint}/chat/completions", json=body,
                                   headers={"Authorization": f"Bearer {token}"})
        payload = response.json()
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError("The text model returned no message.", code="bad_output") from error
        if payload["choices"][0].get("finish_reason") == "content_filter":
            raise ProviderError("The text model's content filter stopped the answer.", code="content_filter")
        return TextResult(text, round(time.perf_counter() - started, 2), deployment, payload.get("usage") or {})


class RateWindow:
    """At most `limit` calls in any rolling 60-second window."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.calls: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def wait(self) -> float:
        waited = 0.0
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.limit:
                    self.calls.append(now)
                    return waited
                pause = 60 - (now - self.calls[0]) + 0.05
                waited += pause
                await asyncio.sleep(pause)


class ImageClient:
    service = "MAI-Image"

    def __init__(self, endpoint: str, deployment: str, tokens: TokenSource, per_minute: int,
                 transport: httpx.AsyncBaseTransport | None = None, rate_backoff: float = 20.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.deployment = deployment
        self.tokens = tokens
        self.window = RateWindow(per_minute)
        self.transport = transport
        self.rate_backoff = rate_backoff

    @staticmethod
    def check_size(width: int, height: int) -> None:
        if min(width, height) < MIN_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
            raise ProviderError(
                f"MAI-Image needs each side >= {MIN_IMAGE_SIDE} px and at most {MAX_IMAGE_PIXELS:,} pixels "
                f"(asked for {width}x{height}).", code="bad_request")

    async def generate(self, prompt: str, width: int, height: int) -> bytes:
        self.check_size(width, height)
        body = {"model": self.deployment, "prompt": prompt, "width": width, "height": height}
        return await self._call("generations", json=body)

    async def edit(self, prompt: str, images: list[bytes], width: int, height: int) -> bytes:
        self.check_size(width, height)
        if not images:
            return await self.generate(prompt, width, height)
        data = {"model": self.deployment, "prompt": prompt, "width": str(width), "height": str(height)}
        files = [("image", (f"ref{index}.png", image, "image/png")) for index, image in enumerate(images)]
        return await self._call("edits", data=data, files=files)

    async def probe(self) -> dict[str, Any]:
        """Cheap reachability test: a deliberately undersized request should fail validation (400), not auth."""
        token = await self.tokens.token()
        async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
            response = await client.post(f"{self.endpoint}/mai/v1/images/generations",
                                         json={"model": self.deployment, "prompt": "connection test", "width": 64,
                                               "height": 64}, headers={"Authorization": f"Bearer {token}"})
        if response.status_code in (400, 422):
            return {"ok": True, "detail": "Reachable and signed in (the 64 px test request was rejected as expected)."}
        if response.status_code < 400:
            return {"ok": True, "detail": "Reachable and signed in."}
        raise classify(response, self.service)

    async def _call(self, operation: str, **kwargs: Any) -> bytes:
        url = f"{self.endpoint}/mai/v1/images/{operation}"
        for attempt in range(4):
            await self.window.wait()
            token = await self.tokens.token()
            async with httpx.AsyncClient(timeout=240, transport=self.transport) as client:
                try:
                    response = await _send(client, self.service, "POST", url, attempts=1,
                                           headers={"Authorization": f"Bearer {token}"}, **kwargs)
                except ProviderError as error:
                    if error.code in ("rate_limit", "upstream", "timeout") and attempt < 3:
                        await asyncio.sleep(self.rate_backoff * (attempt + 1))
                        continue
                    raise
            payload = response.json()
            try:
                return base64.b64decode(payload["data"][0]["b64_json"])
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ProviderError("MAI-Image returned no image data.", code="bad_output") from error
        raise ProviderError("MAI-Image kept rate-limiting; try again in a minute.", code="rate_limit", retryable=True)


class VideoClient:
    service = "Sora"

    def __init__(self, endpoint: str, deployment: str, tokens: TokenSource,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base = endpoint.rstrip("/") + "/videos"
        self.deployment = deployment
        self.tokens = tokens
        self.transport = transport

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self.tokens.token()}"}

    async def create(self, prompt: str, *, seconds: int, size: str, input_reference: bytes | None = None) -> dict[str, Any]:
        fields = {"model": self.deployment, "prompt": prompt, "seconds": str(seconds), "size": size}
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            if input_reference is not None:
                response = await _send(client, self.service, "POST", self.base, attempts=2, data=fields,
                                       files=[("input_reference", ("reference.png", input_reference, "image/png"))],
                                       headers=await self._headers(), retry_codes=("upstream",))
            else:
                response = await _send(client, self.service, "POST", self.base, attempts=2, json=fields,
                                       headers=await self._headers(), retry_codes=("upstream",))
        return response.json()

    async def remix(self, video_id: str, prompt: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await _send(client, self.service, "POST", f"{self.base}/{video_id}/remix", attempts=2,
                                   json={"prompt": prompt}, headers=await self._headers(), retry_codes=("upstream",))
        return response.json()

    async def get(self, video_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
            response = await _send(client, self.service, "GET", f"{self.base}/{video_id}",
                                   headers=await self._headers())
        return response.json()

    async def download(self, video_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=300, transport=self.transport) as client:
            response = await _send(client, self.service, "GET", f"{self.base}/{video_id}/content",
                                   headers=await self._headers())
        return response.content

    async def ping(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
            response = await _send(client, self.service, "GET", f"{self.base}?limit=1", attempts=1,
                                   headers=await self._headers())
        return {"ok": True, "jobs_visible": len(response.json().get("data", []))}


class SpeechClient:
    service = "Speech"

    def __init__(self, region: str, resource_id: str, tokens: TokenSource, voice_model: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.region = region
        self.resource_id = resource_id
        self.tokens = tokens
        self.voice_model = voice_model
        self.transport = transport
        self._voices: list[dict[str, Any]] | None = None
        self._voices_at = 0.0

    async def _auth(self) -> str:
        return f"Bearer aad#{self.resource_id}#{await self.tokens.token()}"

    async def voices(self) -> list[dict[str, Any]]:
        if self._voices is not None and time.time() - self._voices_at < 3600:
            return self._voices
        async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
            response = await _send(client, self.service, "GET",
                                   f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                                   headers={"Authorization": await self._auth()})
        suffix = f":{self.voice_model}"
        voices = [
            {"name": voice["ShortName"], "display": voice["ShortName"].split(":")[0].split("-")[-1],
             "locale": voice["Locale"], "gender": voice.get("Gender"), "styles": voice.get("StyleList") or []}
            for voice in response.json() if str(voice.get("ShortName", "")).endswith(suffix)
        ]
        self._voices, self._voices_at = voices, time.time()
        return voices

    async def synthesize(self, text: str, voice: str, *, locale: str, style: str | None = None) -> bytes:
        body = escape(text)
        if style:
            body = f"<mstts:express-as style={quoteattr(style)}>{body}</mstts:express-as>"
        ssml = (f"<speak version='1.0' xml:lang={quoteattr(locale)} xmlns='http://www.w3.org/2001/10/synthesis' "
                f"xmlns:mstts='http://www.w3.org/2001/mstts'><voice name={quoteattr(voice)}>{body}</voice></speak>")
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await _send(
                client, self.service, "POST", f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml.encode(), headers={
                    "Authorization": await self._auth(), "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3", "User-Agent": "design-studio",
                })
        if not response.content:
            raise ProviderError("Speech returned empty audio.", code="bad_output")
        return response.content

    async def transcribe(self, wav16k: bytes, *, locale: str, expected: str | None = None) -> dict[str, Any]:
        del expected  # used by the fake provider only
        url = (f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
               f"?language={locale}&format=detailed")
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await _send(client, self.service, "POST", url, content=wav16k, headers={
                "Authorization": await self._auth(),
                "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"})
        payload = response.json()
        best = (payload.get("NBest") or [{}])[0]
        return {"status": payload.get("RecognitionStatus"), "text": payload.get("DisplayText") or "",
                "confidence": best.get("Confidence")}
