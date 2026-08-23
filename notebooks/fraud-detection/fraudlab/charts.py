"""Every chart in the notebook, as a Plotly figure.

Charts are interactive by default: hover a bar and the value appears, drag to
zoom, click a legend entry to hide a series. Where a chart needs a control, it
uses Plotly's own buttons and range sliders rather than `ipywidgets`, because
Plotly controls survive an HTML export and widgets do not -- and the HTML export
is the artefact that gets used when the network is what failed.

Charts return figures and never call `.show()`, so the notebook decides how to
display them and a future service could reuse the same definitions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config

_LAYOUT = dict(template=config.PLOT_TEMPLATE, height=420, margin=dict(l=70, r=40, t=90, b=60))


def _binned(values, bins: int = 60, density: bool = False, rng=None):
    """Bin once, in numpy, and send the bins.

    Plotly's own `go.Histogram` ships every underlying value to the browser, so a
    chart of a million transactions embeds a million numbers in the notebook and
    stalls the projector. Sixty bin heights say the same thing.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.array([]), np.array([])
    counts, edges = np.histogram(values, bins=bins, range=rng, density=density)
    centres = (edges[:-1] + edges[1:]) / 2
    return centres, counts


def _box_stats(values) -> dict:
    """Five numbers instead of every point."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    return dict(
        q1=[q1], median=[med], q3=[q3],
        lowerfence=[max(values.min(), q1 - 1.5 * iqr)],
        upperfence=[min(values.max(), q3 + 1.5 * iqr)],
    )


def _title(text: str, subtitle: str | None = None) -> dict:
    full = text if subtitle is None else f"{text}<br><sup>{subtitle}</sup>"
    return dict(text=full, x=0.5, xanchor="center")


def class_balance(transactions: pd.DataFrame) -> go.Figure:
    """The imbalance, drawn twice.

    Shown side by side rather than behind a toggle: on a linear axis the fraud bar
    is a few pixels tall, and seeing that next to the log version is the whole
    point. Nobody has to click anything to get it.
    """
    counts = transactions["is_fraud"].value_counts().sort_index()
    legit, fraud = int(counts.get(0, 0)), int(counts.get(1, 0))
    total = legit + fraud

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Log scale — both visible",
                        "Linear scale — the fraud bar all but vanishes"],
    )
    for col in (1, 2):
        fig.add_trace(
            go.Bar(
                x=["Legitimate", "Fraud"], y=[legit, fraud],
                marker_color=[config.COLOR_LEGIT, config.COLOR_FRAUD],
                text=[f"{legit:,}<br>{legit/total:.2%}", f"{fraud:,}<br>{fraud/total:.2%}"],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{x}<br>Transactions: %{y:,}<extra></extra>",
            ),
            row=1, col=col,
        )

    fig.update_yaxes(type="log", title_text="Transactions", row=1, col=1)
    fig.update_yaxes(type="linear", title_text="Transactions", row=1, col=2)
    fig.update_layout(
        **{**_LAYOUT, "height": 440, "margin": dict(l=70, r=40, t=110, b=60)},
        title=_title(
            "Class balance",
            f"{fraud:,} frauds in {total:,} transactions &nbsp;·&nbsp; {fraud/total:.3%}",
        ),
        showlegend=False,
    )
    return fig


def amount_distribution(transactions: pd.DataFrame) -> go.Figure:
    """Raw amount beside log amount -- why the transform is not cosmetic."""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Transaction amount ($)", "log(1 + amount)"],
    )
    raw_x, raw_y = _binned(transactions["amt"], bins=70)
    log_x, log_y = _binned(np.log1p(transactions["amt"]), bins=70)

    fig.add_trace(
        go.Bar(x=raw_x, y=raw_y, marker_color=config.COLOR_LEGIT, name="amount",
               hovertemplate="around $%{x:,.0f}<br>%{y:,} transactions<extra></extra>"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(x=log_x, y=log_y, marker_color=config.COLOR_ACCENT, name="log amount",
               hovertemplate="log value %{x:.2f}<br>%{y:,} transactions<extra></extra>"),
        row=1, col=2,
    )
    fig.update_layout(
        **_LAYOUT, bargap=0.02,
        title=_title("Amount is heavily right-skewed",
                     "A handful of very large purchases stretch the axis and hide the shape"),
        showlegend=False,
    )
    return fig


def amount_by_class(transactions: pd.DataFrame) -> go.Figure:
    """The first real signal: fraud sits in a different, tighter band."""
    legit = np.log1p(transactions.loc[transactions["is_fraud"] == 0, "amt"])
    fraud = np.log1p(transactions.loc[transactions["is_fraud"] == 1, "amt"])
    span = (float(min(legit.min(), fraud.min())), float(max(legit.max(), fraud.max())))

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.62, 0.38],
        subplot_titles=["Distribution of log(amount) by class", "Same data, as a box plot"],
    )
    for values, name, color in ((legit, "Legitimate", config.COLOR_LEGIT),
                                (fraud, "Fraud", config.COLOR_FRAUD)):
        x, y = _binned(values, bins=60, density=True, rng=span)
        fig.add_trace(
            go.Bar(x=x, y=y, name=name, marker_color=color, opacity=0.65,
                   hovertemplate="log value %{x:.2f}<br>density %{y:.3f}<extra>" + name + "</extra>"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Box(name=name, marker_color=color, showlegend=False, **_box_stats(values)),
            row=1, col=2,
        )

    fig.update_layout(
        **_LAYOUT, barmode="overlay", bargap=0.02,
        title=_title("Fraudulent amounts are not drawn from the same distribution",
                     "Densities are normalised, because otherwise the 0.5% class is invisible"),
    )
    return fig


def rate_by_category(transactions: pd.DataFrame, column: str, label: str) -> go.Figure:
    """Fraud rate by a categorical column, sorted by rate with volume on the hover."""
    grouped = (
        transactions.groupby(column, observed=True)["is_fraud"]
        .agg(["mean", "size", "sum"])
        .rename(columns={"mean": "rate", "size": "transactions", "sum": "frauds"})
        .sort_values("rate", ascending=True)
        .reset_index()
    )
    fig = go.Figure(
        go.Bar(
            x=grouped["rate"], y=grouped[column].astype(str), orientation="h",
            marker=dict(color=grouped["rate"], colorscale="Reds", showscale=False),
            customdata=np.stack([grouped["transactions"], grouped["frauds"]], axis=-1),
            hovertemplate=(
                "<b>%{y}</b><br>Fraud rate: %{x:.3%}"
                "<br>Transactions: %{customdata[0]:,}"
                "<br>Frauds: %{customdata[1]:,}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 480},
        title=_title(f"Fraud rate by {label}",
                     "Sorted by rate. Hover for volume -- rate and volume disagree, and that matters"),
        xaxis=dict(title="Fraud rate", tickformat=".2%"),
        yaxis=dict(title=""),
    )
    return fig


def fraud_rate_by_hour(transactions: pd.DataFrame) -> go.Figure:
    """Twenty-four bars, and a night-time spike nobody had to be told about."""
    hourly = (
        transactions.assign(hour=transactions["trans_date_trans_time"].dt.hour)
        .groupby("hour")["is_fraud"]
        .agg(["mean", "size"])
        .rename(columns={"mean": "rate", "size": "transactions"})
        .reset_index()
    )
    overall = transactions["is_fraud"].mean()

    fig = go.Figure(
        go.Bar(
            x=hourly["hour"], y=hourly["rate"],
            marker_color=np.where(hourly["rate"] > overall, config.COLOR_FRAUD, config.COLOR_LEGIT),
            customdata=hourly["transactions"],
            hovertemplate="%{x}:00<br>Fraud rate: %{y:.3%}<br>Transactions: %{customdata:,}<extra></extra>",
        )
    )
    fig.add_hline(y=overall, line_dash="dash", line_color=config.COLOR_MUTED,
                  annotation_text=f"Overall {overall:.3%}", annotation_position="top right")
    fig.update_layout(
        **_LAYOUT,
        title=_title("Fraud rate by hour of day",
                     "Red bars sit above the overall rate. This is domain knowledge arriving from the data"),
        xaxis=dict(title="Hour of day (local)", dtick=2),
        yaxis=dict(title="Fraud rate", tickformat=".2%"),
    )
    return fig


def numeric_by_class(transactions: pd.DataFrame, column: str, label: str,
                     clip_quantile: float = 0.99) -> go.Figure:
    """The four-beat feature chart: distribution split by class, before and after."""
    cutoff = transactions[column].quantile(clip_quantile)
    df = transactions[transactions[column] <= cutoff]
    span = (float(df[column].min()), float(cutoff))

    fig = go.Figure()
    for flag, name, color in ((0, "Legitimate", config.COLOR_LEGIT), (1, "Fraud", config.COLOR_FRAUD)):
        x, y = _binned(df.loc[df["is_fraud"] == flag, column], bins=50, density=True, rng=span)
        fig.add_trace(
            go.Bar(x=x, y=y, name=name, marker_color=color, opacity=0.65,
                   hovertemplate=f"{label}: %{{x:,.2f}}<br>Density: %{{y:.4f}}<extra>{name}</extra>")
        )
    fig.update_layout(
        **{**_LAYOUT, "height": 360}, barmode="overlay", bargap=0.02,
        title=_title(label, f"Densities normalised · values above the {clip_quantile:.0%} percentile clipped for readability"),
        xaxis=dict(title=label), yaxis=dict(title="Density"),
    )
    return fig


def correlation_heatmap(corr: pd.DataFrame, method: str = "Pearson") -> go.Figure:
    """Feature-to-feature correlation. Its real job is spotting redundancy."""
    fig = go.Figure(
        go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.index, zmid=0,
            colorscale="RdBu_r", colorbar=dict(title=method, thickness=14),
            hovertemplate="%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 560, "margin": dict(l=170, r=60, t=90, b=150)},
        title=_title(f"{method} correlation between features",
                     "Look for redundant pairs, not for a relationship with the target"),
        xaxis=dict(tickangle=-45),
    )
    return fig


def association_bars(frame: pd.DataFrame, value_col: str, title: str, subtitle: str) -> go.Figure:
    """A ranked bar chart of feature-to-target association."""
    ordered = frame.sort_values(value_col, ascending=True)
    fig = go.Figure(
        go.Bar(
            x=ordered[value_col], y=ordered["Feature"], orientation="h",
            marker=dict(color=ordered[value_col], colorscale="Blues", showscale=False),
            hovertemplate="<b>%{y}</b><br>%{x:.5f}<extra></extra>",
        )
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 520, "margin": dict(l=210, r=70, t=90, b=60)},
        title=_title(title, subtitle), xaxis=dict(title=value_col), yaxis=dict(title=""),
    )
    return fig


def weekly_volume_and_rate(weekly: pd.DataFrame) -> go.Figure:
    """Volume and fraud rate over time, with a range slider.

    Drag the window across the two years and the fraud rate visibly moves. That is
    the argument for a time-ordered split, made before anything has been trained.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=weekly["trans_date_trans_time"], y=weekly["transactions"],
               name="Transactions", marker_color=config.COLOR_MUTED, opacity=0.55,
               hovertemplate="Week of %{x|%Y-%m-%d}<br>%{y:,} transactions<extra></extra>"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=weekly["trans_date_trans_time"], y=weekly["fraud_rate"],
                   name="Fraud rate", mode="lines", line=dict(color=config.COLOR_FRAUD, width=2),
                   hovertemplate="Week of %{x|%Y-%m-%d}<br>Fraud rate %{y:.3%}<extra></extra>"),
        secondary_y=True,
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 460},
        title=_title("Weekly volume and fraud rate",
                     "Drag the slider below. The rate moves, and we have not trained anything yet"),
        xaxis=dict(rangeslider=dict(visible=True), title=""),
        legend=dict(x=0.01, y=0.99),
    )
    fig.update_yaxes(title_text="Transactions per week", secondary_y=False)
    fig.update_yaxes(title_text="Fraud rate", tickformat=".2%", secondary_y=True)
    return fig


def split_timeline(parts: dict) -> go.Figure:
    """Monthly volume, coloured by which side of the split it fell on.

    Drawn as counts per month rather than as date ranges: it shows the order of
    the split *and* how much data is on each side, in one picture.
    """
    colors = {"train": config.COLOR_LEGIT, "test": config.COLOR_ACCENT}
    fig = go.Figure()

    for name, part in parts.items():
        monthly = (
            part.set_index("trans_date_trans_time")
            .resample("MS")
            .agg(transactions=("is_fraud", "size"), frauds=("is_fraud", "sum"))
            .reset_index()
        )
        fig.add_trace(
            go.Bar(
                x=monthly["trans_date_trans_time"], y=monthly["transactions"],
                name=f"{name} ({len(part):,} transactions)",
                marker_color=colors.get(name, config.COLOR_MUTED),
                customdata=monthly["frauds"],
                hovertemplate=("%{x|%b %Y}<br>%{y:,} transactions"
                               "<br>%{customdata:,} frauds<extra>" + name + "</extra>"),
            )
        )

    fig.update_layout(
        **{**_LAYOUT, "height": 380},
        title=_title("The split is made by date",
                     "The model learns from the blue months and is scored on the green ones"),
        xaxis=dict(title=""), yaxis=dict(title="Transactions per month"),
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def split_comparison(random_result: dict, time_result: dict) -> go.Figure:
    """What the random split buys you, and what it is actually worth."""
    labels = ["Precision", "Recall", "F1"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=[random_result[k.lower()] for k in labels], name="Random split (flattering)",
        marker_color=config.COLOR_WARN, text=[f"{random_result[k.lower()]:.1%}" for k in labels],
        textposition="outside"))
    fig.add_trace(go.Bar(
        x=labels, y=[time_result[k.lower()] for k in labels], name="Time-ordered split (honest)",
        marker_color=config.COLOR_LEGIT, text=[f"{time_result[k.lower()]:.1%}" for k in labels],
        textposition="outside"))
    fig.update_layout(
        **{**_LAYOUT, "height": 400},
        title=_title("The same model, scored two ways",
                     "The gap is the size of the lie a random split tells you"),
        yaxis=dict(title="Score at the review budget", tickformat=".0%", range=[0, 1.15]),
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def confusion_heatmap(result: dict, title: str = "Confusion matrix") -> go.Figure:
    """The four boxes. Everything else on the leaderboard is derived from these.

    Cells are coloured by what they *mean* -- caught, missed, interrupted, correctly
    cleared -- not by how big they are. Colouring by magnitude would paint the
    182,000 correctly-cleared transactions dark and everything else invisible,
    which is precisely the distortion this whole section is about.
    """
    counts = [[result["tp"], result["fn"]], [result["fp"], result["tn"]]]
    meaning = [[0, 3], [2, 1]]  # caught, missed / interrupted, cleared
    labels = [["Caught fraud<br>(true positive)", "Missed fraud<br>(false negative)"],
              ["Good customer stopped<br>(false positive)", "Correctly cleared<br>(true negative)"]]
    text = [[f"{labels[r][c]}<br><b>{counts[r][c]:,}</b>" for c in range(2)] for r in range(2)]

    fig = go.Figure(
        go.Heatmap(
            z=meaning, x=["Model flagged it", "Model cleared it"],
            y=["Actually fraud", "Actually clean"],
            text=text, texttemplate="%{text}", showscale=False,
            zmin=0, zmax=3,
            colorscale=[[0.0, "#C8E6C9"], [0.33, "#C8E6C9"],
                        [0.34, "#E8F5E9"], [0.66, "#E8F5E9"],
                        [0.67, "#FFE0B2"], [0.99, "#FFE0B2"],
                        [1.0, "#FFCDD2"]],
            customdata=counts,
            hovertemplate="%{y} / %{x}<br>%{customdata:,} transactions<extra></extra>",
        )
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 420},
        title=_title(
            title,
            f"Precision {result['precision']:.1%} &nbsp;·&nbsp; Recall {result['recall']:.1%} "
            f"&nbsp;·&nbsp; Accuracy {result['accuracy']:.2%} "
            f"&nbsp;·&nbsp; {result['flagged']:,} sent to review",
        ),
        xaxis=dict(side="top"),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def leaderboard_chart(leaderboard: pd.DataFrame) -> go.Figure:
    """Recall beside precision -- what you catch, and what it costs to catch it."""
    ordered = leaderboard.sort_values("Recall")
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                        subplot_titles=["Recall — of all fraud, how much we caught",
                                        "Precision — of our flags, how many were real"])
    fig.add_trace(
        go.Bar(x=ordered["Recall"], y=ordered["Model"], orientation="h",
               marker_color=config.COLOR_ACCENT, text=ordered["Recall"].map("{:.1%}".format),
               textposition="outside", showlegend=False, cliponaxis=False,
               hovertemplate="<b>%{y}</b><br>Recall %{x:.2%}<extra></extra>"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(x=ordered["Precision"], y=ordered["Model"], orientation="h",
               marker_color=config.COLOR_WARN, text=ordered["Precision"].map("{:.1%}".format),
               textposition="outside", showlegend=False, cliponaxis=False,
               hovertemplate="<b>%{y}</b><br>Precision %{x:.2%}<extra></extra>"),
        row=1, col=2,
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 430, "margin": dict(l=170, r=70, t=100, b=60)},
        title=_title("Every model, judged at the same 3% review budget",
                     "Same data, same treatment, same number of analyst-minutes to spend"),
    )
    fig.update_xaxes(tickformat=".0%", range=[0, 1.1], row=1, col=1)
    fig.update_xaxes(tickformat=".0%", range=[0, 0.3], row=1, col=2)
    return fig


def balancing_chart(bakeoff: pd.DataFrame) -> go.Figure:
    """Five treatments, same model family, judged on caught versus interrupted."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=bakeoff["Treatment"], y=bakeoff["Recall"], name="Recall",
               marker_color=config.COLOR_ACCENT, text=bakeoff["Recall"].map("{:.1%}".format),
               textposition="outside"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=bakeoff["Treatment"], y=bakeoff["Precision"], name="Precision",
                   mode="markers+lines", marker=dict(size=11, color=config.COLOR_FRAUD),
                   line=dict(color=config.COLOR_FRAUD, dash="dot")),
        secondary_y=True,
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 430},
        title=_title("Class balancing bake-off",
                     "Same model, same split, same budget -- only the balancing treatment changes"),
        legend=dict(x=0.01, y=0.99),
    )
    fig.update_yaxes(title_text="Recall", tickformat=".0%", range=[0, 1.15], secondary_y=False)
    fig.update_yaxes(title_text="Precision", tickformat=".0%", secondary_y=True)
    return fig


def threshold_sweep_chart(sweep: pd.DataFrame, chosen: float | None = None) -> go.Figure:
    """Precision against recall against cost, as the threshold moves."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=sweep["review_rate"], y=sweep["recall"], name="Recall (fraud caught)",
                   mode="lines", line=dict(color=config.COLOR_ACCENT, width=2),
                   hovertemplate="Review %{x:.2%}<br>Recall %{y:.1%}<extra></extra>"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=sweep["review_rate"], y=sweep["precision"], name="Precision (of those flagged)",
                   mode="lines", line=dict(color=config.COLOR_FRAUD, width=2),
                   hovertemplate="Review %{x:.2%}<br>Precision %{y:.1%}<extra></extra>"),
        secondary_y=False,
    )
    if "dollars_missed" in sweep:
        fig.add_trace(
            go.Scatter(x=sweep["review_rate"], y=sweep["dollars_missed"], name="Fraud $ missed",
                       mode="lines", line=dict(color=config.COLOR_MUTED, width=2, dash="dot"),
                       hovertemplate="Review %{x:.2%}<br>$%{y:,.0f} missed<extra></extra>"),
            secondary_y=True,
        )
    if chosen is not None:
        fig.add_vline(x=chosen, line_dash="dash", line_color="#444",
                      annotation_text=f"budget {chosen:.0%}", annotation_position="top right")

    fig.update_layout(
        **{**_LAYOUT, "height": 460},
        title=_title("The threshold is a business decision wearing technical clothing",
                     "Nothing in the mathematics says where it belongs -- only the cost of a "
                     "blocked customer against the cost of a chargeback"),
        xaxis=dict(title="Share of transactions sent to a human", tickformat=".1%"),
        legend=dict(x=0.55, y=0.99),
    )
    fig.update_yaxes(title_text="Rate", tickformat=".0%", secondary_y=False)
    fig.update_yaxes(title_text="Fraud value missed ($)", secondary_y=True)
    return fig


def weekly_performance_chart(weekly: pd.DataFrame) -> go.Figure:
    """Precision and recall week by week -- what monitoring actually watches."""
    fig = go.Figure()
    for col, name, color in (("recall", "Recall", config.COLOR_ACCENT),
                             ("precision", "Precision", config.COLOR_FRAUD)):
        fig.add_trace(
            go.Scatter(x=weekly["trans_date_trans_time"], y=weekly[col], name=name,
                       mode="lines+markers", line=dict(color=color, width=2),
                       hovertemplate=f"Week of %{{x|%Y-%m-%d}}<br>{name} %{{y:.1%}}<extra></extra>")
        )
    fig.update_layout(
        **{**_LAYOUT, "height": 400},
        title=_title("Performance week by week across the held-out period",
                     "A model is not finished when it is accurate. It is finished when somebody can watch it"),
        yaxis=dict(title="Rate", tickformat=".0%", range=[0, 1.05]),
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def score_distribution(scores, threshold: float) -> go.Figure:
    """Where the model put today's transactions, and where the cut falls."""
    scores = np.asarray(scores, dtype=float)
    x, y = _binned(scores, bins=60, rng=(0.0, 1.0))
    colors = [config.COLOR_FRAUD if centre >= threshold else config.COLOR_LEGIT for centre in x]

    fig = go.Figure(
        go.Bar(x=x, y=y, marker_color=colors,
               hovertemplate="Score around %{x:.2f}<br>%{y:,} transactions<extra></extra>")
    )
    fig.add_vline(x=threshold, line_dash="dash", line_color="#444",
                  annotation_text=f"review above {threshold:.3f}",
                  annotation_position="top right")
    flagged = int((scores >= threshold).sum())
    fig.update_layout(
        **{**_LAYOUT, "height": 380}, bargap=0.02,
        title=_title("Where the model placed this batch",
                     f"{flagged:,} of {len(scores):,} transactions land above the cut "
                     f"and go to a human"),
        xaxis=dict(title="Fraud score"), yaxis=dict(title="Transactions", type="log"),
        showlegend=False,
    )
    return fig


def label_maturity_chart(summary: pd.DataFrame) -> go.Figure:
    """How much of the history can actually be trained on today."""
    fig = go.Figure(
        go.Bar(
            x=summary["Transactions"], y=summary["Bucket"], orientation="h",
            marker_color=[config.COLOR_LEGIT, config.COLOR_WARN],
            text=summary["Share"].map("{:.1%}".format), textposition="outside",
            hovertemplate="%{y}<br>%{x:,} transactions<extra></extra>",
        )
    )
    fig.update_layout(
        **{**_LAYOUT, "height": 300, "margin": dict(l=330, r=90, t=90, b=60)},
        title=_title("What actually carries a trustworthy label today",
                     f"A chargeback is confirmed about {config.LABEL_LAG_DAYS} days after the transaction"),
        xaxis=dict(title="Transactions"), yaxis=dict(title=""),
    )
    return fig
