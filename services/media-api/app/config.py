from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "media-api"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    live_images: bool = False
    live_video: bool = False
    daily_image_cap: int = Field(default=40, ge=0)
    daily_video_cap: int = Field(default=4, ge=0)
    max_prompt_characters: int = Field(default=1800, ge=400, le=4000)

    image_endpoint: str = "https://aifoundry-image-studio-ymao.services.ai.azure.com/mai/v1/images/generations"
    image_edit_endpoint: str = "https://aifoundry-image-studio-ymao.services.ai.azure.com/mai/v1/images/edits"
    image_deployment: str = "mai-image-2-6"
    image_width: int = Field(default=1536, ge=768)
    image_height: int = Field(default=864, ge=1)
    image_retry_attempts: int = Field(default=3, ge=1, le=6)
    image_retry_backoff_seconds: float = Field(default=1.0, ge=0, le=30)

    video_endpoint: str = "https://kestrel-ai.openai.azure.com/openai/v1/videos"
    video_model: str = "sora-2"
    video_size: str = "1280x720"
    video_seconds: str = "4"

    azure_scope: str = "https://cognitiveservices.azure.com/.default"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MEDIA_", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def image_pixels(self) -> int:
        return self.image_width * self.image_height


settings = Settings()
