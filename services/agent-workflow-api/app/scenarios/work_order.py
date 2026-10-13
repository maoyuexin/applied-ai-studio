"""Sequential pipeline: monitor -> diagnose -> plan -> field check (plain code) -> dispatch."""

from __future__ import annotations

import re
from typing import Annotated, Any

from agent_framework import AgentExecutorResponse, Executor, Message, WorkflowContext, handler, tool
from agent_framework.orchestrations import SequentialBuilder

from ..specs import ActorSpec, AgentSpec, BusinessSpec, EdgeSpec, NodeSpec, Scenario, StageSpec, TaskSpec, ToolSpec
from .common import final_message, first_result, last_json_block, messages_from, outbox_actions

# Neutral ids for the Studio's packaged sensor windows (their real ids describe the answer).
WINDOWS = {
    "W-1104": "S5_F4_real_warning",
    "W-0708": "S6_drift_false_alarm",
    "W-0215": "S1_clean_training_week",
    "W-0611": "S7_borderline_watch",
}
ASSET = "APU-1 air compressor"

MONITOR = """You are the monitoring agent for compressor APU-1. Call score_machine once for the sensor window in the request.
Report in at most 5 lines: the peak score and when, the policy route at the peak (work order / watch / no action), how many hours alerted, and the two strongest drivers in plain words.
Only use numbers from the tool. The score ranks unusual behaviour; it is not a diagnosis."""

DIAGNOSE = """You are the diagnosis agent. Read the monitor's report. If the route is "work order" or "watch", call search_procedures at most twice: once for how to inspect the likely problem suggested by the drivers, once for how to isolate the equipment safely before work (lockout/tagout).
List the 2-4 most useful passages with their citation copied exactly from the tool, and one line on what each means for the technician.
If the route is "no action", say no procedure search is needed."""

PLANNER = """You are the maintenance planner. Using the monitor and diagnosis messages, draft the work order as ONE JSON code block with exactly these keys:
{"work_order_needed": true|false, "asset": str, "priority": "high"|"medium"|"low", "problem": str, "evidence": [str], "steps": [str], "safety": [str], "citations": [str], "due_within_hours": int}
Use "high" priority and due_within_hours <= 24 when the route is "work order"; "medium" for "watch". If the route is "no action", set work_order_needed to false and leave the lists empty.
Copy citations exactly as the diagnosis agent quoted them. Do not add anything after the JSON block."""

DISPATCHER = """You are the dispatcher. The last message is an automatic field check written in plain code.
If the check PASSED and a work order is needed, call create_work_order once using the planner's JSON (a supervisor must approve). If the check FAILED, do not file anything; list what must be fixed. If no work order is needed, do not file anything.
Finish with one or two sentences for the shift supervisor that state exactly what the tool returned (filed, or rejected by the supervisor)."""

SCENARIO = Scenario(
    id="work-order",
    title="Machine Alert to Work Order",
    tagline="An assembly line of agents, with one step that is plain code",
    industry="Manufacturing",
    pattern="sequential",
    pattern_label="Sequential",
    summary=(
        "A compressor's sensor score jumps. Four agents work in a fixed order: monitor reads the "
        "anomaly model, diagnosis searches maintenance procedures, the planner drafts a work order, "
        "a plain-code check validates it, and the dispatcher files it after a supervisor approves."
    ),
    watch_for=[
        "The order of steps is fixed in advance: that is what makes it sequential.",
        "The field check is ordinary code. If a function can do the job, it does not need an agent.",
        "The check verifies that every citation came from the procedure search, not from memory.",
    ],
    agents=[
        AgentSpec("monitor", "Monitor", "Reads the anomaly score", "#7eaeb8", MONITOR, ["score_machine"], "sense"),
        AgentSpec("diagnose", "Diagnose", "Finds the right procedures", "#b48ead", DIAGNOSE, ["search_procedures"], "plan"),
        AgentSpec("planner", "Planner", "Drafts the work order", "#e8913c", PLANNER, [], "plan"),
        AgentSpec("dispatcher", "Dispatcher", "Files it once checked", "#a3be8c", DISPATCHER, ["create_work_order"], "act"),
    ],
    tools=[
        ToolSpec("score_machine", "Anomaly score", "sense", "model",
                 "Scores a week of compressor sensor data against the machine's own normal and applies the work-order policy.",
                 "Studio maintenance service: robust anomaly baseline on the UCI MetroPT-3 compressor data"),
        ToolSpec("search_procedures", "Procedure search", "sense", "lookup",
                 "Retrieves maintenance-procedure passages with citations.",
                 "Studio procedures service: retrieval over public maintenance and safety documents"),
        ToolSpec("create_work_order", "Create work order", "act", "action",
                 "Files the work order in the maintenance system. Needs a supervisor's approval.",
                 "Demo outbox only; no real maintenance system", approval=True),
    ],
    nodes=[
        NodeSpec("task", "Sensor alert", "input", "One week of readings from APU-1"),
        NodeSpec("field_check", "Field check", "code", "Plain code: required fields, priority rule, citations really retrieved"),
        NodeSpec("person", "Shift supervisor", "human", "Approves the work order"),
        NodeSpec("result", "Work order", "output", "Filed work order or 'no action'"),
    ],
    edges=[
        EdgeSpec("task", "monitor"),
        EdgeSpec("monitor", "diagnose"),
        EdgeSpec("diagnose", "planner"),
        EdgeSpec("planner", "field_check"),
        EdgeSpec("field_check", "dispatcher"),
        EdgeSpec("dispatcher", "person", "approval", "file?"),
        EdgeSpec("dispatcher", "result"),
    ],
    layout={
        "task": (80, 170), "monitor": (330, 170), "diagnose": (580, 170), "planner": (830, 170),
        "field_check": (830, 430), "dispatcher": (580, 430), "result": (310, 430), "person": (840, 640),
    },
    tasks=[
        TaskSpec("W-1104", "Score climbs 14 hours before a reported air leak",
                 f"Sensor alert for {ASSET}: review sensor window W-1104 and prepare maintenance work if it is needed.",
                 truth="This window ends in a documented air-leak failure; the score crossed the line about 14 hours earlier."),
        TaskSpec("W-0708", "High score on a busy but healthy week",
                 f"Sensor alert for {ASSET}: review sensor window W-0708 and prepare maintenance work if it is needed.",
                 truth="No documented failure: the machine was simply busier than in the training months (a false alarm caused by drift)."),
        TaskSpec("W-0215", "A quiet, normal week",
                 f"Sensor alert for {ASSET}: review sensor window W-0215 and prepare maintenance work if it is needed.",
                 truth="A clean week from the training months."),
        TaskSpec("W-0611", "Borderline: sits in the watch band",
                 f"Sensor alert for {ASSET}: review sensor window W-0611 and prepare maintenance work if it is needed.",
                 truth="No documented failure; the score stays in the watch band."),
    ],
    requires=["maintenance", "procedures"],
    data_note="Sensor data: UCI MetroPT-3 (CC BY 4.0). The Studio's maintenance model is a robust statistical baseline, not a classroom notebook model. Window labels are hidden from the agents.",
)

SAFETY_WORDS = re.compile(r"lock\s*-?\s*out|tag\s*-?\s*out|isolat|de-?energi|bleed|depressur", re.I)


def check_order(order: dict | None, retrieved: set[str]) -> list[dict]:
    if order is None:
        return [{"check": "Planner produced a JSON work order", "ok": False}]
    checks = [{"check": "Planner produced a JSON work order", "ok": True}]
    needed = order.get("work_order_needed")
    checks.append({"check": "States whether a work order is needed", "ok": isinstance(needed, bool)})
    if needed is not True:
        return checks
    citations = [str(c) for c in order.get("citations") or []]
    unknown = [c for c in citations if c not in retrieved]
    priority = order.get("priority")
    due = order.get("due_within_hours")
    checks += [
        {"check": "Asset named", "ok": bool(str(order.get("asset", "")).strip())},
        {"check": "Priority is high, medium or low", "ok": priority in {"high", "medium", "low"}},
        {"check": "High priority is due within 24 h", "ok": priority != "high" or (isinstance(due, (int, float)) and due <= 24)},
        {"check": "At least two work steps", "ok": len(order.get("steps") or []) >= 2},
        {"check": "Safety step isolates the machine (lockout/tagout)",
         "ok": any(SAFETY_WORDS.search(str(s)) for s in (order.get("safety") or []) + (order.get("steps") or []))},
        {"check": "At least one citation", "ok": bool(citations)},
        {"check": "Every citation came from the procedure search",
         "ok": bool(citations) and not unknown, "detail": ", ".join(unknown) if unknown else ""},
    ]
    return checks


class FieldCheck(Executor):
    """Deterministic validation between the planner and the dispatcher."""

    def __init__(self, recorder) -> None:  # type: ignore[no-untyped-def]
        super().__init__(id="field_check")
        self.recorder = recorder

    @handler
    async def check(self, response: AgentExecutorResponse, ctx: WorkflowContext[list[Message]]) -> None:
        conversation = list(response.full_conversation or [])
        order = last_json_block([response.agent_response.text or ""])
        retrieved: set[str] = set()
        for event in self.recorder.events:
            if event["type"] == "tool_result" and event.get("tool") == "search_procedures":
                for passage in (event.get("result") or {}).get("passages", []):
                    retrieved.add(passage.get("citation", ""))
        checks = check_order(order, retrieved)
        passed = all(c["ok"] for c in checks)
        self.recorder.code_step("field_check", "Field check", passed, checks)
        failed = [c["check"] for c in checks if not c["ok"]]
        note = "[Automatic field check - plain code, not an agent] " + (
            "PASSED: all required fields present and every citation was retrieved."
            if passed
            else "FAILED: " + "; ".join(failed)
        )
        conversation.append(Message("user", [note], author_name="field_check"))
        await ctx.send_message(conversation)


def build(ctx) -> Any:  # type: ignore[no-untyped-def]
    maintenance = ctx.service("maintenance")
    procedures = ctx.service("procedures")

    @tool
    async def score_machine(window_id: Annotated[str, "Sensor window id from the alert"]) -> dict:
        """Score one week of compressor sensor data and apply the work-order policy."""
        studio_id = WINDOWS.get(window_id.strip().upper())
        if studio_id is None:
            return {"error": f"Unknown window {window_id}"}
        response = await ctx.http.post(f"{maintenance}/api/maintenance/score", json={"window_id": studio_id})
        response.raise_for_status()
        s = response.json()
        return {
            "asset": ASSET,
            "window": f"{s['start']} to {s['end']}",
            "hours_with_data": s["hours_with_data"],
            "policy": "work order at a score of 6.0 or more; watch from 3.0",
            "peak_score": s["peak_score"],
            "peak_at": s["peak_at"],
            "median_score": s["median_score"],
            "route_at_peak": s["route_label"],
            "hours_at_work_order_level": s["alert_hours"],
            "hours_in_watch_band": s["watch_hours"],
            "first_alert_hour": s["first_alert_hour"],
            "drivers": [
                {"signal": d.get("display_name"), "reading": d.get("reading"), "normal": d.get("normal"),
                 "meaning": d.get("plain_direction")}
                for d in (s.get("drivers") or [])[:3]
            ],
            "note": s["score_note"],
        }

    @tool
    async def search_procedures(question: Annotated[str, "What the technician needs to know"]) -> dict:
        """Search maintenance procedures and return the best passages with citations."""
        response = await ctx.http.post(f"{procedures}/api/procedures/ask", json={"question": question[:400]})
        response.raise_for_status()
        r = response.json()
        return {
            "search_result": r.get("decision_label"),
            "passages": [
                {"citation": p["citation"], "source": p["source_title"], "score": round(p["score"], 2),
                 "text": " ".join(str(p.get("text", "")).split())[:420]}
                for p in r.get("passages", [])[:3]
            ],
            "note": "Similarity says the wording is close; a qualified person confirms it applies.",
        }

    @tool(approval_mode="always_require")
    def create_work_order(
        asset: Annotated[str, "Asset id"],
        priority: Annotated[str, "high, medium or low"],
        problem: Annotated[str, "One-line problem statement"],
        due_within_hours: Annotated[int, "Hours until the work is due"],
    ) -> str:
        """File the work order in the maintenance system. A supervisor must approve."""
        return ctx.file_action("create_work_order", asset=asset, priority=priority, problem=problem,
                               due_within_hours=due_within_hours)

    specs = {a.id: a for a in SCENARIO.agents}
    participants = [
        ctx.agent(specs["monitor"], [score_machine]),
        ctx.agent(specs["diagnose"], [search_procedures]),
        ctx.agent(specs["planner"]),
        FieldCheck(ctx.recorder),
        ctx.agent(specs["dispatcher"], [create_work_order]),
    ]
    agents = [p for p in participants if not isinstance(p, Executor)]
    return SequentialBuilder(participants=participants, intermediate_output_from=agents[:-1]).build()


def summarize(events: list[dict], outbox: list[dict]) -> dict:
    score = first_result(events, "score_machine") or {}
    order = last_json_block(messages_from(events, "planner"))
    check = next((e for e in events if e["type"] == "code_step"), None)
    return {
        "headline": "Work order filed" if outbox_actions(outbox, "create_work_order") else "No work order filed",
        "fields": [
            {"label": "Peak score", "value": f"{score.get('peak_score', '-')} ({score.get('route_at_peak', '-')})"},
            {"label": "Field check", "value": "-" if check is None else ("passed" if check["passed"] else "failed")},
            {"label": "Priority", "value": (order or {}).get("priority", "-")},
        ],
        "document": order,
        "final": final_message(events, "dispatcher"),
        "outbox": outbox,
    }


SCENARIO.business = BusinessSpec(
    question="A compressor is behaving unusually. Does it need a work order, and what should the technician do?",
    situation=(
        "A train's air compressor reports sensor readings all day. A score built from them flags unusual "
        "hours. Maintenance must decide whether to send a technician, and with which instructions."
    ),
    stakes=[
        "Miss a real fault and the train can fail in service.",
        "Raise needless work orders and technicians stop trusting the alerts.",
        "Every work order must follow the safety procedure.",
    ],
    decides="The shift supervisor approves every work order. A technician inspects the machine and decides the repair.",
    good=[
        "Every flagged week is reviewed the same way.",
        "Work orders cite the maintenance manuals and include the lockout step.",
        "Nothing is filed without the supervisor.",
    ],
    today=[
        "An engineer watches the anomaly dashboard.",
        "Looks up the right procedures in the manuals.",
        "Writes the work order and gets it signed.",
    ],
    with_agent=[
        "Four agents work in a fixed order, like an assembly line.",
        "A plain-code check catches missing fields and made-up citations.",
        "The supervisor approves or rejects the finished order.",
    ],
    actors=[
        ActorSpec("sensors", "Compressor sensors", "trigger", "One week of readings from the machine", ref="task"),
        ActorSpec("monitor", "Monitor", "agent", "Reads the anomaly score and says how serious it is", ref="monitor"),
        ActorSpec("diagnose", "Diagnose", "agent", "Finds the right procedures in the manuals", ref="diagnose"),
        ActorSpec("planner", "Planner", "agent", "Drafts the work order", ref="planner"),
        ActorSpec("check", "Field check", "code", "Fixed rules: required fields, a lockout step, real citations", ref="field_check"),
        ActorSpec("dispatcher", "Dispatcher", "agent", "Files the order once it is checked and approved", ref="dispatcher"),
        ActorSpec("supervisor", "Shift supervisor", "person", "Approves or rejects the work order", ref="person"),
    ],
    stages=[
        StageSpec("alert", "Sensor alert arrives", "sensors", "A week of compressor readings is sent for review.",
                  [{"type": "run_start"}], "alert", "The alert becomes the task message that starts the run."),
        StageSpec("score", "Score the machine", "monitor", "The monitor reads the anomaly score: how far this week is from the machine's own normal.",
                  [{"agent": "monitor"}], "machine", "Tool call score_machine: a statistical model in the maintenance service."),
        StageSpec("manual", "Find the procedures", "diagnose", "Diagnose decides the route and finds the inspection and lockout steps in the manuals.",
                  [{"agent": "diagnose"}], "manual", "Tool call search_procedures: search over maintenance manuals (retrieval)."),
        StageSpec("draft", "Draft the work order", "planner", "The planner writes the work order: priority, steps, safety and sources.",
                  [{"agent": "planner"}], "workorder", "The language model writes the order as structured data (JSON)."),
        StageSpec("check", "Check it with fixed rules", "check", "Plain code checks the order. No AI: the same rules every time.",
                  [{"type": "code_step"}], "fieldcheck", "A code step in the workflow, between two agents."),
        StageSpec("approve", "Supervisor approves", "supervisor", "The dispatcher asks to file the order; the supervisor approves or rejects it.",
                  [{"type": "tool_call", "tool": "create_work_order"}, {"type": "approval_request"}], "approval",
                  "Tool call create_work_order: an action, locked until a person approves.",
                  optional=True, skipped="Nothing to approve: no work order was needed."),
        StageSpec("file", "File it, or stand down", "dispatcher", "The dispatcher reports what was filed, or that no action was needed.",
                  [{"type": "message", "agent": "dispatcher", "last": True}], "note", "The last agent in the line writes the final message."),
    ],
)
SCENARIO.builder = build
SCENARIO.summarize = summarize
