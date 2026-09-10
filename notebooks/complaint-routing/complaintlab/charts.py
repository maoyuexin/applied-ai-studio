"""Plotly figures shared by the executable notebook and the offline HTML.

Every figure aggregates before plotting - bars, binned histograms, and curves,
never tens of thousands of raw points. Colors follow the palette in ``config``
so the course's charts read as one family, and no figure relies on color alone:
each one repeats its message in a label, a text mark, or an axis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config


def _layout(figure: go.Figure, title: str, height: int = 440) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=70, r=40, t=80, b=70),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


# ── Stage 1 ─────────────────────────────────────────────────────────────────

def narrative_volume() -> go.Figure:
    """Narrative complaints per year in the source database (not the sample)."""
    years = list(config.SOURCE_NARRATIVE_ROWS_PER_YEAR)
    counts = [config.SOURCE_NARRATIVE_ROWS_PER_YEAR[year] for year in years]
    in_window = [year != "2022" for year in years]
    figure = go.Figure(
        go.Bar(
            x=years,
            y=counts,
            marker_color=[
                config.COLOR_PRIMARY if keep else config.COLOR_MUTED for keep in in_window
            ],
            text=[f"{count / 1000:,.0f}k" for count in counts],
            textposition="outside",
            hovertemplate="%{x}<br>%{y:,} complaints with a narrative<extra></extra>",
        )
    )
    figure.add_annotation(
        x="2022", y=config.SOURCE_NARRATIVE_ROWS_PER_YEAR["2022"],
        text="2022: outside our window (grey)", showarrow=True, arrowhead=2,
        ax=10, ay=-60, font=dict(size=12, color="#5A5F6B"),
    )
    figure.update_yaxes(title="Complaints carrying a written narrative", rangemode="tozero")
    figure.update_xaxes(title="Year the complaint was received")
    return _layout(
        figure,
        "Complaint narratives roughly quadrupled between 2022 and 2025",
        height=430,
    )


# ── Stage 2 ─────────────────────────────────────────────────────────────────

def team_distribution(counts: pd.DataFrame) -> go.Figure:
    """Stacked bar per team: how the committed sample divides across splits."""
    ordered = counts.sort_values("total", ascending=False)
    figure = go.Figure()
    series = [
        ("train", config.COLOR_PRIMARY),
        ("validation", config.COLOR_WARN),
        ("test", config.COLOR_ACCENT),
    ]
    for name, color in series:
        figure.add_bar(
            x=ordered["Team"],
            y=ordered[name],
            name=name,
            marker_color=color,
            hovertemplate="%{x}<br>" + name + ": %{y:,} complaints<extra></extra>",
        )
    for _, row in ordered.iterrows():
        figure.add_annotation(
            x=row["Team"], y=row["total"], text=f"{row['total']:,}",
            showarrow=False, yshift=12, font=dict(size=12),
        )
    figure.update_layout(barmode="stack", legend_title_text="Split")
    # Explicit headroom so the printed totals cannot collide with the plot edge.
    figure.update_yaxes(
        title="Complaints in the committed sample", range=[0, ordered["total"].max() * 1.12]
    )
    figure.update_xaxes(title="Specialist team (the label the model predicts)")
    return _layout(
        figure,
        "Even after the cap, credit reporting is 1.5x debt collection and 8.9x student loans",
        height=470,
    )


def duplicate_share_by_team() -> go.Figure:
    """Share of each team's window rows that were exact copies of an earlier row."""
    teams = sorted(
        config.DEDUPE_SHARE_BY_TEAM, key=config.DEDUPE_SHARE_BY_TEAM.get, reverse=True
    )
    shares = [config.DEDUPE_SHARE_BY_TEAM[team] for team in teams]
    rows = [config.DEDUPE_TEAM_ROWS_IN_WINDOW[team] for team in teams]
    figure = go.Figure(
        go.Bar(
            x=teams,
            y=shares,
            marker_color=[
                config.COLOR_ALERT if share >= 0.20 else config.COLOR_MUTED for share in shares
            ],
            text=[f"{share:.1%}" for share in shares],
            textposition="outside",
            customdata=np.stack([rows], axis=-1),
            hovertemplate=(
                "%{x}<br>%{y:.1%} of rows were exact copies"
                "<br>out of %{customdata[0]:,} rows in the window<extra></extra>"
            ),
        )
    )
    figure.add_hline(
        y=config.DEDUPE_SHARE_REMOVED, line_color=config.COLOR_ACCENT,
        line_width=2, line_dash="dash",
        annotation_text=f"all teams together: {config.DEDUPE_SHARE_REMOVED:.1%}",
        annotation_position="top right",
    )
    figure.update_yaxes(
        title="Share of the team's rows that repeated an earlier narrative",
        tickformat=".0%", range=[0, 0.62],
    )
    figure.update_xaxes(title="Specialist team")
    return _layout(
        figure,
        "Template letters concentrate in credit reporting: one in two rows repeats another",
        height=470,
    )


def narrative_length(train: pd.DataFrame, display_cap: int = 6000) -> go.Figure:
    """Histogram of narrative length in characters, with the tail cut for display."""
    lengths = train[config.TEXT_COLUMN].str.len()
    beyond = int((lengths > display_cap).sum())
    shown = lengths.clip(upper=display_cap)
    edges = np.arange(0, display_cap + 150, 150)
    tallest = int(np.histogram(shown, bins=edges)[0].max())
    figure = go.Figure(
        go.Histogram(
            x=shown,
            xbins=dict(start=0, end=display_cap, size=150),
            marker_color=config.COLOR_PRIMARY,
            hovertemplate="around %{x:,.0f} characters<br>%{y:,} complaints<extra></extra>",
            name="training complaints",
        )
    )
    figure.add_vline(
        x=float(lengths.median()), line_color=config.COLOR_ACCENT, line_width=3,
    )
    figure.add_annotation(
        x=float(lengths.median()), y=tallest * 1.16, text=f"median {lengths.median():,.0f} characters",
        showarrow=True, arrowhead=2, ax=70, ay=0,
        font=dict(size=12, color=config.COLOR_ACCENT),
    )
    figure.add_annotation(
        x=display_cap * 0.68, y=tallest * 0.72, showarrow=False,
        text=(f"{beyond:,} complaints are longer than {display_cap:,} characters"
              "<br>and are drawn in the last bar"),
        font=dict(size=12, color="#5A5F6B"), align="left",
    )
    figure.update_xaxes(title=f"Characters in the narrative (display capped at {display_cap:,})")
    # Headroom above the tallest bin keeps the median callout clear of the bars.
    figure.update_yaxes(title="Training complaints", range=[0, tallest * 1.26])
    return _layout(figure, "Most complaints are short; a long tail runs to 32,609 characters",
                   height=440)


# ── Stage 3 ─────────────────────────────────────────────────────────────────

def leaderboard_chart(leaderboard: pd.DataFrame) -> go.Figure:
    """Validation accuracy and macro-F1 for every compared candidate."""
    labels = [name.replace(" + ", "<br>+ ") for name in leaderboard["Model"]]
    figure = go.Figure()
    figure.add_bar(
        x=labels, y=leaderboard["Validation accuracy"], name="Accuracy",
        marker_color=config.COLOR_PRIMARY,
        text=[f"{value:.1%}" for value in leaderboard["Validation accuracy"]],
        textposition="outside",
        hovertemplate="%{x}<br>accuracy %{y:.2%}<extra></extra>",
    )
    figure.add_bar(
        x=labels, y=leaderboard["Validation macro-F1"], name="Macro-F1",
        marker_color=config.COLOR_WARN,
        text=[f"{value:.3f}" for value in leaderboard["Validation macro-F1"]],
        textposition="outside",
        hovertemplate="%{x}<br>macro-F1 %{y:.3f}<extra></extra>",
    )
    figure.update_layout(barmode="group", legend_title_text="Measure")
    figure.update_yaxes(title="Score on the same 8,728 validation complaints",
                        tickformat=".0%", range=[0, 1.0])
    figure.update_xaxes(title="")
    return _layout(
        figure,
        "Every bar is the same validation split; only the model changes",
        height=490,
    )


# ── Stage 4 ─────────────────────────────────────────────────────────────────

def per_team_precision_recall(per_team: pd.DataFrame) -> go.Figure:
    """Precision and recall side by side for each team (macro row excluded)."""
    teams = per_team[per_team["Team"] != "macro average"].sort_values("Recall")
    figure = go.Figure()
    figure.add_bar(
        y=teams["Team"], x=teams["Precision"], name="Precision", orientation="h",
        marker_color=config.COLOR_PRIMARY,
        hovertemplate="%{y}<br>precision %{x:.1%}<extra></extra>",
    )
    figure.add_bar(
        y=teams["Team"], x=teams["Recall"], name="Recall", orientation="h",
        marker_color=config.COLOR_WARN,
        customdata=np.stack([teams["Complaints in the split"]], axis=-1),
        hovertemplate="%{y}<br>recall %{x:.1%}<br>%{customdata[0]:,} complaints<extra></extra>",
    )
    figure.update_layout(barmode="group", legend_title_text="Measure")
    figure.update_xaxes(title="Rate (both run 0% to 100%)", tickformat=".0%", range=[0, 1.0])
    figure.update_yaxes(title="")
    return _layout(
        figure,
        "Loans is the weakest team: the model finds only 64% of the loan complaints",
        height=500,
    )


def confidence_distribution(
    confidence: np.ndarray, correct: np.ndarray, threshold: float = config.CONFIDENCE_THRESHOLD
) -> go.Figure:
    """Where correct and wrong predictions sit on the confidence scale."""
    correct = np.asarray(correct, bool)
    edges = np.arange(0, 1.025, 0.025)
    tallest = int(
        max(
            np.histogram(confidence[correct], bins=edges)[0].max(),
            np.histogram(confidence[~correct], bins=edges)[0].max(),
        )
    )
    figure = go.Figure()
    figure.add_histogram(
        x=confidence[correct], name="model was right",
        xbins=dict(start=0, end=1.0, size=0.025),
        marker_color=config.COLOR_PRIMARY, opacity=0.75,
        hovertemplate="confidence around %{x:.2f}<br>%{y:,} correct<extra></extra>",
    )
    figure.add_histogram(
        x=confidence[~correct], name="model was wrong",
        xbins=dict(start=0, end=1.0, size=0.025),
        marker_color=config.COLOR_ALERT, opacity=0.75,
        hovertemplate="confidence around %{x:.2f}<br>%{y:,} wrong<extra></extra>",
    )
    figure.add_vline(
        x=threshold, line_color=config.COLOR_ACCENT, line_width=3,
        annotation_text=f"threshold {threshold}", annotation_position="top right",
    )
    figure.add_annotation(
        x=0.26, y=tallest * 1.12, showarrow=False,
        text="left of the line -> human triage", font=dict(size=12, color="#5A5F6B"),
    )
    figure.add_annotation(
        x=0.78, y=tallest * 1.12, showarrow=False,
        text="right of the line -> auto-routed", font=dict(size=12, color="#5A5F6B"),
    )
    figure.update_layout(barmode="overlay", legend_title_text="Outcome")
    figure.update_xaxes(title="Confidence (the model's highest team probability)", range=[0, 1])
    # Headroom above the tallest bin so the two callouts never touch a bar.
    figure.update_yaxes(title="Validation complaints", range=[0, tallest * 1.22])
    return _layout(
        figure,
        "Wrong answers cluster at low confidence - which is what makes a threshold work",
        height=460,
    )


def threshold_sweep_chart(sweep: pd.DataFrame, chosen: float) -> go.Figure:
    """Coverage and accuracy-among-auto-routed against the candidate thresholds."""
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(
            x=sweep["threshold"], y=sweep["coverage"], mode="lines+markers",
            name="Coverage (share auto-routed)",
            line=dict(color=config.COLOR_WARN, width=3),
            hovertemplate="threshold %{x}<br>%{y:.1%} of complaints auto-routed<extra></extra>",
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=sweep["threshold"], y=sweep["accuracy_among_auto_routed"], mode="lines+markers",
            name="Accuracy among the auto-routed",
            line=dict(color=config.COLOR_PRIMARY, width=3, dash="dot"),
            hovertemplate="threshold %{x}<br>%{y:.1%} of auto-routes correct<extra></extra>",
        ),
        secondary_y=True,
    )
    figure.add_vline(x=chosen, line_color=config.COLOR_ACCENT, line_width=3, line_dash="dash")
    row = sweep.loc[sweep["threshold"] == chosen].iloc[0]
    figure.add_annotation(
        x=chosen, y=row["coverage"],
        text=(f"frozen at {chosen}: {row['coverage']:.1%} auto-routed, "
              f"{row['accuracy_among_auto_routed']:.1%} of those correct"),
        showarrow=True, arrowhead=2, ax=95, ay=-55,
        font=dict(size=12, color=config.COLOR_ACCENT), align="left",
    )
    figure.add_hline(
        y=0.90, line_color=config.COLOR_MUTED, line_width=2, line_dash="dot", secondary_y=True,
        annotation_text="the 90% rule we set before looking", annotation_position="bottom left",
    )
    figure.update_xaxes(title="Confidence threshold for auto-routing")
    figure.update_yaxes(title="Coverage: auto-routed / all complaints", tickformat=".0%",
                        range=[0, 1.02], secondary_y=False)
    figure.update_yaxes(title="Accuracy: correct / auto-routed", tickformat=".0%",
                        range=[0.80, 1.0], secondary_y=True)
    figure.update_layout(legend=dict(orientation="h", y=-0.25))
    return _layout(
        figure,
        "Raising the threshold buys accuracy on the auto-routed stream and pays in coverage",
        height=520,
    )


def confusion_heatmap(frame: pd.DataFrame, population: str) -> go.Figure:
    """True team (rows) against predicted team (columns), counts in the cells."""
    values = frame.to_numpy()
    off_diagonal = values.copy()
    np.fill_diagonal(off_diagonal, 0)
    figure = go.Figure(
        go.Heatmap(
            z=off_diagonal,
            x=list(frame.columns),
            y=list(frame.index),
            text=values,
            texttemplate="%{text:,}",
            colorscale=[[0, "#FFFFFF"], [0.35, "#FBD3CB"], [1, config.COLOR_ALERT]],
            showscale=True,
            colorbar=dict(title="Complaints<br>sent to the<br>wrong team", thickness=14, len=0.75),
            hovertemplate="belonged to %{y}<br>model said %{x}<br>%{text:,} complaints<extra></extra>",
        )
    )
    figure.update_xaxes(title="Team the model chose", side="bottom", tickangle=-35)
    figure.update_yaxes(title="Team the complaint actually belonged to", autorange="reversed")
    return _layout(
        figure,
        f"Where the {population} complaints landed (shading shows mistakes only)",
        height=560,
    )


# ── Stage 5 ─────────────────────────────────────────────────────────────────

def routing_words_bar(words: pd.DataFrame, team: str, complaint_label: str) -> go.Figure:
    """The words that pushed one complaint toward the team the model chose."""
    ordered = words.sort_values("Push toward this team")
    figure = go.Figure(
        go.Bar(
            x=ordered["Push toward this team"],
            y=ordered["Word or phrase"],
            orientation="h",
            marker_color=config.TEAM_COLORS.get(team, config.COLOR_PRIMARY),
            text=[f"+{value:.2f}" for value in ordered["Push toward this team"]],
            textposition="outside",
            hovertemplate="%{y}<br>push toward " + team + ": +%{x:.3f}<extra></extra>",
        )
    )
    figure.update_xaxes(title=f"Push toward {team} (TF-IDF value x this team's weight)",
                        rangemode="tozero")
    figure.update_yaxes(title="")
    return _layout(
        figure,
        f"Why complaint {complaint_label} went to {team}",
        height=400,
    )
