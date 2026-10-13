"""Group chat: a chair picks who speaks; merchandiser, copywriter and brand reviewer refine a promotion."""

from __future__ import annotations

import re
from typing import Annotated, Any

from agent_framework import tool
from agent_framework.orchestrations import GroupChatBuilder

from ..specs import AgentSpec, EdgeSpec, NodeSpec, Scenario, TaskSpec, ToolSpec
from .common import final_message, last_result, messages_from, outbox_actions

PLANNING_WEEK = "2011-11-28"
OFFER_PERCENT = 15
OFFER_END = re.compile(r"\b(4 dec(ember)?|dec(ember)?\.? 4(th)?)\b", re.I)

CHAIR = """You chair a short planning meeting for the online gift shop's homepage promotion. You choose who speaks next.
Order of work: the merchandiser picks products from data first; then the copywriter drafts the banner; then the brand reviewer checks every claim.
If the reviewer reports problems, give the copywriter one more turn, then the reviewer again. End the meeting once the brand reviewer has submitted the brief for approval."""

MERCHANDISER = f"""You are the merchandiser. Call list_products, then forecast_demand for up to four seasonal candidates.
Pick TWO products for the homepage promotion in the week of {PLANNING_WEEK}: strong expected demand and a good fit for winter gifting.
Reply with a short table (product, price, forecast units for the week with its range, expected sales in dollars) and one line on why. Use only tool numbers; say the forecast is a range, not a promise.
Do not write marketing copy; that is the copywriter's job."""

COPYWRITER = f"""You are the copywriter. The merchandiser's product picks come from the shop's forecast tool: use them as given and never ask for more data.
Write the homepage banner for those two products: a headline (8 words max), two short lines of body copy, the offer exactly as "{OFFER_PERCENT}% off", and a call to action.
Write bold, exciting sales copy: you like strong superlatives and a sense of urgency, because they sell. Reply with the banner only.
If the brand reviewer flags phrases, rewrite only those and resend the full banner."""

REVIEWER = f"""You are the brand and claims reviewer. Our brand voice is warm and calm, never pushy.
Call check_claims on the copywriter's latest full banner text (not the merchandiser's table). Also judge the tone yourself: exclamation marks and pressure words are off-brand.
If check_claims finds issues or the tone is pushy, list the problems briefly and ask the copywriter to fix them. Do not fix the copy yourself.
If the copy passes both, call submit_brief with the two products, the headline, the body copy and the offer; the marketing manager must approve. After it returns, reply "SUBMITTED" and the outcome."""

SCENARIO = Scenario(
    id="holiday-promo",
    title="Holiday Promotion",
    tagline="A meeting of agents with a chair who decides who speaks next",
    industry="Retail and marketing",
    pattern="group_chat",
    pattern_label="Group chat",
    summary=(
        "Plan next week's homepage promotion. A chair runs the meeting: the merchandiser picks products "
        "from the demand forecast, the copywriter drafts the banner, and the brand reviewer checks every "
        "claim with a rules tool. The brief goes to the marketing manager for approval."
    ),
    watch_for=[
        "Everyone sees the whole conversation; the chair picks the next speaker each round.",
        "Roles are set up to disagree: the copywriter is told to write bold sales copy, the reviewer enforces brand rules.",
        "More rounds mean more model calls. Watch the counters grow.",
    ],
    agents=[
        AgentSpec("chair", "Chair", "Runs the meeting and picks who speaks next", "#d8dee9", CHAIR, [], "plan", kind="chair"),
        AgentSpec("merchandiser", "Merchandiser", "Picks products from demand data", "#7eaeb8", MERCHANDISER, ["list_products", "forecast_demand"], "plan"),
        AgentSpec("copywriter", "Copywriter", "Drafts the banner", "#e8913c", COPYWRITER, [], "act"),
        AgentSpec("brand_reviewer", "Brand reviewer", "Checks claims and submits the brief", "#b48ead", REVIEWER, ["check_claims", "submit_brief"], "check"),
    ],
    tools=[
        ToolSpec("list_products", "Product list", "sense", "lookup",
                 "Lists the products the shop can feature, with prices.",
                 "UCI Online Retail II products (2009-2011, CC BY 4.0) in the Studio forecast service"),
        ToolSpec("forecast_demand", "Demand forecast", "sense", "model",
                 "Forecast units for the planning week with a range.",
                 "Studio forecast service: eight-week moving average with an interval"),
        ToolSpec("check_claims", "Claims check", "check", "check",
                 "Brand rules: no unsupported superlatives or urgency claims, the offer must match the brief and show its end date.",
                 "Plain code written for this demo"),
        ToolSpec("submit_brief", "Submit brief", "act", "action",
                 "Sends the brief to the marketing manager. Needs approval.",
                 "Demo outbox only; no real web site", approval=True),
    ],
    nodes=[
        NodeSpec("task", "Promotion request", "input", f"Homepage slot, week of {PLANNING_WEEK}, {OFFER_PERCENT}% off"),
        NodeSpec("person", "Marketing manager", "human", "Approves the brief"),
        NodeSpec("result", "Promotion brief", "output", "Products, banner copy, offer"),
    ],
    edges=[
        EdgeSpec("task", "chair"),
        EdgeSpec("chair", "merchandiser", "chair"),
        EdgeSpec("chair", "copywriter", "chair"),
        EdgeSpec("chair", "brand_reviewer", "chair"),
        EdgeSpec("brand_reviewer", "person", "approval", "approve?"),
        EdgeSpec("chair", "result"),
    ],
    layout={
        "task": (110, 120), "chair": (520, 300), "merchandiser": (250, 300), "copywriter": (790, 300),
        "brand_reviewer": (520, 470), "person": (820, 490), "result": (1060, 120),
    },
    tasks=[
        TaskSpec(
            "homepage-week-48",
            "Homepage promotion, week of 28 Nov 2011",
            f"Plan the homepage promotion for our online gift shop for the week of {PLANNING_WEEK}. "
            f"The offer is {OFFER_PERCENT}% off the two featured products, from 28 Nov to 4 Dec 2011. "
            "Pick the products from our demand data, "
            "write the banner, and make sure every claim is supported before it goes to the marketing manager.",
            truth="Historical data: the week of 28 Nov 2011 is the last week in the dataset.",
        )
    ],
    requires=["forecast"],
    data_note="Products and sales history: UCI Online Retail II (2009-2011, CC BY 4.0). The claims check is plain code.",
)

SUPERLATIVES = re.compile(
    r"\b(best[- ]?sell\w*|best|#1|number one|top[- ]selling|perfect|guaranteed|lowest|cheapest|unbeatable|must[- ]have|ultimate)\b",
    re.I,
)
URGENCY = re.compile(
    r"\b(selling out|sell out|limited stock|only \d+ left|last chance|while (stocks|supplies) last|ends tonight|hurry"
    r"|this week only|today only|don'?t miss( out)?|now or never|act fast|going fast)\b",
    re.I,
)
INTERNAL = re.compile(r"\b(forecast\w*|demand data|units?)\b", re.I)
PERCENT = re.compile(r"(\d{1,2})\s?%")
SHIPPING = re.compile(r"\bfree (shipping|delivery)\b", re.I)


def claims_issues(text: str, offer_percent: int) -> list[dict]:
    issues: list[dict] = []
    for match in SUPERLATIVES.finditer(text):
        issues.append({"phrase": match.group(0), "rule": "Superlative without evidence",
                       "fix": "Describe the product instead of ranking it"})
    for match in URGENCY.finditer(text):
        issues.append({"phrase": match.group(0), "rule": "Urgency or stock claim we cannot verify",
                       "fix": "Remove it or give a real end date"})
    for match in PERCENT.finditer(text):
        if int(match.group(1)) != offer_percent:
            issues.append({"phrase": match.group(0), "rule": f"Offer must be {offer_percent}% off",
                           "fix": f"Use {offer_percent}% off"})
    for match in SHIPPING.finditer(text):
        issues.append({"phrase": match.group(0), "rule": "Free shipping is not part of this offer",
                       "fix": "Remove it"})
    for match in INTERNAL.finditer(text):
        issues.append({"phrase": match.group(0), "rule": "Internal planning data does not belong in customer copy",
                       "fix": "Remove it"})
    if f"{offer_percent}%" not in text.replace(" %", "%"):
        issues.append({"phrase": "(missing)", "rule": f"Banner must state the offer: {offer_percent}% off",
                       "fix": f"Add '{offer_percent}% off'"})
    if not OFFER_END.search(text):
        issues.append({"phrase": "(missing)", "rule": "Offer terms must show the end date (4 Dec)",
                       "fix": "Add 'Ends 4 Dec' near the offer"})
    return issues


def build(ctx) -> Any:  # type: ignore[no-untyped-def]
    forecast = ctx.service("forecast")

    @tool
    async def list_products() -> list[dict]:
        """List the products the shop can feature, with unit prices."""
        response = await ctx.http.get(f"{forecast}/api/forecast/products")
        response.raise_for_status()
        return [
            {"product_id": p["product_id"], "product": p["product"].strip().title(), "unit_price": p["unit_price"]}
            for p in response.json()
        ]

    @tool
    async def forecast_demand(product_id: Annotated[str, "Product id from list_products"]) -> dict:
        """Forecast units for the planning week, with a low-high range."""
        response = await ctx.http.post(f"{forecast}/api/forecast/plan", json={"product_id": product_id.strip()})
        if response.status_code >= 400:
            return {"error": f"No forecast for {product_id}"}
        plan = response.json()
        week = next((w for w in plan["weekly"] if w["week"] == PLANNING_WEEK), plan["weekly"][-1])
        return {
            "product": plan["product"].strip().title(),
            "unit_price": plan["unit_price"],
            "week": week["week"],
            "forecast_units": round(week["point"]),
            "range_units": [round(week["low"]), round(week["high"])],
            "expected_sales_usd": round(week["point"] * plan["unit_price"]),
            "method": "Mean of the last eight weeks, with a range; a starting point, not a promise.",
        }

    @tool
    def check_claims(banner_text: Annotated[str, "The full banner text to check"]) -> dict:
        """Check the banner for unsupported claims and for an offer that differs from the brief."""
        issues = claims_issues(banner_text, OFFER_PERCENT)
        return {"passed": not issues, "issues": issues}

    @tool(approval_mode="always_require")
    def submit_brief(
        products: Annotated[list[str], "The two featured products"],
        headline: Annotated[str, "Banner headline"],
        body: Annotated[str, "Banner body copy"],
        offer: Annotated[str, "The offer"],
    ) -> str:
        """Send the promotion brief to the marketing manager. A person must approve."""
        return ctx.file_action("submit_brief", products=products, headline=headline, body=body, offer=offer)

    specs = {a.id: a for a in SCENARIO.agents}
    merch = ctx.agent(specs["merchandiser"], [list_products, forecast_demand])
    copy = ctx.agent(specs["copywriter"])
    reviewer = ctx.agent(specs["brand_reviewer"], [check_claims, submit_brief])
    chair = ctx.agent(specs["chair"])

    def done(conversation) -> bool:  # type: ignore[no-untyped-def]
        return any(m.author_name == "brand_reviewer" and "SUBMITTED" in (m.text or "") for m in conversation)

    return GroupChatBuilder(
        participants=[merch, copy, reviewer],
        orchestrator_agent=chair,
        termination_condition=done,
        max_rounds=10,
        intermediate_output_from=[merch, copy, reviewer],
    ).build()


def summarize(events: list[dict], outbox: list[dict]) -> dict:
    checks = [e.get("result") for e in events if e["type"] == "tool_result" and e.get("tool") == "check_claims"]
    flagged = sum(len((c or {}).get("issues", [])) for c in checks if isinstance(c, dict))
    brief = outbox_actions(outbox, "submit_brief")
    rounds = sum(1 for e in events if e["type"] == "speaker")
    return {
        "headline": "Brief approved" if brief else "Brief not submitted",
        "fields": [
            {"label": "Speaking turns", "value": str(rounds)},
            {"label": "Claims checks", "value": f"{len(checks)} ({flagged} issues flagged)"},
            {"label": "Last check", "value": "-" if not checks else ("passed" if (checks[-1] or {}).get("passed") else "issues")},
        ],
        "document": brief[-1] if brief else None,
        "final": final_message(events, "brand_reviewer") or final_message(events),
        "copy": (messages_from(events, "copywriter") or [""])[-1],
        "products": last_result(events, "list_products"),
        "outbox": outbox,
    }


SCENARIO.builder = build
SCENARIO.summarize = summarize
