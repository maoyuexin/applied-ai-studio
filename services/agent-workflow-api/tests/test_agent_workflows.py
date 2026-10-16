from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import RECORDINGS_DIR
from app.recorder import Recorder
from app.scenarios import SCENARIOS
from app.scenarios.holiday_promo import claims_issues
from app.scenarios.work_order import check_order
from app.specs import stage_of_events
from scripts.export_specs import render


def make_recorder(scenario_id: str = "card-alert") -> Recorder:
    scenario = SCENARIOS[scenario_id]
    return Recorder(scenario, scenario.tasks[0], mode="test", model="test-model")


def update(agent: str, *contents):  # type: ignore[no-untyped-def]
    return NS(type="intermediate", executor_id=agent, data=NS(author_name=agent, contents=list(contents)))


def test_every_scenario_validates_and_exports() -> None:
    for scenario in SCENARIOS.values():
        scenario.validate()
    specs = json.loads(render())
    assert [s["id"] for s in specs] == list(SCENARIOS)
    assert all("builder" not in s for s in specs)


def test_streamed_function_arguments_become_one_tool_call() -> None:
    rec = make_recorder()
    agent = "card_alert_agent"
    rec.consume(NS(type="executor_invoked", executor_id=agent, data=[]))
    rec.consume(update(agent, NS(type="text", text="Checking.")))
    for part in ['{"transaction_id":', '"abc"}']:
        rec.consume(update(agent, NS(type="function_call", name="get_transaction", call_id="c1", arguments=part)))
    rec.consume(update(agent, NS(type="usage", usage_details={"input_token_count": 10, "output_token_count": 5})))
    rec.consume(update(agent, NS(type="function_result", call_id="c1", result='{"amount_usd": 1}', exception=None)))
    kinds = [e["type"] for e in rec.events]
    assert kinds == ["agent_start", "message", "tool_call", "tool_result"]
    call = rec.events[2]
    assert call["args"] == {"transaction_id": "abc"} and call["step"] == "sense"
    assert rec.events[3]["result"] == {"amount_usd": 1}
    assert rec.stats["tool_calls"] == 1 and rec.stats["input_tokens"] == 10


def test_handoff_calls_are_hidden_and_handoff_event_recorded() -> None:
    rec = make_recorder("coding-team")
    rec.consume(NS(type="executor_invoked", executor_id="developer", data=NS(should_respond=True)))
    rec.consume(update("developer", NS(type="function_call", name="handoff_to_tester", call_id="h1", arguments="{}")))
    rec.consume(update("developer", NS(type="function_result", call_id="h1", result="ok", exception=None)))
    rec.consume(NS(type="handoff_sent", executor_id=None, data=NS(source="developer", target="tester")))
    assert [e["type"] for e in rec.events] == ["agent_start", "handoff"]
    assert rec.stats["tool_calls"] == 0 and rec.stats["handoffs"] == 1


def test_broadcast_invocations_do_not_change_the_active_agent() -> None:
    rec = make_recorder("coding-team")
    rec.consume(NS(type="executor_invoked", executor_id="tester", data=NS(should_respond=False)))
    assert rec.events == []


def test_code_interpreter_result_before_code_still_records_code() -> None:
    rec = make_recorder("coding-team")
    rec.consume(update("tester", NS(type="code_interpreter_tool_result", call_id="ci", outputs=[])))
    rec.consume(update("tester", NS(type="code_interpreter_tool_call", call_id="ci", inputs=[NS(text="print(1)")])))
    rec.consume(update("tester", NS(type="text", text="RESULT: 1/1 passed")))
    rec.flush_all()
    call = next(e for e in rec.events if e["type"] == "tool_call")
    assert call["tool"] == "run_python" and call["args"]["code"] == "print(1)"


def test_approval_request_is_recorded_with_owner() -> None:
    rec = make_recorder()
    agent = "card_alert_agent"
    rec.consume(update(agent, NS(type="function_call", name="hold_card", call_id="c9", arguments='{"card_last4":"0161"}')))
    request = NS(type="function_approval_request", function_call=NS(name="hold_card", call_id="c9", arguments='{"card_last4":"0161"}'))
    rec.consume(NS(type="request_info", executor_id=None, request_id="r1", data=request))
    approval = rec.events[-1]
    assert approval["type"] == "approval_request" and approval["agent"] == agent
    assert approval["args"] == {"card_last4": "0161"}


def test_work_order_check_requires_retrieved_citations_and_lockout() -> None:
    order = {
        "work_order_needed": True, "asset": "APU-1", "priority": "high", "problem": "leak",
        "evidence": [], "steps": ["inspect", "repair"], "safety": ["Apply lockout/tagout"],
        "citations": ["Doc p. 1"], "due_within_hours": 24,
    }
    assert all(c["ok"] for c in check_order(order, {"Doc p. 1"}))
    failed = {c["check"] for c in check_order({**order, "safety": [], "steps": ["a", "b"]}, {"Doc p. 2"}) if not c["ok"]}
    assert "Every citation came from the procedure search" in failed
    assert "Safety step isolates the machine (lockout/tagout)" in failed
    assert check_order(None, set())[0]["ok"] is False
    assert all(c["ok"] for c in check_order({"work_order_needed": False}, set()))


def test_claims_rules_flag_superlatives_wrong_offer_and_missing_end_date() -> None:
    issues = claims_issues("The best gift! 20% off, selling out fast", 15)
    rules = {i["rule"] for i in issues}
    assert "Superlative without evidence" in rules
    assert "Offer must be 15% off" in rules
    assert "Offer terms must show the end date (4 Dec)" in rules
    assert claims_issues("Cosy gifts. 15% off until 4 Dec. Shop now.", 15) == []


def test_every_recording_maps_onto_its_business_stages() -> None:
    for path in sorted(RECORDINGS_DIR.glob("*/*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        business = SCENARIOS[run["scenario"]].business
        assert business is not None, run["scenario"]
        stages = stage_of_events(business, run["events"])
        reached = {business.stages[i].id for i in stages if i >= 0}
        required = {stage.id for stage in business.stages if not stage.optional}
        assert required <= reached, (path.name, required - reached)
        # Only the trial finder loops back (it searches again after reading trials).
        if run["scenario"] != "trial-finder":
            assert stages == sorted(stages), path.name
    missed = json.loads((RECORDINGS_DIR / "card-alert" / "missed-fraud-1--1.json").read_text(encoding="utf-8"))
    business = SCENARIOS["card-alert"].business
    assert business is not None
    reached = {business.stages[i].id for i in stage_of_events(business, missed["events"]) if i >= 0}
    assert {"request", "approve"}.isdisjoint(reached)


def test_card_alert_tasks_use_pinned_transactions() -> None:
    from app.scenarios.card_alert import TRANSACTIONS

    for task in SCENARIOS["card-alert"].tasks:
        transaction_id = task.prompt.split("transaction ")[1].split()[0]
        record = TRANSACTIONS[transaction_id]
        assert record["transaction"]["transaction_id"] == transaction_id
        assert f"card ending {record['card_last4']}" in task.prompt


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_api_lists_scenarios_and_rejects_unsafe_paths(client: TestClient) -> None:
    response = client.get("/api/agent-workflows/scenarios")
    assert response.status_code == 200
    assert {s["id"] for s in response.json()} == set(SCENARIOS)
    assert client.get("/api/agent-workflows/recordings/recordings/card-alert/..%2F..%2Fsecret.json").status_code == 404
    assert client.get("/api/agent-workflows/recordings/elsewhere/card-alert/a.json").status_code == 404


def test_api_rejects_unknown_scenario_and_task(client: TestClient) -> None:
    if not main.settings.live_ready:
        pytest.skip("live settings not configured")
    assert client.post("/api/agent-workflows/runs", json={"scenario": "nope", "task": "x"}).status_code == 404
    assert client.post("/api/agent-workflows/runs", json={"scenario": "card-alert", "task": "x"}).status_code == 404
