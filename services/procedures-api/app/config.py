from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_ARTIFACT_DIR = REPOSITORY_ROOT / "notebooks" / "procedure-assistant" / "artifacts"

# The longest question this service will read. The longest packaged question is
# 102 characters, and a question is a question: 500 leaves room for a wordy one
# while keeping a paste of a whole procedure out of the retriever, which would
# be truncated at 256 wordpiece tokens anyway.
MAX_QUESTION_CHARACTERS = 500


class Settings(BaseSettings):
    service_name: str = "procedures-api"
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
