"""Plotly figures shared by the executable notebook and the offline HTML.

Every figure aggregates before plotting - hourly means, binned histograms,
monthly rates - so nothing embeds a quarter of a million raw sensor readings.
Colors follow the palette in ``config`` so the course's charts read as one
family, and no figure relies on color alone to make its point.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config


def _layout(figure: go.Figure, title: str, height: int = 430) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=70, r=30, t=80, b=60),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


def _failure_bands(figure: go.Figure, row: int | None = None, col: int | None = None) -> None:
    """Shade the four documented failure windows on a time axis."""
    kwargs = {}
    if row is not None:
        kwargs = {"row": row, "col": col}
    for name, start, end, _note in config.failure_windows():
        figure.add_vrect(
            x0=start, x1=end, fillcolor=config.COLOR_FAILURE, opacity=0.18,
            line_width=0, annotation_text=name, annotation_position="top left",
            annotation_font_size=11, **kwargs,
        )


# ── Stage 1 ─────────────────────────────────────────────────────────────────

def coverage_timeline(daily: pd.DataFrame, gap_count: int, missing_hours: float) -> go.Figure:
    """Share of each day's 1,440 minutes that carry a sensor reading."""
    figure = go.Figure()
    figure.add_bar(
        x=daily["date"], y=daily["share_recorded"],
        marker_color=np.where(daily["share_recorded"] < 0.5,
                              config.COLOR_WARN, config.COLOR_NORMAL),
        name="Minutes recorded",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.0%} of the day recorded<extra></extra>",
    )
    figure.add_hline(y=0.5, line_dash="dash", line_color=config.COLOR_MUTED,
                     annotation_text="half the day", annotation_position="right")
    _failure_bands(figure)
    figure.update_yaxes(title="Share of the day with sensor data", tickformat=".0%", range=[0, 1.05])
    figure.update_xaxes(title="Date (2020)")
    figure.update_layout(showlegend=False)
    return _layout(
        figure,
        f"The recorder stopped {gap_count} times: {missing_hours:,.0f} hours of this "
        "seven-month record are simply not there",
        height=400,
    )


# ── Stage 2 ─────────────────────────────────────────────────────────────────

def motor_current_regimes(histogram: pd.DataFrame) -> go.Figure:
    """The compressor has three states, and the current meter shows all three."""
    colors = np.where(
        histogram["amperes"] > config.MOTOR_LOAD_THRESHOLD, config.COLOR_FAILURE,
        np.where(histogram["amperes"] > config.MOTOR_OFF_THRESHOLD,
                 config.COLOR_WARN, config.COLOR_NORMAL),
    )
    figure = go.Figure(
        go.Bar(
            x=histogram["amperes"], y=histogram["minutes"], marker_color=colors,
            hovertemplate="%{x:.1f} A<br>%{y:,} minutes<extra></extra>",
        )
    )
    for value, label in [(config.MOTOR_OFF_THRESHOLD, "1.0 A: motor spinning"),
                         (config.MOTOR_LOAD_THRESHOLD, "4.75 A: compressing air")]:
        figure.add_vline(x=value, line_dash="dash", line_color="#20242B",
                         annotation_text=label, annotation_position="top",
                         annotation_font_size=11)
    figure.update_yaxes(title="Minutes in the seven-month record", type="log")
    figure.update_xaxes(title="Motor current (amperes), 1-minute mean")
    figure.update_layout(showlegend=False)
    return _layout(figure, "Off (blue), idling (orange), working hard (red) - three peaks, two cut points")


def leak_signature(normal: pd.Series, failure: pd.Series) -> go.Figure:
    """Hour-by-hour working-hard share: a healthy week beside a leaking one."""
    figure = make_subplots(
        rows=2, cols=1, shared_yaxes=True, vertical_spacing=0.18,
        subplot_titles=("A healthy week (2020-02-15 to 2020-02-21)",
                        "The F3 air leak (2020-06-05 10:00 to 2020-06-07 14:30)"),
    )
    figure.add_scatter(
        x=list(range(len(normal))), y=normal.to_numpy(), mode="lines",
        line=dict(color=config.COLOR_NORMAL, width=1.6), name="Healthy",
        hovertemplate="hour %{x}<br>%{y:.0%} of the hour compressing<extra></extra>",
        row=1, col=1,
    )
    figure.add_scatter(
        x=list(range(len(failure))), y=failure.to_numpy(), mode="lines",
        line=dict(color=config.COLOR_FAILURE, width=1.6), name="Air leak",
        hovertemplate="hour %{x}<br>%{y:.0%} of the hour compressing<extra></extra>",
        row=2, col=1,
    )
    figure.update_yaxes(title="Share of hour compressing", tickformat=".0%", range=[0, 1.05])
    figure.update_xaxes(title="Hours from the start of the window", row=2, col=1)
    figure.update_layout(showlegend=False)
    return _layout(figure, "A leak does not look like a spike. It looks like a machine that never gets to stop", height=520)


def effect_size_chart(effects: pd.DataFrame) -> go.Figure:
    """Cohen's d during a failure, next to Cohen's d 24 hours before it."""
    frame = effects.copy()
    frame["abs_during"] = frame["cohens_d_during"].abs()
    frame["abs_before"] = frame["cohens_d_24h_before"].abs()
    frame = frame.sort_values("abs_during")
    figure = go.Figure()
    figure.add_bar(
        y=frame["display"], x=frame["abs_during"], orientation="h",
        marker_color=config.COLOR_FAILURE, name="During the failure",
        text=[f"{v:.1f}" for v in frame["abs_during"]], textposition="outside",
        hovertemplate="%{y}<br>|d| = %{x:.2f} during the failure<extra></extra>",
    )
    figure.add_bar(
        y=frame["display"], x=frame["abs_before"], orientation="h",
        marker_color=config.COLOR_MUTED, name="24 hours before onset",
        text=[f"{v:.1f}" for v in frame["abs_before"]], textposition="outside",
        hovertemplate="%{y}<br>|d| = %{x:.2f} in the 24 h before onset<extra></extra>",
    )
    figure.update_xaxes(title="Separation from the baseline months, |Cohen's d| (pooled standard deviations)",
                        range=[0, 6.6])
    figure.update_yaxes(title="")
    figure.update_layout(barmode="group", legend=dict(orientation="h", y=1.10), bargap=0.28)
    return _layout(figure, "Every feature that screams during a failure is silent the day before it", height=520)


# ── Stage 3 ─────────────────────────────────────────────────────────────────

def model_comparison(compare: pd.DataFrame) -> go.Figure:
    """False technician callouts per month at an identical alerting budget."""
    frame = compare.sort_values("false_callouts_per_month")
    labels = [f"{n} of 4 caught" for n in frame["failures_detected"]]
    colors = [config.COLOR_ACCENT if n == 4 else config.COLOR_WARN for n in frame["failures_detected"]]
    figure = go.Figure(
        go.Bar(
            x=frame["model"], y=frame["false_callouts_per_month"],
            marker_color=colors, text=labels, textposition="outside",
            hovertemplate="%{x}<br>%{y:.2f} false callouts per month<br>%{text}<extra></extra>",
        )
    )
    figure.update_yaxes(title="False technician callouts per month (clean hours only)", range=[0, 5.4])
    figure.update_xaxes(title="")
    figure.update_layout(showlegend=False)
    return _layout(figure, "Same six features, same training months, same 2% alert budget - the simplest model wins", height=460)


def score_timeline(score: pd.Series) -> go.Figure:
    """The whole record, one point per scored hour, with the policy line."""
    figure = go.Figure()
    figure.add_scatter(
        x=score.index, y=score.to_numpy(), mode="lines",
        line=dict(color=config.COLOR_NORMAL, width=0.9), name="Hourly score",
        hovertemplate="%{x|%Y-%m-%d %H:00}<br>score %{y:.2f}<extra></extra>",
    )
    figure.add_hline(y=config.THRESHOLD, line_color=config.COLOR_FAILURE, line_dash="dash",
                     annotation_text=f"work order at {config.THRESHOLD}", annotation_position="right")
    figure.add_hline(y=config.WATCH_THRESHOLD, line_color=config.COLOR_WARN, line_dash="dot",
                     annotation_text=f"watch at {config.WATCH_THRESHOLD}", annotation_position="right")
    figure.add_vrect(x0=config.TRAIN_START, x1=config.TRAIN_END, fillcolor=config.COLOR_MUTED,
                     opacity=0.22, line_width=0, annotation_text="training months",
                     annotation_position="top left", annotation_font_size=11)
    _failure_bands(figure)
    figure.update_yaxes(title="Detector score (robust standard deviations from normal)")
    figure.update_xaxes(title="2020")
    figure.update_layout(showlegend=False)
    return _layout(figure, "Seven months of hourly scores: the four documented failures, and everything else", height=460)


# ── Stage 4 ─────────────────────────────────────────────────────────────────

def cost_curve(sweep: pd.DataFrame, never_cost: float, daily_cost: float) -> go.Figure:
    """Total synthetic cost and technician workload against the threshold."""
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
        row_heights=[0.62, 0.38],
        subplot_titles=("Total cost over Apr 1 - Sep 1 (SYNTHETIC dollars)",
                        "Technician callouts per month"),
    )
    figure.add_scatter(
        x=sweep["threshold"], y=sweep["total_cost_usd"], mode="lines+markers",
        line=dict(color=config.COLOR_NORMAL, width=2.4), marker=dict(size=8),
        name="Detector",
        hovertemplate="threshold %{x}<br>$%{y:,.0f}<extra></extra>",
        row=1, col=1,
    )
    figure.add_hline(y=never_cost, line_color=config.COLOR_FAILURE, line_dash="dash",
                     annotation_text=f"never alert  ${never_cost:,.0f}",
                     annotation_position="top right", row=1, col=1)
    figure.add_hline(y=daily_cost, line_color=config.COLOR_WARN, line_dash="dot",
                     annotation_text=f"inspect daily  ${daily_cost:,.0f}",
                     annotation_position="bottom right", row=1, col=1)
    figure.add_scatter(
        x=[config.THRESHOLD],
        y=[float(sweep.loc[sweep["threshold"] == config.THRESHOLD, "total_cost_usd"].iloc[0])],
        mode="markers+text", marker=dict(size=15, color=config.COLOR_ACCENT, symbol="diamond"),
        text=["chosen: 6.0"], textposition="bottom center", name="Chosen",
        hovertemplate="chosen threshold 6.0<extra></extra>", row=1, col=1,
    )
    figure.add_bar(
        x=sweep["threshold"], y=sweep["callouts_per_month"],
        marker_color=config.COLOR_MUTED, name="Callouts/month",
        hovertemplate="threshold %{x}<br>%{y:.1f} callouts per month<extra></extra>",
        row=2, col=1,
    )
    figure.update_yaxes(title="Total cost (USD)", type="log", row=1, col=1)
    figure.update_yaxes(title="Callouts / month", row=2, col=1)
    figure.update_xaxes(title="Alert threshold (detector score)", row=2, col=1)
    figure.update_layout(showlegend=False)
    return _layout(figure, "Where the money is: cost is flat from 6 to 10, and falls off a cliff at 12", height=580)


def naive_rule_drift(drift: pd.DataFrame) -> go.Figure:
    """One feature, one fixed threshold: the alert rate climbs all summer."""
    months = [c for c in drift.columns if c != "feature"]
    figure = go.Figure()
    highlight = config.FEATURE_DISPLAY_NAMES["rest_minutes_per_cycle"]
    for _, row in drift.iterrows():
        is_headline = row["feature"] == highlight
        figure.add_scatter(
            x=months, y=[row[m] for m in months], mode="lines+markers",
            name=row["feature"],
            line=dict(width=3.6 if is_headline else 1.5,
                      color=config.COLOR_FAILURE if is_headline else config.COLOR_MUTED,
                      dash="solid" if is_headline else "dot"),
            marker=dict(size=9 if is_headline else 6),
            hovertemplate="%{fullData.name}<br>%{x}: %{y:.1f}% of clean hours alerting<extra></extra>",
        )
    figure.update_yaxes(title="Share of that month's CLEAN hours alerting", ticksuffix="%", range=[0, 100])
    figure.update_xaxes(title="Month (2020)")
    figure.update_layout(legend=dict(orientation="h", y=-0.32, font_size=11))
    return _layout(
        figure,
        "The classic air-leak rule: right 19% of the time in April, on almost permanently by August",
        height=560,
    )


def drift_callout_heatmap(callouts: pd.DataFrame) -> go.Figure:
    """False callouts per month for the six-feature detector, by threshold."""
    months = [c for c in callouts.columns if c != "threshold"]
    values = callouts[months].to_numpy()
    figure = go.Figure(
        go.Heatmap(
            z=values, x=months, y=[f"threshold {t}" for t in callouts["threshold"]],
            colorscale="Reds", zmin=0, zmax=float(values.max()),
            text=values, texttemplate="%{text}", textfont=dict(size=14),
            colorbar=dict(title="False<br>callouts"),
            hovertemplate="%{y}<br>%{x}: %{z} false technician callouts<extra></extra>",
        )
    )
    figure.update_xaxes(title="Month (2020)")
    figure.update_yaxes(title="", autorange="reversed")
    return _layout(
        figure,
        "The cruel interaction: the low threshold that buys lead time is the one that floods the queue",
        height=400,
    )


# ── Stage 5 ─────────────────────────────────────────────────────────────────

def flat_line_trace(trace: pd.DataFrame) -> go.Figure:
    """F3: thirty-six hours of nothing, then the onset hour."""
    colors = [config.COLOR_FAILURE if v >= config.THRESHOLD else config.COLOR_NORMAL
              for v in trace["score"]]
    figure = go.Figure(
        go.Bar(
            x=trace["hours_from_onset"], y=trace["score"], marker_color=colors,
            hovertemplate="%{x:+.0f} h from onset<br>score %{y:.2f}<extra></extra>",
        )
    )
    figure.add_hline(y=config.THRESHOLD, line_color=config.COLOR_FAILURE, line_dash="dash",
                     annotation_text="work order at 6.0", annotation_position="top left")
    figure.add_vline(x=0, line_color="#20242B", line_width=2,
                     annotation_text="documented onset", annotation_position="top right",
                     annotation_font_size=11)
    figure.update_yaxes(title="Detector score")
    figure.update_xaxes(title="Hours from the documented onset of F3 (negative = before)")
    figure.update_layout(showlegend=False)
    before = trace.loc[trace["hours_from_onset"] < 0, "score"]
    onset = trace.loc[trace["hours_from_onset"] == 0, "score"]
    return _layout(
        figure,
        f"F3, the year's longest failure: flat under {before.max():.1f} for "
        f"{len(before):.0f} hours, then {float(onset.iloc[0]):.1f} in the onset hour itself",
        height=430,
    )


def indistinguishable_pair(healthy: pd.DataFrame, failure: pd.DataFrame,
                           healthy_peak: float, failure_peak: float) -> go.Figure:
    """A healthy May day and the year's worst failure, scored side by side."""
    figure = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06,
        subplot_titles=(f"S6 - healthy compressor, busy May day (peak {healthy_peak:.2f})",
                        f"S2 - F1, the year's worst failure (peak {failure_peak:.2f})"),
    )
    for column, frame, color in [(1, healthy, config.COLOR_NORMAL), (2, failure, config.COLOR_FAILURE)]:
        figure.add_scatter(
            x=list(range(len(frame))), y=frame["score"].to_numpy(), mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=5),
            name="healthy" if column == 1 else "failure",
            hovertemplate="hour %{x}<br>score %{y:.2f}<extra></extra>",
            row=1, col=column,
        )
        figure.add_hline(y=config.THRESHOLD, line_color=config.COLOR_FAILURE, line_dash="dash",
                         row=1, col=column)
    figure.update_yaxes(title="Detector score", range=[0, 14], row=1, col=1)
    figure.update_xaxes(title="Hours from the start of the window", row=1, col=1)
    figure.update_xaxes(title="Hours from the start of the window", row=1, col=2)
    figure.update_layout(showlegend=False)
    return _layout(
        figure,
        "No threshold separates these two. Only a person who knows the machine can",
        height=440,
    )
