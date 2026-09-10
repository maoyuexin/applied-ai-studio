from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_ARTIFACT_DIR = REPOSITORY_ROOT / "notebooks" / "credit-risk" / "artifacts"


class Settings(BaseSettings):
    service_name: str = "credit-api"
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    # Classroom assumption, not a measured bank figure: how many accounts this
    # team can actually review in a month. It draws the capacity line on the
    # queue so a student can see the queue outgrow the people who work it.
    review_capacity: int = 15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
