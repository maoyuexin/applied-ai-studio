from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_ARTIFACT_DIR = REPOSITORY_ROOT / "notebooks" / "pneumonia-screening" / "artifacts"
DEFAULT_NOTEBOOK_DIR = REPOSITORY_ROOT / "notebooks" / "pneumonia-screening"


class Settings(BaseSettings):
    service_name: str = "pneumonia-api"
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    notebook_dir: Path = DEFAULT_NOTEBOOK_DIR
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()