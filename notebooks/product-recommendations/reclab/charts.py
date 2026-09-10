"""Plotly figures shared by the executable notebook and the offline HTML backup.

Eight figures, and every one of them aggregates before it plots - a cumulative
popularity curve, binned histograms, one row per model - so nothing embeds
390,571 training pairs or a 4,443-square similarity matrix in the notebook's
output. Colors come from the palette in ``config`` so this lab reads as part of
the same course as the other seven, and no figure relies on color alone: every
point that matters is also stated in a title, an annotation or a text label.

The two-leaderboard figure is the case. It is drawn as one figure with two
panels sharing a single model axis, sorted by the standard protocol, so the
reorder baseline sits at the top of the left panel and at the floor of the
right one - the inversion is a shape, not a sentence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config


def _layout(figure: go.Figure, title: str, height: int = 430,
            bottom: int = 70) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=90, r=40, t=90, b=bottom),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


def _model_colors(names) -> list[str]:
    return [config.MODEL_COLORS.get(name, config.COLOR_MODEL) for name in names]


# ── Stage 1: what the demand looks like ─────────────────────────────────────

def popularity_skew(curve: pd.DataFrame, concentration: dict) -> go.Figure:
    """The long tail: a few products carry the interactions, most carry none.

    ``curve`` is ``data.popularity_curve`` - one row per product, ranked, with
    the cumulative share of all (customer, product) interactions. Two y-axes,
    because the two facts only land together: the per-product counts collapse
    within the first few hundred products, and the cumulative line is already
    most of the way up before the catalog is a third read.
    """
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_scatter(
        x=curve["rank"], y=curve["interactions"], mode="lines",
        line=dict(color=config.COLOR_MODEL, width=2),
        name="Customers who bought this product",
        hovertemplate="rank %{x:,}<br>%{y:,} customers bought it<extra></extra>",
        secondary_y=False,
    )
    figure.add_scatter(
        x=curve["rank"], y=curve["cumulative_share"], mode="lines",
        line=dict(color=config.COLOR_RISK, width=2.4, dash="solid"),
        name="Cumulative share of all interactions",
        hovertemplate="the %{x:,} most-bought products<br>hold %{y:.1%} of all "
                      "interactions<extra></extra>",
        secondary_y=True,
    )
    for rank, share, label in (
        (100, concentration["top_100_share"], "top 100"),
        (500, concentration["top_500_share"], "top 500"),
    ):
        figure.add_vline(x=rank, line_dash="dot", line_color=config.COLOR_MUTED)
        figure.add_annotation(
            x=np.log10(rank), y=share, yref="y2", text=f"{label}: {share:.0%}",
            showarrow=True, arrowhead=0, ax=52, ay=-26, font=dict(size=11),
            bgcolor="rgba(255,255,255,0.85)",
        )
    figure.update_xaxes(title="Product, ranked by how many customers bought it "
                              "(1 = most bought)", type="log")
    figure.update_yaxes(title="Customers who bought the product", type="log",
                        secondary_y=False)
    figure.update_yaxes(title="Cumulative share of all interactions",
                        tickformat=".0%", range=[0, 1.02], secondary_y=True)
    figure.update_layout(legend=dict(orientation="h", y=-0.26))
    return _layout(
        figure,
        f"{concentration['items']:,} products, Gini {concentration['gini']:.3f}: "
        f"the top 500 hold {concentration['top_500_share']:.0%} of every "
        "customer-product interaction",
        height=470,
    )


def sparsity_profile(split) -> go.Figure:
    """The matrix is 98.2% empty, and both margins say so.

    Left: how many distinct products each customer bought before the cut.
    Right: how many customers bought each product. Both are binned in log
    space and drawn on a log count axis, because both distributions run from
    single digits to four figures and a linear axis shows one bar.
    """
    per_user = np.asarray(split.R.sum(1)).ravel()
    per_item = np.asarray(split.R.sum(0)).ravel()
    density = split.R.nnz / (split.R.shape[0] * split.R.shape[1])

    figure = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.11,
        subplot_titles=(
            f"Products bought per customer (median {np.median(per_user):.0f})",
            f"Customers per product (median {np.median(per_item):.0f})"),
    )
    for column, values, color in ((1, per_user, config.COLOR_MODEL),
                                  (2, per_item, config.COLOR_ACCENT)):
        positive = values[values > 0]
        edges = np.logspace(0, np.log10(positive.max()) + 0.05, 34)
        counts, _ = np.histogram(positive, bins=edges)
        centres = np.sqrt(edges[:-1] * edges[1:])
        figure.add_bar(
            x=centres, y=counts, marker_color=color, showlegend=False,
            hovertemplate="around %{x:.0f}<br>%{y:,} of them<extra></extra>",
            row=1, col=column,
        )
    figure.update_xaxes(title="Distinct products bought before the cut", type="log",
                        row=1, col=1)
    figure.update_xaxes(title="Customers who bought the product", type="log",
                        row=1, col=2)
    figure.update_yaxes(title="Customers", type="log", row=1, col=1)
    figure.update_yaxes(title="Products", type="log", row=1, col=2)
    return _layout(
        figure,
        f"{split.n_users:,} customers x {split.n_items:,} products = "
        f"{split.n_users * split.n_items:,} cells, {split.R.nnz:,} of them filled "
        f"- {1 - density:.3%} of this matrix is empty",
        height=440,
    )


# ── Stage 3: the case ───────────────────────────────────────────────────────

def two_leaderboards(comparison: pd.DataFrame,
                     random_discovery: float | None = None) -> go.Figure:
    """The whole lesson in one figure: same models, two protocols, inverted order.

    ``comparison`` is ``evaluate.two_table_comparison``. The model axis is
    shared and sorted by the standard protocol, so the reorder baseline is the
    top bar on the left. On the right it is the shortest bar on the chart, and
    the dashed line marks where ten products drawn at random land - which the
    reorder baseline is below.
    """
    frame = comparison.sort_values("Standard HR@10").reset_index(drop=True)
    colors = _model_colors(frame["Model"])

    figure = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06,
        subplot_titles=("Standard next-purchase<br>"
                        "<sub>truth: everything bought after the cut, repeats included</sub>",
                        "Discovery<br>"
                        "<sub>truth: only products never bought before, history masked</sub>"),
    )
    for column, key in ((1, "Standard HR@10"), (2, "Discovery HR@10")):
        figure.add_bar(
            y=frame["Model"], x=frame[key], orientation="h", marker_color=colors,
            text=[f"{value:.4f}" for value in frame[key]], textposition="outside",
            cliponaxis=False, showlegend=False,
            hovertemplate="%{y}<br>HR@10 = %{x:.4f}<extra></extra>",
            row=1, col=column,
        )
    if random_discovery is not None:
        figure.add_vline(
            x=random_discovery, line_dash="dash", line_color=config.COLOR_MUTED,
            row=1, col=2,
        )
        figure.add_annotation(
            x=random_discovery, y=len(frame) - 0.35, xref="x2", yref="y",
            text=f"ten random products: {random_discovery:.4f}", showarrow=False,
            xanchor="left", xshift=6, font=dict(size=11, color="#5A5F6A"),
        )

    reorder_rows = frame.index[frame["Model"] == config.REORDER_LABEL]
    if len(reorder_rows):
        position = int(reorder_rows[0])
        figure.add_annotation(
            x=frame.loc[position, "Discovery HR@10"], y=position, xref="x2", yref="y",
            text="first place becomes last,<br>and below random",
            showarrow=True, arrowhead=2, arrowcolor=config.COLOR_RISK,
            ax=118, ay=42, font=dict(size=11, color=config.COLOR_RISK),
            bgcolor="rgba(255,255,255,0.88)",
        )
    figure.update_xaxes(title="HR@10", range=[0, 0.99], row=1, col=1)
    figure.update_xaxes(title="HR@10", range=[0, 0.99], row=1, col=2)
    figure.update_yaxes(title="", row=1, col=1)
    figure.update_layout(bargap=0.32)
    return _layout(
        figure,
        "Same models, same day, same data - the ground truth is the only thing "
        "that changed",
        height=520,
    )


def coverage_vs_accuracy(discovery: pd.DataFrame) -> go.Figure:
    """Discovery accuracy against how much of the catalog a model ever shows.

    Two models can post the same hit rate while one of them has shown 80
    products and the other 1,145. Printing coverage next to accuracy is the
    only way that is visible, so this figure puts them on the same axes.
    """
    figure = go.Figure()
    for row in discovery.to_dict("records"):
        figure.add_scatter(
            x=[row["Coverage"]], y=[row["HR@10"]], mode="markers+text",
            marker=dict(size=20, color=config.MODEL_COLORS.get(row["Model"],
                                                               config.COLOR_MODEL),
                        line=dict(width=1.4, color="#FFFFFF")),
            text=[row["Model"]], textposition="top center",
            textfont=dict(size=11), name=row["Model"], showlegend=False,
            hovertemplate=(f"{row['Model']}<br>discovery HR@10 = %{{y:.4f}}"
                           "<br>coverage = %{x:.2%} of the catalog"
                           f"<br>novelty = {row['Novelty']:.2f}"
                           f"<br>mean popularity rank = {row['Mean pop rank']:.0f}"
                           "<extra></extra>"),
        )
    figure.add_annotation(
        x=0.02, y=0.03, xref="paper", yref="paper", xanchor="left",
        text="bottom left: accurate at nothing and shows almost nothing<br>"
             "top right: the only corner worth deploying from",
        showarrow=False, align="left", font=dict(size=11, color="#5A5F6A"),
    )
    figure.update_xaxes(title="Catalog coverage - share of the 4,443 products that "
                              "reached anyone's ten slots", tickformat=".0%",
                        range=[-0.02, max(discovery["Coverage"]) * 1.22 + 0.02])
    figure.update_yaxes(title="Discovery HR@10",
                        range=[-0.02, max(discovery["HR@10"]) * 1.28])
    return _layout(
        figure,
        "Accuracy alone cannot separate these models. Accuracy and coverage can",
        height=470,
    )


# ── Stage 4: what deployment does to the catalog ────────────────────────────

def exposure_loop(history: pd.DataFrame,
                  rounds: int = config.FEEDBACK_ROUNDS) -> go.Figure:
    """Ten rounds of a popularity model feeding on its own recommendations.

    A LABELED CLASSROOM ASSUMPTION, captioned on the figure itself: 5% of shown
    slots are assumed to convert. Nothing here is measured from the retailer's
    data, and the caption says so where the chart is, not in a footnote.
    """
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        row_heights=[0.60, 0.40],
        subplot_titles=("Share of all interactions held by the ten most-bought products",
                        "Distinct products the system has EVER shown, across all rounds"),
    )
    figure.add_scatter(
        x=history["Round"], y=history["Top-10 share"], mode="lines+markers",
        line=dict(color=config.COLOR_RISK, width=2.8), marker=dict(size=9),
        name="Top-10 share", showlegend=False,
        hovertemplate="round %{x}<br>%{y:.2%} of all interactions<extra></extra>",
        row=1, col=1,
    )
    figure.add_scatter(
        x=history["Round"], y=history["Top-100 share"], mode="lines+markers",
        line=dict(color=config.COLOR_WARN, width=2, dash="dot"), marker=dict(size=7),
        name="Top-100 share", showlegend=False,
        hovertemplate="round %{x}<br>top 100 hold %{y:.2%}<extra></extra>",
        row=1, col=1,
    )
    figure.add_bar(
        x=history["Round"], y=history["Distinct products ever shown"],
        marker_color=config.COLOR_MUTED, showlegend=False,
        hovertemplate="round %{x}<br>%{y} distinct products shown, ever<extra></extra>",
        row=2, col=1,
    )
    start = float(history["Top-10 share"].iloc[0])
    end = float(history["Top-10 share"].iloc[-1])
    figure.add_annotation(
        x=history["Round"].iloc[-1], y=end, xref="x", yref="y",
        text=f"{start:.2%} → {end:.2%}<br>(+{end / start - 1:.0%} relative)",
        showarrow=True, arrowhead=2, arrowcolor=config.COLOR_RISK,
        ax=-84, ay=32, font=dict(size=11, color=config.COLOR_RISK),
        bgcolor="rgba(255,255,255,0.88)",
    )
    figure.add_annotation(
        x=0.0, y=1.0, xref="paper", yref="paper", xanchor="left", yanchor="bottom",
        yshift=44,
        text="ASSUMPTION, NOT A MEASUREMENT: "
             f"{config.FEEDBACK_CONVERSION:.0%} of shown slots are assumed to convert",
        showarrow=False, font=dict(size=11, color=config.COLOR_RISK),
    )
    figure.update_yaxes(title="Share of all interactions", tickformat=".1%", row=1, col=1)
    figure.update_yaxes(title="Distinct products", rangemode="tozero", row=2, col=1)
    figure.update_xaxes(title=f"Round of retraining (0 = before deployment, "
                              f"{rounds} rounds shown)", dtick=1, row=2, col=1)
    return _layout(
        figure,
        "Nothing about the products changed. The model manufactured the evidence "
        "that ten of them are the best",
        height=560,
    )


# ── Stage 4: the split that flatters you ────────────────────────────────────

def loo_inflation(wide: pd.DataFrame) -> go.Figure:
    """Identical targets, two training sets: the leak, and how it scales.

    ``wide`` is ``evaluate.loo_inflation`` - one row per model, HR@10 under the
    honest training set and under leave-one-out, plus the inflation between
    them. The point is not that leave-one-out is higher. It is that the gap
    grows with model capacity, so the leak flatters exactly the models you were
    hoping to justify.
    """
    honest_column, leaky_column = wide.columns[1], wide.columns[2]
    frame = wide.copy()
    figure = go.Figure()
    figure.add_bar(
        x=frame["Model"], y=frame[honest_column], marker_color=config.COLOR_ACCENT,
        name="A - honest: nothing after the cut, for anyone",
        text=[f"{value:.4f}" for value in frame[honest_column]],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>honest HR@10 = %{y:.4f}<extra></extra>",
    )
    figure.add_bar(
        x=frame["Model"], y=frame[leaky_column], marker_color=config.COLOR_RISK,
        name="B - leave-one-out: everything except the held-out purchase",
        text=[f"{value:.4f}" for value in frame[leaky_column]],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>leave-one-out HR@10 = %{y:.4f}<extra></extra>",
    )
    top = float(max(frame[leaky_column])) * 1.55
    for position, row in enumerate(frame.to_dict("records")):
        figure.add_annotation(
            x=position, y=max(row[honest_column], row[leaky_column]),
            text=f"+{row['Inflation']:.0%}", showarrow=False, yshift=34,
            font=dict(size=13, color=config.COLOR_RISK),
        )
    figure.update_yaxes(title="HR@10 on ONE held-out product per customer",
                        range=[0, top])
    figure.update_xaxes(title="")
    figure.update_layout(barmode="group", bargap=0.34,
                         legend=dict(orientation="h", y=-0.20, font_size=11))
    return _layout(
        figure,
        "Same targets, same metric, only the training data changed - and the "
        "leak grows with the model's capacity to exploit it",
        height=490,
    )


# ── Stage 5: who the policy cannot serve ────────────────────────────────────

def cold_start_share(census: dict) -> go.Figure:
    """Two populations that are both called cold start, kept apart on purpose.

    The left bar is registered customers with no usable training history, as a
    share of registered customers active in the test window. The right bar is
    transactions with no customer id at all, as a share of test-window rows.
    They have different denominators. The figure refuses to stack them.
    """
    left = [
        ("Cold: never seen before the cut", census["cold_registered_share"],
         census["cold_registered_customers"], config.COLOR_RISK),
        ("Thin: seen, but under 5 products", census["thin_history_share"],
         census["thin_history_customers"], config.COLOR_WARN),
    ]
    served = 1.0 - census["unservable_share"]
    figure = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.20,
        subplot_titles=(
            f"Registered customers active after the cut<br>"
            f"<sub>denominator: {census['registered_customers_active_in_test']:,} "
            f"registered customers</sub>",
            "Rows in the test window<br>"
            f"<sub>denominator: {census['all_rows_in_test']:,} invoice lines</sub>"),
    )
    figure.add_bar(
        x=["Servable"], y=[served], marker_color=config.COLOR_ACCENT,
        text=[f"{served:.1%}"], textposition="outside", cliponaxis=False,
        showlegend=False,
        hovertemplate="personalized: %{y:.1%} of registered test customers<extra></extra>",
        row=1, col=1,
    )
    for label, share, count, color in left:
        figure.add_bar(
            x=[label], y=[share], marker_color=color,
            text=[f"{share:.1%}<br>{count:,}"], textposition="outside",
            cliponaxis=False, showlegend=False,
            hovertemplate=f"{label}<br>%{{y:.1%}} of registered test customers"
                          f"<br>{count:,} customers<extra></extra>",
            row=1, col=1,
        )
    figure.add_bar(
        x=["Guest checkout<br>(no customer id at all)"], y=[census["guest_row_share"]],
        marker_color=config.COLOR_PURPLE,
        text=[f"{census['guest_row_share']:.1%}<br>{census['guest_rows_in_test']:,} rows"],
        textposition="outside", cliponaxis=False, showlegend=False,
        hovertemplate="guest rows: %{y:.1%} of test-window rows<extra></extra>",
        row=1, col=2,
    )
    figure.add_bar(
        x=["Guest share of<br>test-window revenue"], y=[census["guest_revenue_share"]],
        marker_color=config.COLOR_MUTED,
        text=[f"{census['guest_revenue_share']:.1%}"], textposition="outside",
        cliponaxis=False, showlegend=False,
        hovertemplate="guest revenue: %{y:.1%} of test-window revenue<extra></extra>",
        row=1, col=2,
    )
    figure.add_annotation(
        x=0.5, y=-0.30, xref="paper", yref="paper", xanchor="center",
        text="These two panels have different denominators. The shares must never "
             "be added together.",
        showarrow=False, font=dict(size=11, color=config.COLOR_RISK),
    )
    figure.update_yaxes(title="Share of registered test customers", tickformat=".0%",
                        range=[0, 1.05], row=1, col=1)
    figure.update_yaxes(title="Share of the test window", tickformat=".0%",
                        range=[0, 0.34], row=1, col=2)
    figure.update_layout(bargap=0.38)
    return _layout(
        figure,
        f"{census['unservable_share']:.1%} of registered customers cannot be "
        "personalized at all - and guests are a separate population again",
        height=520, bottom=120,
    )


# ── Stage 5: the deflating number ───────────────────────────────────────────

def incremental_revenue(frame: pd.DataFrame) -> go.Figure:
    """An UPPER BOUND on what personalization is worth here, beside a rule.

    One panel, one bar per model: the share of test-window revenue on products
    new to that customer that sits on something the model actually ranked. The
    deployed model reaches 3.53%. A ten-product list with no personalization in
    it reaches 2.81%. The gap is the whole measured case for the model, and it
    is an upper bound.
    """
    ordered = [name for name in config.MODEL_ORDER
               if name in set(frame["Model"])]
    table = frame.set_index("Model").loc[ordered].reset_index()
    share = table["Share of available new-product revenue"]
    colors = _model_colors(table["Model"])

    figure = go.Figure()
    figure.add_bar(
        x=table["Model"], y=share, marker_color=colors,
        text=[f"{value:.2%}" for value in share], textposition="outside",
        cliponaxis=False, showlegend=False,
        customdata=np.stack([table["Revenue reached"],
                             table["Discovery hits per customer"]], axis=-1),
        hovertemplate="%{x}<br>%{y:.2%} of available new-product revenue"
                      "<br>%{customdata[0]:,.0f} reached"
                      "<br>%{customdata[1]:.3f} discovery hits per customer<extra></extra>",
    )
    deployed = table.index[table["Model"] == config.DEPLOYED_MODEL_LABEL]
    fallback = table.index[table["Model"] == config.FALLBACK_LABEL]
    if len(deployed) and len(fallback):
        best = float(share.iloc[int(deployed[0])])
        plain = float(share.iloc[int(fallback[0])])
        figure.add_hline(
            y=plain, line_dash="dash", line_color=config.COLOR_WARN,
            annotation_text=f"no personalization at all: {plain:.2%}",
            annotation_position="top left", annotation_font_size=11,
        )
        figure.add_annotation(
            x=int(deployed[0]), y=best,
            text=f"the entire measured gain from<br>collaborative filtering: "
                 f"{best - plain:.2%} of new-product revenue",
            showarrow=True, arrowhead=2, arrowcolor=config.COLOR_ACCENT,
            ax=0, ay=-62, font=dict(size=11, color="#20242B"),
            bgcolor="rgba(255,255,255,0.88)",
        )
    available = frame.attrs.get("available_revenue")
    customers = frame.attrs.get("customers")
    caption = "UPPER BOUND: it credits the model for revenue the customer would " \
              "have generated anyway"
    if available is not None and customers is not None:
        caption = (f"{available:,.0f} of new-product revenue was available across "
                   f"{customers:,} customers. " + caption)
    figure.add_annotation(
        x=0.5, y=-0.34, xref="paper", yref="paper", xanchor="center",
        text=caption, showarrow=False, font=dict(size=11, color=config.COLOR_RISK),
    )
    figure.update_yaxes(title="Share of available new-product revenue reached",
                        tickformat=".1%", range=[0, float(share.max()) * 1.45])
    figure.update_xaxes(title="")
    figure.update_layout(bargap=0.34)
    return _layout(
        figure,
        "The number nobody puts on a slide: the best model reaches 3.53% of the "
        "available new-product revenue, a generic list reaches 2.81%",
        height=540, bottom=130,
    )
