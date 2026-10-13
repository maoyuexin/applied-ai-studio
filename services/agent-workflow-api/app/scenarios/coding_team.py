"""Handoff team: product owner -> developer <-> tester -> reviewer, tests run in a hosted sandbox."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from agent_framework.orchestrations import HandoffBuilder

from ..specs import ActorSpec, AgentSpec, BusinessSpec, EdgeSpec, NodeSpec, Scenario, StageSpec, TaskSpec, ToolSpec
from .common import final_message, last_code_block, messages_from, outbox_actions

TICKET = """Ticket SHIP-142 from the e-commerce team.
Our checkout needs a Python function shipping_cost(weight_lb, zone, express=False) that returns the parcel shipping price in dollars.
- Zone 1 costs $5.00, zone 2 $7.50 and zone 3 $10.00 for the first pound.
- Each additional pound, or part of a pound, adds $1.25 in zones 1 and 2, and $2.00 in zone 3.
- Express shipping doubles the price.
- Parcels heavier than 70 lb cannot ship as parcels, and the weight must be greater than zero: raise ValueError in those cases. Unknown zones also raise ValueError.
- Return the price rounded to cents."""

ACCEPTANCE_TESTS = [
    {"case": 1, "call": "shipping_cost(1, 1)", "expected": 5.0},
    {"case": 2, "call": "shipping_cost(0.4, 2)", "expected": 7.5},
    {"case": 3, "call": "shipping_cost(2, 1)", "expected": 6.25},
    {"case": 4, "call": "shipping_cost(2.1, 1)", "expected": 7.5},
    {"case": 5, "call": "shipping_cost(10, 3)", "expected": 28.0},
    {"case": 6, "call": "shipping_cost(3, 2, express=True)", "expected": 20.0},
    {"case": 7, "call": "shipping_cost(70, 3)", "expected": 148.0},
    {"case": 8, "call": "shipping_cost(70.5, 1)", "expected": "ValueError"},
    {"case": 9, "call": "shipping_cost(0, 1)", "expected": "ValueError"},
    {"case": 10, "call": "shipping_cost(5, 4)", "expected": "ValueError"},
]

TEAM_RULE = """
Team rule: the others see only the text you write, never your tool results. Write your full result in your reply first, then hand off."""

PRODUCT_OWNER = """You are the product owner. Turn the ticket into a short spec for the developer: the function signature, the rules as numbered bullets, and three example calls with expected results. Do not write code.
Then hand off to the developer.""" + TEAM_RULE

DEVELOPER = """You are the developer. Write ONE Python function that implements the spec, in a single ```python code block with a short docstring. No tests, no prints, no explanation longer than one sentence.
If the tester or reviewer reported problems, fix exactly those and send the whole corrected function again.
Then hand off to the tester.""" + TEAM_RULE

TESTER = """You are the tester. Call get_acceptance_tests to get the official cases (the developer has not seen them).
Use the Python tool to run the developer's latest function against every case: a case whose expected value is "ValueError" passes only if ValueError is raised; numeric cases pass if the result equals the expected value.
Then write a compact table in your reply (case, call, expected, got, pass/fail) and a final line "RESULT: X/Y passed".
If anything failed, hand off to the developer and name the failing cases. If everything passed, hand off to the reviewer.""" + TEAM_RULE

REVIEWER = """You are the code reviewer. Read the developer's latest function and the tester's result.
If all tests passed and the code is clear, call merge_change with a one-line summary; a person must approve the merge. After the tool returns, reply with "MERGED" if it was approved, or "NOT MERGED" and the reason if it was rejected.
If you find a real problem, hand off to the developer with one concrete change request instead. Do not request cosmetic changes.""" + TEAM_RULE

SCENARIO = Scenario(
    id="coding-team",
    title="Coding Team",
    tagline="Agents pass the task to each other, like a small software team",
    industry="Software",
    pattern="handoff",
    pattern_label="Handoff",
    summary=(
        "A ticket asks for a shipping-cost function. The product owner writes the spec, the developer "
        "writes code, the tester runs hidden acceptance tests in a hosted sandbox and can send the work "
        "back, and the reviewer asks a person to approve the merge."
    ),
    watch_for=[
        "Each handoff moves ownership of the task; nobody is in the middle directing traffic.",
        "The tester's cases are hidden from the developer, so the maker cannot grade its own work.",
        "If a test fails, the task goes back to the developer: that loop is the point of the pattern.",
    ],
    agents=[
        AgentSpec("product_owner", "Product owner", "Turns the ticket into a spec", "#7eaeb8", PRODUCT_OWNER, [], "plan"),
        AgentSpec("developer", "Developer", "Writes the function", "#e8913c", DEVELOPER, [], "act"),
        AgentSpec("tester", "Tester", "Runs the hidden acceptance tests", "#a3be8c", TESTER, ["get_acceptance_tests", "run_python"], "check"),
        AgentSpec("reviewer", "Reviewer", "Reviews code, asks to merge", "#b48ead", REVIEWER, ["merge_change"], "check"),
    ],
    tools=[
        ToolSpec("get_acceptance_tests", "Acceptance tests", "sense", "lookup",
                 "Returns the official test cases. Only the tester has this tool.",
                 "Ten fixed cases written with the ticket"),
        ToolSpec("run_python", "Python sandbox", "check", "code",
                 "Runs Python in a hosted, isolated sandbox; nothing runs on this computer.",
                 "Hosted code interpreter in Microsoft Foundry"),
        ToolSpec("merge_change", "Merge change", "act", "action",
                 "Merges the change into the main branch. Needs a person's approval.",
                 "Demo outbox only; no real repository", approval=True),
    ],
    nodes=[
        NodeSpec("task", "Ticket SHIP-142", "input", "Shipping-cost function for checkout"),
        NodeSpec("person", "Engineering lead", "human", "Approves the merge"),
        NodeSpec("result", "Merged code", "output", "Function + test results"),
    ],
    edges=[
        EdgeSpec("task", "product_owner"),
        EdgeSpec("product_owner", "developer", "handoff"),
        EdgeSpec("developer", "tester", "handoff"),
        EdgeSpec("tester", "developer", "handoff", "fix"),
        EdgeSpec("tester", "reviewer", "handoff"),
        EdgeSpec("reviewer", "developer", "handoff", "change"),
        EdgeSpec("reviewer", "person", "approval", "merge?"),
        EdgeSpec("reviewer", "result"),
    ],
    layout={
        "task": (80, 300), "product_owner": (280, 300), "developer": (530, 140), "tester": (780, 300),
        "reviewer": (530, 460), "person": (800, 520), "result": (1080, 400),
    },
    tasks=[
        TaskSpec("ship-142", "Shipping-cost function (ticket SHIP-142)", TICKET,
                 truth="Ten hidden acceptance cases; edge cases are partial pounds, the 70 lb limit and unknown zones."),
    ],
    requires=[],
    data_note="The ticket and test cases were written for this demo. Code runs only in the hosted sandbox.",
)


def build(ctx) -> Any:  # type: ignore[no-untyped-def]
    @tool
    def get_acceptance_tests() -> list[dict]:
        """Return the official acceptance test cases for ticket SHIP-142."""
        return ACCEPTANCE_TESTS

    @tool(approval_mode="always_require")
    def merge_change(summary: Annotated[str, "One-line summary of the change"]) -> str:
        """Merge the change into the main branch. A person must approve."""
        return ctx.file_action("merge_change", summary=summary)

    specs = {a.id: a for a in SCENARIO.agents}
    persist = {"require_per_service_call_history_persistence": True}
    po = ctx.agent(specs["product_owner"], **persist)
    dev = ctx.agent(specs["developer"], **persist)
    tester = ctx.agent(
        specs["tester"], [get_acceptance_tests, ctx.client.get_code_interpreter_tool()], **persist
    )
    reviewer = ctx.agent(specs["reviewer"], [merge_change], **persist)

    def done(conversation) -> bool:  # type: ignore[no-untyped-def]
        return any(
            m.author_name == "reviewer" and "MERGED" in (m.text or "") for m in conversation
        )

    return (
        HandoffBuilder(name="coding_team", participants=[po, dev, tester, reviewer], termination_condition=done)
        .with_start_agent(po)
        .add_handoff(po, [dev])
        .add_handoff(dev, [tester])
        .add_handoff(tester, [dev, reviewer])
        .add_handoff(reviewer, [dev])
        .with_autonomous_mode(turn_limits={"product_owner": 2, "developer": 4, "tester": 4, "reviewer": 3})
        .build()
    )


def summarize(events: list[dict], outbox: list[dict]) -> dict:
    code = last_code_block(messages_from(events, "developer"))
    tester_lines = [line for text in messages_from(events, "tester") for line in text.splitlines() if "RESULT:" in line]
    test_rounds = sum(1 for e in events if e["type"] == "tool_call" and e.get("tool") == "run_python")
    sent_back = sum(1 for e in events if e["type"] == "handoff" and e.get("source") in {"tester", "reviewer"} and e.get("target") == "developer")
    return {
        "headline": "Merged" if outbox_actions(outbox, "merge_change") else "Not merged",
        "fields": [
            {"label": "Test results", "value": " -> ".join(l.split("RESULT:")[-1].strip(" *") for l in tester_lines) or "-"},
            {"label": "Sandbox runs", "value": str(test_rounds)},
            {"label": "Sent back to developer", "value": str(sent_back)},
        ],
        "code": code,
        "final": final_message(events, "reviewer"),
        "outbox": outbox,
    }


SCENARIO.business = BusinessSpec(
    question="Can a team of AI agents deliver tested code that a person is willing to merge?",
    situation=(
        "An online shop needs a function that prices parcel shipping. A ticket describes it. The work "
        "passes through a product owner, a developer, a tester and a reviewer, as in a software team."
    ),
    stakes=[
        "A wrong price costs money on every order.",
        "Edge cases break quietly: partial pounds, the weight limit, unknown zones.",
        "Code goes live only after a person approves the merge.",
    ],
    decides="The engineering lead approves the merge. People wrote the acceptance tests before the agents started.",
    good=[
        "Every hidden acceptance test passes.",
        "Work goes back to the developer when a test fails.",
        "The reviewer explains the change before asking to merge.",
    ],
    today=[
        "A product owner writes the ticket.",
        "A developer codes it; a tester runs the tests and sends bugs back.",
        "A reviewer reads the code; a lead approves the merge.",
    ],
    with_agent=[
        "Four agents play the same roles and hand the work to each other.",
        "The tests run as code in a sandbox; the tester reports the results.",
        "The lead still approves the merge.",
    ],
    actors=[
        ActorSpec("ticket", "Ticket", "trigger", "A feature request from the shop team", ref="task"),
        ActorSpec("product_owner", "Product owner", "agent", "Turns the ticket into a clear spec", ref="product_owner"),
        ActorSpec("developer", "Developer", "agent", "Writes the code", ref="developer"),
        ActorSpec("tester", "Tester", "agent", "Runs the hidden tests and reports", ref="tester"),
        ActorSpec("reviewer", "Reviewer", "agent", "Reads the code and asks to merge", ref="reviewer"),
        ActorSpec("lead", "Engineering lead", "person", "Approves or rejects the merge", ref="person"),
    ],
    stages=[
        StageSpec("ticket", "Ticket arrives", "ticket", "The shop team asks for a shipping-cost function.",
                  [{"type": "run_start"}], "alert", "The ticket becomes the task message that starts the run."),
        StageSpec("spec", "Write the spec", "product_owner", "The product owner turns the ticket into rules and examples.",
                  [{"type": "message", "agent": "product_owner"}], "ticket", "The language model writes the spec; no tools."),
        StageSpec("code", "Write the code", "developer", "The product owner hands the work to the developer, who writes the function.",
                  [{"type": "handoff", "target": "developer"}, {"type": "message", "agent": "developer"}], "code",
                  "Handoff to developer; the language model writes Python."),
        StageSpec("test", "Test it", "tester", "The tester runs ten hidden acceptance tests and reports every result.",
                  [{"type": "handoff", "target": "tester"}, {"type": "tool_call", "tool": "get_acceptance_tests"},
                   {"type": "tool_call", "tool": "run_python"}, {"type": "message", "agent": "tester"}], "tests",
                  "Tool calls get_acceptance_tests and run_python: the tests run as code in a hosted sandbox."),
        StageSpec("review", "Review the code", "reviewer", "The reviewer reads the code and the test results.",
                  [{"type": "handoff", "target": "reviewer"}, {"type": "message", "agent": "reviewer", "nth": 1}], "review",
                  "Handoff to reviewer; the language model reviews."),
        StageSpec("approve", "Lead approves the merge", "lead", "The reviewer asks to merge; the engineering lead decides.",
                  [{"type": "tool_call", "tool": "merge_change"}, {"type": "approval_request"}], "approval",
                  "Tool call merge_change: an action, locked until a person approves.",
                  optional=True, skipped="No merge was requested."),
        StageSpec("merged", "Merged", "reviewer", "The reviewer confirms the outcome.",
                  [{"type": "message", "agent": "reviewer", "last": True}], "note", "The last agent to hold the task writes the final message.",
                  optional=True, skipped="The reviewer did not confirm a merge."),
    ],
)
SCENARIO.builder = build
SCENARIO.summarize = summarize
