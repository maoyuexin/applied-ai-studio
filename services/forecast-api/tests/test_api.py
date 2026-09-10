import asyncio
import json

import pandas as pd
from httpx import ASGITransport, AsyncClient

from app.config import DEFAULT_ARTIFACT_DIR
from app.main import create_app


def read_manifest() -> pd.DataFrame:
    return pd.read_parquet(DEFAULT_ARTIFACT_DIR / "sample_manifest.parquet")


def test_health_reports_artifact_readiness_and_version() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            payload = health.json()
            assert payload["status"] == "ok"
            assert payload["service"] == "forecast-api"
            assert payload["model"] == "loaded"
            assert payload["model_version"] == "M06-fc-1.0"
            assert payload["policy_version"] == "M06-policy-1.0"
            assert payload["packaged_products"] == 10
            assert payload["cohort_products"] == 469
            assert payload["scored_product_weeks"] == 12194
            assert all(payload["artifacts"].values())
            assert set(payload["artifacts"]) == {
                "forecaster.joblib",
                "model_card.json",
                "evaluation.json",
                "operating_policy.json",
                "sample_manifest.parquet",
                "online_retail_weekly.csv.gz",
            }

    asyncio.run(run())


def test_model_carries_the_frozen_evidence_the_sweep_and_the_christmas_failure() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/forecast/model")
            assert response.status_code == 200
            info = response.json()

            assert info["model_version"] == "M06-fc-1.0"
            assert "moving average" in info["model_type"]
            assert info["cohort_products"] == 469
            assert info["residuals_per_product"] == 68

            # The frozen holdout, scored once. Every number the page prints.
            evaluation = info["evaluation"]
            assert evaluation["scored_once"] is True
            assert evaluation["rows"] == 12194
            assert evaluation["test_weeks"] == 26
            assert evaluation["mae_units"] == 51.5667
            assert evaluation["rmse_units"] == 133.2642
            assert evaluation["coverage_delivered"] == 0.8406
            assert evaluation["coverage_promised"] == 0.8
            assert evaluation["median_band_units"] == 88.075
            assert evaluation["band_over_median_demand"] == 2.5904
            assert [
                evaluation["pinball_10"],
                evaluation["pinball_50"],
                evaluation["pinball_90"],
            ] == [8.8938, 25.7833, 19.0267]
            # A flat-zero forecast beats the model on MAPE, which is why MAPE is
            # reported here only as a warning.
            assert evaluation["mape_of_a_flat_zero_forecast"] < 1
            assert evaluation["mape_of_the_point_forecast"] > 1e12
            assert "MAPE" in evaluation["metric_not_reported"]

            # The boundary has to survive the trip to the page, word for word.
            assert "not a promise" in info["boundary_short"]
            assert "not a guarantee" in info["boundary_short"]
            assert "never places one" in info["boundary_short"]
            assert "never places an order" in info["authority_boundary"]

            policy = info["policy"]
            assert policy["policy_version"] == "M06-policy-1.0"
            assert policy["critical_ratios"] == {"2:1": 0.6667, "4:1": 0.8, "9:1": 0.9}
            assert policy["cohort_size"] == 469
            assert policy["products_refused"] == 4402
            assert policy["window_weeks"] == 8
            assert policy["horizon_weeks"] == 1
            assert policy["costs_are_classroom_assumptions"] is True
            assert "CLASSROOM ASSUMPTION" in policy["cost_assumption_note"]

            # The newsvendor sweep, straight from the notebook's evidence file.
            sweep = {row["ratio"]: row for row in info["newsvendor_sweep"]}
            assert set(sweep) == {"2:1", "3:1", "4:1", "6:1", "9:1", "19:1"}
            assert round(sweep["2:1"]["vs_point_pct"], 1) == -0.1
            assert round(sweep["4:1"]["vs_point_pct"], 1) == -9.4
            assert round(sweep["9:1"]["vs_point_pct"], 1) == -28.3
            assert round(sweep["4:1"]["shortfall_point"]) == 337594
            assert round(sweep["4:1"]["shortfall_quantile"]) == 197366
            assert round(sweep["9:1"]["shortfall_quantile"]) == 124679

            # The interval comparison, including the accurate model that was the
            # wrong model: better MAE, worse coverage.
            methods = {row["method"]: row for row in info["interval_methods"]}
            deployed = next(name for name in methods if "DEPLOYED" in name)
            assert methods[deployed]["coverage"] == 0.8406
            boosted = next(name for name in methods if name.startswith("B1"))
            assert methods[boosted]["MAE_of_median"] < methods[deployed]["MAE_of_median"]
            assert methods[boosted]["coverage"] < 0.8

            # Seasonal-naive loses to forecasting zero forever.
            baselines = {row["Point forecast"]: row for row in info["point_baselines"]}
            seasonal = next(name for name in baselines if name.startswith("Seasonal-naive"))
            flat = next(name for name in baselines if name.startswith("Flat zero"))
            assert baselines[seasonal]["MAE"] > baselines[flat]["MAE"]

            # The Christmas table: the average is fine and the ramp is not.
            christmas = info["seasonal_coverage"]
            assert len(christmas["slices"]) == 4
            assert christmas["worst_slice_coverage"] == 66.2
            assert "RAMP" in christmas["worst_slice_label"]
            assert christmas["misses_above_band_share"] == "69%"

            outcomes = {row["ratio"]: row for row in info["per_product_outcomes"]}
            assert outcomes["4:1"]["cheaper"] == 354
            assert outcomes["4:1"]["more_expensive"] == 115
            assert round(outcomes["4:1"]["cheaper_share"], 3) == 0.755

            assert info["limitations"]
            assert info["monitoring"]

    asyncio.run(run())


def test_products_are_the_packaged_products_and_the_limit_is_clamped() -> None:
    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/forecast/products?limit=24")
            assert response.status_code == 200
            products = response.json()
            assert len(products) == len(manifest) == 10
            assert [item["product_id"] for item in products] == list(
                manifest["StockCode"].astype(str)
            )
            # The packaged set is not a highlight reel: it carries the products
            # where the policy costs more, on purpose.
            assert any(item["policy_is_cheaper"] for item in products)
            assert any(not item["policy_is_cheaper"] for item in products)
            for item, (_, row) in zip(products, manifest.iterrows()):
                assert item["product"] == row["product"]
                assert item["unit_price"] == float(row["unit_price"])
                assert item["coverage"] == float(row["coverage"])
                assert item["cost_change_pct"] == float(row["cost_change_pct"])
                assert item["mean_units_per_week"] == float(row["test_mean_units"])
                assert item["demand_summary"]
                assert item["policy_outcome"]

            assert len((await client.get("/api/forecast/products?limit=1")).json()) == 1
            assert (await client.get("/api/forecast/products?limit=0")).status_code == 422
            assert (await client.get("/api/forecast/products?limit=99")).status_code == 422

    asyncio.run(run())


def test_planning_a_packaged_product_reproduces_the_stored_forecast_exactly() -> None:
    """The contract test: serving must return the notebook's own numbers.

    The service rebuilds the weekly panel from the committed CSV, re-scores the
    held-out weeks with the exported forecaster, and prices the orders through the
    notebook's own PolicyBoard. Every packaged product is planned through the API
    and compared with what the notebook stored in ``sample_manifest.parquet``.
    Equality is exact, not approximate: if the service rebuilt the panel
    differently, read the band at a different quantile, or priced a unit
    differently, one of these would move.
    """

    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _, row in manifest.iterrows():
                code = str(row["StockCode"])
                response = await client.post(
                    "/api/forecast/plan", json={"product_id": code}
                )
                assert response.status_code == 200
                plan = response.json()

                assert plan["product"] == row["product"]
                assert plan["why_this_product"] == row["why_this_product"]
                assert plan["unit_price"] == float(row["unit_price"])
                assert plan["weeks_planned"] == int(row["test_weeks"]) == 26
                assert plan["cost_ratio"] == 4.0
                assert plan["critical_ratio"] == 0.8
                assert plan["is_policy_ratio"] is True

                # Week for week: the actual, the point forecast, both edges of the
                # band, and whether the band caught what happened.
                stored = json.loads(row["weekly"])
                assert len(plan["weekly"]) == len(stored)
                for got, want in zip(plan["weekly"], stored):
                    assert got["week"] == want["week"]
                    assert got["actual"] == want["actual"]
                    assert got["point"] == want["point"]
                    assert got["low"] == want["low"]
                    assert got["high"] == want["high"]
                    assert got["covered"] == want["covered"]
                    # The point forecast is what ordering at the point orders.
                    assert got["order_point"] == want["point"]
                    assert got["order_quantile"] >= got["point"] - 0.05

                # Both order quantities, and what each one cost over the 26 weeks.
                assert plan["point_plan"]["units_short"] == float(row["units_short_point"])
                assert plan["point_plan"]["units_excess"] == float(row["units_excess_point"])
                assert plan["point_plan"]["cost"] == float(row["cost_point"])
                assert plan["quantile_plan"]["units_short"] == float(
                    row["units_short_quantile"]
                )
                assert plan["quantile_plan"]["units_excess"] == float(
                    row["units_excess_quantile"]
                )
                assert plan["quantile_plan"]["cost"] == float(row["cost_quantile"])
                assert plan["cost_change_pct"] == float(row["cost_change_pct"])
                assert plan["policy_is_cheaper"] is bool(row["policy_is_cheaper"])

                # And the interval's own report card for this product.
                assert plan["coverage"] == float(row["coverage"])
                assert plan["misses"] == int(row["misses"])
                assert plan["misses_above_band"] == int(row["misses_above_band"])
                assert plan["band_over_demand"] == float(row["band_over_demand"])
                assert plan["mean_units_per_week"] == float(row["test_mean_units"])

                # Context the manifest does not carry, but the chart needs.
                assert len(plan["history"]) == 12
                assert plan["history"][-1]["week"] < plan["weekly"][0]["week"]
                assert plan["latest"]["week"] == plan["weekly"][-1]["week"]
                assert "not a promise" in plan["boundary"]

    asyncio.run(run())


def test_the_cost_ratio_moves_the_order_quantity_and_never_the_forecast() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def plan(**body: object) -> dict:
                response = await client.post("/api/forecast/plan", json=body)
                assert response.status_code == 200
                return response.json()

            frozen = await plan(product_id="85099B")
            cautious = await plan(product_id="85099B", cost_ratio=9)
            even = await plan(product_id="85099B", cost_ratio=1)

            assert frozen["critical_ratio"] == 0.8
            assert cautious["critical_ratio"] == 0.9
            assert even["critical_ratio"] == 0.5
            assert cautious["is_policy_ratio"] is False
            assert "what-if" in cautious["ratio_note"]

            # The order moves with the ratio; the forecast and the band never do.
            assert (
                even["quantile_plan"]["units_ordered"]
                < frozen["quantile_plan"]["units_ordered"]
                < cautious["quantile_plan"]["units_ordered"]
            )
            assert cautious["quantile_plan"]["units_short"] < frozen["quantile_plan"][
                "units_short"
            ]
            assert cautious["quantile_plan"]["units_excess"] > frozen["quantile_plan"][
                "units_excess"
            ]
            for other in (cautious, even):
                assert [week["point"] for week in other["weekly"]] == [
                    week["point"] for week in frozen["weekly"]
                ]
                assert [week["low"] for week in other["weekly"]] == [
                    week["low"] for week in frozen["weekly"]
                ]
                assert [week["high"] for week in other["weekly"]] == [
                    week["high"] for week in frozen["weekly"]
                ]
                assert other["point_plan"]["units_ordered"] == frozen["point_plan"][
                    "units_ordered"
                ]
                assert other["coverage"] == frozen["coverage"]

            # A unit short and a unit left over costing the same is the one case
            # where the newsvendor order is the middle of the band.
            assert even["quantile_plan"]["quantile"] == 0.5

            # A control dragged out of range clamps instead of failing.
            assert (await plan(product_id="85099B", cost_ratio=999))["cost_ratio"] == 20.0
            assert (await plan(product_id="85099B", cost_ratio=0))["cost_ratio"] == 1.0

            # The product where the policy loses money is still allowed to lose it.
            loser = await plan(product_id="22084")
            assert loser["policy_is_cheaper"] is False
            assert loser["cost_change_pct"] > 0

    asyncio.run(run())


def test_the_policy_sweep_recomputes_the_cohort_at_two_ratios() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            frozen = (await client.get("/api/forecast/policy-sweep")).json()
            assert frozen["cost_ratio"] == 4.0
            assert frozen["critical_ratio"] == 0.8
            assert frozen["is_policy_ratio"] is True
            assert frozen["products"] == 469
            assert frozen["product_weeks"] == 12194
            assert frozen["test_weeks"] == 26

            # Recomputed live, and it lands exactly on the notebook's frozen row.
            assert frozen["point_plan"]["cost"] == 314386.59
            assert frozen["quantile_plan"]["cost"] == 284973.19
            assert frozen["mean_plan"]["cost"] == 324007.66
            assert frozen["vs_point_pct"] == -9.36
            assert frozen["vs_mean_pct"] == -12.05
            assert frozen["units_uplift_pct"] == 53.35
            assert round(frozen["point_plan"]["units_short"]) == 337594
            assert round(frozen["quantile_plan"]["units_short"]) == 197366
            assert frozen["cheaper_than_point"] is True
            assert frozen["cheaper_than_mean"] is True

            # The losers are counted and named, not hidden.
            assert frozen["products_cheaper"] == 354
            assert frozen["products_worse"] == 115
            assert round(frozen["products_worse_share"], 3) == 0.245
            assert len(frozen["worst_products"]) == 8
            assert all(item["change_pct"] > 0 for item in frozen["worst_products"])
            assert "22084" in {item["product_id"] for item in frozen["worst_products"]}
            assert all(item["change_pct"] < 0 for item in frozen["best_products"])
            assert frozen["extra_cost_on_losers"] > 0
            assert "CLASSROOM ASSUMPTION" in frozen["cost_note"]
            assert "not a promise" in frozen["boundary"]

            cautious = (await client.get("/api/forecast/policy-sweep?ratio=9")).json()
            assert cautious["cost_ratio"] == 9.0
            assert cautious["critical_ratio"] == 0.9
            assert cautious["is_policy_ratio"] is False
            assert round(cautious["quantile_plan"]["units_short"]) == 124679
            assert cautious["vs_point_pct"] < frozen["vs_point_pct"]
            assert cautious["products_worse"] == 58
            assert cautious["products_cheaper"] == 411
            # Buying more means fewer units short and more units left over.
            assert (
                cautious["quantile_plan"]["units_ordered"]
                > frozen["quantile_plan"]["units_ordered"]
            )
            assert (
                cautious["quantile_plan"]["units_excess"]
                > frozen["quantile_plan"]["units_excess"]
            )
            # Same fields, same shape, whatever the ratio.
            assert set(cautious) == set(frozen)

            # At 2:1 the rule is barely worth having, and the sweep says so.
            even = (await client.get("/api/forecast/policy-sweep?ratio=2")).json()
            assert even["vs_point_pct"] == -0.06
            assert even["products_worse"] > frozen["products_worse"]

    asyncio.run(run())


def test_requests_that_do_not_make_sense_are_rejected() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unknown_field = await client.post(
                "/api/forecast/plan", json={"product_id": "85099B", "point": 999}
            )
            assert unknown_field.status_code == 422

            unknown_product = await client.post(
                "/api/forecast/plan", json={"product_id": "not-a-product"}
            )
            assert unknown_product.status_code == 422
            assert "Unknown packaged product" in unknown_product.text

            missing_product = await client.post("/api/forecast/plan", json={"cost_ratio": 4})
            assert missing_product.status_code == 422

            not_a_number = await client.post(
                "/api/forecast/plan", json={"product_id": "85099B", "cost_ratio": "high"}
            )
            assert not_a_number.status_code == 422

            empty_product = await client.post("/api/forecast/plan", json={"product_id": ""})
            assert empty_product.status_code == 422

            assert (await client.get("/api/forecast/policy-sweep?ratio=0")).status_code == 422
            assert (await client.get("/api/forecast/policy-sweep?ratio=40")).status_code == 422

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/health",
                "/api/forecast/model",
                "/api/forecast/products",
                "/api/forecast/policy-sweep",
            ):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:forecast" in response.text
                assert "01_forecast_build.ipynb" in response.text

            planned = await client.post("/api/forecast/plan", json={"product_id": "85099B"})
            assert planned.status_code == 503

    asyncio.run(run())
