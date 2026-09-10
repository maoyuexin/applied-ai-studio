"""Plotly figures shared by the executable notebook and the offline HTML.

Every figure aggregates before plotting: bars, binned heatmaps, and curves,
never tens of thousands of raw points. Colors follow the fraud-lab palette in
``config`` so the course's charts read as one family.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config, data, metrics


def _layout(figure: go.Figure, title: str, height: int = 430) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=60, r=30, t=70, b=60),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


# ── Stage 2 ─────────────────────────────────────────────────────────────────

def class_balance(summary: pd.DataFrame) -> go.Figure:
    """Stacked bar per split: paid vs missed-payment accounts."""
    figure = go.Figure()
    paid = summary["Accounts"] - summary["Missed next payment"]
    figure.add_bar(
        x=summary["Split"], y=paid, name="Paid October 2005",
        marker_color=config.COLOR_REPAID,
        hovertemplate="%{x}<br>%{y:,} accounts paid<extra></extra>",
    )
    figure.add_bar(
        x=summary["Split"], y=summary["Missed next payment"], name="Missed October 2005",
        marker_color=config.COLOR_DEFAULT,
        customdata=np.stack([summary["Default rate"]], axis=-1),
        hovertemplate="%{x}<br>%{y:,} accounts missed<br>%{customdata[0]:.1%} of split<extra></extra>",
    )
    figure.update_layout(barmode="stack", legend_title_text="Next-month outcome")
    figure.update_yaxes(title="Accounts")
    figure.update_xaxes(title="Split")
    return _layout(figure, "Stratification keeps the 22.1% default rate identical in all three splits")


def delinquency_gradient(train_df: pd.DataFrame) -> go.Figure:
    """Default rate by current repayment status (PAY_0), training accounts."""
    status = np.clip(train_df["PAY_0"].to_numpy(), 0, None)
    status = np.where(status >= 3, 3, status)
    labels = ["Not behind", "1 month behind", "2 months behind", "3+ months behind"]
    frame = pd.DataFrame({"group": status, "y": train_df[config.TARGET].to_numpy()})
    grouped = frame.groupby("group")["y"].agg(["size", "mean"]).reindex(range(4))
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=grouped["mean"],
            marker_color=[config.COLOR_REPAID, config.COLOR_WARN,
                          config.COLOR_DEFAULT, config.COLOR_DEFAULT],
            text=[f"{v:.0%}" for v in grouped["mean"]],
            textposition="outside",
            customdata=np.stack([grouped["size"]], axis=-1),
            hovertemplate="%{x}<br>default rate %{y:.1%}<br>%{customdata[0]:,} training accounts<extra></extra>",
        )
    )
    figure.update_yaxes(title="Share that missed the next payment", tickformat=".0%",
                        range=[0, 0.85])
    figure.update_xaxes(title="Repayment status in the most recent month (September 2005)")
    return _layout(figure, "Already behind is the strongest signal in the dataset")


def demographic_gaps(train_df: pd.DataFrame) -> go.Figure:
    """Default rate by sex, education, and age band. Audit-only columns."""
    figure = make_subplots(
        rows=1, cols=3, shared_yaxes=True,
        subplot_titles=("By sex", "By education", "By age band"),
    )
    panels = [
        (train_df["SEX"].map(config.SEX_LABELS), 1),
        (train_df["EDUCATION"].map(config.EDUCATION_LABELS), 2),
        (data.age_band(train_df["AGE"]), 3),
    ]
    y = train_df[config.TARGET]
    for series, column in panels:
        grouped = y.groupby(series, observed=True).agg(["mean", "size"])
        figure.add_trace(
            go.Bar(
                x=grouped.index.astype(str),
                y=grouped["mean"],
                marker_color=config.COLOR_MUTED,
                text=[f"{v:.0%}" for v in grouped["mean"]],
                textposition="outside",
                customdata=np.stack([grouped["size"]], axis=-1),
                hovertemplate="%{x}<br>default rate %{y:.1%}<br>%{customdata[0]:,} training accounts<extra></extra>",
                showlegend=False,
            ),
            row=1, col=column,
        )
    figure.update_yaxes(title="Default rate", tickformat=".0%", range=[0, 0.35], row=1, col=1)
    for annotation in figure.layout.annotations:
        annotation.font.size = 13
    return _layout(
        figure,
        "The gaps exist in the data - and these columns stay out of the model",
        height=460,
    )


def utilization_gradient(utilization: np.ndarray, y: np.ndarray) -> go.Figure:
    """Default rate by share of the credit limit currently used (training)."""
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 2.01]
    labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%", "over 100%"]
    band = pd.cut(utilization, bins=edges, labels=labels, right=False, include_lowest=True)
    grouped = pd.Series(y).groupby(band, observed=True).agg(["mean", "size"]).reindex(labels)
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=grouped["mean"],
            marker_color=config.COLOR_WARN,
            text=[f"{v:.0%}" for v in grouped["mean"]],
            textposition="outside",
            customdata=np.stack([grouped["size"]], axis=-1),
            hovertemplate="Using %{x} of the limit<br>default rate %{y:.1%}<br>%{customdata[0]:,} training accounts<extra></extra>",
        )
    )
    figure.update_yaxes(title="Share that missed the next payment", tickformat=".0%",
                        range=[0, 0.42])
    figure.update_xaxes(title="Share of the credit limit currently used (September bill / limit)")
    return _layout(figure, "Heavier use of the limit goes with more missed payments")


# ── Stage 3 ─────────────────────────────────────────────────────────────────

def roc_curves(y_val: np.ndarray, candidates: dict[str, np.ndarray]) -> go.Figure:
    """Validation ROC curves for the compared models plus the no-skill line."""
    from sklearn.metrics import roc_auc_score, roc_curve

    figure = go.Figure()
    colors = [config.COLOR_REPAID, config.COLOR_DEFAULT, config.COLOR_ACCENT]
    for (name, probabilities), color in zip(candidates.items(), colors):
        fpr, tpr, _ = roc_curve(y_val, probabilities)
        auc = roc_auc_score(y_val, probabilities)
        figure.add_scatter(
            x=fpr, y=tpr, mode="lines", name=f"{name} (AUC {auc:.3f})",
            line=dict(color=color, width=3),
            hovertemplate="false-alarm rate %{x:.2f}<br>caught defaulters %{y:.2f}<extra></extra>",
        )
    figure.add_scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="No skill (AUC 0.500)",
        line=dict(color=config.COLOR_MUTED, width=2, dash="dash"),
        hoverinfo="skip",
    )
    figure.update_xaxes(title="Share of paying accounts wrongly ranked risky (false-alarm rate)",
                        range=[0, 1])
    figure.update_yaxes(title="Share of defaulters ranked above the cut", range=[0, 1.02])
    return _layout(figure, "Ranking skill on validation accounts, before any policy exists", height=480)


# ── Stage 4 ─────────────────────────────────────────────────────────────────

def reliability_curve(table: pd.DataFrame) -> go.Figure:
    """Mean predicted probability vs observed default rate per bin."""
    populated = table.dropna(subset=["Mean predicted"])
    figure = go.Figure()
    figure.add_scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Perfectly honest scores",
        line=dict(color=config.COLOR_MUTED, width=2, dash="dash"), hoverinfo="skip",
    )
    figure.add_scatter(
        x=populated["Mean predicted"],
        y=populated["Observed default rate"],
        mode="lines+markers",
        name="This model",
        line=dict(color=config.COLOR_DEFAULT, width=3),
        marker=dict(size=np.clip(populated["Accounts"] / 60, 6, 22), sizemode="diameter"),
        customdata=np.stack([populated["Accounts"]], axis=-1),
        hovertemplate=("model said %{x:.1%}<br>actually defaulted %{y:.1%}"
                       "<br>%{customdata[0]:,} validation accounts<extra></extra>"),
    )
    figure.update_xaxes(title="What the model predicted (mean probability in the bin)",
                        tickformat=".0%", range=[0, 1])
    figure.update_yaxes(title="What actually happened (observed default rate)",
                        tickformat=".0%", range=[0, 1.02])
    return _layout(figure, "The raw probabilities track reality closely enough to price decisions with",
                   height=480)


def risk_exposure_plane(
    p: np.ndarray, expo: np.ndarray, review_cost: float, display_cap: float = 400_000
) -> go.Figure:
    """Binned validation accounts on the risk x money plane, with the policy boundary."""
    capped = np.minimum(expo, display_cap)
    figure = go.Figure(
        go.Histogram2d(
            x=capped,
            y=p,
            xbins=dict(start=0, end=display_cap, size=display_cap / 40),
            ybins=dict(start=0, end=1.0, size=0.025),
            colorscale=[[0, "#FFFFFF"], [0.15, "#C9D2F5"], [1, config.COLOR_REPAID]],
            colorbar=dict(title="Accounts", thickness=14, len=0.8),
            hovertemplate="exposure ~NT$%{x:,.0f}<br>p(default) ~%{y:.2f}<br>%{z} accounts<extra></extra>",
        )
    )
    boundary_x = np.linspace(review_cost / (config.LOSS_GIVEN_DEFAULT * 1.0), display_cap, 300)
    boundary_y = review_cost / (config.LOSS_GIVEN_DEFAULT * boundary_x)
    mask = boundary_y <= 1.0
    figure.add_scatter(
        x=boundary_x[mask], y=boundary_y[mask], mode="lines",
        name=f"Flag boundary at NT${review_cost:,.0f}",
        line=dict(color=config.COLOR_ACCENT, width=4),
        hovertemplate=f"boundary: p x exposure x 0.5 = NT${review_cost:,.0f}<extra></extra>",
    )
    figure.add_annotation(x=display_cap * 0.72, y=0.88, text="flagged: risk x money too big",
                          showarrow=False, font=dict(color=config.COLOR_ACCENT, size=13))
    figure.add_annotation(x=display_cap * 0.18, y=0.045, text="not flagged",
                          showarrow=False, font=dict(color=config.COLOR_MUTED, size=13))
    figure.update_xaxes(title=f"Money at risk if the account defaults (NT$, display capped at {display_cap:,.0f})")
    figure.update_yaxes(title="Model probability of missing the next payment", range=[0, 1])
    figure.update_layout(legend=dict(orientation="h", y=1.06))
    return _layout(figure, "One rule, two ingredients: how likely x how much money", height=520)


def policy_sweep_chart(sweep: pd.DataFrame, chosen_cost: int) -> go.Figure:
    """Flagged share and net savings across candidate review costs."""
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        subplot_titles=("Share of all validation accounts flagged", "Net savings (NT$ millions)"),
    )
    figure.add_trace(
        go.Scatter(
            x=sweep["review_cost_NT"], y=sweep["flagged_share"],
            mode="lines+markers", name="Flagged share",
            line=dict(color=config.COLOR_WARN, width=3),
            hovertemplate="review cost NT$%{x:,}<br>%{y:.1%} of accounts flagged<extra></extra>",
        ),
        row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=sweep["review_cost_NT"], y=sweep["net_savings_NT"] / 1e6,
            mode="lines+markers", name="Net savings",
            line=dict(color=config.COLOR_ACCENT, width=3),
            hovertemplate="review cost NT$%{x:,}<br>net savings NT$%{y:.1f}M<extra></extra>",
        ),
        row=2, col=1,
    )
    for row in (1, 2):
        figure.add_vline(x=chosen_cost, line_color=config.COLOR_ACCENT, line_width=2,
                         line_dash="dash", row=row, col=1)
    cheap = sweep.iloc[0]
    figure.add_annotation(
        x=cheap["review_cost_NT"], y=cheap["flagged_share"], row=1, col=1,
        text=f"NT$1,000 reviews: flag {cheap['flagged_share']:.0%} of the book",
        showarrow=True, arrowhead=2, ax=90, ay=-5, font=dict(size=12),
    )
    figure.add_annotation(
        x=chosen_cost, y=float(sweep.loc[sweep["review_cost_NT"] == chosen_cost,
                                          "flagged_share"].iloc[0]),
        row=1, col=1, text=f"frozen: NT${chosen_cost:,}", showarrow=True,
        arrowhead=2, ax=40, ay=-30, font=dict(size=12, color=config.COLOR_ACCENT),
    )
    figure.update_yaxes(tickformat=".0%", row=1, col=1)
    figure.update_xaxes(title="Assumed cost of one review (NT$)", row=2, col=1)
    figure.update_layout(showlegend=False)
    for annotation in figure.layout.annotations[:2]:
        annotation.font.size = 13
    return _layout(figure, "The review cost, not the model, decides how many accounts get flagged",
                   height=560)


def confusion_heatmap(counts: dict[str, int], population: str) -> go.Figure:
    """Flag-vs-outcome counts as a 2x2 heatmap."""
    values = np.array([[counts["TN"], counts["FN"]], [counts["FP"], counts["TP"]]])
    text = np.array(
        [
            [f"{counts['TN']:,}<br>left alone, paid", f"{counts['FN']:,}<br>missed, not flagged"],
            [f"{counts['FP']:,}<br>reviewed, paid anyway", f"{counts['TP']:,}<br>caught before default"],
        ]
    )
    figure = go.Figure(
        go.Heatmap(
            z=values,
            x=["Later paid", "Later missed the payment"],
            y=["Not flagged", "Flagged for review"],
            text=text,
            texttemplate="%{text}",
            colorscale=[[0, "#EFF3F8"], [1, config.COLOR_WARN]],
            showscale=False,
            hovertemplate="%{y}<br>%{x}<br>%{z:,} accounts<extra></extra>",
        )
    )
    figure.update_xaxes(title="Outcome recorded one month later", side="bottom")
    figure.update_yaxes(title="Policy decision this month")
    return _layout(figure, f"Where the frozen policy's {population} accounts landed", height=430)


# ── Stage 5 ─────────────────────────────────────────────────────────────────

def reason_bar(frame: pd.DataFrame, account_label: str) -> go.Figure:
    """All 7 SHAP contributions for one account, risk-raising in red."""
    colors = [
        config.COLOR_DEFAULT if value > 0 else config.COLOR_REPAID
        for value in frame["contribution"]
    ]
    figure = go.Figure(
        go.Bar(
            x=frame["contribution"],
            y=frame["display_name"],
            orientation="h",
            marker_color=colors,
            customdata=np.stack([frame["value"]], axis=-1),
            hovertemplate="%{y}<br>account value %{customdata[0]:,.2f}<br>contribution %{x:.3f}<extra></extra>",
        )
    )
    figure.add_vline(x=0, line_color=config.COLOR_MUTED, line_width=1)
    figure.update_xaxes(title="Push on the risk score (SHAP, log-odds; right = riskier)")
    figure.update_yaxes(title="")
    return _layout(figure, f"Why the model scored {account_label} the way it did", height=430)
