"""Counting rules, and the drift measurements.

Two accounting decisions are made once here and never re-argued:

1. **A technician callout, not an alert hour, is the unit of work.** Alerts
   within 6 hours of each other are one trip to the machine, because that is
   what actually happens. Counting alert hours would inflate the workload of
   any long event by a factor of ten.

2. **False alarms are counted on clean hours only.** An hour inside
   [onset - 72 h, end + 24 h] is neither a hit nor a false alarm - the machine
   may genuinely have been degrading before anyone wrote the report, and we
   refuse to score ourselves on hours whose truth we do not know.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def window_masks(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """(credit, ambiguous) masks over an hourly index."""
    credit = pd.Series(False, index=index)
    ambiguous = pd.Series(False, index=index)
    for _name, start, end, _note in config.failure_windows():
        credit |= (index >= start - pd.Timedelta(hours=config.PRE_CREDIT_HOURS)) & (
            index <= end + pd.Timedelta(hours=config.POST_WINDOW_HOURS)
        )
        ambiguous |= (index >= start - pd.Timedelta(hours=config.AMBIGUOUS_PRE_HOURS)) & (
            index <= end + pd.Timedelta(hours=config.AMBIGUOUS_POST_HOURS)
        )
    return credit, ambiguous


def episodes(alert_index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Collapse alert hours into technician callouts (6-hour merge gap)."""
    if len(alert_index) == 0:
        return []
    out = []
    start = previous = alert_index[0]
    for stamp in alert_index[1:]:
        if (stamp - previous) > pd.Timedelta(hours=config.MERGE_GAP_HOURS):
            out.append((start, previous))
            start = stamp
        previous = stamp
    out.append((start, previous))
    return out


def evaluate(score: pd.Series, threshold: float, window=None) -> dict:
    """Detection and false-alarm accounting for one threshold."""
    series = score.dropna()
    if window is not None:
        series = series[(series.index >= window[0]) & (series.index < window[1])]
    index = series.index
    _credit, ambiguous = window_masks(index)
    alert = series >= threshold
    clean = ~ambiguous
    false_hours = index[(alert & clean).to_numpy()]
    false_episodes = episodes(false_hours)
    months = max((index.max() - index.min()).days / 30.44, 1e-9)

    per_failure = {}
    for name, start, end, _note in config.failure_windows():
        window_hours = series[
            (index >= start - pd.Timedelta(hours=config.PRE_CREDIT_HOURS))
            & (index <= end + pd.Timedelta(hours=config.POST_WINDOW_HOURS))
        ]
        if len(window_hours) == 0:
            per_failure[name] = {"detected": None, "lead_hours": None, "note": "outside this window"}
            continue
        hits = window_hours.index[(window_hours >= threshold).to_numpy()]
        if len(hits) == 0:
            per_failure[name] = {"detected": False, "lead_hours": None}
            continue
        first = hits[0]
        per_failure[name] = {
            "detected": True,
            "first_alert": str(first),
            "lead_hours": round((start - first).total_seconds() / 3600, 1),
        }

    return {
        "threshold": float(threshold),
        "scored_hours": int(len(series)),
        "alert_hours": int(alert.sum()),
        "clean_hours": int(clean.sum()),
        "false_alarm_hours": int(len(false_hours)),
        "false_alarm_rate_on_clean_hours": round(len(false_hours) / max(int(clean.sum()), 1), 4),
        "false_callouts": len(false_episodes),
        "false_callouts_per_month": round(len(false_episodes) / months, 2),
        "months": round(months, 2),
        "failures_detected": sum(1 for v in per_failure.values() if v.get("detected")),
        "failures_with_advance_warning": sum(
            1 for v in per_failure.values()
            if v.get("detected") and (v.get("lead_hours") or 0) > 0
        ),
        "per_failure": per_failure,
    }


def lead_time_table(score: pd.Series, thresholds=None, window=None) -> pd.DataFrame:
    """Threshold sweep with per-failure lead time. Positive = before onset."""
    thresholds = thresholds or config.THRESHOLD_SWEEP
    window = window or (config.SCORED_START, config.SCORED_END)
    rows = []
    for threshold in thresholds:
        result = evaluate(score, threshold, window)
        row = {
            "threshold": threshold,
            "alert_hours": result["alert_hours"],
            "false_callouts": result["false_callouts"],
            "false_callouts_per_month": result["false_callouts_per_month"],
            "failures_detected": result["failures_detected"],
        }
        for name, detail in result["per_failure"].items():
            row[f"{name}_lead_h"] = detail.get("lead_hours")
        rows.append(row)
    return pd.DataFrame(rows)


def failure_trace(score: pd.Series, name: str, before: int = 36, after: int = 6) -> pd.DataFrame:
    """Hour-by-hour score around one documented onset."""
    match = [f for f in config.failure_windows() if f[0] == name][0]
    _n, start, end, _note = match
    stop = min(end, start + pd.Timedelta(hours=after))
    window = score[(score.index >= start - pd.Timedelta(hours=before)) & (score.index <= stop)]
    return pd.DataFrame({
        "hour": window.index,
        "hours_from_onset": (window.index - start).total_seconds() / 3600,
        "score": window.to_numpy(),
    })


def compare_models(scores: dict[str, pd.Series], quantile: float = 0.98, window=None) -> pd.DataFrame:
    """Score every candidate at the same quantile of its own scored period.

    Different models produce numbers on completely different scales, so a
    shared numeric threshold would be meaningless. Setting each one's cut at
    the same quantile - here, alerting on the top 2% of hours - makes the
    alerting budget identical and lets the comparison be about which hours
    each model picks.
    """
    window = window or (config.SCORED_START, config.SCORED_END)
    rows = []
    for name, series in scores.items():
        scored = series.dropna()
        scored = scored[(scored.index >= window[0]) & (scored.index < window[1])]
        threshold = float(np.quantile(scored.to_numpy(), quantile))
        result = evaluate(series, threshold, window)
        rows.append({
            "model": name,
            "alerts on top": f"{(1 - quantile):.0%} of hours",
            "failures_detected": result["failures_detected"],
            "with_advance_warning": result["failures_with_advance_warning"],
            "false_callouts": result["false_callouts"],
            "false_callouts_per_month": result["false_callouts_per_month"],
        })
    return pd.DataFrame(rows)


def one_vs_two_sided(one_sided: pd.Series, two_sided: pd.Series, thresholds=(4, 5, 6, 7)) -> pd.DataFrame:
    rows = []
    for threshold in thresholds:
        a = evaluate(one_sided, threshold, (config.SCORED_START, config.SCORED_END))
        b = evaluate(two_sided, threshold, (config.SCORED_START, config.SCORED_END))
        rows.append({
            "threshold": threshold,
            "one-sided detected": a["failures_detected"],
            "one-sided false callouts/month": a["false_callouts_per_month"],
            "two-sided detected": b["failures_detected"],
            "two-sided false callouts/month": b["false_callouts_per_month"],
        })
    return pd.DataFrame(rows)


def scaling_comparison(variants: dict[str, pd.Series], thresholds=(2, 3, 4, 5, 6, 7, 8, 10)) -> pd.DataFrame:
    """Failures detected at each threshold, per scaling choice.

    Read it as an operating band: how wide is the range of thresholds that
    still catches all four?
    """
    rows = []
    for name, series in variants.items():
        row = {"scaling": name}
        for threshold in thresholds:
            result = evaluate(series, threshold, (config.SCORED_START, config.SCORED_END))
            row[f"thr {threshold}"] = result["failures_detected"]
        rows.append(row)
    return pd.DataFrame(rows)


# ── Drift ───────────────────────────────────────────────────────────────────

def naive_single_feature_drift(score_frame: pd.DataFrame, threshold: float = 3.0) -> pd.DataFrame:
    """The rule a first team actually writes: one feature, 3 robust SDs, fixed.

    Cell value = share of that month's CLEAN hours that alert. Denominator is
    the clean hours in that month, printed in the last column for April.
    """
    _credit, ambiguous = window_masks(score_frame.index)
    clean = ~ambiguous
    rows = []
    for column in config.MODEL_FEATURES:
        frame = pd.DataFrame({"z": score_frame[column], "clean": clean}).dropna()
        frame = frame[frame.index >= config.SCORED_START]
        frame["alert"] = frame["z"] >= threshold
        row = {"feature": config.FEATURE_DISPLAY_NAMES[column]}
        for period, chunk in frame.groupby(frame.index.to_period("M")):
            clean_chunk = chunk[chunk["clean"]]
            if len(clean_chunk) < 24:
                continue
            row[str(period)] = round(100 * clean_chunk["alert"].mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def detector_callouts_by_month(score: pd.Series, thresholds=(3, 4, 5, 6, 8)) -> pd.DataFrame:
    """False technician callouts per month for the six-feature detector."""
    _credit, ambiguous = window_masks(score.index)
    clean = ~ambiguous
    rows = []
    for threshold in thresholds:
        frame = pd.DataFrame({"s": score, "clean": clean}).dropna()
        frame = frame[frame.index >= config.SCORED_START]
        frame["alert"] = frame["s"] >= threshold
        row = {"threshold": threshold}
        for period, chunk in frame.groupby(frame.index.to_period("M")):
            clean_chunk = chunk[chunk["clean"]]
            if len(clean_chunk) < 24:
                continue
            row[str(period)] = len(episodes(clean_chunk.index[clean_chunk["alert"].to_numpy()]))
        rows.append(row)
    return pd.DataFrame(rows)


def monthly_alert_load(score: pd.Series, threshold: float) -> pd.DataFrame:
    """Clean-hour alert rate and callout count per month at one threshold."""
    _credit, ambiguous = window_masks(score.index)
    clean = ~ambiguous
    frame = pd.DataFrame({"s": score, "clean": clean}).dropna()
    frame = frame[frame.index >= config.SCORED_START]
    frame["alert"] = frame["s"] >= threshold
    rows = []
    for period, chunk in frame.groupby(frame.index.to_period("M")):
        clean_chunk = chunk[chunk["clean"]]
        if len(clean_chunk) < 24:
            continue
        rows.append({
            "month": str(period),
            "clean_hours": len(clean_chunk),
            "alert_hours": int(clean_chunk["alert"].sum()),
            "pct_of_clean_hours": round(100 * clean_chunk["alert"].mean(), 1),
            "false_callouts": len(episodes(clean_chunk.index[clean_chunk["alert"].to_numpy()])),
        })
    return pd.DataFrame(rows)


def training_window_alerts(score: pd.Series, threshold: float) -> dict:
    """How many 'clean' training hours would have alerted, had we scored them.

    The uncomfortable number. Nobody filed a work order in February or March,
    which is not the same as knowing the machine was healthy.
    """
    training = score[(score.index >= config.TRAIN_START) & (score.index < config.TRAIN_END)].dropna()
    above = training[training >= threshold]
    runs = episodes(above.index)
    return {
        "training_hours": int(len(training)),
        "hours_above_threshold": int(len(above)),
        "share_above_threshold": round(float(len(above) / len(training)), 4),
        "episodes": len(runs),
        "peak_score": round(float(training.max()), 2),
        "peak_at": str(training.idxmax()),
        "episode_list": [
            {"from": str(a), "to": str(b), "peak": round(float(training[a:b].max()), 2)}
            for a, b in runs
        ],
    }


def mitigation_table(fixed: pd.Series, rolling: dict[str, pd.Series],
                     threshold: float, high_threshold: float) -> pd.DataFrame:
    """What each baseline strategy costs in false callouts AND in detection.

    Two thresholds on purpose. At the low one the rolling baseline looks like
    a clear win. At the high one it stops catching failures, because a window
    that keeps re-learning 'normal' eventually learns the fault.
    """
    window = (config.SCORED_START, config.SCORED_END)
    rows = []
    for name, series in {"Fixed Feb-Mar baseline": fixed, **rolling}.items():
        low = evaluate(series, threshold, window)
        high = evaluate(series, high_threshold, window)
        rows.append({
            "baseline": name,
            f"false callouts @ {threshold:g}": low["false_callouts"],
            f"per month @ {threshold:g}": low["false_callouts_per_month"],
            f"failures caught @ {threshold:g}": low["failures_detected"],
            f"failures caught @ {high_threshold:g}": high["failures_detected"],
        })
    return pd.DataFrame(rows)
