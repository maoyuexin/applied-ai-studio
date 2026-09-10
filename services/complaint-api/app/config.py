from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_ARTIFACT_DIR = REPOSITORY_ROOT / "notebooks" / "complaint-routing" / "artifacts"

# The longest complaint this service will read. The longest packaged narrative is
# 5,655 characters and the 90th percentile of the training split is well under
# that, so 8,000 accepts every real complaint in the lab while keeping one paste
# from turning into an unbounded request body.
MAX_NARRATIVE_CHARACTERS = 8_000


class Settings(BaseSettings):
    service_name: str = "complaint-api"
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
