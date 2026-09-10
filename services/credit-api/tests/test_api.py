import asyncio
import json

import pandas as pd
from httpx import ASGITransport, AsyncClient

from app.config import DEFAULT_ARTIFACT_DIR
from app.main import create_app


def read_manifest() -> pd.DataFrame:
    manifest = pd.read_parquet(DEFAULT_ARTIFACT_DIR / "sample_manifest.parquet")
    manifest["account_id"] = manifest["account_id"].astype(str)
    return manifest


def test_health_model_and_samples() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            model = await client.get("/api/credit/model")
            samples = await client.get("/api/credit/samples?limit=8")

            assert health.status_code == 200
            readiness = health.json()
            assert readiness["status"] == "ok"
            assert readiness["service"] == "credit-api"
            assert readiness["model"] == "loaded"
            assert readiness["packaged_accounts"] == 60
            assert all(readiness["artifacts"].values())
            assert set(readiness["artifacts"]) == {
                "model.joblib",
                "model_card.json",
                "evaluation.json",
                "operating_policy.json",
                "sample_manifest.parquet",
            }
            assert readiness["model_version"]

            assert model.status_code == 200
            info = model.json()
            assert info["packaging"].startswith("joblib Pipeline")
            assert [feature["name"] for feature in info["features"]] == [
                "months_late_now",
                "worst_delay_6m",
                "num_late_months_6m",
                "utilization",
                "payment_ratio_6m",
                "bill_trend_6m",
                "credit_limit",
            ]
            # The governance view needs the frozen test numbers, the policy in
            # plain words, the boundary, and the fairness evidence.
            assert info["test_metrics"]["auc"] == 0.7852
            assert info["test_metrics"]["confusion"]["TP"] == 367
            assert info["policy"]["review_cost_NT"] == 10000
            assert "analyst decides" in info["policy"]["boundary"]
            assert info["fairness"]["excluded_columns"] == ["SEX", "MARRIAGE", "AGE"]
            assert info["fairness"]["delta_auc"] == 0.0015
            slices = {group["key"]: group for group in info["fairness"]["slices"]}
            assert set(slices) == {"sex", "age_band"}
            assert {row["group"] for row in slices["sex"]["rows"]} == {"female", "male"}
            assert len(slices["age_band"]["rows"]) == 5
            assert all(
                {"accounts", "mean_score", "flagged_share", "actual_default_rate"} <= set(row)
                for group in info["fairness"]["slices"]
                for row in group["rows"]
            )
            assert info["limitations"] and info["excluded_uses"]

            assert samples.status_code == 200
            packaged = samples.json()
            assert len(packaged) == 8
            # Both routes and both later outcomes are represented, so the page can
            # show a catch, a false alarm, and a miss.
            assert {account["route"] for account in packaged} == {
                "priority_review",
                "standard_monitoring",
            }
            assert {account["actual_outcome"] for account in packaged} == {
                "Later missed the payment",
                "Later paid",
            }
            losses = [account["expected_loss_NT"] for account in packaged]
            assert losses == sorted(losses, reverse=True)

    asyncio.run(run())


def test_samples_limit_is_clamped() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/credit/samples?limit=0")).status_code == 422
            assert (await client.get("/api/credit/samples?limit=99")).status_code == 422
            assert len((await client.get("/api/credit/samples?limit=1")).json()) == 1
            assert len((await client.get("/api/credit/samples?limit=24")).json()) == 24

    asyncio.run(run())


def test_score_reproduces_the_notebook_artifact_exactly() -> None:
    """The contract test: the service must return the notebook's own numbers.

    Every packaged account is scored through the API and compared with the
    probability, route, and reason codes the notebook stored in
    ``sample_manifest.parquet``. Equality is exact, not approximate: if the
    service ever rebuilt features differently, or loaded a different model, the
    probabilities would drift in the last bits and this would fail.
    """

    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            packaged = (await client.get("/api/credit/samples?limit=24")).json()
            by_id = {account["account_id"]: account for account in packaged}
            stored = manifest.set_index("account_id")

            for account_id, account in by_id.items():
                row = stored.loc[account_id]
                response = await client.post("/api/credit/score", json=account["inputs"])
                assert response.status_code == 200
                result = response.json()

                assert result["probability"] == float(row["probability"])
                assert result["route"] == row["route"]
                assert result["reasons"] == json.loads(row["reasons"])
                assert result["is_what_if"] is False
                assert result["changed_inputs"] == []
                assert result["actual_outcome"] == (
                    "Later missed the payment" if int(row["actual_outcome"]) else "Later paid"
                )
                # The policy is arithmetic on the score, not a second model.
                exposure = min(max(float(row["BILL_AMT1"]), 0.0), float(row["LIMIT_BAL"]))
                assert result["exposure_NT"] == exposure
                assert result["expected_loss_NT"] == (
                    result["probability"] * exposure * result["loss_given_default"]
                )
                assert result["route"] == (
                    "priority_review"
                    if result["expected_loss_NT"] > result["review_cost_NT"]
                    else "standard_monitoring"
                )
                assert len(result["reasons"]) <= 3
                assert all(reason["direction"] == "raises risk" for reason in result["reasons"])
                assert "not a default determination" in result["score_note"]

    asyncio.run(run())


def test_changing_an_input_becomes_a_what_if_without_a_known_outcome() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            packaged = (await client.get("/api/credit/samples?limit=8")).json()
            example = next(
                account for account in packaged if account["inputs"]["months_late_now"] >= 1
            )
            baseline = (await client.post("/api/credit/score", json=example["inputs"])).json()
            assert baseline["is_what_if"] is False
            assert baseline["actual_outcome"] is not None

            caught_up = {
                **example["inputs"],
                "months_late_now": 0.0,
                "num_late_months_6m": 0.0,
                "worst_delay_6m": 0.0,
            }
            what_if = (await client.post("/api/credit/score", json=caught_up)).json()
            assert what_if["is_what_if"] is True
            # A changed input has no known history, so no outcome is offered.
            assert what_if["actual_outcome"] is None
            assert set(what_if["changed_inputs"]) == {
                "Months behind now",
                "Worst delay in the last 6 months",
                "Late months in the last 6 months",
            }
            assert what_if["probability"] < baseline["probability"]

            # A display-only change still voids the history, and still scores.
            payment_only = {**example["inputs"], "last_payment": example["inputs"]["last_payment"] + 1}
            moved = (await client.post("/api/credit/score", json=payment_only)).json()
            assert moved["is_what_if"] is True
            assert moved["actual_outcome"] is None
            assert moved["changed_inputs"] == ["Last payment"]

            # Raising the bill moves both the model input and the money exposed.
            bigger_bill = {**example["inputs"], "current_bill": example["inputs"]["credit_limit"]}
            raised = (await client.post("/api/credit/score", json=bigger_bill)).json()
            assert raised["is_what_if"] is True
            assert raised["behavior"]["utilization"] == 1.0
            assert raised["exposure_NT"] == example["inputs"]["credit_limit"]

    asyncio.run(run())


def test_review_queue_ranks_by_expected_loss_and_prices_the_control() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            frozen = (await client.get("/api/credit/review-queue?limit=100")).json()
            summary = frozen["summary"]
            assert summary["review_cost_NT"] == 10000
            assert summary["packaged_accounts"] == 60
            assert summary["flagged_accounts"] == 15
            assert summary["review_capacity"] == 15
            assert summary["accounts_over_capacity"] == 0
            assert "synthetic classroom assumptions" in summary["assumption_note"]

            losses = [item["expected_loss_NT"] for item in frozen["items"]]
            assert losses == sorted(losses, reverse=True)
            assert len(frozen["items"]) == 15
            assert all(loss > summary["review_cost_NT"] for loss in losses)
            assert summary["total_expected_loss_NT"] == sum(losses)
            assert [item["rank"] for item in frozen["items"]] == list(range(1, 16))
            assert all(item["within_capacity"] for item in frozen["items"])

            # The frozen test-split record travels with the queue and never moves.
            assert frozen["population"]["accounts"] == 6000
            assert frozen["population"]["flagged"] == 761
            assert frozen["population"]["review_cost_NT"] == 10000
            assert len(frozen["policy_sweep"]) == 9

            # A cheaper review flags more accounts and exceeds the team's capacity.
            cheaper = (await client.get("/api/credit/review-queue?limit=100&review_cost=3000")).json()
            assert cheaper["summary"]["flagged_accounts"] == 27
            assert cheaper["summary"]["accounts_over_capacity"] == 12
            assert cheaper["summary"]["total_expected_loss_NT"] > summary["total_expected_loss_NT"]
            assert [item["within_capacity"] for item in cheaper["items"]][:15] == [True] * 15
            assert not any(item["within_capacity"] for item in cheaper["items"][15:])
            assert cheaper["population"] == frozen["population"]

            # An out-of-range control value clamps to the swept range, never errors.
            clamped = (await client.get("/api/credit/review-queue?review_cost=1")).json()
            assert clamped["summary"]["review_cost_NT"] == 1000
            assert len((await client.get("/api/credit/review-queue?limit=3")).json()["items"]) == 3
            assert (await client.get("/api/credit/review-queue?limit=0")).status_code == 422

    asyncio.run(run())


def test_score_rejects_unknown_fields_and_impossible_histories() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            example = (await client.get("/api/credit/samples?limit=1")).json()[0]["inputs"]

            unknown_field = await client.post(
                "/api/credit/score", json={**example, "actual_outcome": 1}
            )
            assert unknown_field.status_code == 422

            impossible_history = await client.post(
                "/api/credit/score",
                json={**example, "months_late_now": 5, "worst_delay_6m": 2},
            )
            assert impossible_history.status_code == 422
            assert "cannot exceed the worst delay" in impossible_history.text

            behind_but_never_late = await client.post(
                "/api/credit/score",
                json={
                    **example,
                    "months_late_now": 2,
                    "worst_delay_6m": 2,
                    "num_late_months_6m": 0,
                },
            )
            assert behind_but_never_late.status_code == 422

            out_of_range = await client.post(
                "/api/credit/score", json={**example, "payment_ratio_6m": 40}
            )
            assert out_of_range.status_code == 422

            unknown_account = await client.post(
                "/api/credit/score", json={**example, "account_id": "not-an-account"}
            )
            assert unknown_account.status_code == 422
            assert "packaged held-out accounts" in unknown_account.text

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("/health", "/api/credit/model", "/api/credit/samples"):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:credit" in response.text

    asyncio.run(run())
