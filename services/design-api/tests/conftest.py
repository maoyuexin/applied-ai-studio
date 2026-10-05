from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "provider_mode": "fake", "data_dir": tmp_path / "data", "video_poll_seconds": 0.01,
        "install_name": "Test", "c2patool": "c2patool-not-installed-for-tests",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture()
def make_client(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(**overrides: Any) -> TestClient:
        folder = tmp_path / f"install{len(clients)}"
        client = TestClient(create_app(make_settings(folder, **overrides)))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture()
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
