import asyncio
import json

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import DEFAULT_ARTIFACT_DIR
from app.main import create_app


TEAMS = [
    "Bank accounts",
    "Credit cards",
    "Credit reporting",
    "Debt collection",
    "Loans",
    "Money transfers",
    "Mortgages",
    "Student loans",
]


def read_manifest() -> pd.DataFrame:
    manifest = pd.read_parquet(DEFAULT_ARTIFACT_DIR / "sample_manifest.parquet")
    manifest["complaint_id"] = manifest["complaint_id"].astype(str)
    return manifest


def test_health_reports_the_loaded_artifacts() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            readiness = health.json()
            assert readiness["status"] == "ok"
            assert readiness["service"] == "complaint-api"
            assert readiness["model"] == "loaded"
            assert readiness["packaged_complaints"] == 60
            assert readiness["teams"] == 8
            assert readiness["model_version"]
            assert all(readiness["artifacts"].values())
            assert set(readiness["artifacts"]) == {
                "model.joblib",
                "model_card.json",
                "evaluation.json",
                "operating_policy.json",
                "sample_manifest.parquet",
            }

    asyncio.run(run())


def test_model_card_carries_the_frozen_evidence() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/complaints/model")
            assert response.status_code == 200
            info = response.json()

            assert info["packaging"].startswith("joblib Pipeline")
            assert info["representation"]["kind"].startswith("TF-IDF")
            assert info["representation"]["settings"]["ngram_range"] == [1, 2]
            assert info["representation"]["columns_learned"] == 50000
            assert info["max_narrative_characters"] == 8000

            # The frozen test numbers the evidence view quotes, read from the
            # artifact rather than written into the page.
            metrics = info["test_metrics"]
            assert metrics["accuracy"] == 0.8207
            assert metrics["macro_f1"] == 0.8097
            assert metrics["coverage"] == 0.7829
            assert metrics["accuracy_among_auto_routed"] == 0.8967
            assert metrics["triage_share"] == 0.2171
            assert metrics["baseline_accuracy"] == 0.3052

            assert [team["name"] for team in info["teams"]] == TEAMS
            assert all(team["description"] for team in info["teams"])
            assert [row["team"] for row in info["per_team"]] == TEAMS + ["macro average"]
            assert info["confusion"]["labels"] == TEAMS
            assert len(info["confusion"]["matrix"]) == 8
            assert info["confusion"]["rows_are_true_team"] is True

            policy = info["policy"]
            assert policy["confidence_threshold"] == 0.55
            assert policy["boundary"] == "the model routes; it never judges whether a complaint is valid"
            assert "never scored" in policy["fallback"]
            assert policy["triage_complaints"] == 1895
            chosen = [row for row in info["threshold_sweep"] if row["is_chosen"]]
            assert len(chosen) == 1 and chosen[0]["threshold"] == 0.55

            # The representation comparison: the transformer scored lower here.
            comparison = info["representation_comparison"]
            assert comparison["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
            assert len(comparison["results"]) == 2
            tfidf, minilm = comparison["results"]
            assert tfidf["validation_accuracy"] == 0.8083
            assert minilm["validation_accuracy"] == 0.8048
            assert minilm["validation_accuracy"] < tfidf["validation_accuracy"]
            assert comparison["winner"] == tfidf["model"]
            assert {row["trained_on"] for row in comparison["results"]} == {15000}
            assert comparison["embedding_facts"]["Longest input it reads"].startswith("256")

            # The duplicate-template finding and what skipping it would have cost.
            dedupe = info["dedupe"]
            assert dedupe["share_removed"] == 0.4149
            assert dedupe["rows_removed"] == 1093131
            assert dedupe["inflated_test_accuracy"] == 0.843
            assert dedupe["honest_test_accuracy"] == 0.819
            assert dedupe["share_removed_by_team"][0]["team"] == "Credit reporting"
            shares = [row["share_removed"] for row in dedupe["share_removed_by_team"]]
            assert shares == sorted(shares, reverse=True)

            assert info["limitations"] and info["excluded_uses"]
            assert info["dataset"]["split_counts"] == {
                "train": 40729,
                "validation": 8728,
                "test": 8728,
            }

    asyncio.run(run())


def test_samples_prefer_the_curated_complaints_and_clamp_the_limit() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/complaints/samples?limit=12")
            assert response.status_code == 200
            packaged = response.json()
            assert len(packaged) == 12
            assert all(sample["curated"] for sample in packaged)
            # All eight teams, so any team's language can be shown.
            assert {sample["known_team"] for sample in packaged} == set(TEAMS)
            # Both routes, so the human path is one click away.
            assert {sample["route"] for sample in packaged} == {"auto_route", "human_triage"}
            assert sum(sample["is_misroute_example"] for sample in packaged) == 1
            confidences = [sample["confidence"] for sample in packaged]
            assert confidences == sorted(confidences, reverse=True)
            assert all(sample["narrative"].strip() for sample in packaged)
            assert all(sample["top_words"] for sample in packaged)
            assert all(sample["scenario_label"] and sample["learning_note"] for sample in packaged)

            misroute = next(sample for sample in packaged if sample["is_misroute_example"])
            assert misroute["route"] == "auto_route"
            assert misroute["correct"] is False
            assert misroute["confidence"] > 0.55
            assert misroute["known_team"] != misroute["predicted_team"]

            assert (await client.get("/api/complaints/samples?limit=0")).status_code == 422
            assert (await client.get("/api/complaints/samples?limit=25")).status_code == 422
            assert len((await client.get("/api/complaints/samples?limit=1")).json()) == 1
            wide = (await client.get("/api/complaints/samples?limit=24")).json()
            assert len(wide) == 24
            assert len({sample["complaint_id"] for sample in wide}) == 24

    asyncio.run(run())


def test_classify_reproduces_the_notebook_artifact() -> None:
    """The contract test: the service must return the notebook's own numbers.

    Every packaged narrative is classified through the API and compared with the
    predicted team, confidence, route, and routing words the notebook stored in
    ``sample_manifest.parquet``. Confidence allows only 1e-12 absolute rounding
    drift across numerical libraries and platforms. Team, route, and routing
    words must still match exactly.
    """

    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _, row in manifest.iterrows():
                response = await client.post(
                    "/api/complaints/classify",
                    json={"narrative": row["narrative"]},
                )
                assert response.status_code == 200
                result = response.json()

                assert result["predicted_team"] == row["predicted_team"]
                assert result["confidence"] == pytest.approx(float(row["confidence"]), rel=0, abs=1e-12)
                assert result["route"] == row["route"]
                assert result["routing_words"] == json.loads(row["top_words"])

                # The route is arithmetic on the confidence, not a second model.
                assert result["threshold"] == 0.55
                assert result["route"] == (
                    "auto_route" if result["confidence"] >= 0.55 else "human_triage"
                )
                # All eight teams come back, largest first, and they sum to one.
                probabilities = [team["probability"] for team in result["probabilities"]]
                assert len(probabilities) == 8
                assert probabilities == sorted(probabilities, reverse=True)
                assert abs(sum(probabilities) - 1) < 1e-9
                assert probabilities[0] == result["confidence"]
                assert sum(team["is_predicted"] for team in result["probabilities"]) == 1

                # A packaged complaint carries its recorded team; the comparison
                # with the route is the model's own accuracy on that complaint.
                assert result["is_packaged_complaint"] is True
                assert result["known_team"] == row["team"]
                assert result["correct"] is bool(row["correct"])
                assert "not a judgement" in result["score_note"]

    asyncio.run(run())


def test_below_threshold_text_goes_to_a_person_and_pasted_text_has_no_known_team() -> None:
    async def run() -> None:
        manifest = read_manifest()
        triage = manifest[manifest["route"] == "human_triage"].iloc[0]
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/complaints/classify",
                json={"narrative": triage["narrative"]},
            )
            result = response.json()
            assert result["confidence"] < 0.55
            assert result["route"] == "human_triage"
            assert result["route_label"] == "Sent to human triage"
            assert "clerk reads it" in result["route_action"]
            # Even below the cutoff a team is still named, so the page can show
            # what the model leaned toward without acting on it.
            assert result["predicted_team"] in TEAMS

            typed = "The bank charged me an overdraft fee I never agreed to."
            pasted = await client.post("/api/complaints/classify", json={"narrative": typed})
            assert pasted.status_code == 200
            unknown = pasted.json()
            assert unknown["is_packaged_complaint"] is False
            assert unknown["known_team"] is None
            assert unknown["correct"] is None
            assert "no recorded team" in unknown["outcome_note"]
            assert unknown["routing_words"]
            assert unknown["characters"] == len(typed)
            assert unknown["words"] == len(typed.split())

            # Surrounding whitespace cannot change a TF-IDF row, so a pasted copy
            # of a packaged complaint still scores and still matches.
            padded = await client.post(
                "/api/complaints/classify",
                json={"narrative": f"\n  {triage['narrative']}  \n"},
            )
            assert padded.json()["confidence"] == result["confidence"]
            assert padded.json()["is_packaged_complaint"] is True

    asyncio.run(run())


def test_classify_rejects_blank_text_oversized_text_and_unknown_fields() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            blank = await client.post("/api/complaints/classify", json={"narrative": "   \n\t "})
            assert blank.status_code == 422
            assert "no complaint text to read" in blank.text
            assert "human triage queue" in blank.text

            empty = await client.post("/api/complaints/classify", json={"narrative": ""})
            assert empty.status_code == 422

            too_long = await client.post(
                "/api/complaints/classify",
                json={"narrative": "overdraft fee " * 700},
            )
            assert too_long.status_code == 422
            assert "9,800 characters" in too_long.text
            assert "reads up to 8,000" in too_long.text

            # 8,000 characters exactly is accepted; the cap is inclusive.
            assert (
                await client.post(
                    "/api/complaints/classify",
                    json={"narrative": "a" * 7999 + "b"},
                )
            ).status_code == 200

            unknown_field = await client.post(
                "/api/complaints/classify",
                json={"narrative": "The collector called my job.", "team": "Debt collection"},
            )
            assert unknown_field.status_code == 422

            missing = await client.post("/api/complaints/classify", json={})
            assert missing.status_code == 422

    asyncio.run(run())


def test_queues_group_the_packaged_worklist_by_team_and_state_the_triage_workload() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/complaints/queues?limit=60")
            assert response.status_code == 200
            board = response.json()

            summary = board["summary"]
            assert summary["packaged_complaints"] == 60
            assert summary["auto_routed"] == 45
            assert summary["sent_to_triage"] == 15
            assert summary["threshold"] == 0.55
            assert abs(summary["triage_share"] - 0.25) < 1e-9
            assert summary["misroutes_in_auto_routed"] >= 1
            assert "deliberately larger" in summary["selection_note"]
            assert summary["boundary"].startswith("the model routes")

            # Every team gets a lane, including one with nothing in it, so the
            # worklist never changes shape between calls.
            assert [team["team"] for team in board["teams"]] == TEAMS
            assert sum(team["complaints"] for team in board["teams"]) == summary["auto_routed"]
            assert all(
                item["route"] == "auto_route" and item["confidence"] >= 0.55
                for team in board["teams"]
                for item in team["items"]
            )
            assert all(
                item["predicted_team"] == team["team"]
                for team in board["teams"]
                for item in team["items"]
            )
            assert abs(sum(team["share_of_auto_routed"] for team in board["teams"]) - 1) < 1e-9
            assert sum(team["misrouted"] for team in board["teams"]) == (
                summary["misroutes_in_auto_routed"]
            )

            triage = board["triage"]
            assert triage["complaints"] == 15
            assert len(triage["items"]) == 15
            assert all(item["confidence"] < 0.55 for item in triage["items"])
            assert "Nothing here is closed" in triage["workload_note"]
            assert all(item["excerpt"] for item in triage["items"])

            # The frozen test-split workload travels with the queue and never moves.
            assert board["test"]["triage_share"] == 0.2171
            assert board["test"]["triage_rows"] == 1895
            assert board["test"]["complaints"] == 8728
            assert board["test"]["accuracy_among_auto_routed"] == 0.8967
            assert "21.7%" in summary["workload_note"]

            # The deliberate misroute is reachable from the worklist.
            misroutes = [
                item
                for team in board["teams"]
                for item in team["items"]
                if item["is_misroute_example"]
            ]
            assert len(misroutes) == 1
            assert misroutes[0]["correct"] is False
            assert misroutes[0]["known_team"] != misroutes[0]["predicted_team"]

            # A smaller limit still spans both routes rather than keeping only
            # the most confident complaints.
            small = (await client.get("/api/complaints/queues?limit=20")).json()
            assert small["summary"]["packaged_complaints"] == 20
            assert small["summary"]["sent_to_triage"] > 0
            assert small["summary"]["auto_routed"] > 0
            assert small["test"] == board["test"]

            assert (await client.get("/api/complaints/queues?limit=0")).status_code == 422
            assert (await client.get("/api/complaints/queues?limit=61")).status_code == 422

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/health",
                "/api/complaints/model",
                "/api/complaints/samples",
                "/api/complaints/queues",
            ):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:complaints" in response.text
                assert "complaint-routing notebook" in response.text

            classify = await client.post(
                "/api/complaints/classify",
                json={"narrative": "The collector called my job about an old debt."},
            )
            assert classify.status_code == 503
            assert "npm run prepare:complaints" in classify.text

    asyncio.run(run())
