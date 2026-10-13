"""Single agent with two look-up tools and one action that needs a person's approval."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool
from agent_framework.orchestrations import SequentialBuilder

from ..specs import ActorSpec, AgentSpec, BusinessSpec, EdgeSpec, NodeSpec, Scenario, StageSpec, TaskSpec, ToolSpec
from .common import final_message, first_result, outbox_actions

INSTRUCTIONS = """You are a card-alert agent at a bank. For the transaction in the request:
1. Look it up with get_transaction.
2. Score it with score_transaction. This is the bank's fraud model; its `decision` field already applies the bank's review policy (score at or above the threshold means review).
3. If the decision is "review", request a temporary hold with hold_card. A person must approve it, so give a one-sentence reason based on the model's top reasons.
4. If the decision is "normal", do not hold the card.
Finish with a short note for the fraud team (4 lines max): the decision, the score compared with the threshold, the top two reasons in plain words, and what a person should check next.
Rules: use only numbers returned by the tools; never say fraud is proven, because the score ranks risk; do not ask the user questions."""

SCENARIO = Scenario(
    id="card-alert",
    title="Card Alert",
    tagline="One agent, two look-up tools, one action that needs approval",
    industry="Banking",
    pattern="single",
    pattern_label="Single agent",
    summary=(
        "A card transaction arrives. The agent looks it up, asks the fraud model for a score, "
        "and decides whether to request a temporary hold. A person approves or rejects the hold."
    ),
    watch_for=[
        "The agent chooses which tool to call next; nobody scripted the order.",
        "The fraud model is a tool. The agent explains the score; it does not change it.",
        "The hold is only a request until a person approves it.",
    ],
    agents=[
        AgentSpec(
            id="card_alert_agent",
            label="Card Alert agent",
            role="Reviews the alert; may request a hold",
            color="#e8913c",
            instructions=INSTRUCTIONS,
            tools=["get_transaction", "score_transaction", "hold_card"],
            step="plan",
        )
    ],
    tools=[
        ToolSpec(
            id="get_transaction",
            label="Look up transaction",
            step="sense",
            kind="lookup",
            description="Returns merchant, amount, time and recent card activity.",
            source="Synthetic card transactions (Sparkov generator) served by the Studio fraud service",
        ),
        ToolSpec(
            id="score_transaction",
            label="Fraud model score",
            step="check",
            kind="model",
            description="Scores the transaction and applies the review cutoff; returns the top reasons.",
            source="Random forest fraud model in the Studio fraud service, with tree SHAP reasons",
        ),
        ToolSpec(
            id="hold_card",
            label="Hold card",
            step="act",
            kind="action",
            description="Places a temporary hold on the card. Needs a person's approval.",
            source="Demo outbox only; no real card system",
            approval=True,
        ),
    ],
    nodes=[
        NodeSpec(id="task", label="Card alert", kind="input", detail="One transaction to review"),
        NodeSpec(id="person", label="Fraud analyst", kind="human", detail="Approves or rejects the hold"),
        NodeSpec(id="result", label="Decision note", kind="output", detail="Hold request + note for the fraud team"),
    ],
    edges=[
        EdgeSpec("task", "card_alert_agent"),
        EdgeSpec("card_alert_agent", "person", kind="approval", label="hold?"),
        EdgeSpec("card_alert_agent", "result"),
    ],
    layout={"task": (110, 260), "card_alert_agent": (430, 260), "person": (760, 110), "result": (860, 330)},
    tasks=[
        TaskSpec(
            id="caught-fraud-2",
            label="$1,026 online purchase at 11:06 PM",
            prompt="New card alert: transaction 00d98f6d319ddee3b61bea07843952f1 on the card ending 0161. Review it and decide whether to hold the card.",
            truth="Labeled fraud in the data.",
        ),
        TaskSpec(
            id="reviewed-normal-1",
            label="$284 kids & pets purchase, 2:43 PM",
            prompt="New card alert: transaction 942bb9e03c995db22e4753be999d53ee on the card ending 0070. Review it and decide whether to hold the card.",
            truth="Labeled normal in the data: the model's review flag is a false alarm.",
        ),
        TaskSpec(
            id="missed-fraud-1",
            label="$6.45 online purchase at 10:45 PM",
            prompt="New card alert: transaction 90920633247d8a3750c394e7488e38fc on the card ending 0064. Review it and decide whether to hold the card.",
            truth="Labeled fraud in the data: the score sits just below the cutoff, so the model misses it.",
        ),
        TaskSpec(
            id="normal-transaction-1",
            label="$62 gym purchase, 8:22 PM",
            prompt="New card alert: transaction 8575b675c7fcbb5ee0e7281555903f53 on the card ending 0263. Review it and decide whether to hold the card.",
            truth="Labeled normal in the data.",
        ),
    ],
    requires=["fraud"],
    data_note="Transactions are synthetic (Sparkov generator). Labels are hidden from the agent and shown only after the run.",
)

HIDDEN_FIELDS = {"known_outcome", "scenario_id", "scenario_label", "learning_note"}

BUSINESS = BusinessSpec(
    question="A card purchase looks unusual. Hold the card, or let it through?",
    situation=(
        "The bank's card system flags a purchase. Someone has to decide quickly whether to put a "
        "temporary hold on the card, and record why."
    ),
    stakes=[
        "Miss real fraud and the bank and the cardholder lose money.",
        "Hold a good customer's card and they are stuck at the checkout.",
        "Every decision has to be explainable later.",
    ],
    decides="A fraud analyst. The assistant may only request a hold; a person approves it.",
    good=[
        "Every alert gets the same checks, in seconds.",
        "A hold happens only when the fraud model says review and a person agrees.",
        "A short note explains each decision in plain words.",
    ],
    today=[
        "An analyst opens the purchase and the card's recent activity.",
        "Checks the fraud model's score on another screen.",
        "Decides, places the hold and writes the note by hand.",
    ],
    with_agent=[
        "The assistant gathers the facts and the score.",
        "It drafts the hold request and the note.",
        "The analyst reviews, then approves or rejects.",
    ],
    actors=[
        ActorSpec("alert", "Card system", "trigger", "Flags a purchase for review", ref="task"),
        ActorSpec("assistant", "AI assistant", "agent", "Gathers the facts, reads the score, drafts the request and the note", ref="card_alert_agent"),
        ActorSpec("records", "Card records", "system", "Purchase details and recent card activity", ref="get_transaction"),
        ActorSpec("model", "Fraud model", "model", "Scores how unusual a purchase is; learned from past transactions", ref="score_transaction"),
        ActorSpec("analyst", "Fraud analyst", "person", "Approves or rejects the hold", ref="person"),
    ],
    stages=[
        StageSpec("alert", "Alert arrives", "alert", "The card system flags one purchase for review.",
                  [{"type": "run_start"}], "alert", "The alert becomes the task message that starts the run."),
        StageSpec("lookup", "Look up the purchase", "records", "The assistant pulls the purchase details and the card's recent activity.",
                  [{"type": "tool_call", "tool": "get_transaction"}], "receipt", "Tool call get_transaction: a read-only look-up."),
        StageSpec("score", "Score the risk", "model", "The bank's fraud model scores the purchase and compares it with the review cutoff.",
                  [{"type": "tool_call", "tool": "score_transaction"}], "risk", "Tool call score_transaction: a trained machine-learning model used as a tool."),
        StageSpec("request", "Request a hold", "assistant", "The model said review, so the assistant asks for a temporary hold and gives a reason.",
                  [{"type": "tool_call", "tool": "hold_card"}], "request", "Tool call hold_card: an action, so it is locked until a person approves.",
                  optional=True, skipped="No hold requested: the model said normal, so the purchase went through."),
        StageSpec("approve", "Analyst decides", "analyst", "A person reads the request and approves or rejects the hold.",
                  [{"type": "approval_request"}], "approval", "Approval request: the run waits until a person answers.",
                  optional=True, skipped="Nobody was asked: there was no hold to approve."),
        StageSpec("note", "Write the note", "assistant", "The assistant writes a short note for the fraud team.",
                  [{"type": "message", "agent": "card_alert_agent", "last": True}], "note", "The language model writes the final message."),
    ],
)
SCENARIO.business = BUSINESS


def build(ctx) -> Any:  # type: ignore[no-untyped-def]
    base = ctx.service("fraud")
    cache: dict[str, dict] = {}

    async def find(transaction_id: str) -> dict | None:
        if not cache:
            response = await ctx.http.get(f"{base}/api/fraud/samples")
            response.raise_for_status()
            for sample in response.json():
                cache[sample["transaction"]["transaction_id"]] = sample
        return cache.get(transaction_id.strip())

    @tool
    async def get_transaction(
        transaction_id: Annotated[str, "Transaction id from the alert"],
    ) -> dict:
        """Look up a card transaction: merchant, amount, time, location and recent card activity."""
        sample = await find(transaction_id)
        if sample is None:
            return {"error": f"No transaction {transaction_id}"}
        t = sample["transaction"]
        return {
            "transaction_id": t["transaction_id"],
            "card_last4": sample["card_last4"],
            "merchant": sample["merchant"],
            "location": sample["location"],
            "amount_usd": t["amount"],
            "category": t["category"].replace("_", " "),
            "occurred_at": t["occurred_at"],
            "amount_vs_card_average": f"{t['amount_ratio_to_card_mean']:.1f}x",
            "card_transactions_last_24h": t["card_transactions_24h"],
            "distance_from_home_km": round(t["distance_from_home_km"]),
        }

    @tool
    async def score_transaction(
        transaction_id: Annotated[str, "Transaction id to score"],
    ) -> dict:
        """Score a transaction with the bank's fraud model and apply the review cutoff."""
        sample = await find(transaction_id)
        if sample is None:
            return {"error": f"No transaction {transaction_id}"}
        response = await ctx.http.post(f"{base}/api/fraud/score", json=sample["transaction"])
        response.raise_for_status()
        s = response.json()
        reasons = sorted(
            s["explanation"]["contributions"], key=lambda c: abs(c["contribution"]), reverse=True
        )[:4]
        return {
            "model": s["model_name"],
            "fraud_score": round(s["fraud_score"], 3),
            "review_threshold": round(s["threshold"], 3),
            "decision": s["decision"],
            "top_reasons": [
                {
                    "feature": r["label"],
                    "value": r["value"],
                    "pushes": "toward review" if r["direction"] == "toward_review" else "toward normal",
                    "weight": round(r["contribution"], 3),
                }
                for r in reasons
            ],
            "note": s["score_note"],
        }

    @tool(approval_mode="always_require")
    def hold_card(
        card_last4: Annotated[str, "Last four digits of the card"],
        transaction_id: Annotated[str, "Transaction that triggered the hold"],
        reason: Annotated[str, "One-sentence reason for the fraud analyst"],
    ) -> str:
        """Place a temporary hold on the card. A person must approve this action."""
        return ctx.file_action("hold_card", card_last4=card_last4, transaction_id=transaction_id, reason=reason)

    spec = SCENARIO.agents[0]
    agent = ctx.agent(spec, tools=[get_transaction, score_transaction, hold_card])
    return SequentialBuilder(participants=[agent]).build()


def summarize(events: list[dict], outbox: list[dict]) -> dict:
    score = first_result(events, "score_transaction") or {}
    return {
        "headline": "Hold requested" if any(e["type"] == "approval_request" for e in events) else "No hold",
        "fields": [
            {"label": "Model decision", "value": score.get("decision", "-")},
            {"label": "Score / cutoff", "value": f"{score.get('fraud_score', '-')} / {score.get('review_threshold', '-')}"},
            {"label": "Hold placed", "value": "Yes" if outbox_actions(outbox, "hold_card") else "No"},
        ],
        "final": final_message(events, "card_alert_agent"),
        "outbox": outbox,
    }


SCENARIO.builder = build
SCENARIO.summarize = summarize
