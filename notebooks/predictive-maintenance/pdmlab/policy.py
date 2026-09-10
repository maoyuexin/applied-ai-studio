"""The operating policy: turning a score into an action, and pricing it.

Every dollar figure in this file is a SYNTHETIC CLASSROOM ASSUMPTION. They are
anchored on the published fact that air-production-unit faults caused Metro do
Porto to cancel more than 170 trips in 2017. They are not that organization's
real numbers, and nothing measured here transfers to another fleet.

The cost model says what near-zero lead time actually buys. It is not failure
avoidance: it is a SHORTER FAULT. A detected fault is charged for the hours
from its documented onset to the first alert, plus the four hours a technician
takes to arrive. An undetected fault is charged for its full documented length.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .metrics import episodes

COSTS = config.COSTS


def route(score: float) -> str:
    """The three-way routing rule. This is the whole policy."""
    if score >= config.THRESHOLD:
        return config.ROUTE_WORK_ORDER
    if score >= config.WATCH_THRESHOLD:
        return config.ROUTE_WATCH
    return config.ROUTE_NO_ACTION


def route_series(scores: pd.Series) -> pd.Series:
    return scores.map(route)


def fault_cost(hours_unaddressed: float, costs: dict = COSTS) -> float:
    """Running cost of a leak, plus a one-off interruption charge past 12 h."""
    total = hours_unaddressed * costs["fault_usd_per_hour"]
    if hours_unaddressed > costs["interruption_after_hours"]:
        total += costs["service_interruption_usd"]
    return total


def policy_cost(score: pd.Series, threshold: float, window, costs: dict = COSTS) -> dict:
    """Full cost of running 'alert above threshold' over one window."""
    series = score.dropna()
    series = series[(series.index >= window[0]) & (series.index < window[1])]
    alerts = series.index[(series >= threshold).to_numpy()]
    trips = episodes(alerts)
    failures = [f for f in config.failure_windows() if window[0] <= f[1] < window[1]]

    explained: set[int] = set()
    detail = []
    fault_total = 0.0
    for name, start, end, _note in failures:
        duration = (end - start).total_seconds() / 3600
        hits = [t for t in alerts if start - pd.Timedelta(hours=config.PRE_CREDIT_HOURS) <= t <= end]
        if hits:
            first = hits[0]
            unaddressed = max(0.0, (first - start).total_seconds() / 3600) + costs["response_hours"]
            unaddressed = min(unaddressed, duration)
            for position, (a, b) in enumerate(trips):
                if a <= first <= b:
                    explained.add(position)
        else:
            unaddressed = duration
        cost = fault_cost(unaddressed, costs)
        fault_total += cost
        detail.append({
            "failure": name,
            "documented_hours": round(duration, 1),
            "detected": bool(hits),
            "hours_unaddressed": round(unaddressed, 1),
            "fault_cost_usd": round(cost),
        })

    callouts = len(trips)
    months = max((series.index.max() - series.index.min()).days / 30.44, 1e-9)
    return {
        "threshold": float(threshold),
        "callouts": callouts,
        "false_callouts": callouts - len(explained),
        "callouts_per_month": round(callouts / months, 2),
        "technician_hours": round(callouts * costs["technician_hours_per_callout"], 1),
        "failures_caught": int(sum(d["detected"] for d in detail)),
        "failures_total": len(detail),
        "callout_cost_usd": callouts * costs["callout_usd"],
        "fault_cost_usd": round(fault_total),
        "total_cost_usd": round(callouts * costs["callout_usd"] + fault_total),
        "detail": detail,
    }


def never_alert(window, costs: dict = COSTS) -> dict:
    """Do nothing. Every fault runs its full documented length."""
    failures = [f for f in config.failure_windows() if window[0] <= f[1] < window[1]]
    total = sum(fault_cost((end - start).total_seconds() / 3600, costs) for _n, start, end, _d in failures)
    return {
        "policy": "never alert",
        "callouts": 0,
        "technician_hours": 0.0,
        "failures_caught": 0,
        "failures_total": len(failures),
        "callout_cost_usd": 0,
        "fault_cost_usd": round(total),
        "total_cost_usd": round(total),
    }


def scheduled_inspection(window, every_days: int, costs: dict = COSTS) -> dict:
    """Calendar maintenance: a technician walks the machine every N days at 09:00."""
    failures = [f for f in config.failure_windows() if window[0] <= f[1] < window[1]]
    visits = pd.date_range(window[0], window[1], freq=f"{every_days}D")
    visits = pd.DatetimeIndex([v.normalize() + pd.Timedelta(hours=9) for v in visits])
    total = 0.0
    caught = 0
    for _name, start, end, _note in failures:
        inside = [v for v in visits if start <= v <= end]
        duration = (end - start).total_seconds() / 3600
        if inside:
            caught += 1
            unaddressed = min((inside[0] - start).total_seconds() / 3600 + costs["response_hours"], duration)
        else:
            unaddressed = duration
        total += fault_cost(unaddressed, costs)
    return {
        "policy": f"scheduled inspection every {every_days} d",
        "callouts": len(visits),
        "technician_hours": len(visits) * costs["technician_hours_per_callout"],
        "failures_caught": caught,
        "failures_total": len(failures),
        "callout_cost_usd": len(visits) * costs["callout_usd"],
        "fault_cost_usd": round(total),
        "total_cost_usd": round(len(visits) * costs["callout_usd"] + total),
    }


def threshold_sweep(score: pd.Series, window, thresholds=None, costs: dict = COSTS) -> pd.DataFrame:
    """The operating-policy table: what each threshold costs and catches."""
    thresholds = thresholds or config.THRESHOLD_SWEEP
    rows = []
    for threshold in thresholds:
        result = policy_cost(score, threshold, window, costs)
        result.pop("detail")
        rows.append(result)
    return pd.DataFrame(rows)


def baseline_table(window, costs: dict = COSTS) -> pd.DataFrame:
    """Never-alert and calendar maintenance, priced over the same window."""
    rows = [never_alert(window, costs)]
    rows += [scheduled_inspection(window, days, costs) for days in (30, 14, 7, 3, 1)]
    return pd.DataFrame(rows)


def cost_assumptions_table() -> pd.DataFrame:
    return pd.DataFrame([
        ("Technician callout", f"${COSTS['callout_usd']:,}",
         f"{COSTS['technician_hours_per_callout']:.0f} technician-hours at a $200/h loaded rate"),
        ("Fault running unaddressed", f"${COSTS['fault_usd_per_hour']:,} / hour",
         "Wasted energy and accelerated wear while the leak continues"),
        ("Service interruption", f"${COSTS['service_interruption_usd']:,}",
         f"Charged once if a fault runs more than {COSTS['interruption_after_hours']} h unaddressed"),
        ("Response time", f"{COSTS['response_hours']:.0f} hours",
         "Alert raised to technician on site"),
    ], columns=["Parameter", "Value (SYNTHETIC)", "What it stands for"])
