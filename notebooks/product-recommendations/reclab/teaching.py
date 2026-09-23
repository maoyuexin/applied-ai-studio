"""Small, classroom-facing API for the Module 6 Next Best Product lesson."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import wrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config, data, evaluate, matrix, models, policy

BASELINE_LABEL = config.POPULARITY_LABEL
MODEL_LABEL = config.DEPLOYED_MODEL_LABEL
FULL_MODEL_LABEL = config.ITEMITEM_FULL_LABEL


@dataclass(frozen=True)
class LessonData:
    """The verified transaction data and chronological split."""

    interactions: pd.DataFrame
    descriptions: pd.Series
    split: matrix.Split


def load_lesson() -> LessonData:
    """Load the committed interactions and make the global time split."""
    interactions = data.load_interactions()
    descriptions = data.load_descriptions()
    split = matrix.build_split(interactions)
    return LessonData(interactions, descriptions, split)


def lesson_summary(lesson: LessonData) -> pd.DataFrame:
    """Only the facts needed to understand the recommendation question."""
    split = lesson.split
    density = split.R.nnz / (split.n_users * split.n_items)
    rows = [
        ("Committed basket-product rows", f"{len(lesson.interactions):,}"),
        ("Training matrix", f"{split.n_users:,} customers x {split.n_items:,} products"),
        ("Filled customer-product cells", f"{split.R.nnz:,} ({density:.3%})"),
        ("Empty cells", f"{1 - density:.3%}"),
        ("Customers in the discovery test", f"{len(split.truth_discovery):,}"),
        ("Ranking question", "which unseen products belong in ten slots?"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def fit_models(split: matrix.Split) -> dict[str, models.Fitted]:
    """Fit the baseline plus full and top-15 item-item candidates."""
    dense = models.item_similarity(split.R)
    return {
        BASELINE_LABEL: models.fit_popularity(split),
        FULL_MODEL_LABEL: models.fit_item_item(
            split, None, FULL_MODEL_LABEL, similarity=dense),
        MODEL_LABEL: models.fit_item_item(
            split, config.ITEM_NEIGHBOURS, MODEL_LABEL, similarity=dense),
    }


def model_selection_table(split: matrix.Split,
                          fitted: dict[str, models.Fitted]) -> pd.DataFrame:
    """Compare the baseline and two explainable item-item variants."""
    table = evaluate.leaderboard(
        split, fitted, config.PROTOCOL_DISCOVERY,
        include=[BASELINE_LABEL, FULL_MODEL_LABEL, MODEL_LABEL], k=config.SLOTS,
    )
    descriptions = {
        BASELINE_LABEL: "Same popular list for everyone",
        FULL_MODEL_LABEL: "Keep every nonzero product-product similarity",
        MODEL_LABEL: "Keep only each product's 15 strongest neighbors",
    }
    table.insert(1, "How it works", table["Model"].map(descriptions))
    table["Selected"] = table["Model"] == MODEL_LABEL
    return table[["Model", "How it works", "HR@10", "Coverage",
                  "Fit seconds", "Selected"]]


def comparison_table(split: matrix.Split,
                     fitted: dict[str, models.Fitted]) -> pd.DataFrame:
    """Score both models on new products only, with seen products excluded."""
    table = evaluate.leaderboard(
        split,
        fitted,
        config.PROTOCOL_DISCOVERY,
        include=[BASELINE_LABEL, MODEL_LABEL],
        k=config.SLOTS,
    )
    return table[["Model", "HR@10", "Coverage", "Customers scored", "Fit seconds"]]


def cold_start_summary(lesson: LessonData) -> pd.DataFrame:
    """Keep registered cold-start customers and guest baskets separate."""
    census = policy.cold_start_census(lesson.interactions, lesson.split)
    rows = [
        ("Registered customers active after the cut", census["registered_customers_active_in_test"],
         "all registered test-window customers"),
        ("No usable history: use Popular right now", census["unservable_customers"],
         f"{census['unservable_share']:.1%} of registered test-window customers"),
        ("Guest baskets: no customer identity", census["guest_baskets_in_test"],
         "separate population; not added to the customer percentage"),
    ]
    return pd.DataFrame(rows, columns=["Population", "Count", "Denominator or action"])


def example_recommendations(lesson: LessonData, fitted: models.Fitted) -> pd.DataFrame:
    """Choose the first test customer with a visible held-out hit."""
    split = lesson.split
    users = sorted(split.truth_discovery)
    ranked = evaluate.ranked_lists(split, fitted, config.PROTOCOL_DISCOVERY, users)
    user = next(user for user in users
                if set(ranked[user].tolist()) & split.truth_discovery[user])
    scores = models.score(fitted, split, [user])[0]
    rows = []
    for slot, item in enumerate(ranked[user], start=1):
        code = split.items[int(item)]
        rows.append({
            "Slot": slot,
            "Customer": split.users[user],
            "StockCode": code,
            "Product": lesson.descriptions.get(code, code),
            "Score": float(scores[int(item)]),
            "Bought later": int(item) in split.truth_discovery[user],
        })
    return pd.DataFrame(rows)


def similar_product_table(lesson: LessonData, fitted: models.Fitted,
                          code: str = "85099B", count: int = 5) -> pd.DataFrame:
    """The strongest real product neighbors for a familiar product."""
    split = lesson.split
    item = split.item_index[code]
    similarities = fitted.payload.getrow(item).toarray().ravel()
    neighbors = np.argsort(-similarities)[:count]
    return pd.DataFrame({
        "Rank": np.arange(1, len(neighbors) + 1),
        "Source product": lesson.descriptions.get(code, code),
        "Similar product": [lesson.descriptions.get(split.items[index], split.items[index])
                            for index in neighbors],
        "Cosine similarity": similarities[neighbors],
    })


def product_pair_summary(lesson: LessonData, code: str = "85099B",
                         other_code: str = "22386") -> pd.DataFrame:
    """Count distinct training buyers for an explicit product pair."""
    split = lesson.split
    source = split.R[:, split.item_index[code]]
    other = split.R[:, split.item_index[other_code]]
    source_buyers = int(source.sum())
    other_buyers = int(other.sum())
    shared_buyers = int(source.multiply(other).sum())
    denominator = np.sqrt(source_buyers * other_buyers)
    return pd.DataFrame([{
        "Source code": code,
        "Source product": lesson.descriptions.get(code, code),
        "Other code": other_code,
        "Other product": lesson.descriptions.get(other_code, other_code),
        "Source buyers": source_buyers,
        "Other buyers": other_buyers,
        "Shared buyers": shared_buyers,
        "Cosine similarity": shared_buyers / denominator if denominator else 0.0,
    }])


def recommendation_explanations(lesson: LessonData, fitted: models.Fitted,
                                recommendations: pd.DataFrame,
                                count: int = 5) -> pd.DataFrame:
    """Show which previously bought item contributes most to each real ranking."""
    split = lesson.split
    customer = int(recommendations["Customer"].iloc[0])
    user = split.user_index[customer]
    seen = np.array(sorted(split.seen[user]), dtype=int)
    rows = []
    for _, recommendation in recommendations.head(count).iterrows():
        candidate = split.item_index[str(recommendation["StockCode"])]
        contributions = fitted.payload[seen, candidate].toarray().ravel()
        strongest = int(seen[int(np.argmax(contributions))])
        source_code = split.items[strongest]
        rows.append({
            "Slot": int(recommendation["Slot"]),
            "Recommended product": recommendation["Product"],
            "Total score": float(recommendation["Score"]),
            "Strongest history match": lesson.descriptions.get(source_code, source_code),
            "Similarity contribution": float(contributions.max()),
            "Bought later": bool(recommendation["Bought later"]),
        })
    return pd.DataFrame(rows)


def _layout(figure: go.Figure, title: str, height: int = 440) -> go.Figure:
    figure.update_layout(
        title=title,
        template=config.PLOT_TEMPLATE,
        height=height,
        margin=dict(l=75, r=35, t=85, b=70),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


def time_split_figure(lesson: LessonData) -> go.Figure:
    """Transaction activity remains in chronological order around the cut."""
    registered = lesson.interactions.dropna(subset=["customer_id"]).copy()
    weekly = registered.set_index("invoice_ts").resample("W-MON")["invoice"].nunique()
    figure = go.Figure(go.Scatter(
        x=weekly.index, y=weekly.values, mode="lines",
        line=dict(color=config.COLOR_MODEL, width=1.8),
        hovertemplate="week of %{x|%Y-%m-%d}<br>%{y:,} baskets<extra></extra>",
    ))
    figure.add_vline(x=lesson.split.cut, line_dash="dash", line_width=2,
                     line_color=config.COLOR_RISK,
                     annotation_text="test starts")
    figure.update_xaxes(title="Week", tickformat="%b<br>%Y",
                        range=[weekly.index.min(), weekly.index.max()])
    figure.update_yaxes(title="Registered-customer baskets", rangemode="tozero")
    return _layout(figure, "Train earlier, test later")


def matrix_figure(lesson: LessonData, customers: int = 10,
                  products: int = 12) -> go.Figure:
    """A labeled sample explains the sparse customer-product matrix."""
    split = lesson.split
    item_rows = np.argsort(-split.popularity)[:products]
    activity = np.asarray(split.R[:, item_rows].sum(axis=1)).ravel()
    user_rows = np.argsort(-activity)[:customers]
    values = split.R[user_rows][:, item_rows].toarray()
    labels = [str(lesson.descriptions.get(split.items[index], split.items[index]))[:26]
              for index in item_rows]
    user_labels = [str(split.users[index]) for index in user_rows]
    figure = go.Figure(go.Heatmap(
        z=values,
        x=labels,
        y=user_labels,
        colorscale=[[0, "#F1F3F5"], [1, config.COLOR_MODEL]],
        showscale=False,
        hovertemplate="customer %{y}<br>%{x}<br>bought = %{z:.0f}<extra></extra>",
    ))
    figure.update_xaxes(title="Product", tickangle=-35)
    figure.update_yaxes(title="Customer ID", autorange="reversed")
    return _layout(figure, "Customer-product matrix",
                   height=500)


def similar_products_figure(lesson: LessonData, fitted: models.Fitted,
                            code: str = "85099B", count: int = 10) -> go.Figure:
    """Show the nearest products learned from shared customer histories."""
    split = lesson.split
    item = split.item_index[code]
    row = fitted.payload.getrow(item).toarray().ravel()
    neighbours = np.argsort(-row)[:count]
    frame = pd.DataFrame({
        "Product": [str(lesson.descriptions.get(split.items[index], split.items[index]))
                    for index in neighbours],
        "Similarity": row[neighbours],
    }).sort_values("Similarity")
    labels = frame["Product"].map(lambda name: "<br>".join(wrap(name, width=14)))
    figure = go.Figure(go.Bar(
        x=frame["Similarity"], y=labels, orientation="h",
        marker_color=config.COLOR_ACCENT,
        text=frame["Similarity"].map("{:.3f}".format), textposition="outside",
        cliponaxis=False, customdata=frame["Product"],
        hovertemplate="%{customdata}<br>similarity %{x:.3f}<extra></extra>",
    ))
    figure.update_xaxes(title="Cosine similarity", range=[0, float(row.max()) * 1.28],
                        nticks=4, tickangle=0)
    figure.update_yaxes(title="")
    name = "<br>".join(wrap(str(lesson.descriptions.get(code, code)), width=24))
    return _layout(figure, f"Neighbors of product {code}<br><sup>{name}</sup>",
                   height=650)


def buyer_overlap_figure(lesson: LessonData, code: str = "85099B",
                         other_code: str = "22386") -> go.Figure:
    """Show mutually exclusive buyer groups behind one cosine calculation."""
    pair = product_pair_summary(lesson, code, other_code).iloc[0]
    shared = int(pair["Shared buyers"])
    counts = [int(pair["Source buyers"]) - shared, shared,
              int(pair["Other buyers"]) - shared]
    labels = [f"{code}<br>only", "Both<br>products", f"{other_code}<br>only"]
    figure = go.Figure(go.Bar(
        x=labels, y=counts,
        marker_color=[config.COLOR_MODEL, config.COLOR_ACCENT, config.COLOR_WARN],
        text=[f"{count:,}" for count in counts], textposition="outside",
        cliponaxis=False,
        hovertemplate="%{x}<br>%{y:,} distinct customers<extra></extra>",
    ))
    figure.update_xaxes(title="Training purchase history")
    figure.update_yaxes(title="Distinct customers", range=[0, max(counts) * 1.2])
    return _layout(figure, f"Who bought both products?<br><sup>{code} and {other_code}</sup>")


def neighbor_retention_figure(lesson: LessonData, full: models.Fitted,
                              retained: models.Fitted, code: str = "85099B",
                              count: int = 20) -> go.Figure:
    """Compare actual full similarities with the saved top-15 row."""
    split = lesson.split
    source = split.item_index[code]
    row = np.asarray(full.payload[source]).ravel()
    indices = np.argsort(-row)
    indices = indices[(indices != source) & (row[indices] > 0)][:count]
    saved = retained.payload.getrow(source).toarray().ravel()[indices] > 0
    ranks = np.arange(1, len(indices) + 1)
    codes = [split.items[index] for index in indices]
    names = [str(lesson.descriptions.get(code, code)) for code in codes]
    details = np.column_stack([codes, names])
    figure = go.Figure()
    for mask, label, color in [(saved, "Saved link", config.COLOR_ACCENT),
                               (~saved, "Not saved", config.COLOR_MUTED)]:
        figure.add_bar(
            x=ranks[mask], y=row[indices][mask], name=label, marker_color=color,
            customdata=details[mask],
            hovertemplate=("Rank %{x}<br>%{customdata[0]}: %{customdata[1]}"
                           "<br>similarity %{y:.3f}<extra>%{fullData.name}</extra>"),
        )
    figure.add_vline(x=config.ITEM_NEIGHBOURS + 0.5, line_dash="dash",
                     line_color=config.COLOR_RISK)
    figure.update_xaxes(title="Neighbor rank (strongest first)",
                       tickvals=[1, 5, 10, 15, 20], range=[0.3, len(indices) + 0.7])
    figure.update_yaxes(title="Cosine similarity", rangemode="tozero")
    figure.update_layout(legend=dict(orientation="h", y=1.08, x=0))
    return _layout(figure, f"Keep the 15 strongest links<br><sup>Source product: {code}</sup>",
                   height=470)


def comparison_figure(table: pd.DataFrame) -> go.Figure:
    """Hit Rate and catalog coverage answer different questions."""
    colors = [config.COLOR_WARN, config.COLOR_ACCENT]
    figure = make_subplots(rows=1, cols=2,
                           subplot_titles=("Hit Rate at 10", "Catalog coverage"))
    for column, metric_name in enumerate(("HR@10", "Coverage"), start=1):
        figure.add_bar(x=table["Model"], y=table[metric_name], marker_color=colors,
                       text=table[metric_name].map("{:.1%}".format),
                       textposition="outside", showlegend=False,
                       row=1, col=column)
        figure.update_yaxes(tickformat=".0%", rangemode="tozero", row=1, col=column)
    figure.update_xaxes(tickangle=-12)
    return _layout(figure, "Hits and catalog coverage",
                   height=460)


def recommendation_figure(frame: pd.DataFrame) -> go.Figure:
    """One ranked list connects model scores to a visible workflow action."""
    ordered = frame.sort_values("Slot", ascending=False)
    colors = np.where(ordered["Bought later"], config.COLOR_ACCENT, config.COLOR_MUTED)
    labels = ordered["Product"].str.slice(0, 30)
    figure = go.Figure(go.Bar(
        x=ordered["Score"], y=labels, orientation="h", marker_color=colors,
        customdata=np.column_stack([ordered["Slot"], ordered["Bought later"]]),
        hovertemplate="slot %{customdata[0]}<br>score %{x:.3f}<br>bought later = %{customdata[1]}<extra></extra>",
    ))
    figure.update_xaxes(title="Ranking score")
    figure.update_yaxes(title="")
    customer = int(frame["Customer"].iloc[0])
    hits = int(frame["Bought later"].sum())
    return _layout(figure, f"Customer {customer}: {hits} held-out hit",
                   height=520)