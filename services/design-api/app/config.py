import sys
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AppliedAIStudio" / "design"
    return Path.home() / ".local" / "share" / "applied-ai-studio" / "design"


class Settings(BaseSettings):
    """Design Studio settings. Every model is a *role* mapped to a Foundry deployment here.

    Defaults are empty on purpose: nothing points at anyone's resources until an install
    configures its own (`services/design-api/.env`, see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=SERVICE_ROOT / ".env", env_prefix="DESIGN_", extra="ignore")

    install_name: str = "Local"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    data_dir: Path = Field(default_factory=default_data_dir)
    provider_mode: Literal["live", "fake"] = "live"
    hide_restricted: bool = False
    azure_scope: str = "https://cognitiveservices.azure.com/.default"

    # Text roles (OpenAI v1 chat completions on a Foundry / Azure OpenAI resource)
    text_endpoint: str = ""
    text_draft_deployment: str = ""
    text_judge_deployment: str = ""

    # Image role (MAI-Image REST: /mai/v1/images/generations and /edits)
    image_endpoint: str = ""
    image_deployment: str = ""
    image_model_label: str = "MAI-Image-2.6"
    image_per_minute: int = Field(default=6, ge=1, le=120)

    # Video role (OpenAI v1 Videos API)
    video_endpoint: str = ""
    video_deployment: str = ""
    video_model_label: str = "Sora 2"
    video_model_version: str = ""
    video_retires_on: str = ""
    video_concurrency: int = Field(default=2, ge=1, le=8)
    video_poll_seconds: float = Field(default=8.0, ge=0.01, le=60)
    video_timeout_seconds: float = Field(default=1200, ge=1)

    # Voice + listen-back roles (Azure Speech REST with Entra auth)
    speech_region: str = ""
    speech_resource_id: str = ""
    voice_model: str = "MAI-Voice-2.1-Flash"
    voice_locale: str = "en-US"

    # Daily caps (count toward live provider calls, including Settings tests)
    cap_video_takes: int = Field(default=20, ge=0)
    cap_images: int = Field(default=60, ge=0)
    cap_voice_lines: int = Field(default=200, ge=0)
    cap_text_calls: int = Field(default=500, ge=0)

    max_upload_mb: int = Field(default=25, ge=1, le=200)
    max_import_mb: int = Field(default=800, ge=1)
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    c2patool: str = "c2patool"

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
