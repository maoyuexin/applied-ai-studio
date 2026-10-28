from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.pipelines.alerts import allowed_numbers, compose_draft, numbers_in, unknown_numbers, watch_hits
from tests.helpers import act, at_gate, run_status, wait_for

LANGUAGES = [{"code": "en", "name": "English", "disclosure": "AI-assisted"},
             {"code": "es", "name": "Spanish", "disclosure": "Asistido por IA"}]
FACTS = "River gauge at Main St: 43.1 ft at 4:45 am Sun Aug 27.\nMajor flood stage: 43 ft.\nCity line: 311."
BRIEF = {
    "brief": "Can models turn gauge readings into correct public alerts?",
    "moments": [{"name": "Major flooding", "facts": FACTS, "question": "Is my street flooded?"},
                {"name": "Rising", "facts": "River gauge: 38.6 ft at 10:00 pm, up from 27.0 ft at 9:00 pm."}],
    "languages": LANGUAGES, "models": ["text-mini", "text-pro"], "tries": 2, "max_chars": 160,
    "watch_terms": ["shelter", "closed"],
}


def test_numbers_and_watch_terms() -> None:
    assert numbers_in("43,1 pies a las 4:45; 1,000 casas") == [43.1, 4, 45, 1000]
    allowed = allowed_numbers(FACTS)
    assert unknown_numbers("43.1 ft (43 ft major), 04:45 on 8/27, call 311", allowed) == []
    assert unknown_numbers("22:00 · 38,6 pies", allowed_numbers("38.6 ft at 10:00 pm")) == [], "24-hour clock"
    assert unknown_numbers("Shelter at 99 Main, 44 ft by noon", allowed) == ["99", "44"]
    assert unknown_numbers("45.7 ft", allowed_numbers("Level 45.67 ft")) == [], "rounding to one decimal is fine"
    assert watch_hits("Shelters open; roads closed", FACTS, ["shelter", "closed"]) == ["shelter", "closed"]
    assert watch_hits("Roads closed", "Main St is closed.", ["closed"]) == []


def test_prompt_shape() -> None:
    text = compose_draft({"facts": FACTS, "question": ""}, LANGUAGES, 160)
    assert text.startswith("FACTS (the only facts you may use):\nRiver gauge")
    assert '- es = Spanish (disclosure: "Asistido por IA")' in text
    assert text.endswith('Reply as JSON: {"alert": {"en": "...", "es": "..."}}')


def start(client: TestClient, **overrides: Any) -> str:
    response = client.post("/api/design/runs", json={"pipeline": "alerts", "brief": {**BRIEF, **overrides},
                                                     "title": "Storm alerts"})
    assert response.status_code == 201, response.text
    return response.json()["run"]["id"]


def test_alerts_run_end_to_end(client: TestClient) -> None:
    run_id = start(client)
    detail = wait_for(client, run_id, at_gate("setup"))
    setup = next(s for s in detail["steps"] if s["key"] == "setup")["data"]
    assert setup["calls"] == 16 and len(setup["prompts"]) == 2 and "2. ANSWER" in setup["prompts"][0]
    act(client, run_id, "approve", {"step": "setup"})

    detail = wait_for(client, run_id, at_gate("desk"))
    drafts = [a for a in detail["artifacts"] if a["kind"] == "draft"]
    checks = [a for a in detail["artifacts"] if a["kind"] == "check"]
    assert len(drafts) == 8 and len(checks) == 8 and {a["deployment"] for a in drafts} == {"text-mini", "text-pro"}
    report = next(s for s in detail["steps"] if s["key"] == "check")["data"]["report"]
    assert report["counts"] == {"drafts": 8, "blocked": 0, "failed": 0, "expected": 8}
    mini, pro = report["models"]["text-mini"], report["models"]["text-pro"]
    assert pro["flagged"] == 0 and pro["messages"] == 12, "2 moments × 2 tries, alert in 2 languages + 1 answer each"
    assert mini["flagged"] == 8, "the invented shelter, in both languages of all 4 alerts; answers are clean"
    assert mini["checks"]["numbers"] == 8 and mini["checks"]["watch"] == 8 and mini["checks"]["reviewer"] == 8
    assert mini["checks"]["disclosure"] == 4, "the second language drops the disclosure"
    assert report["languages"]["es"] == {"messages": 12, "flagged": 4}
    bad = next(d for d in drafts if d["deployment"] == "text-mini" and d["params"]["moment"] == 0)
    good = next(d for d in drafts if d["deployment"] == "text-pro" and d["params"]["moment"] == 0)
    assert bad["data"]["flagged"] is True and {c["key"] for c in bad["checks"]} >= {"numbers", "watch", "disclosure"}
    assert good["checks"] == [{"key": "clean", "label": "Every message passed every check", "state": "ok", "basis": ""}]
    assert good["data"]["back"]["es"]["alert"].startswith("[en] River")

    assert act(client, run_id, "sign", {"draft_id": good["id"], "verdict": "maybe"}, expect=409)
    assert act(client, run_id, "sign", {"draft_id": good["id"], "verdict": "edit", "edits": {}},
               expect=409)["detail"].startswith("Change at least one message")
    act(client, run_id, "sign", {"draft_id": good["id"], "verdict": "approve"})
    act(client, run_id, "sign", {"draft_id": bad["id"], "verdict": "approve", "note": "missed it"})
    other = next(d for d in drafts if d["deployment"] == "text-mini" and d["params"]["moment"] == 1)
    act(client, run_id, "sign", {"draft_id": other["id"], "verdict": "edit",
                                 "edits": {"en": {"alert": "River at 38.6 ft and rising. AI-assisted"}}})
    act(client, run_id, "approve", {"step": "desk"})

    detail = wait_for(client, run_id, run_status("completed", "failed"))
    assert detail["run"]["status"] == "completed"
    report_art = next(a for a in detail["artifacts"] if a["kind"] == "report")
    states = {c["key"]: c for c in report_art["checks"]}
    assert states["signed"]["label"].startswith("Signed: 2 approved · 1 edited · 0 rejected · 5 not signed")
    assert states["approved_flagged"]["state"] == "bad"
    document = client.get(f"/api/design/media/{report_art['media_sha']}").json()
    assert len(document["drafts"]) == 8 and document["report"]["signed"]["approved_flagged"] == 1
    table = next(a for a in detail["artifacts"] if a["kind"] == "table")
    rows = client.get(f"/api/design/media/{table['media_sha']}").text.strip().splitlines()
    assert rows[0].startswith("moment,model,try,language,part,message") and len(rows) == 1 + 24
    assert detail["run"]["counters"]["outputs"] == "2 moments · 8 drafts · 4 flagged · 3 signed"
    assert act(client, run_id, "sign", {"draft_id": good["id"], "verdict": "reject"}, expect=409)

    bundle = client.get(f"/api/design/runs/{run_id}/export")
    client.delete(f"/api/design/runs/{run_id}")
    imported = client.post("/api/design/runs/import", files={"file": ("run.zip", bundle.content, "application/zip")})
    assert imported.status_code == 201, imported.text


def test_desk_waits_for_a_person_and_can_be_left_open(client: TestClient) -> None:
    run_id = start(client, models=["text-pro"], tries=1)
    wait_for(client, run_id, at_gate("setup"))
    act(client, run_id, "approve", {"step": "setup"})
    detail = wait_for(client, run_id, at_gate("desk"))
    assert detail["run"]["status"] == "waiting"
    act(client, run_id, "approve", {"step": "desk"})
    detail = wait_for(client, run_id, run_status("completed"))
    states = {c["key"]: c["state"] for c in next(a for a in detail["artifacts"] if a["kind"] == "report")["checks"]}
    assert states["signed"] == "warn" and states["approved_flagged"] == "ok"


@pytest.mark.parametrize(("patch", "message"), [
    ({"languages": [LANGUAGES[0], LANGUAGES[0]]}, "Each language needs its own code"),
    ({"models": []}, "models"),
    ({"moments": []}, "moments"),
])
def test_brief_validation(client: TestClient, patch: dict[str, Any], message: str) -> None:
    response = client.post("/api/design/runs", json={"pipeline": "alerts", "brief": {**BRIEF, **patch}})
    assert response.status_code == 409 and message in response.json()["detail"]
