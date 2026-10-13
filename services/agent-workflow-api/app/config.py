from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_ROOT.parent.parent
DATA_DIR = REPO_ROOT / "data" / "agent-workflows"
RECORDINGS_DIR = DATA_DIR / "recordings"
LIVE_RUNS_DIR = DATA_DIR / "live-runs"
SPECS_FILE = DATA_DIR / "scenarios.json"
# Untracked, machine-specific, non-secret settings (endpoint, model, key *file path*).
LOCAL_SETTINGS = SERVICE_ROOT / "settings.local.json"

DEFAULT_SERVICES = {
    "fraud": "http://127.0.0.1:4340",
    "maintenance": "http://127.0.0.1:4380",
    "procedures": "http://127.0.0.1:4390",
    "forecast": "http://127.0.0.1:4400",
}


@dataclass(frozen=True)
class Settings:
    project_endpoint: str | None
    model: str | None
    services: dict[str, str]
    trial_finder_mcp_url: str | None
    trial_finder_key_file: str | None
    run_timeout_seconds: int = 480

    @property
    def live_ready(self) -> bool:
        return bool(self.project_endpoint and self.model)


def load_settings() -> Settings:
    local: dict = {}
    if LOCAL_SETTINGS.exists():
        local = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))

    def pick(env: str, key: str) -> str | None:
        return os.environ.get(env) or local.get(key) or None

    local_services = local.get("services", {})
    services = {
        name: os.environ.get(f"services__{name}__http__0") or local_services.get(name) or url
        for name, url in DEFAULT_SERVICES.items()
    }
    return Settings(
        project_endpoint=pick("FOUNDRY_PROJECT_ENDPOINT", "foundry_project_endpoint"),
        model=pick("FOUNDRY_MODEL", "foundry_model"),
        services=services,
        trial_finder_mcp_url=pick("TRIAL_FINDER_MCP_URL", "trial_finder_mcp_url"),
        trial_finder_key_file=pick("TRIAL_FINDER_KEY_FILE", "trial_finder_key_file"),
        run_timeout_seconds=int(local.get("run_timeout_seconds", 480)),
    )
