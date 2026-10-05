from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import act, at_gate, run_status, wait_for

SOURCE = {"title": "NASA, Boeing Share Update on Commercial Starliner Development Plans",
          "url": "https://www.nasa.gov/news-release/nasa-boeing-share-update-on-commercial-starliner-development-plans/",
          "published": "2026-09-28",
          "text": "The uncrewed Starliner-1 has the potential to fly in December of this year or January 2027. "
                  "Our current plan is to return astronauts on Starliner-2 by 2028."}


def article_brief(**overrides: Any) -> dict[str, Any]:
    brief = {"format": "news-summary", "brief": "Summarize the release for students in plain words.",
             "target_words": 60, "sources": [SOURCE], "must_not_include": "Ferrari",
             "visible_label": "AI-assisted summary, reviewed by an editor.", "fact_check": True}
    brief.update(overrides)
    return brief


def test_article_outline_draft_check_revise_and_approve(client: TestClient) -> None:
    created = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief()})
    assert created.status_code == 201, created.text
    run_id = created.json()["run"]["id"]
    assert created.json()["run"]["title"].startswith("NASA, Boeing")

    detail = wait_for(client, run_id, at_gate("outline"))
    outline = next(s for s in detail["steps"] if s["key"] == "outline")["data"]
    assert outline["headline"] == "Fake headline" and len(outline["points"]) == 3
    act(client, run_id, "approve", {"step": "outline", "headline": "Starliner update",
                                    "points": [{"text": "Starliner-1 timing", "sources": [1]}]})

    detail = wait_for(client, run_id, at_gate("draft"))
    v1 = next(a for a in detail["artifacts"] if a["label"] == "v1")
    assert v1["metrics"]["unsupported"] == 1 and v1["checks"][0]["state"] == "bad"
    assert v1["data"]["claims"][1]["verdict"] == "unsupported" and v1["data"]["judge"] == "fake-text"

    act(client, run_id, "revise", {"note": "Use the year from the release date."})
    detail = wait_for(client, run_id, at_gate("draft"))
    v2 = next(a for a in detail["artifacts"] if a["label"] == "v2")
    assert v2["parent_id"] == v1["id"] and v2["metrics"]["unsupported"] == 0 and "2026" in v2["data"]["body"]

    act(client, run_id, "save_edit", {"base_id": v2["id"], "body": "Starliner-1 could fly in December 2026."})
    detail = wait_for(client, run_id, at_gate("draft"))
    v3 = next(a for a in detail["artifacts"] if a["label"] == "v3")
    assert v3["data"]["author"] == "you" and v3["status"] == "ready" and v3["checks"]

    act(client, run_id, "approve", {"step": "draft", "version_id": v2["id"]})
    detail = wait_for(client, run_id, run_status("completed", "failed"))
    assert detail["run"]["status"] == "completed"
    final = next(a for a in detail["artifacts"] if a["kind"] == "final")
    assert final["parent_id"] == v2["id"] and final["data"]["markdown"].startswith("# Fake headline")
    assert "AI-assisted summary" in final["data"]["markdown"] and "Sources:" in final["data"]["markdown"]
    text = client.get(f"/api/design/media/{final['media_sha']}").text
    assert "December 2026" in text
    assert detail["run"]["counters"]["outputs"].startswith("3 versions")


def test_article_rules_and_validation(client: TestClient) -> None:
    short = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief(sources=[])})
    assert short.status_code == 409 and "sources" in short.json()["detail"]
    run_id = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief(
        must_not_include="agency", fact_check=False)}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("outline"))
    act(client, run_id, "approve", {"step": "outline"})
    detail = wait_for(client, run_id, at_gate("draft"))
    v1 = next(a for a in detail["artifacts"] if a["label"] == "v1")
    assert [c["key"] for c in v1["checks"]] == ["length", "rules"] and v1["checks"][1]["state"] == "bad"
    assert act(client, run_id, "revise", {"note": ""}, expect=409)["detail"].startswith("Say what")


def test_run_chooses_its_own_text_models(client: TestClient) -> None:
    models = {"text-draft": "gpt-6-astra", "text-judge": "gpt-6.1-sol"}
    created = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief(), "models": models})
    assert created.status_code == 201, created.text
    run_id = created.json()["run"]["id"]
    assert created.json()["run"]["settings"] == {"models": models}
    detail = wait_for(client, run_id, at_gate("outline"))
    assert next(s for s in detail["steps"] if s["key"] == "outline")["data"]["model"] == "gpt-6-astra"
    act(client, run_id, "approve", {"step": "outline"})
    detail = wait_for(client, run_id, at_gate("draft"))
    v1 = next(a for a in detail["artifacts"] if a["label"] == "v1")
    assert v1["deployment"] == "gpt-6-astra" and v1["data"]["judge"] == "gpt-6.1-sol"
    assert "gpt-6.1-sol" in v1["checks"][0]["basis"]
    assert {"gpt-6-astra", "gpt-6.1-sol"} <= set(detail["run"]["counters"]["models"])
    bundle = client.get(f"/api/design/runs/{run_id}/export")
    assert bundle.status_code == 200


def test_live_install_only_allows_its_text_models(make_client: Any) -> None:
    client = make_client(provider_mode="live", text_endpoint="https://example.openai.azure.com/openai/v1",
                         text_draft_deployment="gpt-6-astra", text_judge_deployment="gpt-6.1-sol",
                         text_models="gpt-5.4-mini")
    status = client.get("/api/design/status").json()
    assert status["text_models"] == ["gpt-6-astra", "gpt-6.1-sol", "gpt-5.4-mini"]
    assert status["text_defaults"] == {"text-draft": "gpt-6-astra", "text-judge": "gpt-6.1-sol"}
    response = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief(),
                                                     "models": {"text-draft": "not-deployed"}})
    assert response.status_code == 409 and "not one of this install's text models" in response.json()["detail"]
    response = client.post("/api/design/runs", json={"pipeline": "article", "brief": article_brief(),
                                                     "models": {"video": "sora-3"}})
    assert response.status_code == 409 and "Only text models" in response.json()["detail"]
