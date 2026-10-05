import base64
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ShotId = Literal["s1", "s2", "s3", "s4", "s5"]
Paint = Literal["Moonlit graphite", "Pearl champagne", "Deep oxblood", "Ceramic white"]
Lighting = Literal[
    "Dark studio light sweep",
    "Blue-hour coastal road",
    "Rainy city reflections",
    "Warm gallery reveal",
]
Wheels = Literal[
    "Turbine alloy",
    "Minimal aero disc",
    "Polished split-spoke",
    "Black performance rim",
]
Setting = Literal["Quiet studio", "Coastal highway", "Modern hotel arrival", "Glass-walled gallery"]

MAX_FREE_TEXT_CHARACTERS = 160


class QuotaView(BaseModel):
    images: int
    videos: int


class StatusResponse(BaseModel):
    service: str
    live_images: bool
    live_video: bool
    remaining_daily_quota: QuotaView
    caps: QuotaView
    image_model: str
    video_model: str
    note: str


class ImageOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paint: Paint
    lighting: Lighting
    wheels: Wheels
    setting: Setting


class ImageGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: ShotId
    options: ImageOptions
    free_text: str | None = Field(default=None, max_length=MAX_FREE_TEXT_CHARACTERS)

    @field_validator("free_text")
    @classmethod
    def clean_free_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = " ".join(value.split())
        return stripped or None


class ImageEditRequest(ImageGenerateRequest):
    image_b64: str = Field(min_length=16, max_length=7_500_000)

    @field_validator("image_b64")
    @classmethod
    def validate_png_b64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as error:
            raise ValueError("image_b64 must be valid base64-encoded PNG bytes") from error
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("image_b64 must contain PNG bytes")
        return value


class ImageResponse(BaseModel):
    image_data_url: str
    elapsed_seconds: float
    prompt_summary: str
    remaining_daily_quota: QuotaView


class VideoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: ShotId
    free_text: str | None = Field(default=None, max_length=MAX_FREE_TEXT_CHARACTERS)
    input_reference_b64: str | None = Field(default=None, min_length=16, max_length=7_500_000)

    @field_validator("free_text")
    @classmethod
    def clean_free_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = " ".join(value.split())
        return stripped or None

    @field_validator("input_reference_b64")
    @classmethod
    def validate_reference_b64(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as error:
            raise ValueError("input_reference_b64 must be valid base64-encoded PNG bytes") from error
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("input_reference_b64 must contain PNG bytes")
        return value


class VideoJobResponse(BaseModel):
    id: str
    status: str
    progress: int | None = None
    prompt_summary: str | None = None
    remaining_daily_quota: QuotaView | None = None
    video_data_url: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    live_images: bool
    live_video: bool
