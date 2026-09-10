from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
NOTEBOOK_DIR = REPOSITORY_ROOT / "notebooks" / "product-recommendations"
DEFAULT_ARTIFACT_DIR = NOTEBOOK_DIR / "artifacts"

# The most packaged customers one request may ask for. Twelve are packaged, so
# 24 is headroom rather than a limit anyone reaches, and it keeps a stray
# ?limit=100000 from turning into a large response.
MAX_PACKAGED_CUSTOMERS = 24


class Settings(BaseSettings):
    service_name: str = "recommend-api"
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
