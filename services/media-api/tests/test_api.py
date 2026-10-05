import asyncio
import base64

import httpx
from httpx import ASGITransport, AsyncClient

from app.clients import FoundryImageClient, MediaProviderError
from app.config import Settings
from app.main import create_app


PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\nnot-a-real-image").decode("ascii")


class FakeImageClient:
    def __init__(self) -> None:
        self.generated: list[str] = []
        self.edited: list[tuple[str, str]] = []

    async def generate(self, prompt: str) -> str:
        self.generated.append(prompt)
        return PNG_B64

    async def edit(self, prompt: str, image_b64: str) -> str:
        self.edited.append((prompt, image_b64))
        return PNG_B64


class ContentFilterImageClient:
    async def generate(self, prompt: str) -> str:
        raise MediaProviderError(
            "The vendor's filter blocked the generated response (BingBlockList). Treat this "
            "as classroom evidence that automated guardrails can create false positives.",
            status_code=400,
            provider_code="content_safety_violation",
            content_filter=True,
        )

    async def edit(self, prompt: str, image_b64: str) -> str:
        return PNG_B64


class FakeVideoClient:
    def __init__(self) -> None:
        self.created: list[str] = []

    async def create(self, prompt: str, input_reference_b64: str | None = None) -> dict:
        self.created.append(prompt)
        return {"id": "video_test", "status": "queued", "progress": 0}

    async def get(self, video_id: str) -> dict:
        return {"id": video_id, "status": "completed", "progress": 100}

    async def download(self, video_id: str) -> bytes:
        return b"fake mp4 bytes"


def image_payload() -> dict:
    return {
        "shot_id": "s1",
        "options": {
            "paint": "Moonlit graphite",
            "lighting": "Dark studio light sweep",
            "wheels": "Turbine alloy",
            "setting": "Quiet studio",
        },
        "free_text": "slower light sweep",
    }


def test_status_reports_live_flags_and_disabled_generation() -> None:
    async def run() -> None:
        app = create_app(Settings(live_images=False, live_video=False), image_client=FakeImageClient())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            status = await client.get("/api/media/status")
            assert status.status_code == 200
            payload = status.json()
            assert payload["live_images"] is False
            assert payload["live_video"] is False
            assert payload["remaining_daily_quota"] == {"images": 40, "videos": 4}

            response = await client.post("/api/media/images/generate", json=image_payload())
            assert response.status_code == 503
            assert response.json()["detail"] == "Live image generation is disabled."

    asyncio.run(run())


def test_live_off_disables_video_generation_too() -> None:
    async def run() -> None:
        app = create_app(Settings(live_video=False), video_client=FakeVideoClient())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/media/videos", json={"shot_id": "s1"})
            assert response.status_code == 503
            assert response.json()["detail"] == "Live video generation is disabled."

    asyncio.run(run())


def test_live_image_generation_builds_prompt_server_side_and_enforces_quota() -> None:
    async def run() -> None:
        fake = FakeImageClient()
        app = create_app(
            Settings(live_images=True, daily_image_cap=1),
            image_client=fake,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/media/images/generate", json=image_payload())
            assert response.status_code == 200
            payload = response.json()
            assert payload["image_data_url"] == f"data:image/png;base64,{PNG_B64}"
            assert payload["remaining_daily_quota"]["images"] == 0
            assert "SOLENNE GT is a fictional" in payload["prompt_summary"]
            assert "Moonlit graphite" in payload["prompt_summary"]
            assert "slower light sweep" in payload["prompt_summary"]
            assert fake.generated == [payload["prompt_summary"]]

            exhausted = await client.post("/api/media/images/generate", json=image_payload())
            assert exhausted.status_code == 429
            assert "quota is exhausted" in exhausted.json()["detail"]

    asyncio.run(run())


def test_content_filter_error_is_teachable_not_a_crash() -> None:
    async def run() -> None:
        app = create_app(
            Settings(live_images=True),
            image_client=ContentFilterImageClient(),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/media/images/generate", json=image_payload())
            assert response.status_code == 409
            assert "vendor's filter blocked" in response.json()["detail"]
            assert "false positives" in response.json()["detail"]

    asyncio.run(run())


def test_live_image_edit_requires_png_b64_and_calls_edit_endpoint() -> None:
    async def run() -> None:
        fake = FakeImageClient()
        app = create_app(Settings(live_images=True), image_client=fake)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            bad = await client.post(
                "/api/media/images/edit",
                json={**image_payload(), "image_b64": base64.b64encode(b"not png").decode("ascii")},
            )
            assert bad.status_code == 422

            good = await client.post(
                "/api/media/images/edit",
                json={**image_payload(), "image_b64": PNG_B64},
            )
            assert good.status_code == 200
            assert fake.edited[0][1] == PNG_B64
            assert "Edit the supplied image" in fake.edited[0][0]

    asyncio.run(run())


def test_foundry_image_client_retries_mai_rate_limit_and_sends_bearer_token() -> None:
    class FakeTokenProvider:
        async def token(self) -> str:
            return "test-token"

    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert request.headers["authorization"] == "Bearer test-token"
            if len(requests) == 1:
                return httpx.Response(
                    429,
                    json={
                        "error": {
                            "code": "RateLimitReached",
                            "message": "Requests to this deployment exceeded 6 requests per minute.",
                        }
                    },
                )
            return httpx.Response(200, json={"data": [{"b64_json": PNG_B64}]})

        client = FoundryImageClient(
            Settings(image_retry_backoff_seconds=0),
            token_provider=FakeTokenProvider(),
            transport=httpx.MockTransport(handler),
        )

        assert await client.generate("prompt") == PNG_B64
        assert len(requests) == 2

    asyncio.run(run())


def test_live_video_create_poll_and_download_are_mocked() -> None:
    async def run() -> None:
        fake = FakeVideoClient()
        app = create_app(Settings(live_video=True, daily_video_cap=1), video_client=fake)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post(
                "/api/media/videos",
                json={"shot_id": "s2", "free_text": "hold the coastal reflection"},
            )
            assert created.status_code == 200
            assert created.json()["id"] == "video_test"
            assert created.json()["remaining_daily_quota"]["videos"] == 0
            assert "hold the coastal reflection" in fake.created[0]

            polled = await client.get("/api/media/videos/video_test")
            assert polled.status_code == 200
            payload = polled.json()
            assert payload["status"] == "completed"
            assert payload["progress"] == 100
            assert payload["video_data_url"] == (
                "data:video/mp4;base64," + base64.b64encode(b"fake mp4 bytes").decode("ascii")
            )

            exhausted = await client.post("/api/media/videos", json={"shot_id": "s1"})
            assert exhausted.status_code == 429

    asyncio.run(run())
