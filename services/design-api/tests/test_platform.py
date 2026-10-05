import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.engine import Engine
from app.events import Broker
from app.media import MediaStore, MediaTools
from app.pipelines import build_pipelines
from app.providers.auth import StaticTokenProvider
from app.providers.base import ProviderError
from app.providers.live import ImageClient, TextClient, TextResult, VideoClient
from app.providers.registry import Providers
from app.store import Store, now
from tests.conftest import make_settings
from tests.helpers import act, at_gate, png_bytes, run_status, wait_for
from tests.test_video import video_brief


def finished_video_run(client: TestClient) -> str:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "tags": ["Module 8"], "brief": video_brief(
        shots=1, takes_per_shot=1)}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("shotlist"))
    act(client, run_id, "approve", {"step": "shotlist"})
    detail = wait_for(client, run_id, at_gate("takes"))
    take = next(a for a in detail["artifacts"] if a["kind"] == "take")
    act(client, run_id, "decide", {"artifact_id": take["id"], "verdict": "keep"})
    act(client, run_id, "approve", {"step": "takes"})
    wait_for(client, run_id, run_status("completed"), timeout=120)
    return run_id


def test_export_import_roundtrip_and_restricted(make_client: Any) -> None:
    mac, server = make_client(), make_client(install_name="Home server")
    run_id = finished_video_run(mac)
    bundle = mac.get(f"/api/design/runs/{run_id}/export")
    assert bundle.status_code == 200 and bundle.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(bundle.content)).namelist()
    assert "run.json" in names and any(name.startswith("media/") for name in names)

    imported = server.post("/api/design/runs/import", files={"file": ("bundle.zip", bundle.content,
                                                                      "application/zip")})
    assert imported.status_code == 201, imported.text
    original, copy = mac.get(f"/api/design/runs/{run_id}").json(), imported.json()
    assert copy["run"]["status"] == "completed" and copy["run"]["tags"] == ["Module 8"]
    assert len(copy["artifacts"]) == len(original["artifacts"])
    final = next(a for a in copy["artifacts"] if a["kind"] == "final")
    assert server.get(f"/api/design/media/{final['media_sha']}").status_code == 200
    assert copy["events"][-1]["code"] == "imported"
    again = server.post("/api/design/runs/import", files={"file": ("bundle.zip", bundle.content, "application/zip")})
    assert again.status_code == 409 and "already" in again.json()["detail"]

    mac.patch(f"/api/design/runs/{run_id}", json={"restricted": True})
    refused = mac.get(f"/api/design/runs/{run_id}/export")
    assert refused.status_code == 409 and "never exported" in refused.json()["detail"]


def test_import_rejects_tampered_bundle(client: TestClient) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("run.json", json.dumps({"format": "design-studio-run", "version": 1, "run": {"id": "r"},
                                                 "media": [{"sha": "a" * 64, "media_type": "image/png"}]}))
        archive.writestr("media/" + "a" * 64, b"not the right bytes")
    response = client.post("/api/design/runs/import", files={"file": ("x.zip", buffer.getvalue(), "application/zip")})
    assert response.status_code == 409 and "checksum" in response.json()["detail"]
    with zipfile.ZipFile(buffer := io.BytesIO(), "w") as archive:
        archive.writestr("../evil.txt", b"x")
        archive.writestr("run.json", "{}")
    response = client.post("/api/design/runs/import", files={"file": ("x.zip", buffer.getvalue(), "application/zip")})
    assert response.status_code == 409 and "Unexpected file" in response.json()["detail"]


def test_history_filters_patch_and_delete(client: TestClient) -> None:
    run_id = finished_video_run(client)
    assert client.get("/api/design/runs?q=SOLENNE").json()["runs"][0]["id"] == run_id
    assert client.get("/api/design/runs?pipeline=image").json()["runs"] == []
    assert client.get("/api/design/runs?tag=Module 8").json()["tags"] == ["Module 8"]
    patched = client.patch(f"/api/design/runs/{run_id}", json={"title": "Renamed", "tags": ["Friday"]}).json()
    assert patched["run"]["title"] == "Renamed" and patched["run"]["tags"] == ["Friday"]
    final = next(a for a in patched["artifacts"] if a["kind"] == "final")
    assert client.delete(f"/api/design/runs/{run_id}").status_code == 204
    assert client.get(f"/api/design/runs/{run_id}").status_code == 404
    assert client.get(f"/api/design/media/{final['media_sha']}").status_code == 404


def test_upload_rejects_non_images(client: TestClient) -> None:
    response = client.post("/api/design/uploads", files={"file": ("notes.png", b"hello", "image/png")})
    assert response.status_code == 422 and "not an image" in response.json()["detail"]
    assert client.get("/api/design/media/../../etc/passwd").status_code == 404


def test_stream_sends_hello(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief()}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("shotlist"))
    client.delete(f"/api/design/runs/{run_id}")
    assert client.get(f"/api/design/runs/{run_id}/stream").status_code == 404


def test_resume_after_restart_polls_the_saved_vendor_job(tmp_path: Path) -> None:
    """A take that was running when the server stopped resumes by its saved Sora job id instead of re-generating."""

    async def scenario() -> None:
        settings = make_settings(tmp_path)
        settings.data_dir.mkdir(parents=True)
        store = Store(settings.data_dir / "design.db")
        media = MediaStore(settings.data_dir / "media", store)
        providers = Providers(settings)
        engine = Engine(settings, store, media, MediaTools(), providers, Broker(), build_pipelines(settings))
        stamp = now()
        shot = {"id": "s1", "title": "Coast road", "subject": "scene", "mode": "t2v", "keyframe_prompt": "",
                "prompt": "The car drives along the coast at sunrise.", "sound": "", "on_screen_text": ""}
        brief = engine.pipelines["video"].normalize_brief(video_brief(shots=1, takes_per_shot=1))
        store.insert_run(
            {"id": "run_resume", "pipeline": "video", "title": "Resume", "status": "running", "brief": brief,
             "settings": {}, "tags": [], "restricted": False, "source": "studio", "current_step": "takes",
             "counters": {}, "created_at": stamp, "updated_at": stamp},
            [{"idx": 0, "key": "shotlist", "title": "Shot list", "gate": True, "status": "done",
              "data": {"shots": [shot]}},
             {"idx": 1, "key": "keyframes", "title": "Keyframes", "gate": True, "status": "skipped", "data": {}},
             {"idx": 2, "key": "takes", "title": "Takes", "gate": True, "status": "running",
              "data": {"_started": True}},
             {"idx": 3, "key": "voiceover", "title": "Voiceover", "gate": False, "status": "pending", "data": {}},
             {"idx": 4, "key": "assemble", "title": "Assemble", "gate": False, "status": "pending", "data": {}},
             {"idx": 5, "key": "provenance", "title": "Provenance", "gate": False, "status": "pending", "data": {}}])
        take = store.insert_artifact({"run_id": "run_resume", "step_key": "takes", "kind": "take", "grp": "s1",
                                      "label": "s1_t1", "status": "running", "role": "video",
                                      "prompt": shot["prompt"], "params": {"seconds": 4, "size": "1280x720",
                                                                           "mode": "t2v"},
                                      "vendor_job_id": "video_before_restart"})
        providers.video.adopt("video_before_restart", shot["prompt"])
        await engine.start()
        await engine.idle(30)
        resumed = store.get_artifact(take["id"])
        assert resumed and resumed["status"] == "ready" and resumed["media_sha"]
        assert providers.video.calls == [], "no new Sora job was created"
        assert store.get_step("run_resume", "takes")["status"] == "waiting"
        assert any(e["code"] == "resumed" for e in store.list_events("run_resume"))
        await engine.stop()
        store.close()

    asyncio.run(scenario())


# Live client behavior with recorded vendor responses


def test_image_client_retries_rate_limits_and_maps_filter_blocks() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if b"blocked" in request.content:
            return httpx.Response(400, json={"error": {"code": "content_safety_violation",
                                                       "message": "Blocked by BingBlockList"}})
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": {"code": "RateLimitReached", "message": "slow down"}})
        import base64
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]})

    client = ImageClient("https://example.services.ai.azure.com", "mai-image-2-6", StaticTokenProvider(), 60,
                         httpx.MockTransport(handler), rate_backoff=0.01)
    data = asyncio.run(client.generate("a silver car", 1536, 864))
    assert data.startswith(b"\x89PNG") and calls["count"] == 2
    with pytest.raises(ProviderError) as blocked:
        asyncio.run(client.generate("blocked", 1536, 864))
    assert blocked.value.code == "content_filter" and "BingBlockList" in str(blocked.value)
    with pytest.raises(ProviderError) as too_small:
        asyncio.run(client.generate("x", 512, 512))
    assert too_small.value.code == "bad_request"


def test_video_client_maps_busy_and_auth_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/videos") and request.method == "POST":
            return httpx.Response(429, json={"error": {"code": "too_many_requests",
                                                       "message": "Too many running tasks."}})
        return httpx.Response(401, json={"error": {"code": "Unauthorized", "message": "bad token"}})

    client = VideoClient("https://example.openai.azure.com/openai/v1", "sora-2", StaticTokenProvider(),
                         httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as busy:
        asyncio.run(client.create("x", seconds=4, size="1280x720"))
    assert busy.value.code == "too_many_tasks" and busy.value.retryable
    with pytest.raises(ProviderError) as auth:
        asyncio.run(client.get("video_1"))
    assert auth.value.code == "auth" and "az login" in str(auth.value)


def test_text_client_and_json_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "gpt-5.4-mini" and body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n{\"shots\": []}\n```"},
                                                      "finish_reason": "stop"}], "usage": {"total_tokens": 9}})

    client = TextClient("https://example.openai.azure.com/openai/v1", StaticTokenProvider(),
                        httpx.MockTransport(handler))
    result = asyncio.run(client.complete("gpt-5.4-mini", "system", "user"))
    assert result.json() == {"shots": []} and result.usage == {"total_tokens": 9}
    with pytest.raises(ProviderError):
        TextResult("no json here", 0, "m").json()


def test_image_client_retries_dropped_connections() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadError("connection dropped", request=request)
        import base64
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]})

    client = ImageClient("https://example.services.ai.azure.com", "mai-image-2-6", StaticTokenProvider(), 60,
                         httpx.MockTransport(handler), rate_backoff=0.01)
    assert asyncio.run(client.edit("a car", [png_bytes()], 1536, 864)).startswith(b"\x89PNG")
    assert calls["count"] == 2
