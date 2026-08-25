import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_model_samples_and_score_contract() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            model = await client.get("/api/fraud/model")
            samples = await client.get("/api/fraud/samples?limit=8")

            assert health.status_code == 200
            assert health.json() == {"status": "ok", "service": "fraud-api", "model": "loaded"}
            assert model.status_code == 200
            assert model.json()["packaging"].startswith("MLflow pyfunc")
            assert len(model.json()["features"]) == 13
            assert samples.status_code == 200
            assert len(samples.json()) == 8

            example = samples.json()[0]
            scored = await client.post("/api/fraud/score", json=example["transaction"])
            assert scored.status_code == 200
            prediction = scored.json()
            assert 0 <= prediction["fraud_score"] <= 1
            assert prediction["decision"] == (
                "review" if prediction["fraud_score"] >= prediction["threshold"] else "normal"
            )
            assert "not proof" in prediction["score_note"]
            explanation = prediction["explanation"]
            contributions = explanation["contributions"]
            reconstructed_score = explanation["baseline_score"] + sum(
                item["contribution"] for item in contributions
            )
            assert explanation["method"] == "Tree SHAP"
            assert abs(reconstructed_score - prediction["fraud_score"]) < 1e-6
            assert contributions == sorted(
                contributions,
                key=lambda item: abs(item["contribution"]),
                reverse=True,
            )
            assert {item["feature"] for item in contributions} == {
                "amount",
                "amount_ratio_to_card_mean",
                "card_transactions_1h",
                "card_transactions_24h",
                "minutes_since_previous",
                "distance_from_home_km",
                "customer_age",
                "city_population",
                "occurred_at",
                "category",
            }

            normal_example = next(
                sample
                for sample in samples.json()
                if sample["scenario_id"].startswith("normal-transaction")
            )
            normal_score = await client.post(
                "/api/fraud/score",
                json=normal_example["transaction"],
            )
            assert normal_score.status_code == 200
            assert normal_score.json()["decision"] == "normal"
            assert normal_score.json()["decision_label"] == "Not flagged for review"

            card_average = example["transaction"]["amount"] / example["transaction"][
                "amount_ratio_to_card_mean"
            ]
            low_amount_score = await client.post(
                "/api/fraud/score",
                json={
                    **example["transaction"],
                    "amount": 2,
                    "amount_ratio_to_card_mean": 2 / card_average,
                },
            )
            ratio_driver = next(
                item
                for item in low_amount_score.json()["explanation"]["contributions"]
                if item["feature"] == "amount_ratio_to_card_mean"
            )
            assert ratio_driver["value"] == "0.03x usual"

    asyncio.run(run())


def test_review_queue_is_sorted_and_schema_is_strict() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            queue = await client.get("/api/fraud/review-queue?limit=10")
            assert queue.status_code == 200
            payload = queue.json()
            scores = [item["fraud_score"] for item in payload["items"]]
            assert scores == sorted(scores, reverse=True)
            assert all(score >= payload["summary"]["threshold"] for score in scores)

            sample = (await client.get("/api/fraud/samples?limit=1")).json()[0]["transaction"]
            invalid = await client.post("/api/fraud/score", json={**sample, "future_label": 1})
            assert invalid.status_code == 422

            impossible_velocity = await client.post(
                "/api/fraud/score",
                json={
                    **sample,
                    "card_transactions_1h": sample["card_transactions_24h"] + 1,
                },
            )
            assert impossible_velocity.status_code == 422
            assert "1 hour cannot exceed" in impossible_velocity.text

    asyncio.run(run())