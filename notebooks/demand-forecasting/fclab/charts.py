"""Plotly figures shared by the executable notebook and the offline HTML.

One function per figure, each returning a ``go.Figure``. Every figure is built
from a table another ``fclab`` module already computed - nothing here measures
anything, so a chart and the number printed beside it cannot disagree.

Colors come from the palette in ``config`` so the course's charts read as one
family, and no figure relies on color alone: every colored series is also
labeled, annotated, or named in the title.

Nine figures, in the order the notebook draws them:

    1  product_demand              one product, 102 weeks, the split marked
    2  zero_week_distribution      why 4,871 products become 469
    3  baseline_mae                the four candidate point forecasts
    4  fan_chart                   point forecast + 80% band against actual
    5  interval_method_coverage    coverage against the promise, by method
    6  cost_vs_quantile            where the money is, with the critical ratio
    7  policy_outcomes             winners and losers, per product
    8  christmas_coverage          the seasonal failure the average hides
    9  metric_panel                the frozen metric set, in one frame
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
        margin=dict(l=80, r=40, t=90, b=70),
        font=dict(family="Arial", size=13, color=config.COLOR_ACTUAL),
        hoverlabel=dict(font_size=13),
    )
    return figure


def _split_marker(figure: go.Figure, weeks, row: int | None = None,
                  col: int | None = None) -> None:
    """Shade the 76 training weeks and name the wall the test weeks sit behind."""
    kwargs = {} if row is None else {"row": row, "col": col}
    weeks = list(weeks)
    figure.add_vrect(
        x0=weeks[0], x1=weeks[config.N_TRAIN - 1],
        fillcolor=config.COLOR_MUTED, opacity=0.18, line_width=0,
        annotation_text=f"{config.N_TRAIN} training weeks",
        annotation_position="top left", annotation_font_size=11, **kwargs,
    )
    figure.add_vline(
        x=weeks[config.N_TRAIN], line_color=config.COLOR_ACTUAL, line_width=1.6,
        line_dash="dash", **kwargs,
    )


# ── Stage 1: the data ───────────────────────────────────────────────────────

def product_demand(panel: pd.DataFrame, code: str, names: pd.Series) -> go.Figure:
    """One product's 102 weekly totals, with the train/test wall drawn on it.

    The point of the figure is the shape a weekly grain reveals: a level that
    drifts, a Q4 ramp, and week-to-week noise that no point forecast can chase.
    """
    row = panel.loc[code]
    weeks = list(row.index)
    values = row.to_numpy(dtype=float)
    train = values[: config.N_TRAIN]

    figure = go.Figure()
    figure.add_scatter(
        x=weeks, y=values, mode="lines+markers",
        line=dict(color=config.COLOR_ACTUAL, width=1.8), marker=dict(size=4),
        name="Units sold",
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:,.0f} units<extra></extra>",
    )
    figure.add_hline(
        y=float(train.mean()), line_dash="dot", line_color=config.COLOR_MUTED,
        annotation_text=f"training mean {train.mean():,.0f} units/week",
        annotation_position="bottom left", annotation_font_size=11,
    )
    _split_marker(figure, weeks)
    figure.update_yaxes(title="Units sold that week", rangemode="tozero")
    figure.update_xaxes(title="Week beginning (Monday)")
    figure.update_layout(showlegend=False)
    return _layout(
        figure,
        f"{names.get(code, code)} ({code}): {values.max():,.0f} units in its biggest "
        f"week, {train.mean():,.0f} in an average training week",
        height=430,
    )


def zero_week_distribution(histogram: pd.DataFrame, cohort_size: int,
                           catalog_size: int) -> go.Figure:
    """Every product's zero-week share - the reason the catalog is cut to 469.

    ``histogram`` is ``features.zero_week_histogram``, measured over all 102
    weeks. The deployed cohort rule reads the 76 TRAINING weeks only, so the
    marked band below is where the cohort lives, not a restatement of the rule.
    """
    frame = histogram.copy()
    inside = frame["zero_share_high"] <= (1 - config.COHORT_MIN_NONZERO) + 1e-9
    colors = np.where(inside, config.COLOR_ACCENT, config.COLOR_MUTED)

    figure = go.Figure(
        go.Bar(
            x=frame["zero_share_low"] + (frame["zero_share_high"]
                                         - frame["zero_share_low"]) / 2,
            y=frame["products"], marker_color=colors,
            width=(frame["zero_share_high"] - frame["zero_share_low"]) * 0.92,
            hovertemplate="%{customdata[0]:.0%}-%{customdata[1]:.0%} of weeks with "
                          "no sale<br>%{y:,} products<extra></extra>",
            customdata=frame[["zero_share_low", "zero_share_high"]].to_numpy(),
        )
    )
    figure.add_vline(
        x=1 - config.COHORT_MIN_NONZERO, line_dash="dash",
        line_color=config.COLOR_ACTUAL,
        annotation_text=f"the cohort line: at most "
                        f"{1 - config.COHORT_MIN_NONZERO:.0%} zero weeks",
        annotation_position="top right", annotation_font_size=11,
    )
    figure.add_annotation(
        x=0.05, y=float(frame["products"].max()) * 0.62, xref="x", yref="y",
        text=f"<b>{cohort_size} products</b><br>are forecastable",
        showarrow=False, align="center", font=dict(size=12, color=config.COLOR_ACCENT),
    )
    figure.update_xaxes(title="Share of the 102 weeks in which the product sold nothing",
                        tickformat=".0%")
    figure.update_yaxes(title="Products in the catalog")
    figure.update_layout(showlegend=False, bargap=0.06)
    return _layout(
        figure,
        f"Most of the catalog is mostly zeros: {cohort_size} of {catalog_size:,} "
        "products sell nearly every week, and only those get a forecast",
        height=430,
    )


# ── Stage 2: the point forecast ─────────────────────────────────────────────

def baseline_mae(table: pd.DataFrame) -> go.Figure:
    """The candidate point forecasts on the same held-out weeks, ranked by MAE.

    ``table`` is ``forecast.baseline_table``. The adopted rule is the one named
    in the bar labels, not the one with the prettiest color.
    """
    frame = table.sort_values("MAE", ascending=False)
    adopted = frame["Point forecast"].str.startswith("Moving average, 8")
    seasonal = frame["Point forecast"].str.startswith("Seasonal-naive")
    colors = np.where(adopted, config.COLOR_ACCENT,
                      np.where(seasonal, config.COLOR_MISS, config.COLOR_MUTED))

    figure = go.Figure(
        go.Bar(
            y=frame["Point forecast"], x=frame["MAE"], orientation="h",
            marker_color=colors,
            text=[f"{v:,.1f}" for v in frame["MAE"]], textposition="outside",
            customdata=frame[["RMSE"]].to_numpy(),
            hovertemplate="%{y}<br>MAE %{x:,.2f} units<br>"
                          "RMSE %{customdata[0]:,.2f} units<extra></extra>",
        )
    )
    figure.update_xaxes(title="Mean absolute error over the 12,194 held-out "
                              "product-weeks (units)",
                        range=[0, float(frame["MAE"].max()) * 1.18])
    figure.update_yaxes(title="")
    figure.update_layout(showlegend=False, bargap=0.32)
    return _layout(
        figure,
        "Forecasting nothing at all beats last year's same week - and the "
        "8-week moving average beats everything",
        height=460,
    )


def fan_chart(scored: pd.DataFrame, code: str, names: pd.Series) -> go.Figure:
    """The deployed forecast for one product: the band, the line, the actuals.

    ``scored`` is ``forecast.score_holdout``. One row per held-out week, so the
    band drawn here is the band a planner would have been shown that Monday.
    """
    frame = scored[scored["StockCode"] == code].sort_values("week")
    weeks = list(frame["week"])
    actual = frame["actual"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    missed = (actual > high) | (actual < low)
    covered = int((~missed).sum())

    figure = go.Figure()
    figure.add_scatter(
        x=weeks, y=high, mode="lines", line=dict(width=0, color=config.COLOR_BAND),
        name="Band, 90th percentile", showlegend=False,
        hovertemplate="week of %{x|%Y-%m-%d}<br>band high %{y:,.0f}<extra></extra>",
    )
    figure.add_scatter(
        x=weeks, y=low, mode="lines", line=dict(width=0, color=config.COLOR_BAND),
        fill="tonexty", fillcolor="rgba(99,110,250,0.20)",
        name=f"{config.NOMINAL_COVERAGE:.0%} band",
        hovertemplate="week of %{x|%Y-%m-%d}<br>band low %{y:,.0f}<extra></extra>",
    )
    figure.add_scatter(
        x=weeks, y=frame["point"].to_numpy(dtype=float), mode="lines",
        line=dict(color=config.COLOR_FORECAST, width=2.4, dash="dash"),
        name="Point forecast (8-week mean)",
        hovertemplate="week of %{x|%Y-%m-%d}<br>forecast %{y:,.0f} units<extra></extra>",
    )
    figure.add_scatter(
        x=weeks, y=actual, mode="markers",
        marker=dict(size=9, color=np.where(missed, config.COLOR_MISS,
                                           config.COLOR_ACTUAL),
                    symbol=np.where(missed, "x", "circle"), line=dict(width=0)),
        name="What actually sold",
        hovertemplate="week of %{x|%Y-%m-%d}<br>actual %{y:,.0f} units<extra></extra>",
    )
    figure.update_yaxes(title="Units in the week", rangemode="tozero")
    figure.update_xaxes(title="Held-out week beginning (Monday)")
    figure.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom",
                                     x=0, font_size=11))
    return _layout(
        figure,
        f"{names.get(code, code)}: {covered} of {len(frame)} held-out weeks landed "
        f"inside a band that promised {config.NOMINAL_COVERAGE:.0%}"
        + (f", and the {int(missed.sum())} misses are marked" if missed.any() else ""),
        height=470,
    )


# ── Stage 3: the interval ───────────────────────────────────────────────────

def interval_method_coverage(table: pd.DataFrame) -> go.Figure:
    """Coverage against the promise, method by method, on identical weeks.

    ``table`` is ``intervals.comparison_table``. The bar to read is the distance
    from the dashed line, not the height: a method that promises 80% and pays
    75% is not a cheaper model, it is a worse promise.
    """
    frame = table.sort_values("coverage")
    deployed = frame["method"].str.contains("DEPLOYED")
    short = frame["coverage"] < config.NOMINAL_COVERAGE
    colors = np.where(deployed, config.COLOR_ACCENT,
                      np.where(short, config.COLOR_MISS, config.COLOR_MUTED))

    figure = go.Figure(
        go.Bar(
            y=frame["method"], x=frame["coverage"], orientation="h",
            marker_color=colors,
            text=[f"{v:.1%}" for v in frame["coverage"]], textposition="outside",
            customdata=frame[["median_band", "fit_seconds"]].to_numpy(),
            hovertemplate="%{y}<br>coverage %{x:.2%}<br>"
                          "median band %{customdata[0]:,.1f} units<br>"
                          "fit %{customdata[1]:.2f} s<extra></extra>",
        )
    )
    figure.add_vline(
        x=config.NOMINAL_COVERAGE, line_dash="dash", line_color=config.COLOR_ACTUAL,
        annotation_text=f"promised {config.NOMINAL_COVERAGE:.0%}",
        annotation_position="top", annotation_font_size=11,
    )
    figure.update_xaxes(title="Share of the 12,194 held-out product-weeks that "
                              "landed inside the band",
                        tickformat=".0%", range=[0, 1.0])
    figure.update_yaxes(title="")
    figure.update_layout(showlegend=False, bargap=0.3)
    return _layout(
        figure,
        "Ten lines of numpy keeps its promise; the gradient booster, fitted three "
        "times, does not",
        height=470,
    )


# ── Stage 4: the order ──────────────────────────────────────────────────────

def cost_vs_quantile(curve: pd.DataFrame) -> go.Figure:
    """Total holdout cost at every order quantile, with the critical ratio marked.

    ``curve`` is ``PolicyBoard.cost_curve``. The newsvendor formula predicts the
    minimum before the sweep is run; this figure is that prediction being
    checked, which is the only reason to trust the formula on the next product.

    CLASSROOM ASSUMPTION: every cost here rests on co = 0.10 x unit price.
    """
    figure = go.Figure()
    palette = {0: config.COLOR_FORECAST, 1: config.COLOR_WARN}
    positions = ["top right", "bottom right"]
    for order, (ratio, block) in enumerate(curve.groupby("ratio", sort=False)):
        block = block.sort_values("order_quantile")
        color = palette.get(order, config.COLOR_MUTED)
        figure.add_scatter(
            x=block["order_quantile"], y=block["cost"], mode="lines+markers",
            line=dict(color=color, width=2.4), marker=dict(size=7),
            name=f"stockout : overstock = {ratio}",
            hovertemplate=f"{ratio}<br>order at the %{{x:.0%}} quantile<br>"
                          "cost %{y:,.0f}<extra></extra>",
        )
        best = block.loc[block["is_minimum"]]
        figure.add_scatter(
            x=best["order_quantile"], y=best["cost"], mode="markers",
            marker=dict(size=15, color=color, symbol="diamond",
                        line=dict(width=1.5, color=config.COLOR_ACTUAL)),
            name=f"cheapest quantile, {ratio}",
            hovertemplate=f"{ratio} cheapest at %{{x:.0%}}<extra></extra>",
            showlegend=False,
        )
        critical = float(block["critical_ratio"].iloc[0])
        figure.add_vline(
            x=critical, line_dash="dot", line_color=color,
            annotation_text=f"cu/(cu+co) = {critical:.2f} at {ratio}",
            annotation_position=positions[order % 2], annotation_font_size=11,
        )
    figure.update_xaxes(title="Order the band read at this quantile", tickformat=".0%")
    figure.update_yaxes(title="Total cost over the 26 held-out weeks "
                              "(CLASSROOM ASSUMPTION dollars)")
    figure.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom",
                                     x=0, font_size=11))
    return _layout(
        figure,
        "The cost curve bottoms out where the formula said it would - the critical "
        "ratio is derived, then checked",
        height=470,
    )


def policy_outcomes(product: pd.DataFrame, names: pd.Series,
                    ratio: str = "4:1") -> go.Figure:
    """Every product's change in cost under the newsvendor order. Losers included.

    ``product`` is ``PolicyBoard.per_product``. An average saving hides the fact
    that the same rule makes some products more expensive; those bars point
    down and are drawn in the same figure on purpose.
    """
    frame = product.sort_values("saving_pct", ascending=False).reset_index(drop=True)
    change = frame["saving_pct"].to_numpy(dtype=float)
    losers = change < 0
    rank = np.arange(1, len(frame) + 1)
    labels = frame["StockCode"].map(names).fillna(frame["StockCode"])

    figure = go.Figure(
        go.Bar(
            x=rank, y=change,
            marker_color=np.where(losers, config.COLOR_MISS, config.COLOR_ACCENT),
            customdata=np.column_stack([labels.to_numpy(),
                                        frame["StockCode"].to_numpy(),
                                        frame["cost_point"].to_numpy(),
                                        frame["cost_quantile"].to_numpy()]),
            hovertemplate="%{customdata[0]} (%{customdata[1]})<br>"
                          "cost %{customdata[2]:,.0f} -> %{customdata[3]:,.0f}<br>"
                          "%{y:+.1f}% cheaper<extra></extra>",
            name="Change in cost",
        )
    )
    figure.add_hline(y=0, line_color=config.COLOR_ACTUAL, line_width=1.4)
    worst = frame.iloc[-1]
    figure.add_annotation(
        x=float(len(frame)), y=float(worst["saving_pct"]),
        text=f"worst: {names.get(worst['StockCode'], worst['StockCode'])}"
             f"<br>{-worst['saving_pct']:,.0f}% MORE expensive",
        showarrow=True, arrowhead=2, ax=-90, ay=-30,
        font=dict(size=11, color=config.COLOR_MISS), align="right",
    )
    figure.add_annotation(
        x=0.62, y=0.90, xref="paper", yref="paper", showarrow=False,
        align="left", font=dict(size=12, color=config.COLOR_ACCENT),
        text=f"<b>{int((~losers).sum())} of {len(frame)} products are cheaper</b>"
             f"<br>{int(losers.sum())} are more expensive under the same rule",
    )
    figure.update_xaxes(title=f"The {len(frame)} cohort products, ranked by outcome")
    figure.update_yaxes(title=f"Change in holdout cost at {ratio} (negative = the "
                              "policy cost more)", ticksuffix="%")
    figure.update_layout(showlegend=False, bargap=0.0)
    return _layout(
        figure,
        f"One rule, {len(frame)} products, two outcomes: the {ratio} newsvendor "
        "order is cheaper on most and worse on a real minority",
        height=470,
    )


# ── Stage 5: where it breaks ────────────────────────────────────────────────

def christmas_coverage(weekly: pd.DataFrame, scored: pd.DataFrame, code: str,
                       names: pd.Series) -> go.Figure:
    """The seasonal failure the 84% average hides, at two levels of zoom.

    Top: coverage week by week across the whole cohort, with the Oct-Nov ramp
    shaded. Bottom: the same weeks for one Christmas product, so the miss is a
    product a person can picture rather than a dip in an average.

    ``weekly`` is ``intervals.coverage_by_week``; ``scored`` is
    ``forecast.score_holdout``.
    """
    frame = scored[scored["StockCode"] == code].sort_values("week")
    weeks = list(frame["week"])
    actual = frame["actual"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    missed = (actual > high) | (actual < low)

    ramp = weekly[weekly["week"].dt.month.isin(config.Q4_RAMP_MONTHS)]["week"]
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        row_heights=[0.46, 0.54],
        subplot_titles=(
            f"All {config.COHORT_SIZE} products: share of the week's forecasts "
            "that landed inside the band",
            f"{names.get(code, code)} ({code}): the band, and what actually sold",
        ),
    )
    figure.add_scatter(
        x=weekly["week"], y=weekly["coverage"], mode="lines+markers",
        line=dict(color=config.COLOR_FORECAST, width=2.2), marker=dict(size=7),
        name="Coverage that week",
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:.1%} covered<extra></extra>",
        row=1, col=1,
    )
    figure.add_hline(
        y=config.NOMINAL_COVERAGE, line_dash="dash", line_color=config.COLOR_ACTUAL,
        annotation_text=f"promised {config.NOMINAL_COVERAGE:.0%}",
        annotation_position="bottom left", annotation_font_size=11, row=1, col=1,
    )
    if len(ramp):
        for row in (1, 2):
            figure.add_vrect(
                x0=ramp.min(), x1=ramp.max(), fillcolor=config.COLOR_WARN,
                opacity=0.14, line_width=0,
                annotation_text="the Oct-Nov ramp" if row == 1 else None,
                annotation_position="top left", annotation_font_size=11,
                row=row, col=1,
            )
    figure.add_scatter(
        x=weeks, y=high, mode="lines", line=dict(width=0, color=config.COLOR_BAND),
        showlegend=False, hoverinfo="skip", row=2, col=1,
    )
    figure.add_scatter(
        x=weeks, y=low, mode="lines", line=dict(width=0, color=config.COLOR_BAND),
        fill="tonexty", fillcolor="rgba(99,110,250,0.20)",
        name=f"{config.NOMINAL_COVERAGE:.0%} band", hoverinfo="skip", row=2, col=1,
    )
    figure.add_scatter(
        x=weeks, y=actual, mode="lines+markers",
        line=dict(color=config.COLOR_ACTUAL, width=1.6),
        marker=dict(size=9, color=np.where(missed, config.COLOR_MISS,
                                           config.COLOR_ACTUAL),
                    symbol=np.where(missed, "x", "circle")),
        name="What actually sold",
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:,.0f} units<extra></extra>",
        row=2, col=1,
    )
    figure.update_yaxes(title="Covered", tickformat=".0%", range=[0, 1.05],
                        row=1, col=1)
    figure.update_yaxes(title="Units in the week", rangemode="tozero", row=2, col=1)
    figure.update_xaxes(title="Held-out week beginning (Monday)", row=2, col=1)
    figure.update_layout(legend=dict(orientation="h", y=-0.16, x=0, font_size=11))
    above = int((actual > high).sum())
    return _layout(
        figure,
        f"The average holds until the season starts: {int(missed.sum())} misses on "
        f"this product and {above} of them are ABOVE the band - a stockout, not a "
        "surplus",
        height=620,
    )


def metric_panel(summary: dict) -> go.Figure:
    """The frozen metric set in one frame, each metric beside what judges it.

    ``summary`` is ``metrics.score_frame``. Nothing here is a new measurement;
    the panel exists so no single number can be quoted without its companion.
    """
    figure = make_subplots(
        rows=2, cols=2, vertical_spacing=0.24, horizontal_spacing=0.16,
        subplot_titles=(
            "Typical miss, against the forecast that learned nothing",
            f"Coverage against the {config.NOMINAL_COVERAGE:.0%} it promised",
            "Pinball loss: each edge of the band, scored on its own",
            "How wide the band is, against the demand it covers",
        ),
    )
    # 1: MAE / RMSE / flat zero
    figure.add_bar(
        x=["MAE", "RMSE", "MAE of a<br>flat-zero forecast"],
        y=[summary["MAE"], summary["RMSE"], summary["MAE_flat_zero"]],
        marker_color=[config.COLOR_FORECAST, config.COLOR_WARN, config.COLOR_MUTED],
        text=[f"{summary['MAE']:,.1f}", f"{summary['RMSE']:,.1f}",
              f"{summary['MAE_flat_zero']:,.1f}"],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:,.2f} units<extra></extra>",
        row=1, col=1,
    )
    # 2: coverage
    figure.add_bar(
        x=["Delivered", "Promised"],
        y=[summary["coverage_80"], config.NOMINAL_COVERAGE],
        marker_color=[config.COLOR_ACCENT, config.COLOR_MUTED],
        text=[f"{summary['coverage_80']:.2%}", f"{config.NOMINAL_COVERAGE:.0%}"],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:.2%} of held-out product-weeks<extra></extra>",
        row=1, col=2,
    )
    # 3: pinball
    figure.add_bar(
        x=["@ 0.1<br>lower edge", "@ 0.5<br>middle line", "@ 0.9<br>upper edge"],
        y=[summary["pinball_10"], summary["pinball_50"], summary["pinball_90"]],
        marker_color=[config.COLOR_MUTED, config.COLOR_FORECAST, config.COLOR_ACCENT],
        text=[f"{summary['pinball_10']:.3f}", f"{summary['pinball_50']:.3f}",
              f"{summary['pinball_90']:.3f}"],
        textposition="outside",
        hovertemplate="Pinball %{x}<br>%{y:.3f}<extra></extra>",
        row=2, col=1,
    )
    # 4: band width vs demand
    figure.add_bar(
        x=["Median band width", "Median non-zero<br>week of demand"],
        y=[summary["median_band"], summary["median_nonzero_demand"]],
        marker_color=[config.COLOR_FORECAST, config.COLOR_ACTUAL],
        text=[f"{summary['median_band']:,.1f}",
              f"{summary['median_nonzero_demand']:,.1f}"],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:,.1f} units<extra></extra>",
        row=2, col=2,
    )
    figure.update_yaxes(title="Units", rangemode="tozero", row=1, col=1)
    figure.update_yaxes(title="Share of held-out weeks", tickformat=".0%",
                        range=[0, 1.05], row=1, col=2)
    figure.update_yaxes(title="Loss (lower is better)", rangemode="tozero",
                        row=2, col=1)
    figure.update_yaxes(title="Units", rangemode="tozero", row=2, col=2)
    figure.update_layout(showlegend=False, bargap=0.42, uniformtext_minsize=10)
    return _layout(
        figure,
        f"The frozen holdout, {summary['n_rows']:,} product-weeks: every headline "
        f"number printed beside the one that keeps it honest "
        f"(band = {summary['band_over_median_demand']:.2f}x the median week)",
        height=680,
    )
