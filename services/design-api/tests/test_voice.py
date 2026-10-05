from typing import Any

from fastapi.testclient import TestClient

from app.pipelines.voice import listen_back
from tests.helpers import act, at_gate, run_status, wait_for

SPEAKERS = [{"name": "Host A", "voice": "en-US-Harper:MAI-Voice-2.1-Flash", "style": "cheerful"},
            {"name": "Host B", "voice": "en-US-Ethan:MAI-Voice-2.1-Flash", "style": ""}]


def voice_brief(**overrides: Any) -> dict[str, Any]:
    brief = {"format": "two-hosts", "brief": "Welcome students to Module 8: AI in media and creative work.",
             "target_seconds": 30, "locale": "en-US", "speakers": SPEAKERS, "pause_ms": 300, "disclosure": True}
    brief.update(overrides)
    return brief


def test_voice_run_with_listen_back_and_rerecord(client: TestClient) -> None:
    voices = client.get("/api/design/voices?locale=en-US").json()
    assert {v["name"] for v in voices} >= {SPEAKERS[0]["voice"], SPEAKERS[1]["voice"]}
    run_id = client.post("/api/design/runs", json={"pipeline": "voice", "brief": voice_brief()}).json()["run"]["id"]
    detail = wait_for(client, run_id, at_gate("script"))
    lines = next(s for s in detail["steps"] if s["key"] == "script")["data"]["lines"]
    assert [line["speaker"] for line in lines[:2]] == ["Host A", "Host B"]
    lines[-1]["text"] = "These voices were generated with AI."
    act(client, run_id, "approve", {"step": "script", "lines": lines})

    detail = wait_for(client, run_id, at_gate("lines"))
    recorded = [a for a in detail["artifacts"] if a["kind"] == "line"]
    assert len(recorded) == len(lines) and all(a["verdict"] == "keep" for a in recorded)
    first = recorded[0]
    assert first["params"]["voice"] == SPEAKERS[0]["voice"] and first["params"]["style"] == "cheerful"
    assert first["metrics"]["word_errors"] == 0 and first["checks"][0]["state"] == "ok"
    act(client, run_id, "regenerate_line", {"line_id": "l1", "text": "Welcome to Module 8!"})
    detail = wait_for(client, run_id, at_gate("lines"))
    takes = [a for a in detail["artifacts"] if a["grp"] == "l1"]
    assert [a["verdict"] for a in takes] == [None, "keep"], "a re-record replaces its parent as the kept take"
    assert next(s for s in detail["steps"] if s["key"] == "script")["data"]["lines"][0]["text"] == "Welcome to Module 8!"
    act(client, run_id, "approve", {"step": "lines"})
    detail = wait_for(client, run_id, run_status("completed", "failed"))
    assert detail["run"]["status"] == "completed", detail["run"]["error"]
    mix = next(a for a in detail["artifacts"] if a["kind"] == "final")
    assert mix["media_type"] == "audio/mpeg" and mix["metrics"]["lines"] == len(lines)
    assert next(c for c in mix["checks"] if c["key"] == "disclosure")["state"] == "ok"
    assert mix["data"]["transcript"][0] == {"speaker": "Host A", "text": "Welcome to Module 8!"}


def test_voice_rejects_unknown_voice_and_duplicate_names(client: TestClient) -> None:
    bad_voice = client.post("/api/design/runs", json={"pipeline": "voice", "brief": voice_brief(
        speakers=[{"name": "A", "voice": "en-US-Nobody:MAI-Voice-2.1-Flash"}])})
    assert bad_voice.status_code == 409 and "Unknown voice" in bad_voice.json()["detail"]
    twins = client.post("/api/design/runs", json={"pipeline": "voice", "brief": voice_brief(
        speakers=[SPEAKERS[0], {**SPEAKERS[1], "name": "Host A"}])})
    assert twins.status_code == 409 and "different" in twins.json()["detail"]


def test_listen_back_word_compare() -> None:
    assert listen_back("Welcome to Module 8.", "Welcome to module eight")["word_errors"] == 0
    result = listen_back("The SOLENNE GT drives the quiet.", "The Solon GT drives the quiet.")
    assert result["word_errors"] == 1 and result["diffs"] == [{"script": "solenne", "heard": "solon"}]
    assert listen_back("One two three.", "")["word_errors"] == 3
