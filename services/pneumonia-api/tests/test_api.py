import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_model_samples_and_bounded_score_contract() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            model = await client.get("/api/pneumonia/model")
            samples = await client.get("/api/pneumonia/samples?limit=8")

            assert health.status_code == 200
            assert health.json() == {
                "status": "ok",
                "service": "pneumonia-api",
                "model": "loaded",
            }
            assert model.status_code == 200
            assert model.json()["trainable_parameters"] == 79_009
            assert model.json()["metrics"]["false_negatives"] == 26
            assert "not a diagnosis" in model.json()["score_note"]
            assert samples.status_code == 200
            assert len(samples.json()) == 8

            example = samples.json()[0]
            scored = await client.post(
                "/api/pneumonia/score", json={"sample_id": example["sample_id"]}
            )
            assert scored.status_code == 200
            result = scored.json()
            assert result["quality"]["status"] == "sufficient"
            assert result["model_score"] is not None
            assert result["route"] == (
                "priority_review"
                if result["model_score"] >= result["threshold"]
                else "standard_review"
            )
            assert result["dataset_label"] == example["dataset_label"]
            assert result["overlay_data_uri"].startswith("data:image/png;base64,")

            changed = await client.post(
                "/api/pneumonia/score",
                json={"sample_id": example["sample_id"], "exposure_shift": -30},
            )
            assert changed.status_code == 200
            assert changed.json()["transformed"] is True
            assert changed.json()["dataset_label"] is None

            held = await client.post(
                "/api/pneumonia/score",
                json={"sample_id": example["sample_id"], "exposure_shift": -100},
            )
            assert held.status_code == 200
            assert held.json()["route"] == "quality_hold"
            assert held.json()["model_score"] is None
            assert held.json()["overlay_data_uri"] is None

    asyncio.run(run())


def test_queue_errors_and_request_schema() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            queue = await client.get("/api/pneumonia/review-queue?limit=10")
            assert queue.status_code == 200
            payload = queue.json()
            scores = [item["model_score"] for item in payload["items"]]
            assert scores == sorted(scores, reverse=True)
            assert all(score >= payload["summary"]["threshold"] for score in scores)
            assert payload["summary"]["priority_review"] == 397
            assert payload["summary"]["standard_review"] == 227
            assert {item["comparison"] for item in payload["teaching_cases"]} == {
                "false_positive",
                "false_negative",
            }

            unknown = await client.post(
                "/api/pneumonia/score", json={"sample_id": "test-9999"}
            )
            assert unknown.status_code == 422
            extra = await client.post(
                "/api/pneumonia/score",
                json={"sample_id": "test-0000", "image": "not allowed"},
            )
            assert extra.status_code == 422
            invalid_transform = await client.post(
                "/api/pneumonia/score",
                json={"sample_id": "test-0000", "blur_radius": 13},
            )
            assert invalid_transform.status_code == 422

    asyncio.run(run())