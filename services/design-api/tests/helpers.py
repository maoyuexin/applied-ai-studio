import io
import time
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image


def png_bytes(color: tuple[int, int, int] = (180, 180, 190), size: tuple[int, int] = (1024, 576)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client: TestClient, name: str = "design.png") -> dict[str, Any]:
    response = client.post("/api/design/uploads", files={"file": (name, png_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


def wait_for(client: TestClient, run_id: str, predicate: Callable[[dict[str, Any]], bool],
             timeout: float = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    detail: dict[str, Any] = {}
    while time.monotonic() < deadline:
        detail = client.get(f"/api/design/runs/{run_id}").json()
        if predicate(detail):
            return detail
        time.sleep(0.05)
    statuses = [(s["key"], s["status"], s.get("error")) for s in detail.get("steps", [])]
    raise AssertionError(f"Timed out. Run status {detail.get('run', {}).get('status')}; steps {statuses}; "
                         f"events {[e['message'] for e in detail.get('events', [])][-6:]}")


def at_gate(step: str) -> Callable[[dict[str, Any]], bool]:
    return lambda d: any(s["key"] == step and s["status"] == "waiting" for s in d["steps"]) and not any(
        a["status"] in ("queued", "running") for a in d["artifacts"] if a["step_key"] == step)


def run_status(*statuses: str) -> Callable[[dict[str, Any]], bool]:
    return lambda d: d["run"]["status"] in statuses


def act(client: TestClient, run_id: str, action: str, payload: dict[str, Any] | None = None,
        expect: int = 200) -> dict[str, Any]:
    response = client.post(f"/api/design/runs/{run_id}/actions/{action}", json=payload or {})
    assert response.status_code == expect, response.text
    return response.json()
