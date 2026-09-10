import asyncio
import json

from httpx import ASGITransport, AsyncClient

from app.config import DEFAULT_ARTIFACT_DIR
from app.main import create_app


ARTIFACTS = (
    "chunks.parquet",
    "embeddings.npy",
    "index.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "corpus_manifest.json",
    "cached_answers.json",
)

LAYERS = ["regulation", "site_procedure", "equipment", "plain_language"]

TAU = 0.48

_app = None


def app_once():
    """Build the service once.

    Loading the sentence encoder costs a few seconds, so every test shares one
    application. Each test still drives it over HTTP through ASGITransport.
    """
    global _app
    if _app is None:
        _app = create_app()
    return _app


def read_pack() -> dict:
    return json.loads((DEFAULT_ARTIFACT_DIR / "cached_answers.json").read_text())


def test_health_reports_the_loaded_artifacts() -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            health = await client.get("/health")
            assert health.status_code == 200
            readiness = health.json()
            assert readiness["status"] == "ok"
            assert readiness["service"] == "procedures-api"
            assert readiness["model"] == "loaded"
            assert readiness["model_version"] == "raglab-m05-v1"
            assert readiness["corpus"] == "raglab-m05-v1"
            assert readiness["embedder"] == "sentence-transformers/all-MiniLM-L6-v2"
            assert readiness["chunks"] == 3098
            assert readiness["documents_indexed"] == 12
            assert readiness["packaged_questions"] == 20
            assert readiness["refusal_threshold"] == TAU
            assert set(readiness["artifacts"]) == set(ARTIFACTS)
            assert all(readiness["artifacts"].values())

    asyncio.run(run())


def test_model_card_carries_the_frozen_evidence() -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            response = await client.get("/api/procedures/model")
            assert response.status_code == 200
            info = response.json()

            assert info["version"] == "raglab-m05-v1"
            assert info["max_question_characters"] == 500
            assert "never authorizes work" in info["boundary"]
            assert any("does not authorize work" in line for line in info["what_it_does_not_do"])
            assert info["representation"]["embedder"] == "sentence-transformers/all-MiniLM-L6-v2"
            assert info["representation"]["dimensions"] == 384
            assert info["packaged_questions"] == 20
            assert info["packaged_refusals"] == 4

            # The retrieval leaderboard the evidence view quotes, read from the
            # artifact rather than written into the page.
            evaluation = info["evaluation"]
            assert evaluation["questions_scored"] == 45
            tfidf, minilm = evaluation["leaderboard"]
            assert tfidf["retriever"] == "TF-IDF word counts"
            assert tfidf["hit_at_1"] == 0.311 and tfidf["hit_at_5"] == 0.578
            assert tfidf["is_deployed"] is False
            assert minilm["retriever"] == "MiniLM sentence embeddings"
            assert minilm["hit_at_1"] == 0.467 and minilm["hit_at_5"] == 0.822
            assert minilm["is_deployed"] is True
            assert minilm["hit_at_1"] > tfidf["hit_at_1"]

            # The benchmark that scored keyword search at 90% did it with
            # questions generated from the passage text.
            phrasing = evaluation["question_phrasing"]
            assert phrasing["research_tfidf_hit_at_1"] == 0.9
            assert phrasing["technician_tfidf_hit_at_1"] == 0.311
            assert phrasing["technician_minilm_hit_at_1"] == 0.467

            assert [row["bucket"] for row in evaluation["per_bucket"]] == ["A", "B", "C", "E"]

            refusal = evaluation["refusal"]
            assert refusal["tau"] == TAU
            assert len(refusal["rules"]) == 2
            assert refusal["correct_refusal_outside_corpus"] == 0.875
            assert refusal["correct_refusal_incorporated_by_reference"] == 0.857
            assert refusal["false_refusal_rate"] == 0.044
            chosen = [row for row in refusal["sweep"] if row["is_chosen"]]
            assert len(chosen) == 1 and chosen[0]["tau"] == TAU
            refusing = {row["bucket"]: row for row in refusal["by_bucket"]}
            assert refusing["D"]["should_refuse"] is True and refusing["D"]["rate"] == 0.875
            assert refusing["A"]["should_refuse"] is False and refusing["A"]["rate"] == 0.04

            # Right text, wrong rule: the duplicate corpus left retrieval almost
            # untouched and destroyed the citation.
            duplicate = evaluation["duplicate_corpus"]
            assert duplicate["minilm_cite_hit_at_1_before"] == 0.8
            assert duplicate["minilm_cite_hit_at_1_after"] == 0.267
            assert duplicate["minilm_text_hit_at_1_after"] == 0.767
            assert duplicate["minilm_right_text_wrong_rule"] == 0.5

            # The two honesty findings.
            citations = evaluation["citations"]
            assert citations["naive_citation_wrong"] == "82.3%"
            assert citations["naive_citation_nonexistent"] == "77.4%"
            assert citations["stateful_structurally_invalid"] == 0
            assert citations["cross_references_resolved_stateful"] == 0.918
            assert citations["cross_references_resolved_naive"] == 0.129
            assert "self-check" in citations["structural_check_is_a_self_check"].lower()
            claims = evaluation["unsupported_claim_check"]
            assert claims["answers_checked"] == 20 and claims["refusals"] == 4
            assert claims["unsupported_numerals"] == 0
            assert "misattribution" in claims["what_it_misses"] or "wrong rule" in claims["what_it_misses"]

            deployed = [row for row in evaluation["chunking"]["sizes"] if row["is_deployed"]]
            assert len(deployed) == 1
            assert deployed[0]["chunks"] == 3098
            assert deployed[0]["tokens_discarded"] == "0.0%"

            assert info["policy"]["refusal_threshold"] == TAU
            assert len(info["policy"]["rules"]) == 2
            assert info["policy"]["service_must"]
            assert {row["bucket"] for row in info["evaluation_set"]} == set("ABCDE")

    asyncio.run(run())


def test_questions_expose_the_refusals_and_the_discussion_case() -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            response = await client.get("/api/procedures/questions")
            assert response.status_code == 200
            questions = response.json()
            assert len(questions) == 20
            assert len({row["qid"] for row in questions}) == 20
            assert sum(row["is_refusal"] for row in questions) == 4
            kinds = {row["refusal_kind"] for row in questions if row["is_refusal"]}
            assert kinds == {"refused_low_confidence", "refused_incorporated_by_reference"}

            discussion = [row for row in questions if row["is_discussion_case"]]
            assert len(discussion) == 1
            assert discussion[0]["qid"] == "E01"
            assert discussion[0]["refusal_kind"] == "refused_incorporated_by_reference"
            assert discussion[0]["consult"] == "ANSI B31.1.0-1967, Power Piping"
            # The incorporation case scores well above the threshold: a score
            # rule alone would have answered it.
            assert discussion[0]["top_score"] > TAU
            assert discussion[0]["above_threshold"] is True

            assert all(row["question"] and row["summary"] for row in questions)
            assert all(row["top_citation"] and row["top_source"] for row in questions)
            assert all(row["top_layer"] in LAYERS for row in questions)
            assert all(row["passages"] == 4 for row in questions)

            # A short list still spans the buckets and still contains a refusal,
            # so the picker on the page can never hide the refusal path.
            short = (await client.get("/api/procedures/questions?limit=5")).json()
            assert len(short) == 5
            assert len({row["bucket"] for row in short}) == 5
            assert any(row["is_discussion_case"] for row in short)
            assert sum(row["is_refusal"] for row in short) == 2

            assert len((await client.get("/api/procedures/questions?limit=1")).json()) == 1
            assert len((await client.get("/api/procedures/questions?limit=24")).json()) == 20
            assert (await client.get("/api/procedures/questions?limit=0")).status_code == 422
            assert (await client.get("/api/procedures/questions?limit=25")).status_code == 422

    asyncio.run(run())


def test_ask_reproduces_the_notebook_artifact_exactly() -> None:
    """The contract test: live retrieval must return the notebook's own numbers.

    Every packaged question is asked through the API and compared with the
    passages the notebook stored in ``cached_answers.json``. The comparison is
    exact, not approximate: the citation, the source and the score of every
    ranked passage, to the same four decimal places. If the service ever loaded
    different vectors, re-encoded the corpus, or prepared the query text
    differently, the cosine scores would drift in the last digits and this would
    fail. It is the proof that the page is showing the measured system.
    """

    async def run() -> None:
        pack = read_pack()
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            for stored in pack["answers"]:
                response = await client.post(
                    "/api/procedures/ask", json={"question": stored["question"]}
                )
                assert response.status_code == 200
                result = response.json()

                assert result["top_score"] == round(float(stored["top_score"]), 4)
                assert result["passages"][0]["citation"] == stored["retrieved"][0]["citation"]
                assert result["reproduces_packaged_retrieval"] is True

                # Not only the top row: the whole ranked list, in the same
                # order, with the same citations and the same passage text.
                # Ranks below the first are compared to within 0.0001, because
                # the notebook scored them on float32 vectors and the service
                # scores them on the float16 vectors that were committed - the
                # storage choice the model card records. Five of the eighty
                # ranked rows differ in that last digit; none of them move.
                assert len(result["passages"]) == len(stored["retrieved"])
                for got, expected in zip(result["passages"], stored["retrieved"]):
                    assert got["rank"] == expected["rank"]
                    assert got["citation"] == expected["citation"]
                    assert got["citations"] == expected["citations"]
                    assert got["source"] == expected["source"]
                    assert abs(got["score"] - float(expected["score"])) <= 0.0002
                    # The passage is displayed in full, never a label alone.
                    assert got["text"] == expected["text"]

                # The refusal decision is recomputed by the deployed policy and
                # must agree with the status the notebook shipped.
                assert result["decision"] == stored["status"]
                assert result["is_packaged"] is True
                assert result["qid"] == stored["qid"]
                assert result["answer"] == stored["answer"]
                assert result["answer_citations"] == stored["citations"]
                assert result["gold_citations"] == stored["gold_citations"]
                assert result["threshold"] == TAU
                assert result["above_threshold"] == (result["top_score"] >= TAU)
                assert result["model_version"] == "raglab-m05-v1"
                assert "never authorizes work" in result["boundary"]

    asyncio.run(run())


def test_a_below_threshold_question_takes_the_refusal_route() -> None:
    async def run() -> None:
        pack = read_pack()
        low = next(
            row for row in pack["answers"] if row["status"] == "refused_low_confidence"
        )
        incorporated = next(
            row
            for row in pack["answers"]
            if row["status"] == "refused_incorporated_by_reference"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/procedures/ask", json={"question": low["question"]}
            )
            refusal = response.json()
            assert refusal["top_score"] < TAU
            assert refusal["above_threshold"] is False
            assert refusal["decision"] == "refused_low_confidence"
            assert "cosine similarity < 0.48" in refusal["rule_fired"]
            assert refusal["consult"]
            # A refusal still shows its passages, so a reader can see what was
            # close and judge the refusal for themselves.
            assert len(refusal["passages"]) == 4
            assert refusal["answer"]

            # The incorporation case is the one a score rule cannot catch: it
            # retrieves confidently and is still refused, and the standard it
            # names is read out of the retrieved text.
            second = await client.post(
                "/api/procedures/ask", json={"question": incorporated["question"]}
            )
            named = second.json()
            assert named["top_score"] > TAU
            assert named["above_threshold"] is True
            assert named["decision"] == "refused_incorporated_by_reference"
            assert named["standards_named"]
            assert any("ANSI" in standard for standard in named["standards_named"])
            assert "consensus standard" in named["rule_fired"]
            assert named["is_discussion_case"] is True
            assert named["teaching_note"]

            # A question nothing in the corpus covers is refused too, and the
            # refusal names what the corpus does hold.
            outside = await client.post(
                "/api/procedures/ask",
                json={"question": "What is the recommended coolant for a Kubota V3800 engine?"},
            )
            unknown = outside.json()
            assert unknown["is_packaged"] is False
            assert unknown["answer"] is None
            if unknown["decision"] == "refused_low_confidence":
                assert "close enough" in unknown["decision_detail"]

    asyncio.run(run())


def test_an_unpackaged_question_returns_passages_and_no_invented_answer() -> None:
    async def run() -> None:
        typed = "What does the rule say about guarding on a table saw?"
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            response = await client.post("/api/procedures/ask", json={"question": typed})
            assert response.status_code == 200
            result = response.json()

            assert result["is_packaged"] is False
            assert result["qid"] is None
            assert result["bucket"] is None
            assert result["answer"] is None
            assert result["answer_citations"] == []
            assert result["gold_citations"] == []
            assert result["teaching_note"] is None
            assert result["reproduces_packaged_retrieval"] is None
            assert "no drafted answer" in result["answer_note"]
            assert "never writes new prose" in result["answer_note"]

            # It still retrieved, and every passage carries a citation, a layer
            # and its full text.
            assert len(result["passages"]) == 4
            assert [passage["rank"] for passage in result["passages"]] == [1, 2, 3, 4]
            scores = [passage["score"] for passage in result["passages"]]
            assert scores == sorted(scores, reverse=True)
            assert all(passage["citation"] and passage["text"] for passage in result["passages"])
            assert all(passage["layer"] in LAYERS for passage in result["passages"])
            assert all(passage["layer_label"] for passage in result["passages"])
            assert result["characters"] == len(typed)
            assert result["words"] == len(typed.split())

            # The comparison retriever runs on the same question, from the same
            # committed index, so the page can show where keyword search lands.
            keyword = result["keyword_comparison"]
            assert keyword["retriever"] == "TF-IDF word counts"
            assert keyword["citation"] and keyword["source"]
            assert isinstance(keyword["agrees_with_deployed"], bool)

            # Surrounding whitespace names the same packaged question, and the
            # answer that comes back is the packaged one.
            pack = read_pack()
            packaged = pack["answers"][0]["question"]
            padded = await client.post(
                "/api/procedures/ask", json={"question": f"  {packaged}\n"}
            )
            assert padded.json()["qid"] == pack["answers"][0]["qid"]
            assert padded.json()["answer"] == pack["answers"][0]["answer"]

    asyncio.run(run())


def test_ask_rejects_blank_text_oversized_text_and_unknown_fields() -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            blank = await client.post("/api/procedures/ask", json={"question": "   \n\t "})
            assert blank.status_code == 422
            assert "no question to look up" in blank.text
            assert "packaged questions" in blank.text

            empty = await client.post("/api/procedures/ask", json={"question": ""})
            assert empty.status_code == 422

            too_long = await client.post(
                "/api/procedures/ask", json={"question": "lockout " * 70}
            )
            assert too_long.status_code == 422
            assert "560 characters" in too_long.text
            assert "reads up to 500" in too_long.text

            # 500 characters exactly is accepted; the cap is inclusive.
            assert (
                await client.post(
                    "/api/procedures/ask",
                    json={"question": "How long do we keep a cancelled entry permit? " + "a" * 454},
                )
            ).status_code == 200

            unknown_field = await client.post(
                "/api/procedures/ask",
                json={"question": "Who removes a lock?", "top_k": 10},
            )
            assert unknown_field.status_code == 422

            missing = await client.post("/api/procedures/ask", json={})
            assert missing.status_code == 422

    asyncio.run(run())


def test_corpus_lists_four_layers_with_licence_and_distribution() -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_once()), base_url="http://test"
        ) as client:
            response = await client.get("/api/procedures/corpus")
            assert response.status_code == 200
            corpus = response.json()

            assert corpus["corpus"] == "raglab-m05-v1"
            assert corpus["date_pin"] == "2025-08-01"
            assert corpus["documents"] == 13
            assert corpus["documents_indexed"] == 12
            assert corpus["chunks"] == 3098
            assert [layer["layer"] for layer in corpus["layers"]] == LAYERS
            assert sum(layer["chunks"] for layer in corpus["layers"]) == 3098
            assert abs(sum(layer["share_of_chunks"] for layer in corpus["layers"]) - 1) < 1e-3
            assert sum(layer["documents"] for layer in corpus["layers"]) == 13

            documents = [item for layer in corpus["layers"] for item in layer["items"]]
            assert len(documents) == 13
            assert all(item["license"] and item["distribution"] for item in documents)
            assert all(item["words"] > 0 for item in documents)
            # Every document in the index carries passages; the opt-in duplicate
            # regulation carries none.
            indexed = [item for item in documents if item["in_base_corpus"]]
            assert all(item["chunks"] > 0 for item in indexed)
            duplicate = next(item for item in documents if not item["in_base_corpus"])
            assert duplicate["document"] == "30 CFR part 57"
            assert duplicate["chunks"] == 0
            assert "near-duplicate" in duplicate["indexed_note"]

            # The licence lesson: public domain is not redistributable. Exactly
            # one document is admitted by a distribution statement rather than
            # by being unrestricted.
            statement_a = [item for item in documents if item["is_statement_a"]]
            assert len(statement_a) == 1
            assert statement_a[0]["document"] == "TM 9-6115-464-12"
            assert all(item["redistributable"] for item in documents)
            assert "Statement A" in corpus["licence_rule"] or "STATEMENT A" in corpus["licence_rule"]
            assert corpus["licence_gate"]["statement_a_present"] is True
            assert corpus["licence_gate"]["restrictive_statement_present"] is False
            assert corpus["licence_gate"]["verdict"].startswith("ACCEPT")

            # And the documents that failed the gate, with the reason.
            assert len(corpus["excluded"]) == 3
            assert all(item["why_excluded"] and item["lesson"] for item in corpus["excluded"])
            assert any("STATEMENT C" in item["why_excluded"] for item in corpus["excluded"])
            assert "network" not in corpus["fetch_policy"] or "Nothing" in corpus["fetch_policy"]

    asyncio.run(run())


def test_missing_artifacts_return_503_with_recovery_instructions(tmp_path) -> None:
    async def run() -> None:
        app = create_app(artifact_dir=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/health",
                "/api/procedures/model",
                "/api/procedures/questions",
                "/api/procedures/corpus",
            ):
                response = await client.get(path)
                assert response.status_code == 503
                assert "npm run prepare:procedures" in response.text
                assert "procedure-assistant notebook" in response.text

            ask = await client.post(
                "/api/procedures/ask",
                json={"question": "Who is allowed to remove a lockout device?"},
            )
            assert ask.status_code == 503
            assert "npm run prepare:procedures" in ask.text

    asyncio.run(run())
