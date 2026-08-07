from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OrderDecision


ALGORITHM_PROFILES: dict[str, dict[str, Any]] = {
    "address_validation": {
        "title": "Postal and service-area rule engine",
        "category": "Deterministic rule system",
        "implementation_status": "Executable synthetic implementation",
        "purpose": "Reject malformed or unsupported destinations before payment and fulfillment work begins.",
        "algorithm": "An ordered rule set checks required fields, postal-code structure, region support, and carrier service coverage. The first failing rule returns a reason code.",
        "why_fit": "Published postal and service-area policies are explicit and stable. Learning historical approvals would make a known rule less transparent.",
        "output": "Deliverable or not deliverable, with the failed rule and correction guidance.",
        "training_required": False,
        "training_approach": "No model training. Policy owners version rule tables and effective dates.",
        "training_data": "A curated validation fixture set containing valid, invalid, boundary, and previously misrouted addresses.",
        "target_definition": "Expected deliverability and the exact policy reason for every fixture.",
        "split_strategy": "Not applicable. Maintain separate authoring, regression, and production-monitoring fixture sets.",
        "preprocessing": [
            "Normalize whitespace and casing.",
            "Standardize region abbreviations.",
            "Parse postal code without changing the submitted source value.",
        ],
        "features": [
            {"name": "Postal code", "kind": "categorical", "source": "Checkout address", "role": "Match supported postal formats and service areas."},
            {"name": "Region", "kind": "categorical", "source": "Checkout address", "role": "Select the jurisdiction and carrier rule table."},
            {"name": "Address structure", "kind": "derived", "source": "Checkout address", "role": "Verify required street and locality components."},
            {"name": "Carrier service map", "kind": "reference", "source": "Versioned policy table", "role": "Confirm that at least one allowed carrier serves the destination."},
        ],
        "metrics": [
            {"name": "Invalid-address escape rate", "target": "< 0.5% on regression fixtures", "why": "Measures bad destinations allowed into fulfillment."},
            {"name": "False rejection rate", "target": "< 1% on confirmed deliverable fixtures", "why": "Protects conversion and customer effort."},
            {"name": "Decision coverage", "target": "100% with a reason code", "why": "Every checkout requires an explainable result."},
            {"name": "P95 latency", "target": "< 50 ms", "why": "Validation sits directly in checkout."},
        ],
        "testing": [
            "Unit-test every rule and boundary value.",
            "Replay known delivery failures as regression fixtures.",
            "Mutation-test missing fields and malformed postal codes.",
            "Verify each rejection maps to customer-safe correction guidance.",
        ],
        "monitoring": [
            "Unknown-region and no-service reason-code rates.",
            "Customer correction and checkout-abandonment rates.",
            "Carrier returns caused by addresses that passed validation.",
        ],
        "limitations": [
            "A structurally valid address may still be fraudulent or inaccessible.",
            "Service maps must be refreshed when carrier coverage changes.",
        ],
    },
    "payment_screening": {
        "title": "Payment fraud risk classifier",
        "category": "Supervised binary classification",
        "implementation_status": "Proposed production design; demo uses a deterministic synthetic scorer",
        "purpose": "Estimate fraud probability and route each payment to approve, review, or decline without delaying every customer.",
        "algorithm": "Gradient-boosted decision trees over tabular transaction, account, device, and velocity features, followed by probability calibration.",
        "why_fit": "Fraud depends on nonlinear interactions and changes as confirmed outcomes accumulate. Tree ensembles handle mixed tabular features and support evidence summaries.",
        "output": "Calibrated probability that the payment will become confirmed fraud or a chargeback.",
        "training_required": True,
        "training_approach": "Train on historical orders only after their fraud outcome is mature. Weight recent examples and tune thresholds against review capacity and false-positive cost.",
        "training_data": "At least 12-24 months of permission-cleared orders joined to confirmed fraud, chargeback, refund, and legitimate-delivery outcomes.",
        "target_definition": "1 for confirmed fraud or fraud-related chargeback within the label window; 0 for a matured legitimate order. Analyst decisions alone are not ground truth.",
        "split_strategy": "Time-ordered 70/15/15 train, validation, and test split. Keep all transactions from one account in one split and reserve the newest period for final testing.",
        "preprocessing": [
            "Create velocity features using only events available before checkout.",
            "Bucket rare categorical values and preserve an unknown category.",
            "Fit encoders and calibration only on training data.",
            "Exclude refunds, chargebacks, and review outcomes created after the decision time.",
        ],
        "features": [
            {"name": "Order amount", "kind": "numeric", "source": "Current order", "role": "Captures financial exposure and deviation from normal account behavior."},
            {"name": "Account age", "kind": "numeric", "source": "Customer profile", "role": "Separates established history from newly created accounts."},
            {"name": "Device consistency", "kind": "categorical", "source": "Checkout telemetry", "role": "Flags a device or browser that differs from recent successful orders."},
            {"name": "Address distance", "kind": "numeric", "source": "Account and order addresses", "role": "Measures divergence from prior trusted destinations."},
            {"name": "Payment velocity", "kind": "numeric", "source": "Recent payment attempts", "role": "Counts attempts, cards, and failures inside bounded time windows."},
            {"name": "Prior outcomes", "kind": "aggregated", "source": "Matured order history", "role": "Summarizes confirmed fraud and legitimate-delivery history without post-decision leakage."},
        ],
        "metrics": [
            {"name": "Recall at review budget", "target": ">= 85% of synthetic fraud at <= 3% good-order review rate", "why": "Links detection quality to analyst capacity."},
            {"name": "Precision-recall AUC", "target": "Improve over amount-only baseline", "why": "Fraud is rare; ROC AUC can hide poor positive-class performance."},
            {"name": "Brier score / calibration", "target": "<= 0.12 on temporal holdout", "why": "Thresholds require probabilities that mean what they say."},
            {"name": "False-positive rate", "target": "No increase versus approved baseline", "why": "Protects legitimate customers from friction."},
            {"name": "Review hours and chargeback value", "target": "Reduce review effort without increasing chargebacks", "why": "Pairs technical quality with business impact."},
        ],
        "testing": [
            "Evaluate once on the untouched newest-period holdout.",
            "Slice results by geography, account age, order value, device type, and customer tenure.",
            "Backtest policy thresholds against historical analyst capacity.",
            "Run in shadow mode before recommendations affect routing.",
            "Test missing-feature, stale-feature, and scorer-unavailable fallbacks.",
        ],
        "monitoring": [
            "Feature drift and unknown-category rates.",
            "Probability calibration by week and customer slice.",
            "Review rate, analyst overrides, fraud recall, and chargeback value.",
            "Latency, scorer failures, and fallback-rule usage.",
        ],
        "limitations": [
            "Confirmed fraud labels arrive late and remain incomplete.",
            "Historical analyst actions can encode bias and must not become labels by default.",
            "The current demo score is deterministic and is not a trained production model.",
        ],
    },
    "fulfillment_allocation": {
        "title": "Warehouse and carrier allocation optimizer",
        "category": "Constrained operations-research optimization",
        "implementation_status": "Proposed production design; demo uses a deterministic feasible-allocation heuristic",
        "purpose": "Choose a warehouse and carrier plan that can fulfill the order at acceptable cost while meeting capacity and delivery commitments.",
        "algorithm": "Mixed-integer linear programming minimizes freight, split-shipment, and lateness penalties subject to inventory, capacity, compatibility, and service-window constraints.",
        "why_fit": "The objective and constraints are explicit. A solver can guarantee constraint handling and explain why no feasible allocation exists.",
        "output": "One feasible warehouse/carrier assignment, its objective value, and any binding constraints.",
        "training_required": False,
        "training_approach": "No model training. Operations teams configure objective weights, hard constraints, and approved carrier/service combinations.",
        "training_data": "Benchmark instances built from historical order shapes, inventory snapshots, carrier rates, capacity, and actual service outcomes.",
        "target_definition": "A feasible allocation with lower cost and lateness penalty than the current heuristic while never violating hard constraints.",
        "split_strategy": "Separate tuning scenarios from an untouched benchmark suite covering normal, peak, outage, and infeasible conditions.",
        "preprocessing": [
            "Snapshot inventory and capacity at one decision timestamp.",
            "Normalize carrier rates and service calendars.",
            "Remove assignments prohibited by item, warehouse, route, or policy constraints.",
        ],
        "features": [
            {"name": "Available inventory", "kind": "constraint", "source": "Warehouse inventory", "role": "Limits item quantities assigned to each warehouse."},
            {"name": "Warehouse capacity", "kind": "constraint", "source": "Fulfillment operations", "role": "Caps picking and packing work by location and time window."},
            {"name": "Freight cost", "kind": "objective", "source": "Carrier rate table", "role": "Contributes directly to the cost objective."},
            {"name": "Promised delivery window", "kind": "constraint", "source": "Customer order", "role": "Eliminates assignments that cannot meet the promise."},
            {"name": "Carrier service level", "kind": "reference", "source": "Carrier contract", "role": "Defines eligible services, transit time, and capacity."},
            {"name": "Split-shipment penalty", "kind": "objective", "source": "Operations policy", "role": "Discourages extra parcels and handoffs unless necessary."},
        ],
        "metrics": [
            {"name": "Feasibility rate", "target": "100% of released plans satisfy hard constraints", "why": "Safety and policy constraints are non-negotiable."},
            {"name": "P95 solve time", "target": "< 500 ms for one-order allocation", "why": "Allocation is on the fulfillment path."},
            {"name": "Optimality gap", "target": "< 2% on benchmark instances", "why": "Shows how close the solver is to the best known solution."},
            {"name": "Freight cost per order", "target": "Improve over current heuristic", "why": "Measures economic value."},
            {"name": "On-time promise rate", "target": "No degradation versus baseline", "why": "Prevents savings that harm service."},
        ],
        "testing": [
            "Compare small instances with hand-calculated optimal solutions.",
            "Property-test that no released plan violates inventory or capacity.",
            "Stress-test peak volume, warehouse outage, carrier outage, and zero-feasibility cases.",
            "Replay historical orders against the current heuristic and solver.",
        ],
        "monitoring": [
            "Solve latency, infeasible rate, and fallback-heuristic use.",
            "Binding constraints and capacity saturation by warehouse.",
            "Freight cost, split shipments, and on-time delivery outcomes.",
        ],
        "limitations": [
            "Results are only as current as inventory, rate, and capacity inputs.",
            "Poorly chosen objective weights can optimize cost at the expense of customer experience.",
            "The current demo uses a fixed feasible assignment rather than a live solver.",
        ],
    },
    "delivery_risk_prediction": {
        "title": "Late-delivery risk predictor",
        "category": "Supervised probability prediction",
        "implementation_status": "Proposed production design; demo uses a deterministic synthetic predictor",
        "purpose": "Estimate whether a shipment will miss its promise early enough for operations and support to intervene.",
        "algorithm": "Gradient-boosted trees predict late-delivery probability from route, carrier, shipment, weather, volume, and event-timing features, followed by probability calibration.",
        "why_fit": "Delivery delay is a future outcome driven by nonlinear operational interactions. A calibrated probability supports monitor and intervene thresholds.",
        "output": "Probability of missing the promised delivery window and an expected delay estimate.",
        "training_required": True,
        "training_approach": "Train on completed shipments using only information available at the prediction timestamp. Build separate snapshots at dispatch and major tracking events.",
        "training_data": "At least 12 months of promised and actual delivery timestamps joined to route, carrier, warehouse, weather, volume, and tracking-event history.",
        "target_definition": "1 when actual delivery is later than the customer promise; 0 otherwise. Delay duration is actual minus promised delivery time.",
        "split_strategy": "Time-ordered 70/15/15 split by shipment completion date. Keep all snapshots from one shipment in one split and reserve the newest season for final testing.",
        "preprocessing": [
            "Compute route and event-age features as of the scoring timestamp.",
            "Encode carrier, warehouse, service level, weekday, and season.",
            "Impute missing operational signals with explicit missingness flags.",
            "Exclude actual delivery time and tracking events that occurred after scoring.",
        ],
        "features": [
            {"name": "Warehouse and route", "kind": "categorical", "source": "Fulfillment plan", "role": "Captures lane-specific reliability and handoff patterns."},
            {"name": "Carrier and service level", "kind": "categorical", "source": "Shipment", "role": "Represents different networks and commitments."},
            {"name": "Shipment complexity", "kind": "numeric", "source": "Order and parcel", "role": "Counts items, parcels, weight, and split-shipment exposure."},
            {"name": "Weather and disruption", "kind": "time-varying", "source": "Approved operational feed", "role": "Adds current route hazards without using future observations."},
            {"name": "Network volume", "kind": "numeric", "source": "Carrier and warehouse operations", "role": "Measures congestion relative to expected capacity."},
            {"name": "Tracking-event timing", "kind": "derived", "source": "Shipment events", "role": "Measures lateness or dwell against the expected event schedule."},
        ],
        "metrics": [
            {"name": "Brier score / calibration", "target": "<= 0.10 on temporal holdout", "why": "Operations thresholds depend on trustworthy probabilities."},
            {"name": "Late-event recall", "target": ">= 80% at the intervention threshold", "why": "Measures how many preventable misses are surfaced."},
            {"name": "Arrival-time MAE", "target": "<= 0.5 day", "why": "Measures expected-delay accuracy."},
            {"name": "Worst-5% miss error", "target": "Improve over carrier baseline", "why": "Average error can hide the expensive late tail."},
            {"name": "Support lead time", "target": "Increase intervention time without excess alerts", "why": "Connects prediction to useful workflow action."},
        ],
        "testing": [
            "Evaluate on an untouched future-period and seasonal holdout.",
            "Slice by carrier, warehouse, route, service level, geography, and disruption type.",
            "Backtest monitor and intervene thresholds against support capacity.",
            "Replay missing or delayed tracking feeds and verify fail-safe behavior.",
            "Run shadow predictions before changing customer promises.",
        ],
        "monitoring": [
            "Calibration, recall, and MAE by route and carrier.",
            "Feature drift in volume, weather, dwell, and service mix.",
            "Monitor/intervene rates, human overrides, broken promises, and support contacts.",
            "Prediction age and upstream tracking-feed freshness.",
        ],
        "limitations": [
            "Extreme disruptions may be absent from training history.",
            "Carrier event timestamps can be delayed or inconsistent.",
            "The model should inform promise changes; a fulfillment manager retains authority.",
            "The current demo probability is deterministic and is not a trained production model.",
        ],
    },
}


def algorithm_profile(decision_type: str) -> dict[str, Any]:
    return deepcopy(ALGORITHM_PROFILES[decision_type])


def backfill_algorithm_profiles(session: Session) -> None:
    decisions = session.scalars(
        select(OrderDecision).where(OrderDecision.algorithm_profile.is_(None))
    ).all()
    changed = False
    for decision in decisions:
        profile = ALGORITHM_PROFILES.get(decision.decision_type)
        if profile:
            decision.algorithm_profile = deepcopy(profile)
            changed = True
    if changed:
        session.commit()
