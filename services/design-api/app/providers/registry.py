"""Model roles -> provider clients. Pipelines ask for a role; Settings shows how each is wired."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import Settings
from .auth import AzureTokenProvider, StaticTokenProvider, TokenSource
from .fake import FakeImage, FakeSpeech, FakeText, FakeVideo
from .live import ImageClient, SpeechClient, TextClient, VideoClient

ROLE_LABELS = {
    "text-draft": "Text: drafting",
    "text-judge": "Text: judge / checker",
    "image": "Image",
    "video": "Video",
    "voice": "Voice",
    "listen-back": "Listen-back (speech to text)",
}


@dataclass
class RoleInfo:
    role: str
    label: str
    configured: bool
    resource: str
    deployment: str
    model: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _host(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.split(".")[0] if host else ""


class Providers:
    def __init__(self, settings: Settings, *, tokens: TokenSource | None = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.fake = settings.provider_mode == "fake"
        if self.fake:
            self.tokens: TokenSource = StaticTokenProvider()
            self.text: Any = FakeText()
            self.image: Any = FakeImage()
            self.video: Any = FakeVideo()
            self.speech: Any = FakeSpeech()
            return
        self.tokens = tokens or AzureTokenProvider(settings.azure_scope)
        self.text = TextClient(settings.text_endpoint, self.tokens, transport) if settings.text_endpoint else None
        self.image = (ImageClient(settings.image_endpoint, settings.image_deployment, self.tokens,
                                  settings.image_per_minute, transport)
                      if settings.image_endpoint and settings.image_deployment else None)
        self.video = (VideoClient(settings.video_endpoint, settings.video_deployment, self.tokens, transport)
                      if settings.video_endpoint and settings.video_deployment else None)
        self.speech = (SpeechClient(settings.speech_region, settings.speech_resource_id, self.tokens,
                                    settings.voice_model, transport)
                       if settings.speech_region and settings.speech_resource_id else None)

    @property
    def auth_mode(self) -> str:
        return "Offline fake providers" if self.fake else getattr(self.tokens, "mode", "Azure")

    def deployment(self, role: str) -> str:
        s = self.settings
        return {
            "text-draft": s.text_draft_deployment or ("fake-text" if self.fake else ""),
            "text-judge": s.text_judge_deployment or s.text_draft_deployment or ("fake-text" if self.fake else ""),
            "image": s.image_deployment or ("fake-image" if self.fake else ""),
            "video": s.video_deployment or ("fake-video" if self.fake else ""),
            "voice": s.voice_model,
            "listen-back": "speech-to-text",
        }[role]

    def ready(self, role: str) -> bool:
        if self.fake:
            return True
        s = self.settings
        return {
            "text-draft": self.text is not None and bool(s.text_draft_deployment),
            "text-judge": self.text is not None and bool(s.text_judge_deployment or s.text_draft_deployment),
            "image": self.image is not None,
            "video": self.video is not None,
            "voice": self.speech is not None,
            "listen-back": self.speech is not None,
        }[role]

    def roles(self) -> list[RoleInfo]:
        s = self.settings
        fake = " (offline fake)" if self.fake else ""
        speech_resource = (s.speech_resource_id.rstrip("/").split("/")[-1] if s.speech_resource_id else "")
        version = f" ({s.video_model_version})" if s.video_model_version else ""
        note_video = f"retires {s.video_retires_on}" if s.video_retires_on else ""
        return [
            RoleInfo("text-draft", ROLE_LABELS["text-draft"], self.ready("text-draft"), _host(s.text_endpoint) + fake,
                     self.deployment("text-draft"), self.deployment("text-draft")),
            RoleInfo("text-judge", ROLE_LABELS["text-judge"], self.ready("text-judge"), _host(s.text_endpoint) + fake,
                     self.deployment("text-judge"), self.deployment("text-judge")),
            RoleInfo("image", ROLE_LABELS["image"], self.ready("image"), _host(s.image_endpoint) + fake,
                     self.deployment("image"), s.image_model_label, f"{s.image_per_minute} per minute"),
            RoleInfo("video", ROLE_LABELS["video"], self.ready("video"), _host(s.video_endpoint) + fake,
                     self.deployment("video") + version, s.video_model_label, note_video),
            RoleInfo("voice", ROLE_LABELS["voice"], self.ready("voice"), (speech_resource or "") + fake,
                     f"Speech · {s.voice_model}", s.voice_model, s.speech_region),
            RoleInfo("listen-back", ROLE_LABELS["listen-back"], self.ready("listen-back"),
                     (speech_resource or "") + fake, "Speech to text", "Azure Speech STT", s.speech_region),
        ]
