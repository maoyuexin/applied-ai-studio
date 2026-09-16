"""Teaching displays and evaluation for the notebook-only anomaly comparison."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config, data, metrics

MODEL_NAMES = ("Robust-score baseline", "Isolation Forest")
REVIEW_SHARE = 0.02
COLORS = {"Reference hours": "#167D9A", "Reported failure": "#C84B42", "Other hours": "#8A9299"}
FEATURE_LABELS = {"load_share": "Compressor working", "cycles_per_hour": "Starts per hour",
                  "rest_minutes_per_cycle": "Rest per start", "oil_temp_mean": "Oil temperature",
                  "tp3_std": "Pressure variation", "pressure_fall_rate": "Pressure change"}
FEATURE_FORMATS = {
    "load_share": (100.0, "%"), "cycles_per_hour": (1.0, " starts"),
    "rest_minutes_per_cycle": (1.0, " min"), "oil_temp_mean": (1.0, " C"),
    "tp3_std": (1.0, " bar"), "pressure_fall_rate": (1.0, " bar/min"),
}


def style(figure, title: str, height: int = 380):
    figure.update_layout(template="plotly_white", title=title, height=height, font_size=14,
                         title_font_size=15, margin=dict(l=55, r=25, t=65, b=65),
                         legend=dict(orientation="h", y=-0.28, title_text=""))
    return figure


def source_profile(minutes: pd.DataFrame) -> pd.DataFrame:
    meanings = {
        "TP2": "Compressor outlet pressure (bar)", "TP3": "Panel pressure (bar)",
        "H1": "Separator outlet pressure (bar)", "DV_pressure": "Dryer discharge pressure (bar)",
        "Reservoirs": "Reservoir pressure (bar)", "Oil_temperature": "Oil temperature (C)",
        "Motor_current": "Motor current (A)", "COMP": "Air-intake valve state",
        "LPS": "Low-pressure state", "Oil_level": "Oil-level state",
    }
    roles = {
        "Motor_current": "Yes: working %, starts, and rest",
        "Oil_temperature": "Yes: mean temperature",
        "TP3": "Yes: pressure features",
    }
    return pd.DataFrame([{"Column": name, "What it measures": meanings[name],
                          "Used to build features": roles.get(name, "No")}
                         for name in minutes.columns])


def current_distribution(minutes: pd.DataFrame):
    counts = data.motor_current_histogram(minutes.loc[minutes.index < config.TRAIN_END], bins=45)
    figure = go.Figure(go.Bar(x=counts["amperes"], y=counts["minutes"], marker_color="#167D9A"))
    figure.add_vline(x=config.MOTOR_LOAD_THRESHOLD, line_dash="dash")
    figure.update_xaxes(title_text="Motor current (A)")
    figure.update_yaxes(title_text="Recorded training minutes")
    return style(figure, "Three motor operating ranges")


def coverage_plot(minutes: pd.DataFrame):
    coverage = data.hourly_coverage(minutes)
    counts = pd.DataFrame({"Hour": ["No readings", "Under half", "Usable"],
                           "Hours": [int((coverage == 0).sum()),
                                     int(((coverage > 0) & (coverage < config.MIN_HOUR_COVERAGE)).sum()),
                                     int((coverage >= config.MIN_HOUR_COVERAGE).sum())]})
    figure = px.bar(counts, x="Hour", y="Hours", text="Hours", color="Hour",
                    color_discrete_sequence=["#8A9299", "#B57712", "#167D9A"])
    figure.update_layout(showlegend=False)
    return style(figure, "Which hours have enough data?")


def feature_example(minutes: pd.DataFrame, matrix: pd.DataFrame):
    examples = [("February example", pd.Timestamp("2020-02-15 08:00")),
                ("April reported leak", pd.Timestamp("2020-04-18 02:00"))]
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           subplot_titles=[label for label, stamp in examples], vertical_spacing=0.22)
    rows = []
    for row_number, (label, stamp) in enumerate(examples, start=1):
        readings = minutes.loc[stamp:stamp + pd.Timedelta(minutes=59), "Motor_current"]
        observed = int(readings.notna().sum())
        working = int((readings > config.MOTOR_LOAD_THRESHOLD).sum())
        share = working / observed
        np.testing.assert_allclose(share, matrix.loc[stamp, "load_share"])
        rows.append({"Hour": label, "Working minutes": working, "Recorded minutes": observed,
                     "Working share (%)": round(100 * share, 1)})
        figure.add_trace(go.Scatter(x=(readings.index - stamp).total_seconds() / 60,
            y=readings.to_numpy(), mode="lines+markers", name=label,
            line_color="#167D9A" if row_number == 1 else "#C84B42"), row=row_number, col=1)
        figure.add_hline(y=config.MOTOR_LOAD_THRESHOLD, line_dash="dash", row=row_number, col=1)
    figure.update_yaxes(title_text="Current (A)", range=[0, 9])
    figure.update_xaxes(range=[0, 59])
    figure.update_xaxes(title_text="Minute within the hour", row=2, col=1)
    figure.update_annotations(font_size=13)
    figure.update_layout(showlegend=False)
    return style(figure, "Minutes become a feature", 490), pd.DataFrame(rows)


def feature_cloud(training: pd.DataFrame, validation: pd.DataFrame):
    reference = training[["load_share", "oil_temp_mean"]].copy()
    reference["Group"] = "Reference hours"
    reported = validation.loc[
        (validation.index >= pd.Timestamp("2020-04-18")) &
        (validation.index <= pd.Timestamp("2020-04-18 23:59")), ["load_share", "oil_temp_mean"]].copy()
    reported["Group"] = "Reported failure"
    combined = pd.concat([reference, reported])
    combined["Working time (%)"] = 100 * combined["load_share"]
    figure = px.scatter(combined, x="Working time (%)", y="oil_temp_mean", color="Group", symbol="Group",
                        color_discrete_map=COLORS, labels={"oil_temp_mean": "Oil temperature (C)",
                            "Working time (%)": "Compressor working (%)"},
                        render_mode="svg")
    figure.update_traces(marker_size=6, opacity=0.65)
    return style(figure, "One hour becomes one point", 430)


def score_cutoff_plot(scores: pd.Series, cutoff: float):
    if scores.empty or not np.isfinite(scores).all() or not np.isfinite(cutoff):
        raise ValueError("Finite validation scores and cutoff are required.")
    if not isinstance(scores.index, pd.DatetimeIndex) or scores.index.has_duplicates:
        raise ValueError("Scores need unique date-and-time labels.")
    timeline = scores.sort_index()
    flagged = timeline >= cutoff
    low, high = float(timeline.min()), float(timeline.max())
    padding = max((high - low) * 0.08, 0.01)

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=timeline.index, y=timeline, mode="lines", name="Hour scores",
                                line=dict(color="#167D9A", width=1), connectgaps=False))
    figure.add_trace(go.Scatter(x=timeline.index[flagged], y=timeline[flagged], mode="markers",
                                name="Flagged hours", marker=dict(color="#C84B42", size=7)))
    figure.add_hline(y=cutoff, line=dict(color="#B57712", dash="dash", width=2),
                     annotation_text="Cutoff", annotation_position="bottom right")
    figure.update_xaxes(title_text="Date in the validation period", type="date", tickformat="%b %d", nticks=6)
    figure.update_yaxes(title_text="Anomaly score", range=[low - padding, high + padding])
    style(figure, "Scores over time: above the line = review", 430)

    summary = pd.DataFrame([
        {"Decision": "No flag", "Rule": f"score < {cutoff:.6f}", "Validation hours": int((~flagged).sum())},
        {"Decision": "Flag for review", "Rule": f"score >= {cutoff:.6f}", "Validation hours": int(flagged.sum())},
    ])
    return figure, summary


def compare_models(scores: dict[str, pd.Series], share: float = REVIEW_SHARE) -> pd.DataFrame:
    rows = []
    for name, series in scores.items():
        if series.empty or not series.index.is_monotonic_increasing or not np.isfinite(series).all():
            raise ValueError("Expected finite, time-ordered validation scores.")
        if series.index.min() < config.DEV_START or series.index.max() >= config.DEV_END:
            raise ValueError("Model comparison must use validation-period scores only.")
        cutoff = float(series.quantile(1 - share))
        result = metrics.evaluate(series, cutoff, (config.DEV_START, config.DEV_END))
        rows.append({"Model": name, "Comparison cutoff": cutoff, "Alert hours": result["alert_hours"],
                     "Alert share (%)": 100 * result["alert_hours"] / result["scored_hours"],
                     "Reported events found": result["failures_detected"],
                     "False callouts": result["false_callouts"]})
    return pd.DataFrame(rows)


def choose_model(comparison: pd.DataFrame) -> str:
    ranked = comparison.sort_values(["Reported events found", "False callouts", "Model"],
                                    ascending=[False, True, True])
    return str(ranked.iloc[0]["Model"])


def cutoff_sweep(scores: pd.Series) -> pd.DataFrame:
    rows = []
    for share in [0.01, 0.02, 0.05]:
        row = compare_models({"Selected detector": scores}, share).iloc[0].to_dict()
        row["Alert allowance (%)"] = int(100 * share)
        rows.append(row)
    return pd.DataFrame(rows)[["Alert allowance (%)", "Comparison cutoff", "Alert hours",
                               "Reported events found", "False callouts"]]


def alert_map(matrix: pd.DataFrame, scores: pd.Series, cutoff: float):
    frame = matrix[["load_share", "oil_temp_mean"]].copy()
    frame["Working time (%)"] = frame["load_share"] * 100
    frame["Model route"] = np.where(scores >= cutoff, "Anomaly flag", "No flag")
    figure = px.scatter(frame, x="Working time (%)", y="oil_temp_mean", color="Model route", symbol="Model route",
                        color_discrete_map={"Anomaly flag": "#C84B42", "No flag": "#8A9299"},
                        labels={"oil_temp_mean": "Oil temperature (C)",
                            "Working time (%)": "Compressor working (%)"}, render_mode="svg")
    figure.update_traces(marker_size=6, opacity=0.7)
    return style(figure, "Which later hours get flagged?", 430)


def event_table(scores: pd.Series, cutoff: float, window) -> pd.DataFrame:
    result = metrics.evaluate(scores, cutoff, window)
    rows = []
    for name, start, end, _ in config.failure_windows():
        if not window[0] <= start < window[1]:
            continue
        detail = result["per_failure"][name]
        first = pd.Timestamp(detail["first_alert"]) if detail.get("first_alert") else None
        rows.append({"Event": name, "Reported onset": str(start), "Detected": bool(detail.get("detected")),
                     "First flagged hour": str(first) if first is not None else "No flag",
                     "Recorded lead (h)": detail.get("lead_hours"),
                     "Lead after hour ends (h)": round((start - first - pd.Timedelta(hours=1)).total_seconds() / 3600, 1)
                     if first is not None else None})
    return pd.DataFrame(rows)


def event_timeline(scores: pd.Series, cutoff: float, event: str = "F4"):
    name, start, end, _ = next(failure for failure in config.failure_windows() if failure[0] == event)
    stamps = pd.date_range(start.floor("h") - pd.Timedelta(hours=24), end.ceil("h") + pd.Timedelta(hours=6), freq="h")
    values = scores.reindex(stamps)
    hours = (stamps - start).total_seconds() / 3600
    figure = go.Figure(go.Scatter(x=hours, y=values, mode="lines+markers", line_color="#167D9A",
                                  connectgaps=False, name="Anomaly score"))
    figure.add_hline(y=cutoff, line_dash="dash", annotation_text="Cutoff")
    figure.add_vrect(x0=0, x1=(end - start).total_seconds() / 3600,
                     fillcolor="#C84B42", opacity=0.12, line_width=0)
    figure.update_xaxes(title_text="Hours from reported onset")
    figure.update_yaxes(title_text="Anomaly score")
    return style(figure, f"Inspect the {name} alert timing", 390)


def hourly_agreement(scores: pd.Series, cutoff: float, window):
    series = scores.loc[(scores.index >= window[0]) & (scores.index < window[1])]
    inside = pd.Series(False, index=series.index)
    for name, start, end, _ in config.failure_windows():
        inside |= (series.index < end) & (series.index + pd.Timedelta(hours=1) > start)
    _, ambiguous = metrics.window_masks(series.index)
    outside = ~ambiguous
    flagged = series >= cutoff
    counts = np.array([[int((inside & flagged).sum()), int((inside & ~flagged).sum())],
                       [int((outside & flagged).sum()), int((outside & ~flagged).sum())]])
    figure = go.Figure(go.Heatmap(z=counts, x=["Flag", "No flag"],
        y=["Reported event", "Outside buffer"], text=counts.astype(str), texttemplate="%{text}",
        colorscale=[[0, "#EFF5F4"], [1, "#167D9A"]], showscale=False,
        hovertemplate="%{y}<br>%{x}: %{z} hours<extra></extra>"))
    figure.update_yaxes(autorange="reversed")
    return style(figure, "Alerts versus event reports", 330), int((~inside & ~outside).sum())


def drift_plot(scores: pd.Series, cutoff: float):
    rows = []
    for month in pd.period_range("2020-04", "2020-08", freq="M"):
        result = metrics.evaluate(scores, cutoff, (month.start_time, (month + 1).start_time))
        rows.append({"Month": str(month), "False callouts": result["false_callouts"]})
    frame = pd.DataFrame(rows)
    figure = px.bar(frame, x="Month", y="False callouts", text="False callouts", color_discrete_sequence=["#167D9A"])
    return style(figure, "Watch alert workload over time")


def prediction_timeline(scores: pd.Series, cutoff: float, window):
    start, end = map(pd.Timestamp, window)
    if start >= end or not np.isfinite(cutoff):
        raise ValueError("A finite cutoff and increasing time window are required.")
    if not isinstance(scores.index, pd.DatetimeIndex) or scores.index.has_duplicates:
        raise ValueError("Scores need unique datetime timestamps.")
    if not scores.index.equals(scores.index.floor("h")):
        raise ValueError("Scores must use hour-start timestamps.")
    stamps = pd.date_range(start, end, freq="h", inclusive="left")
    aligned = scores.reindex(stamps)
    if np.isinf(aligned.to_numpy()).any():
        raise ValueError("Scores cannot be infinite.")
    predicted = (aligned >= cutoff).astype(float).where(aligned.notna())
    reported = pd.Series(0, index=stamps, dtype=int)
    events = [event for event in config.failure_windows() if event[1] < end and event[2] > start]
    for name, onset, finish, _ in events:
        reported.loc[(stamps < finish) & (stamps + pd.Timedelta(hours=1) > onset)] = 1
    table = pd.DataFrame({"Score": aligned, "Cutoff": cutoff,
                          "Model flag": predicted, "Reported event": reported})
    table.index.name = "Hour beginning"

    figure = make_subplots(rows=3, cols=1, shared_xaxes=True,
                           row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.12,
                           subplot_titles=["Anomaly score and cutoff", "Model prediction", "Maintenance report"])
    figure.add_trace(go.Scatter(x=stamps, y=aligned, mode="lines", line_color="#167D9A",
        connectgaps=False, name="Anomaly score",
        hovertemplate="%{x|%b %d, %H:%M}<br>Score: %{y:.4f}<extra></extra>"), row=1, col=1)
    figure.add_trace(go.Scatter(x=[start, end], y=[cutoff, cutoff], mode="lines",
        line=dict(color="#B57712", dash="dash"), name="Frozen cutoff",
        hovertemplate="Cutoff: %{y:.6f}<extra></extra>"), row=1, col=1)
    figure.add_trace(go.Scatter(x=stamps, y=predicted, mode="lines+markers",
        line=dict(color="#C84B42", shape="hv"), marker_size=4, connectgaps=False,
        name="Model flag", hovertemplate="%{x|%b %d, %H:%M}<br>Model flag: %{y:.0f}<extra></extra>"), row=2, col=1)
    figure.add_trace(go.Scatter(x=stamps, y=reported, mode="lines+markers",
        line=dict(color="#26834A", shape="hv"), marker_size=4, name="Reported event",
        hovertemplate="%{x|%b %d, %H:%M}<br>Report overlaps hour: %{y:.0f}<extra></extra>"), row=3, col=1)
    for name, onset, finish, _ in events:
        for row in [1, 2, 3]:
            figure.add_vrect(x0=max(onset, start), x1=min(finish, end), row=row, col=1,
                             fillcolor="#26834A", opacity=0.10, line_width=0)
    for row in [2, 3]:
        figure.update_yaxes(range=[-0.15, 1.15], tickvals=[0, 1], ticktext=["0", "1"], row=row, col=1)
    figure.update_yaxes(title_text="Score", row=1, col=1)
    figure.update_yaxes(title_text="Flag", row=2, col=1)
    figure.update_yaxes(title_text="Report", row=3, col=1)
    figure.update_xaxes(type="date", tickformat="%b %d<br>%H:%M", nticks=5)
    focus_start = max(start, events[0][1].normalize() - pd.Timedelta(days=8)) if events else start
    focus_end = min(end, events[0][2].normalize() + pd.Timedelta(days=2)) if events else end
    figure.update_xaxes(range=[focus_start, focus_end])
    full_range = {f"{axis}.range": [start, end] for axis in ["xaxis", "xaxis2", "xaxis3"]}
    focus_range = {f"{axis}.range": [focus_start, focus_end] for axis in ["xaxis", "xaxis2", "xaxis3"]}
    figure.update_layout(updatemenus=[dict(type="buttons", direction="right", x=0, y=1.07,
        xanchor="left", yanchor="bottom", font_size=12, buttons=[
            dict(label="Example days", method="relayout", args=[focus_range]),
            dict(label="Full test", method="relayout", args=[full_range])])])
    figure.update_xaxes(title_text="Date and time (hour beginning)", row=3, col=1)
    figure.update_annotations(font_size=13)
    style(figure, "Predictions and reports over time", 660)
    figure.update_layout(margin=dict(l=55, r=20, t=125, b=75), showlegend=False,
                         hovermode="x unified", title=dict(y=0.985, yanchor="top"))
    return figure, table


def prediction_examples(matrix: pd.DataFrame, scores: pd.Series, cutoff: float) -> pd.DataFrame:
    report_hours = pd.Series(False, index=matrix.index)
    for name, start, end, _ in config.failure_windows():
        report_hours |= (matrix.index < end) & (matrix.index + pd.Timedelta(hours=1) > start)
    _, ambiguous = metrics.window_masks(matrix.index)
    outside = scores.loc[~ambiguous]
    during = scores.loc[report_hours]
    candidates = [("Low-score example", outside.idxmin()),
                  ("Reported-event example", during.idxmax()),
                  ("High score without nearby report", outside.idxmax())]
    rows = []
    for label, stamp in candidates:
        rows.append({"Example": label, "Hour": str(stamp), "Anomaly score": float(scores.loc[stamp]),
                     "Flag": bool(scores.loc[stamp] >= cutoff),
                     "Report overlaps hour": bool(report_hours.loc[stamp]),
                     "Working share (%)": 100 * matrix.loc[stamp, "load_share"],
                     "Oil temperature (C)": matrix.loc[stamp, "oil_temp_mean"]})
    return pd.DataFrame(rows)


def feature_comparison(training: pd.DataFrame, example: pd.Series) -> pd.DataFrame:
    if list(training.columns) != config.MODEL_FEATURES or list(example.index) != config.MODEL_FEATURES:
        raise ValueError("Training and example features must use the configured order.")
    low, high = training.quantile(0.25), training.quantile(0.75)

    def formatted(feature: str, value: float) -> str:
        multiplier, unit = FEATURE_FORMATS[feature]
        scaled = value * multiplier
        decimals = 1 if feature not in {"tp3_std", "pressure_fall_rate"} else 3
        return f"{scaled:.{decimals}f}{unit}"

    rows = []
    for feature in config.MODEL_FEATURES:
        value = float(example[feature])
        reading = ("Higher than typical" if value > high[feature]
                   else "Lower than typical" if value < low[feature]
                   else "Within typical range")
        rows.append({"Measurement": FEATURE_LABELS[feature],
                     "Typical range": f"{formatted(feature, low[feature])} to {formatted(feature, high[feature])}",
                     "This hour": formatted(feature, value), "Compared with typical": reading})
    return pd.DataFrame(rows)


def feature_context(training: pd.DataFrame, example: pd.Series):
    lower, upper = training.quantile(0.25), training.quantile(0.75)
    middle = training.median()
    scale = (upper - lower).replace(0, np.nan)
    positions = (example - middle) / scale
    if not np.isfinite(positions).all():
        raise ValueError("Feature-context plot needs nonzero training interquartile ranges.")
    figure = go.Figure()
    for feature in reversed(config.MODEL_FEATURES):
        figure.add_trace(go.Scatter(x=[(lower[feature] - middle[feature]) / scale[feature],
                                       (upper[feature] - middle[feature]) / scale[feature]],
                                   y=[FEATURE_LABELS[feature]] * 2, mode="lines",
                                   line=dict(color="#B7C5CA", width=14), showlegend=False))
    figure.add_trace(go.Scatter(x=positions.reindex(list(reversed(config.MODEL_FEATURES))),
                               y=[FEATURE_LABELS[feature] for feature in reversed(config.MODEL_FEATURES)],
                               mode="markers", marker=dict(color="#C84B42", size=9), name="Selected hour"))
    figure.add_vline(x=0, line_dash="dot")
    figure.update_xaxes(title_text="Distance (IQR units)")
    figure.update_layout(showlegend=False)
    return style(figure, "Check the flagged measurements", 430)