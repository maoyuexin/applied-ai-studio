from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import act, at_gate, run_status, upload, wait_for

BRIEF = ("A 30-second ad for SOLENNE GT, a fictional luxury electric grand tourer: coastal highway at sunrise, "
         "dad at the wheel, kids in the back, home at dusk.")


def video_brief(refs: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    brief = {"brief": BRIEF, "shots": 2, "seconds": 4, "takes_per_shot": 2, "size": "1280x720",
             "must_not_include": "real car brands or logos, readable license plates",
             "visible_label": "Fictional vehicle. Made with AI.", "end_title": "SOLENNE GT",
             "end_tagline": "Drive the quiet.", "references": refs or []}
    brief.update(overrides)
    return brief


def test_health_status_and_pipelines(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "design-api"}
    status = client.get("/api/design/status").json()
    assert status["install"] == "Test"
    assert {role["role"] for role in status["roles"]} == {"text-draft", "text-judge", "image", "video", "voice",
                                                          "listen-back"}
    assert all(item["ready"] for item in status["pipelines"])
    pipelines = {p["key"]: p for p in client.get("/api/design/pipelines").json()}
    assert set(pipelines) == {"video", "image", "voice", "article", "inspect", "alerts"}
    assert [s["key"] for s in pipelines["video"]["steps"]] == ["shotlist", "keyframes", "takes", "voiceover",
                                                                "assemble", "provenance"]


def test_video_run_end_to_end(client: TestClient) -> None:
    ref = upload(client)
    created = client.post("/api/design/runs", json={
        "pipeline": "video", "title": "SOLENNE GT · family drive", "tags": ["Module 8"],
        "brief": video_brief([{"sha": ref["sha"], "role": "subject", "name": "design sheet"}])})
    assert created.status_code == 201, created.text
    run_id = created.json()["run"]["id"]
    references = [a for a in created.json()["artifacts"] if a["kind"] == "reference"]
    assert references and references[0]["media_sha"] == ref["sha"] and references[0]["thumb_sha"]

    detail = wait_for(client, run_id, at_gate("shotlist"))
    shots = next(s for s in detail["steps"] if s["key"] == "shotlist")["data"]["shots"]
    assert [shot["mode"] for shot in shots] == ["i2v", "t2v"]
    assert detail["gate"] == {"step": "shotlist", "ready": True, "reason": ""}
    shots[1]["prompt"] = "Dad grips the wheel and smiles as palm trees rush past the window."
    act(client, run_id, "approve", {"step": "shotlist", "shots": shots})

    detail = wait_for(client, run_id, at_gate("keyframes"))
    keyframes = [a for a in detail["artifacts"] if a["kind"] == "keyframe"]
    assert len(keyframes) == 1 and keyframes[0]["verdict"] == "keep" and keyframes[0]["inputs"] == [ref["sha"]]
    act(client, run_id, "approve", {"step": "keyframes"})

    detail = wait_for(client, run_id, at_gate("takes"))
    takes = [a for a in detail["artifacts"] if a["kind"] == "take"]
    assert len(takes) == 4 and all(t["status"] == "ready" for t in takes)
    first = next(t for t in takes if t["label"] == "s1_t1")
    assert first["params"]["mode"] == "i2v" and first["inputs"] == [keyframes[0]["media_sha"]]
    assert {c["key"] for c in first["checks"]} == {"motion", "audio", "c2pa"}
    assert first["metrics"]["motion"] is not None and first["vendor_job_id"].startswith("video_fake_")
    s2 = next(t for t in takes if t["label"] == "s2_t1")
    assert s2["params"]["mode"] == "t2v" and s2["inputs"] == []
    assert "Shot 2 needs" not in detail["gate"]["reason"]
    assert detail["gate"]["ready"] is False

    blocked = act(client, run_id, "approve", {"step": "takes"}, expect=409)
    assert "Keep one take for shot 1" in blocked["detail"]
    act(client, run_id, "decide", {"artifact_id": first["id"], "verdict": "keep", "note": "Clean opener",
                                   "checklist": {"Same car as the design sheet?": True}})
    remix = act(client, run_id, "remix_take", {"artifact_id": s2["id"], "note": "Slower camera, warmer light."})
    remixed = [a for a in remix["detail"]["artifacts"] if a["parent_id"] == s2["id"]]
    assert remixed and remixed[0]["params"]["mode"] == "remix" and remixed[0]["label"] == "s2_t3"
    detail = wait_for(client, run_id, lambda d: next(a for a in d["artifacts"] if a["id"] == remixed[0]["id"])[
        "status"] == "ready")
    act(client, run_id, "decide", {"artifact_id": remixed[0]["id"], "verdict": "keep"})
    act(client, run_id, "decide", {"artifact_id": s2["id"], "verdict": "keep"})
    detail = client.get(f"/api/design/runs/{run_id}").json()
    kept_s2 = [a["label"] for a in detail["artifacts"] if a["grp"] == "s2" and a["verdict"] == "keep"]
    assert kept_s2 == ["s2_t1"], "keep is exclusive within a shot"

    act(client, run_id, "approve", {"step": "takes"})
    detail = wait_for(client, run_id, run_status("completed", "failed"), timeout=120)
    assert detail["run"]["status"] == "completed", detail["run"]["error"]
    steps = {s["key"]: s["status"] for s in detail["steps"]}
    assert steps == {"shotlist": "done", "keyframes": "done", "takes": "done", "voiceover": "skipped",
                     "assemble": "done", "provenance": "done"}
    final = next(a for a in detail["artifacts"] if a["kind"] == "final")
    assert final["media_type"] == "video/mp4" and final["params"]["edit_labels"] == ["s1_t1", "s2_t1"]
    assert 9.5 < final["metrics"]["duration"] < 11.5  # two 4 s takes, 0.5 s crossfade, 2.4 s of end card
    report = next(a for a in detail["artifacts"] if a["kind"] == "report")
    assert report["data"]["visible_label"] == "Fictional vehicle. Made with AI."
    counters = detail["run"]["counters"]
    assert counters["takes"] == 5 and counters["kept"] == 2 and counters["final_duration"]
    media = client.get(f"/api/design/media/{final['media_sha']}")
    assert media.status_code == 200 and media.headers["content-type"] == "video/mp4"
    ranged = client.get(f"/api/design/media/{final['media_sha']}", headers={"Range": "bytes=0-99"})
    assert ranged.status_code == 206 and len(ranged.content) == 100

    history = client.get("/api/design/runs?pipeline=video").json()
    item = next(r for r in history["runs"] if r["id"] == run_id)
    assert item["counters"]["outputs"].endswith("5 takes · 3 passed") or "takes" in item["counters"]["outputs"]
    assert item["tags"] == ["Module 8"] and item["counters"]["thumb_sha"]


def test_video_without_references_skips_keyframes(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        takes_per_shot=1, end_title="")}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("shotlist"))
    act(client, run_id, "approve", {"step": "shotlist"})
    detail = wait_for(client, run_id, at_gate("takes"))
    assert next(s for s in detail["steps"] if s["key"] == "keyframes")["status"] == "skipped"
    for take in [a for a in detail["artifacts"] if a["kind"] == "take"]:
        act(client, run_id, "decide", {"artifact_id": take["id"], "verdict": "keep"})
    act(client, run_id, "approve", {"step": "takes"})
    detail = wait_for(client, run_id, run_status("completed", "failed"), timeout=120)
    final = next(a for a in detail["artifacts"] if a["kind"] == "final")
    assert 7.0 < final["metrics"]["duration"] < 8.0 and final["metrics"]["end_card"] is False


def test_shotlist_redraft_and_validation(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief()}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("shotlist"))
    result = act(client, run_id, "redraft_shots", {"note": "Make shot 2 a drone shot."})
    shotlist = next(s for s in result["detail"]["steps"] if s["key"] == "shotlist")
    assert shotlist["data"]["drafts"] == 2 and shotlist["data"]["feedback"] == "Make shot 2 a drone shot."
    bad = act(client, run_id, "update_shots", {"shots": [{"title": "x", "prompt": "short"}]}, expect=409)
    assert "prompt" in bad["detail"]
    assert act(client, run_id, "redraft_shots", {"note": ""}, expect=409)["detail"].startswith("Say what")


def test_sora_busy_waits_for_a_slot_and_failed_take_can_retry(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        shots=1, takes_per_shot=1)}).json()["run"]["id"]
    detail = wait_for(client, run_id, at_gate("shotlist"))
    shots = next(s for s in detail["steps"] if s["key"] == "shotlist")["data"]["shots"]
    shots[0]["prompt"] = "[busy] [fail] The car glides through the city at night."
    act(client, run_id, "approve", {"step": "shotlist", "shots": shots})
    detail = wait_for(client, run_id, at_gate("takes"))
    codes = [e["code"] for e in detail["events"]]
    assert "slot_wait" in codes
    take = next(a for a in detail["artifacts"] if a["kind"] == "take")
    assert take["status"] == "blocked" and take["error_code"] == "content_filter"
    act(client, run_id, "retry_artifact", {"artifact_id": take["id"], "prompt": "The car glides through the city."})
    detail = wait_for(client, run_id, lambda d: next(a for a in d["artifacts"] if a["id"] == take["id"])["status"]
                      == "ready")
    assert next(e for e in reversed(detail["events"]) if e["code"] == "retry")["message"].endswith(
        "with a reworded prompt.")


def test_cancel_and_reopen(client: TestClient) -> None:
    run_id = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        takes_per_shot=1, end_title="")}).json()["run"]["id"]
    wait_for(client, run_id, at_gate("shotlist"))
    act(client, run_id, "approve", {"step": "shotlist"})
    detail = wait_for(client, run_id, at_gate("takes"))
    for take in [a for a in detail["artifacts"] if a["kind"] == "take"]:
        act(client, run_id, "decide", {"artifact_id": take["id"], "verdict": "keep"})
    act(client, run_id, "approve", {"step": "takes"})
    wait_for(client, run_id, run_status("completed"), timeout=120)
    act(client, run_id, "reopen", {"step": "takes"})
    detail = wait_for(client, run_id, run_status("waiting"))
    assert [s["status"] for s in detail["steps"] if s["key"] in ("assemble", "provenance")] == ["pending", "pending"]
    assert next(a for a in detail["artifacts"] if a["kind"] == "final")["status"] == "superseded"
    act(client, run_id, "cancel")
    assert client.get(f"/api/design/runs/{run_id}").json()["run"]["status"] == "canceled"
    assert act(client, run_id, "regenerate_take", {"shot_id": "s1"}, expect=409)["detail"].startswith("This run")


def test_unconfigured_install_refuses_new_runs(make_client: Any) -> None:
    client = make_client(provider_mode="live")
    status = client.get("/api/design/status").json()
    assert not any(p["ready"] for p in status["pipelines"])
    response = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief()})
    assert response.status_code == 409 and "Settings" in response.json()["detail"]


def test_bad_brief_is_a_readable_409(client: TestClient) -> None:
    response = client.post("/api/design/runs", json={"pipeline": "video", "brief": {"brief": "too short"}})
    assert response.status_code == 409 and response.json()["detail"].startswith("brief:")
    missing = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        [{"sha": "0" * 64, "role": "subject"}])})
    assert missing.status_code == 409 and "missing" in missing.json()["detail"]


def test_prompt_helper_off_sends_each_line_as_written(client: TestClient) -> None:
    lines = ["Rain streaks down a cafe window at night; the camera slowly racks focus to neon signs outside.",
             "A barista turns, smiles and slides a steaming cup across the counter toward the camera."]
    created = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        brief="\n".join(lines) + "\n\n", shots=5, takes_per_shot=1, prompt_helper=False, end_title="",
        must_not_include="")})
    assert created.status_code == 201, created.text
    run = created.json()["run"]
    assert run["brief"]["shots"] == 2, "shots follow the number of lines"
    detail = wait_for(client, run["id"], at_gate("shotlist"))
    titles = {s["key"]: (s["title"], s["gate"]) for s in detail["steps"]}
    assert titles["shotlist"] == ("Your lines → shots", True) and titles["keyframes"][1] is False
    shots = next(s for s in detail["steps"] if s["key"] == "shotlist")["data"]["shots"]
    assert [s["prompt"] for s in shots] == lines and {s["mode"] for s in shots} == {"t2v"}
    assert any("no text model" in e["message"] for e in detail["events"])
    assert act(client, run["id"], "redraft_shots", {"note": "more drama"}, expect=409)["detail"].startswith("The prompt helper is off")
    act(client, run["id"], "approve", {"step": "shotlist"})
    detail = wait_for(client, run["id"], at_gate("takes"))
    takes = [a for a in detail["artifacts"] if a["kind"] == "take"]
    assert [t["prompt"] for t in takes] == lines, "Sora gets the line exactly"
    assert next(s for s in detail["steps"] if s["key"] == "keyframes")["status"] == "skipped"


def test_prompt_helper_off_validates_lines(client: TestClient) -> None:
    response = client.post("/api/design/runs", json={"pipeline": "video", "brief": video_brief(
        brief="A long enough first line for a shot.\nshort", prompt_helper=False)})
    assert response.status_code == 409 and "Line 2 is too short" in response.json()["detail"]
