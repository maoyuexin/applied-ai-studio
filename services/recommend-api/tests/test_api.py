import asyncio

import pandas as pd
from httpx import ASGITransport, AsyncClient

from app.config import DEFAULT_ARTIFACT_DIR
from app.main import create_app


DISCUSSION_CUSTOMER = 17841

MODELS = [
    "Random 10",
    "Popularity",
    "Fallback: recent revenue 28d",
    "Item-item CF (full matrix)",
    "Item-item CF (top-15)",
    "TruncatedSVD (64)",
    "Reorder (already-bought)",
]


def read_manifest() -> pd.DataFrame:
    manifest = pd.read_parquet(DEFAULT_ARTIFACT_DIR / "sample_manifest.parquet")
    manifest["customer_id"] = manifest["customer_id"].astype(int)
    return manifest


def test_default_setup_verifies_without_rebuilding_artifacts(monkeypatch) -> None:
    import hashlib
    import runpy
    import sys

    from reclab import handoff, models

    script = DEFAULT_ARTIFACT_DIR.parent / "scripts" / "prepare_app_artifacts.py"
    namespace = runpy.run_path(str(script))
    monkeypatch.setattr(sys, "argv", [str(script)])

    def reject_rebuild(*args, **kwargs):
        raise AssertionError("Default setup must not rebuild a validated bundle")

    monkeypatch.setattr(models, "fit_all", reject_rebuild)
    before = {
        name: hashlib.sha256((DEFAULT_ARTIFACT_DIR / name).read_bytes()).hexdigest()
        for name in handoff.ARTIFACT_ORDER
    }
    namespace["main"]()
    after = {
        name: hashlib.sha256((DEFAULT_ARTIFACT_DIR / name).read_bytes()).hexdigest()
        for name in handoff.ARTIFACT_ORDER
    }
    assert after == before


def test_health_reports_the_loaded_artifacts() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            readiness = health.json()
            assert readiness["status"] == "ok"
            assert readiness["service"] == "recommend-api"
            assert readiness["model"] == "loaded"
            assert readiness["model_version"] == "Online Retail II split 2011-09-09"
            assert readiness["deployed_model"] == "item_item_cosine_top15"
            assert readiness["catalog_products"] == 4443
            assert readiness["matrix_customers"] == 4962
            assert readiness["slots"] == 10
            assert readiness["packaged_customers"] == 12
            assert all(readiness["artifacts"].values())
            assert set(readiness["artifacts"]) == {
                "item_similarity.npz",
                "item_catalog.parquet",
                "model_card.json",
                "evaluation.json",
                "operating_policy.json",
                "sample_manifest.parquet",
                # Not an artifact. The service rebuilds the customer matrix from
                # the committed log, so readiness has to report that file too.
                "interactions.parquet",
            }

    asyncio.run(run())


def test_model_card_carries_both_leaderboards_with_their_protocols_named() -> None:
    """The rule the notebook wrote down: neither leaderboard is optional.

    A leaderboard without its protocol printed on it is not a result, so the
    service is not allowed to ship one table. Both come back, both name their
    ground truth and their candidate set, and coverage rides beside every
    accuracy number in the same row.
    """

    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/recommend/model")
            assert response.status_code == 200
            info = response.json()

            assert info["deployed_model"]["id"] == "item_item_cosine_top15"
            assert info["deployed_model"]["neighbours_kept"] == 15
            assert info["deployed_model"]["stored_links"] == 66631
            assert info["deployed_model"]["stored_megabytes"] < 1
            assert info["deployed_model"]["similarity_digest"].startswith("3153edc3")

            boards = info["leaderboards"]
            assert set(boards) == {
                "rule", "standard", "discovery", "side_by_side", "reorder_zero_score_diagnosis"
            }
            assert "Neither leaderboard is optional" in boards["rule"]

            # Both protocols are named, with the difference that produces the
            # inversion spelled out rather than implied.
            protocols = {row["id"]: row for row in info["protocols"]}
            assert set(protocols) == {"standard", "discovery", "incoherent-middle"}
            assert protocols["standard"]["name"] == "Standard next-purchase"
            assert "are NOT masked" in protocols["standard"]["candidates"]
            assert protocols["discovery"]["name"] == "Discovery"
            assert "NEVER bought" in protocols["discovery"]["ground_truth"]
            assert "none that is answerable" in protocols["incoherent-middle"]["question"]

            standard = {row["model"]: row for row in boards["standard"]}
            discovery = {row["model"]: row for row in boards["discovery"]}
            assert set(standard) == set(MODELS)
            assert set(discovery) == set(MODELS)

            # The frozen standard board: the reorder baseline on top.
            assert standard["Reorder (already-bought)"]["hr_at_10"] == 0.7995
            assert standard["TruncatedSVD (64)"]["hr_at_10"] == 0.7594
            assert standard["Item-item CF (top-15)"]["hr_at_10"] == 0.6533
            assert standard["Item-item CF (full matrix)"]["hr_at_10"] == 0.6261
            assert standard["Popularity"]["hr_at_10"] == 0.5713
            assert standard["Fallback: recent revenue 28d"]["hr_at_10"] == 0.5526
            assert standard["Random 10"]["hr_at_10"] == 0.0784
            assert standard["Reorder (already-bought)"]["rank"] == 1
            assert standard["Reorder (already-bought)"]["customers_scored"] == 2244

            # The frozen discovery board: the same baseline below ten random products.
            assert discovery["TruncatedSVD (64)"]["hr_at_10"] == 0.4437
            assert discovery["Item-item CF (top-15)"]["hr_at_10"] == 0.4156
            assert discovery["Item-item CF (full matrix)"]["hr_at_10"] == 0.3644
            assert discovery["Fallback: recent revenue 28d"]["hr_at_10"] == 0.3007
            assert discovery["Popularity"]["hr_at_10"] == 0.2947
            assert discovery["Random 10"]["hr_at_10"] == 0.0604
            assert discovery["Reorder (already-bought)"]["hr_at_10"] == 0.0217
            assert discovery["Reorder (already-bought)"]["rank"] == 7
            assert discovery["Reorder (already-bought)"]["hr_at_10"] < discovery["Random 10"]["hr_at_10"]
            assert discovery["Reorder (already-bought)"]["customers_scored"] == 2168

            # Coverage travels in the same row as the accuracy, always, which is
            # the only way popularity's 0.23% is visible next to its 57.1%.
            assert standard["Popularity"]["coverage"] == 0.0023
            assert discovery["Popularity"]["coverage"] == 0.018
            assert discovery["Item-item CF (top-15)"]["coverage"] == 0.2577
            assert all(row["coverage"] > 0 and row["novelty"] > 0 for row in boards["standard"])
            assert all(row["coverage"] > 0 and row["novelty"] > 0 for row in boards["discovery"])
            assert all(row["how_it_works"] for row in boards["standard"])
            assert sum(row["is_deployed"] for row in boards["standard"]) == 1

            inversion = {row["model"]: row for row in boards["side_by_side"]}
            reorder = inversion["Reorder (already-bought)"]
            assert reorder["standard_rank"] == 1
            assert reorder["discovery_rank"] == 7
            assert reorder["rank_change"] == -6
            assert boards["reorder_zero_score_diagnosis"]["share_with_all_zero_scores"] == 1.0
            assert boards["reorder_zero_score_diagnosis"]["customers_with_any_positive_score"] == 0

            # The honest revenue ceiling, and the fact that it is a ceiling.
            revenue = info["incremental_revenue"]
            assert revenue["deployed_share"] == 0.0353
            assert revenue["no_personalization_share"] == 0.0281
            assert revenue["gain_percentage_points"] == 0.72
            assert "upper bound" in revenue["upper_bound_note"]

            # The leave-one-out inflation table.
            inflation = {row["model"]: row for row in info["leave_one_out"]["by_model"]}
            assert inflation["Item-item CF"]["honest_hr10"] == 0.0351
            assert inflation["Item-item CF"]["leave_one_out_hr10"] == 0.0664
            assert inflation["TruncatedSVD (64)"]["inflation"] == 1.043

            # The exposure simulation, captioned as the assumption it is.
            loop = info["popularity_bias"]["exposure_loop"]
            assert loop["rounds"] == 10
            assert loop["assumed_conversion"] == 0.05
            assert "NOT measured" in loop["assumption_note"]
            assert loop["start_top_10_share"] == 0.02378
            assert loop["end_top_10_share"] == 0.06259
            assert len(loop["history"]) == 11
            exposure = {row["model"]: row for row in info["popularity_bias"]["what_each_model_shows"]}
            assert exposure["Popularity"]["distinct_products_shown"] == 80

            # The operating policy, read at start-up rather than written in here.
            policy = info["policy"]
            assert policy["slots"] == 10
            assert policy["module_title"] == "Recommended for you"
            assert policy["fallback"]["label"] == "Popular right now"
            assert policy["fallback"]["never_label_it"] == "Recommended for you"
            assert len(policy["fallback"]["items"]) == 10
            assert policy["fallback"]["items"][0]["stock_code"] == "22423"
            assert policy["fallback"]["sweep"][0]["hr_at_10"] == 0.4624
            assert policy["fallback"]["sweep"][0]["is_chosen"] is True
            assert policy["reorder_surface"]["title"] == "Buy it again"
            assert "never" in policy["reorder_surface"]["never"]
            assert policy["outcomes"]["fallback_share"] == 0.22398893881783616
            assert "merchandisers own" in policy["human_authority"]
            assert len(policy["service_must"]) == 5

            assert info["cold_start"]["unservable_share"] == 0.22398893881783616
            assert info["cold_start"]["fallback_hr10"] == 0.4624
            assert "never be added together" in info["cold_start"]["warning"]
            assert info["repeat_purchasing"]["repeat_share"] == 0.3836885611678956
            assert info["repeat_purchasing"]["repeat_revenue_share"] == 0.43545537757235314
            assert info["concentration"]["top_10_share"] == 0.02378312777958425
            assert info["split"]["cut"] == "2011-09-09"
            assert info["split"]["customers_scored_standard"] == 2244
            assert info["split"]["customers_scored_discovery"] == 2168
            assert info["known_limits"] and info["what_it_does_not_do"]
            assert info["prohibited_claims"]
            assert "not evidence of revenue" in " ".join(info["prohibited_claims"])
            assert info["environment"]["seed"] == "42"

            # The engineering trade the small artifact wins.
            trade = {row["neighbours_kept"]: row for row in info["engineering"]["truncation_trade"]}
            assert trade["15"]["is_deployed"] is True
            assert trade["15"]["discovery_hr10"] > trade["all 4,443 (full matrix)"]["discovery_hr10"]
            assert trade["15"]["stored_megabytes"] < trade["all 4,443 (full matrix)"]["stored_megabytes"]
            assert all(
                row["largest_difference_from_alpha_zero"] == 0
                for row in info["engineering"]["popularity_damping_is_a_no_op"]
            )

    asyncio.run(run())


def test_customers_list_the_packaged_roster_and_clamp_the_limit() -> None:
    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/recommend/customers?limit=24")
            assert response.status_code == 200
            packaged = response.json()
            assert len(packaged) == 12

            from_manifest = [row for row in packaged if row["source"] == "manifest"]
            assert len(from_manifest) == 10
            assert [row["customer_id"] for row in from_manifest] == manifest["customer_id"].tolist()
            assert [row["persona"] for row in from_manifest] == manifest["persona"].tolist()
            assert all(row["cold_start"] is False for row in from_manifest)
            assert all(row["cold_start_kind"] == "none" for row in from_manifest)
            assert all(row["training_products"] >= 5 for row in from_manifest)

            # The discussion customer is flagged, with the note that explains why.
            discussion = [row for row in packaged if row["is_discussion_case"]]
            assert len(discussion) == 1
            assert discussion[0]["customer_id"] == DISCUSSION_CUSTOMER
            assert discussion[0]["discovery_hits_out_of_10"] == 0
            assert discussion[0]["reorder_hits_out_of_10_standard"] == 10
            assert "wholesaler restocking" in discussion[0]["discussion_note"]

            # 22.4% of shoppers cannot be served at all, so the roster carries one
            # of each kind rather than showing only customers the model can serve.
            cold = [row for row in packaged if row["cold_start"]]
            assert len(cold) == 2
            assert {row["cold_start_kind"] for row in cold} == {
                "no_history_before_the_cut",
                "history_below_the_threshold",
            }
            assert all(row["source"] == "cold_start_example" for row in cold)
            assert all(row["discovery_hits_out_of_10"] is None for row in cold)
            assert all(row["training_products"] < 5 for row in cold)
            no_history = next(row for row in cold
                              if row["cold_start_kind"] == "no_history_before_the_cut")
            assert no_history["training_products"] == 0
            assert no_history["training_baskets"] == 0

            assert all(row["selection_rule"] and row["history_note"] for row in packaged)

            assert len((await client.get("/api/recommend/customers?limit=1")).json()) == 1
            assert (await client.get("/api/recommend/customers?limit=0")).status_code == 422
            assert (await client.get("/api/recommend/customers?limit=25")).status_code == 422

    asyncio.run(run())


def test_slots_reproduce_the_packaged_manifest_exactly() -> None:
    """The contract test: the service must return the notebook's own ten slots.

    Every packaged customer is ranked through the API under the discovery
    protocol and compared with ``recommended_for_you`` from
    ``sample_manifest.parquet`` - stock code by stock code, in order, not as a
    set. The reorder strip is checked against ``buy_it_again`` the same way, and
    both hit counts against the counts the notebook recorded.

    The comparison is exact because the service reuses the notebook's own
    ``reclab.models.top_k``. If it ever loaded a different similarity matrix,
    rebuilt the customer matrix a different way, or masked a different candidate
    set, the tie-breaks would move and this would fail.
    """

    async def run() -> None:
        manifest = read_manifest()
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _, row in manifest.iterrows():
                customer_id = int(row["customer_id"])
                response = await client.post(
                    "/api/recommend/slots",
                    json={"customer_id": customer_id, "protocol": "discovery"},
                )
                assert response.status_code == 200
                result = response.json()

                assert result["customer_id"] == customer_id
                assert result["persona"] == row["persona"]
                assert result["personalized"] is True
                assert result["module_title"] == "Recommended for you"
                assert result["model_used"] == "Item-item CF (top-15)"
                assert result["matches_shipping_policy"] is True

                slots = [slot["stock_code"] for slot in result["slots"]]
                assert slots == list(row["recommended_for_you"])
                names = [slot["description"] for slot in result["slots"]]
                assert names == list(row["recommended_descriptions"])
                assert result["hits_out_of_10"] == int(row["discovery_hits_out_of_10"])

                # Ten slots, all new to this customer, no fallback, ranked by score.
                assert len(result["slots"]) == 10
                assert result["fallback_used"] is False
                assert result["fallback_slots"] == 0
                assert all(slot["already_owned"] is False for slot in result["slots"])
                assert all(slot["is_new_to_them"] for slot in result["slots"])
                assert all(slot["from_fallback"] is False for slot in result["slots"])
                assert all(slot["label"] == "Recommended for you" for slot in result["slots"])
                scores = [slot["score"] for slot in result["slots"]]
                assert scores == sorted(scores, reverse=True)
                assert all(score > 0 for score in scores)
                assert [slot["slot"] for slot in result["slots"]] == list(range(1, 11))

                # Item-item ships instead of the more accurate SVD because it can
                # name the product that put each slot on the list.
                assert all(slot["because_you_bought"] for slot in result["slots"])
                assert all(
                    slot["because_you_bought"]["description"] in slot["reason"]
                    for slot in result["slots"]
                )

                # The reorder strip is kept separate and matches the manifest too.
                strip = result["buy_it_again"]
                assert strip["title"] == "Buy it again"
                assert strip["available"] is True
                assert [item["stock_code"] for item in strip["items"]] == list(row["buy_it_again"])
                assert strip["hits_out_of_10_standard"] == int(
                    row["reorder_hits_out_of_10_standard"])
                assert "never be" in strip["never"] or "never" in strip["never"]
                assert "never counted" in strip["note"]
                # Nothing in the strip may appear in the slots above it.
                assert not set(slots) & {item["stock_code"] for item in strip["items"]}

                history = result["history"]
                assert history["in_training_matrix"] is True
                assert history["training_products"] == int(row["training_products"])
                assert history["training_baskets"] == int(row["training_baskets"])
                assert history["bought_after_the_cut"] == int(row["bought_after_the_cut"])
                assert history["new_to_them_after_the_cut"] == int(
                    row["new_to_them_after_the_cut"])
                assert history["top_products"]

    asyncio.run(run())


def test_the_protocol_switch_changes_the_result_for_the_same_customer() -> None:
    """The discussion customer, both ways, on the same day with the same model."""

    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # The default is the shipping policy, so an omitted protocol is discovery.
            default = await client.post(
                "/api/recommend/slots", json={"customer_id": DISCUSSION_CUSTOMER})
            assert default.status_code == 200
            assert default.json()["protocol"] == "discovery"

            discovery = default.json()
            standard = (await client.post(
                "/api/recommend/slots",
                json={"customer_id": DISCUSSION_CUSTOMER, "protocol": "standard"},
            )).json()

            discovery_codes = [slot["stock_code"] for slot in discovery["slots"]]
            standard_codes = [slot["stock_code"] for slot in standard["slots"]]
            assert discovery_codes != standard_codes
            assert not set(discovery_codes) & set(standard_codes)

            # Discovery masks the history, so nothing in the slots is owned.
            assert all(slot["already_owned"] is False for slot in discovery["slots"])
            assert discovery["protocol_detail"]["name"] == "Discovery"
            assert discovery["matches_shipping_policy"] is True
            assert "never bought" in discovery["reason"]

            # Standard does not mask it, so this wholesaler - who owns 44% of the
            # catalog - gets ten slots of things already on the shelf.
            assert all(slot["already_owned"] for slot in standard["slots"])
            assert standard["protocol_detail"]["name"] == "Standard next-purchase"
            assert standard["matches_shipping_policy"] is False
            assert "never ships these slots" in standard["reason"]
            assert "would never show this list" in standard["policy_note"]

            # This is the case: 0 of 10 on discovery, 10 of 10 for the baseline
            # that learns nothing, on the same customer at the same moment.
            assert discovery["hits_out_of_10"] == 0
            assert discovery["buy_it_again"]["hits_out_of_10_standard"] == 10
            assert discovery["is_discussion_case"] is True
            assert "wholesaler restocking" in discovery["discussion_note"]

            # The strip does not move when the protocol does: it is not part of
            # the ranking and it is never counted as personalization.
            assert discovery["buy_it_again"] == standard["buy_it_again"]

            # A customer the model serves well moves too, without inverting.
            good_discovery = (await client.post(
                "/api/recommend/slots", json={"customer_id": 14096})).json()
            good_standard = (await client.post(
                "/api/recommend/slots",
                json={"customer_id": 14096, "protocol": "standard"},
            )).json()
            assert good_discovery["hits_out_of_10"] == 8
            assert [slot["stock_code"] for slot in good_discovery["slots"]] != [
                slot["stock_code"] for slot in good_standard["slots"]]

    asyncio.run(run())


def test_a_cold_start_customer_gets_the_labeled_fallback_and_never_recommended_for_you() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            roster = (await client.get("/api/recommend/customers?limit=24")).json()
            cold = [row for row in roster if row["cold_start"]]
            assert len(cold) == 2

            fallback_codes = [
                item["stock_code"]
                for item in (await client.get("/api/recommend/model")).json()["policy"]["fallback"]["items"]
            ]

            for entry in cold:
                for protocol in ("discovery", "standard"):
                    response = await client.post(
                        "/api/recommend/slots",
                        json={"customer_id": entry["customer_id"], "protocol": protocol},
                    )
                    assert response.status_code == 200
                    result = response.json()

                    # The label is the whole point. It says the list is generic.
                    assert result["module_title"] == "Popular right now"
                    assert result["module_title"] != "Recommended for you"
                    assert all(slot["label"] == "Popular right now" for slot in result["slots"])
                    assert result["personalized"] is False
                    assert result["fallback_used"] is True
                    assert result["fallback_slots"] == 10
                    assert result["model_used"] == "Fallback: recent revenue 28d"
                    assert "28 days" in result["score_basis"]

                    # Nothing about the customer chose these products, and the list
                    # is the frozen one from the policy artifact, in its order.
                    assert [slot["stock_code"] for slot in result["slots"]] == fallback_codes
                    assert all(slot["from_fallback"] for slot in result["slots"])
                    assert all(slot["because_you_bought"] is None for slot in result["slots"])
                    assert all("Nothing about this customer" in slot["reason"]
                               for slot in result["slots"])
                    assert result["history"]["in_training_matrix"] is False

                if entry["cold_start_kind"] == "no_history_before_the_cut":
                    assert "bought nothing before the cut" in result["reason"]
                    # No history means no replenishment strip either.
                    assert result["buy_it_again"]["available"] is False
                    assert result["buy_it_again"]["items"] == []
                    assert "nothing to remind them" in result["buy_it_again"]["note"]
                else:
                    assert "fewer than five distinct" in result["reason"]

            # And the comparison says plainly that there is nothing to compare.
            comparison = (await client.get(
                f"/api/recommend/compare?customer_id={cold[0]['customer_id']}")).json()
            assert comparison["personalized"] is False
            assert comparison["models"] == []
            assert "no row in the training matrix" in comparison["reason"]

    asyncio.run(run())


def test_compare_shows_the_reorder_baseline_topping_standard_and_collapsing_on_discovery() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/recommend/compare?customer_id={DISCUSSION_CUSTOMER}")
            assert response.status_code == 200
            board = response.json()

            assert board["personalized"] is True
            assert board["is_discussion_case"] is True
            assert [row["model"] for row in board["models"]] == MODELS
            assert sum(row["is_deployed"] for row in board["models"]) == 1
            assert [row["id"] for row in board["protocols"]] == ["standard", "discovery"]

            reorder = next(row for row in board["models"]
                           if row["model"] == "Reorder (already-bought)")
            # The frozen leaderboard ranks travel with the per-customer lists, so
            # one customer's result is never mistaken for the population result.
            assert reorder["standard_rank"] == 1
            assert reorder["discovery_rank"] == 7
            assert reorder["rank_change"] == -6
            assert reorder["standard_hr10"] == 0.7995
            assert reorder["discovery_hr10"] == 0.0217

            # Standard: ten slots this wholesaler already owns, all scored, all hit.
            assert reorder["standard"]["hits_out_of_10"] == 10
            assert reorder["standard"]["already_owned_in_slots"] == 10
            assert reorder["standard"]["all_scores_zero"] is False
            assert all(slot["score"] > 0 for slot in reorder["standard"]["slots"])

            # Discovery: every already-bought product is masked, so every score is
            # zero and the ten slots are an index-order tie-break, not a ranking.
            assert reorder["discovery"]["all_scores_zero"] is True
            assert all(slot["score"] == 0 for slot in reorder["discovery"]["slots"])
            assert all(slot["already_owned"] is False for slot in reorder["discovery"]["slots"])
            assert "tie-break, not a ranking" in reorder["discovery"]["scores_note"]

            deployed = next(row for row in board["models"]
                            if row["model"] == "Item-item CF (top-15)")
            assert deployed["is_deployed"] is True
            assert deployed["discovery"]["hits_out_of_10"] == 0
            assert deployed["discovery"]["all_scores_zero"] is False
            assert deployed["standard_rank"] == 3
            assert deployed["discovery_rank"] == 2

            assert "The model did not change. The question did." in board["lesson"]
            assert board["truth_standard"] == 865
            assert board["truth_discovery"] == 153

            assert (await client.get("/api/recommend/compare?customer_id=99999")).status_code == 404
            missing = await client.get("/api/recommend/compare")
            assert missing.status_code == 422

    asyncio.run(run())


def test_slots_rejects_unknown_fields_unknown_protocols_and_unknown_customers() -> None:
    async def run() -> None:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unknown_field = await client.post(
                "/api/recommend/slots",
                json={"customer_id": DISCUSSION_CUSTOMER, "protocol": "discovery", "model": "svd"},
            )
            assert unknown_field.status_code == 422
            assert "model" in unknown_field.text

            misspelled = await client.post(
                "/api/recommend/slots", json={"customer": DISCUSSION_CUSTOMER})
            assert misspelled.status_code == 422

            bad_protocol = await client.post(
                "/api/recommend/slots",
                json={"customer_id": DISCUSSION_CUSTOMER, "protocol": "incoherent-middle"},
            )
            assert bad_protocol.status_code == 422
            assert "discovery" in bad_protocol.text and "standard" in bad_protocol.text

            assert (await client.post("/api/recommend/slots", json={})).status_code == 422
            assert (await client.post(
                "/api/recommend/slots", json={"customer_id": -1})).status_code == 422
            assert (await client.post(
                "/api/recommend/slots", json={"customer_id": "17841x"})).status_code == 422

            missing_customer = await client.post(
                "/api/recommend/slots", json={"customer_id": 99999})
            assert missing_customer.status_code == 404
            assert "not in this retailer's history" in missing_customer.text
            assert str(DISCUSSION_CUSTOMER) in missing_customer.text

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/health",
                "/api/recommend/model",
                "/api/recommend/customers",
                f"/api/recommend/compare?customer_id={DISCUSSION_CUSTOMER}",
            ):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:recommendations" in response.text
                assert "product-recommendations notebook" in response.text

            slots = await client.post(
                "/api/recommend/slots", json={"customer_id": DISCUSSION_CUSTOMER})
            assert slots.status_code == 503
            assert "npm run prepare:recommendations" in slots.text
            # The message names the files that are missing, not just the fix.
            assert "item_similarity.npz" in slots.text

    asyncio.run(run())
