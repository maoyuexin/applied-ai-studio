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
            assert payload["service"] == "maintenance-api"
            assert payload["model"] == "loaded"
            assert payload["model_version"]
            assert payload["policy_version"] == "1.0"
            assert payload["packaged_windows"] == 8
            assert payload["scored_hours"] == 4216
            assert all(payload["artifacts"].values())
            assert set(payload["artifacts"]) == {
                "model.joblib",
                "model_card.json",
                "evaluation.json",
                "operating_policy.json",
                "sample_manifest.parquet",
                "metropt_1min.parquet",
            }

    asyncio.run(run())


def test_model_carries_the_frozen_evidence_the_drift_and_the_sweep() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/maintenance/model")
            assert response.status_code == 200
            info = response.json()

            assert info["model_type"] == "one_sided_robust_z"
            assert [feature["name"] for feature in info["features"]] == [
                "load_share",
                "cycles_per_hour",
                "rest_minutes_per_cycle",
                "oil_temp_mean",
                "tp3_std",
                "pressure_fall_rate",
            ]
            # The boundary has to survive the trip to the page.
            assert "does not forecast" in info["boundary_short"]
            assert "never locks out" in info["authority_boundary"]

            # The frozen July-September window, scored once.
            frozen = info["frozen_test"]
            assert frozen["threshold"] == 6.0
            assert frozen["alert_hours"] == 23
            assert frozen["false_alarm_rate_on_clean_hours"] == 0.0035
            assert frozen["false_callouts_per_month"] == 1.47
            assert frozen["lead_hours"] == 14.5
            assert "LOSES on cost" in frozen["honest_roi_note"]

            # The drift block, all five parts of it.
            drift = info["drift"]
            assert len(drift["naive_single_feature_pct_clean_hours_alerting"]) == 6
            assert len(drift["detector_false_callouts_by_month"]) == 5
            assert len(drift["mitigations"]) == 4
            load = drift["monthly_alert_load_at_operating_threshold"]
            assert [row["month"] for row in load] == [
                "2020-04", "2020-05", "2020-06", "2020-07", "2020-08",
            ]
            assert "floods the queue" in drift["cruel_interaction"]

            assert len(info["threshold_sweep"]) == 10
            assert info["full_period_policy"]["total_cost_usd"] == 25200
            assert info["full_period_never_alert"]["total_cost_usd"] == 148980
            assert len(info["baseline_policies"]) == 6
            assert len(info["feature_bug"]["hours_deleted_per_failure"]) == 4
            assert info["training_window_not_clean"]["hours_above_threshold"] == 44
            assert info["data_coverage"]["summary"]
            assert info["limitations"]

            # The discussion case is derived from the manifest, not written down.
            case = info["discussion_case"]
            assert case["healthy_window_id"] == "S6_drift_false_alarm"
            assert case["failure_window_id"] == "S2_F1_worst_failure"
            assert case["gap"] == 0.01
            assert "no threshold anywhere separates them" in case["statement"]

    asyncio.run(run())


def test_samples_are_the_packaged_windows_and_the_limit_is_clamped() -> None:
    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            samples = await client.get("/api/maintenance/samples?limit=24")
            assert samples.status_code == 200
            windows = samples.json()
            assert len(windows) == len(manifest) == 8
            assert [window["sample_id"] for window in windows] == list(manifest["sample_id"])
            assert {window["route_at_peak"] for window in windows} == {
                "no_action", "watch", "work_order",
            }
            assert any(window["covers_documented_failure"] for window in windows)
            assert any(not window["covers_documented_failure"] for window in windows)
            for window, (_, row) in zip(windows, manifest.iterrows()):
                assert window["peak_score"] == float(row["peak_score"])
                assert window["hours_with_data"] == int(row["hours_with_data"])
                assert window["route_label_at_peak"]

            assert len((await client.get("/api/maintenance/samples?limit=1")).json()) == 1
            assert (await client.get("/api/maintenance/samples?limit=0")).status_code == 422
            assert (await client.get("/api/maintenance/samples?limit=99")).status_code == 422

    asyncio.run(run())


def test_scoring_a_packaged_window_reproduces_the_stored_peak_score_exactly() -> None:
    """The contract test: serving must return the notebook's own numbers.

    The service rebuilds the hourly features from the committed 1-minute file and
    scores them with the exported detector. Every packaged window is scored
    through the API and compared with what the notebook stored in
    ``sample_manifest.parquet``. Equality is exact, not approximate: if the
    service ever rebuilt a feature differently, or loaded a different model, the
    peak would move and this would fail.
    """

    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _, row in manifest.iterrows():
                response = await client.post(
                    "/api/maintenance/score", json={"window_id": row["sample_id"]}
                )
                assert response.status_code == 200
                result = response.json()

                assert result["peak_score"] == float(row["peak_score"])
                assert result["peak_at"] == str(row["peak_at"])
                assert result["median_score"] == float(row["median_score"])
                assert result["hours_with_data"] == int(row["hours_with_data"])
                assert len(result["hours"]) == int(row["hours_with_data"])
                assert result["route_at_peak"] == row["route_at_peak"]
                assert result["alert_hours"] == int(row["work_order_hours"])
                assert result["watch_hours"] == int(row["watch_hours"])
                assert result["threshold"] == 6.0
                assert result["threshold_is_override"] is False

                # Hour for hour, including the route the notebook recorded.
                stored = json.loads(row["hourly_scores"])
                assert [hour["hour"] for hour in result["hours"]] == [
                    hour["hour"] for hour in stored
                ]
                assert [hour["score"] for hour in result["hours"]] == [
                    hour["score"] for hour in stored
                ]
                assert [hour["route_at_policy"] for hour in result["hours"]] == [
                    hour["route"] for hour in stored
                ]
                # The peak is the highest hour in the published series. Hours are
                # published to 3 decimals and the peak to 2, so they are compared
                # at the coarser of the two.
                highest = max(result["hours"], key=lambda hour: hour["score"])
                assert highest["hour"] == str(row["peak_at"])
                assert abs(highest["score"] - float(row["peak_score"])) < 0.006

                # The reasons name the same top driver the notebook recorded.
                drivers = result["drivers"]
                assert len(drivers) == 6
                assert drivers[0]["display_name"] == row["top_driver_at_peak"]
                # The manifest keeps one decimal, the service two.
                assert abs(
                    drivers[0]["distance_from_normal"] - float(row["top_driver_z"])
                ) < 0.06
                assert drivers == sorted(
                    drivers, key=lambda item: item["distance_from_normal"], reverse=True
                )
                assert all(driver["sentence"] for driver in drivers)
                assert "technician" in result["boundary"].lower()

    asyncio.run(run())


def test_a_threshold_override_changes_the_route_without_changing_the_score() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # S7 sits in the watch band and never crosses 6.0 (peak 5.24).
            frozen = (
                await client.post(
                    "/api/maintenance/score", json={"window_id": "S7_borderline_watch"}
                )
            ).json()
            assert frozen["route_at_peak"] == "watch"
            assert frozen["alert_hours"] == 0
            assert frozen["first_alert_hour"] is None

            lowered = (
                await client.post(
                    "/api/maintenance/score",
                    json={"window_id": "S7_borderline_watch", "threshold": 4.0},
                )
            ).json()
            assert lowered["threshold"] == 4.0
            assert lowered["threshold_is_override"] is True
            assert lowered["route_at_peak"] == "work_order"
            assert lowered["route_changed_by_threshold"] is True
            assert lowered["alert_hours"] > 0
            assert lowered["first_alert_hour"] is not None
            # The score never moves; only the line drawn through it does.
            assert lowered["peak_score"] == frozen["peak_score"]
            assert [hour["score"] for hour in lowered["hours"]] == [
                hour["score"] for hour in frozen["hours"]
            ]
            assert lowered["alert_hours_at_policy"] == 0
            assert "what-if" in lowered["threshold_note"]

            # Raising the line past the peak sends the same window back to quiet.
            raised = (
                await client.post(
                    "/api/maintenance/score",
                    json={"window_id": "S2_F1_worst_failure", "threshold": 20},
                )
            ).json()
            assert raised["alert_hours"] == 0
            assert raised["route_at_peak"] == "no_action"

            # A control dragged out of range clamps instead of failing.
            clamped = (
                await client.post(
                    "/api/maintenance/score",
                    json={"window_id": "S2_F1_worst_failure", "threshold": 999},
                )
            ).json()
            assert clamped["threshold"] == 20.0

    asyncio.run(run())


def test_queue_recomputes_the_alert_workload_at_two_thresholds() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            operating = (await client.get("/api/maintenance/queue")).json()
            assert operating["threshold"] == 6.0
            assert operating["is_operating_threshold"] is True
            # Recomputed live, and it lands exactly on the notebook's frozen row.
            assert operating["callouts"] == 15
            assert operating["false_callouts"] == 11
            assert operating["alerts_per_month"] == 2.98
            assert operating["technician_hours"] == 30.0
            assert operating["failures_caught"] == 4
            assert operating["failures_missed"] == 0
            assert operating["total_cost_usd"] == 25200
            assert operating["never_alert"]["total_cost_usd"] == 148980
            assert operating["scheduled_inspection"]["total_cost_usd"] == 151380
            assert operating["net_vs_never_usd"] == 123780
            assert operating["beats_never_alert"] is True
            assert operating["beats_scheduled_inspection"] is True
            assert "synthetic classroom assumption" in operating["assumption_note"]

            # The drift: one threshold, very different months.
            months = {row["month"]: row for row in operating["monthly_load"]}
            assert months["2020-04"]["alert_hours"] == 11
            assert months["2020-08"]["alert_hours"] == 1
            assert operating["drift"]["busiest_month"] == "2020-06"
            assert operating["drift"]["quietest_month"] == "2020-08"
            assert "did not change" in operating["drift"]["sentence"]

            lower = (await client.get("/api/maintenance/queue?threshold=4")).json()
            assert lower["threshold"] == 4.0
            assert lower["is_operating_threshold"] is False
            assert lower["callouts"] == 41
            assert lower["technician_hours"] == 82.0
            assert lower["total_cost_usd"] == 35600
            # A lower line means more callouts, more technician hours, more cost.
            assert lower["callouts"] > operating["callouts"]
            assert lower["alerts_per_month"] > operating["alerts_per_month"]
            assert lower["net_vs_never_usd"] < operating["net_vs_never_usd"]
            assert set(row["month"] for row in lower["monthly_load"]) == set(months)

            # Same fields, same shape, whatever the threshold.
            assert set(lower) == set(operating)

            # A threshold nothing can reach leaves every failure uncaught, and the
            # detector then costs the same as never alerting.
            silent = (await client.get("/api/maintenance/queue?threshold=20")).json()
            assert silent["callouts"] == 0
            assert silent["failures_caught"] == 0
            assert silent["failures_missed"] == 4
            assert silent["total_cost_usd"] == silent["never_alert"]["total_cost_usd"]
            assert silent["beats_never_alert"] is False

    asyncio.run(run())


def test_requests_that_do_not_make_sense_are_rejected() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unknown_field = await client.post(
                "/api/maintenance/score",
                json={"window_id": "S1_clean_training_week", "peak_score": 99},
            )
            assert unknown_field.status_code == 422

            unknown_window = await client.post(
                "/api/maintenance/score", json={"window_id": "not-a-window"}
            )
            assert unknown_window.status_code == 422
            assert "Unknown packaged window" in unknown_window.text

            missing_window = await client.post("/api/maintenance/score", json={"threshold": 6})
            assert missing_window.status_code == 422

            not_a_number = await client.post(
                "/api/maintenance/score",
                json={"window_id": "S1_clean_training_week", "threshold": "low"},
            )
            assert not_a_number.status_code == 422

            assert (await client.get("/api/maintenance/queue?threshold=-1")).status_code == 422
            assert (await client.get("/api/maintenance/queue?threshold=40")).status_code == 422

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/health",
                "/api/maintenance/model",
                "/api/maintenance/samples",
                "/api/maintenance/queue",
            ):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:pdm" in response.text
                assert "01_pdm_build.ipynb" in response.text

            scored = await client.post(
                "/api/maintenance/score", json={"window_id": "S1_clean_training_week"}
            )
            assert scored.status_code == 503

    asyncio.run(run())
