from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import act, at_gate, run_status, upload, wait_for

IMAGE_BRIEF = "Hero studio shot of SOLENNE GT, a fictional luxury electric grand tourer, liquid-silver paint."


def image_brief(**overrides: Any) -> dict[str, Any]:
    brief = {"use_case": "hero", "brief": IMAGE_BRIEF, "size": "1536x864", "candidates": 3, "prompt_helper": True,
             "must_not_include": "real car brands or logos", "title": "", "visible_label": "Made with AI"}
    brief.update(overrides)
    return brief


def test_image_run_with_iteration_tree(client: TestClient) -> None:
    subject, scene = upload(client, "hero.png"), upload(client, "scene.png")
    brief = image_brief(references=[{"sha": scene["sha"], "role": "scene", "name": "night road"},
                                    {"sha": subject["sha"], "role": "subject", "name": "design sheet"}],
                        title="SOLENNE GT")
    run_id = client.post("/api/design/runs", json={"pipeline": "image", "brief": brief}).json()["run"]["id"]

    detail = wait_for(client, run_id, at_gate("prompt"))
    prompt = next(s for s in detail["steps"] if s["key"] == "prompt")["data"]["prompt"]
    assert prompt.startswith("[image.prompt]")
    act(client, run_id, "approve", {"step": "prompt", "prompt": "A silver grand tourer on a dark reflective floor."})

    detail = wait_for(client, run_id, at_gate("candidates"))
    candidates = [a for a in detail["artifacts"] if a["kind"] == "image"]
    assert [c["label"] for c in candidates] == ["c1", "c2", "c3"]
    first = candidates[0]
    assert first["inputs"] == [subject["sha"], scene["sha"]], "subject before scene"
    assert first["prompt"].startswith("Image 1 is the subject") and "Image 2 is the scene" in first["prompt"]
    assert first["prompt"].endswith("Keep it free of: real car brands or logos.")
    assert act(client, run_id, "approve", {"step": "candidates"}, expect=409)["detail"].startswith("Keep at least")
    act(client, run_id, "decide", {"artifact_id": first["id"], "verdict": "keep"})
    act(client, run_id, "approve", {"step": "candidates"})

    detail = wait_for(client, run_id, at_gate("iterate"))
    draft = act(client, run_id, "draft_revision", {"artifact_id": first["id"], "note": "Lower the camera.",
                                                   "references": [{"sha": subject["sha"], "role": "subject"}]})
    assert draft["result"]["prompt"].startswith("[image.revise]")
    assert draft["result"]["preview"].startswith("Image 1 is the current image")
    created = act(client, run_id, "revise", {"artifact_id": first["id"], "note": "Lower the camera.",
                                             "prompt": draft["result"]["prompt"], "count": 2,
                                             "references": [{"sha": subject["sha"], "role": "subject"}]})
    v1_id, v2_id = created["result"]["created"]
    detail = wait_for(client, run_id, at_gate("iterate"))
    v1 = next(a for a in detail["artifacts"] if a["id"] == v1_id)
    assert v1["label"] == "v1" and v1["parent_id"] == first["id"] and v1["status"] == "ready"
    assert v1["inputs"][0] == first["media_sha"] and v1["inputs"][1] == subject["sha"]
    branch = act(client, run_id, "revise", {"artifact_id": v1_id, "note": "Night instead of day.", "mode": "edit"})
    v3_id = branch["result"]["created"][0]
    detail = wait_for(client, run_id, at_gate("iterate"))
    v3 = next(a for a in detail["artifacts"] if a["id"] == v3_id)
    assert v3["parent_id"] == v1_id and v3["params"]["core"].endswith("Change: Night instead of day.")
    assert v3["prompt"].count("Keep it free of") == 1, "rules are not stacked on every pass"

    act(client, run_id, "decide", {"artifact_id": v3_id, "verdict": "keep"})
    act(client, run_id, "decide", {"artifact_id": v2_id, "verdict": "keep"})
    kept = [a["label"] for a in client.get(f"/api/design/runs/{run_id}").json()["artifacts"] if a["verdict"] == "keep"]
    assert kept == ["c1", "v2", "v3"], "image keeps are not exclusive"
    assert act(client, run_id, "approve", {"step": "iterate", "final_id": candidates[1]["id"]},
               expect=409)["detail"].startswith("Pick one of the kept")
    act(client, run_id, "approve", {"step": "iterate", "final_id": v3_id})
    detail = wait_for(client, run_id, run_status("completed", "failed"))
    assert detail["run"]["status"] == "completed"
    final = next(a for a in detail["artifacts"] if a["kind"] == "final")
    assert final["parent_id"] == v3_id and final["media_sha"] != v3["media_sha"]
    assert {c["key"] for c in final["checks"]} >= {"label", "title", "c2pa-source", "c2pa-final"}
    assert detail["run"]["counters"]["outputs"] == "3 kept · 3 edit passes"


def test_image_filter_block_then_reword(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "image", "brief": image_brief(
        prompt_helper=False, candidates=1, brief="[blocked] A famous sports car with its badge.")}).json()["run"]["id"]
    detail = wait_for(client, run_id, at_gate("prompt"))
    assert any(e["code"] == "drafted" and "helper is off" in e["message"] for e in detail["events"])
    act(client, run_id, "approve", {"step": "prompt"})
    detail = wait_for(client, run_id, at_gate("candidates"))
    blocked = next(a for a in detail["artifacts"] if a["kind"] == "image")
    assert blocked["status"] == "blocked" and "BingBlockList" in blocked["error"]
    assert detail["run"]["counters"]["blocked"] == 1
    assert client.get("/api/design/status").json()["caps"]["image"]["used"] == 0, "blocked calls give the cap back"
    act(client, run_id, "retry_artifact", {"artifact_id": blocked["id"], "prompt": "A fictional silver coupe."})
    detail = wait_for(client, run_id, lambda d: next(a for a in d["artifacts"] if a["id"] == blocked["id"])["status"]
                      == "ready")
    assert next(a for a in detail["artifacts"] if a["id"] == blocked["id"])["prompt"] == "A fictional silver coupe."


def test_more_candidates_and_caps(make_client: Any) -> None:
    client = make_client(cap_images=2)
    run_id = client.post("/api/design/runs", json={"pipeline": "image", "brief": image_brief(
        candidates=2)}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("prompt"))
    act(client, run_id, "approve", {"step": "prompt"})
    wait_for(client, run_id, at_gate("candidates"))
    act(client, run_id, "more_candidates", {"count": 1})
    detail = wait_for(client, run_id, at_gate("candidates"))
    c3 = next(a for a in detail["artifacts"] if a["label"] == "c3")
    assert c3["status"] == "failed" and c3["error_code"] == "cap_reached"
    status = client.get("/api/design/status").json()
    assert status["caps"]["image"] == {"label": "Images", "used": 2.0, "cap": 2, "detail": "6 per minute"}
