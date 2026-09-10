"""The operating policy: ten slots, who gets personalized, and what everyone else sees.

The model produces a ranking. The policy decides what a shopper is actually
shown, and it is a written rule a merchandiser could read:

    for each shopper:
        if the shopper is in the training matrix:
            rank products they have NEVER bought, using item-item top-15
            remove anything on the merchandiser's exclusion list
            fill 10 slots under the heading "Recommended for you"
            if fewer than 10 products score above zero, backfill from the
            fallback list and re-label the backfilled slots
        else:
            show the fallback list under the heading "Popular right now"

    Products the shopper already owns are never eligible for these slots. They
    belong to a separate "Buy it again" strip, which is a replenishment
    reminder and is never counted, measured or reported as personalization.

Two populations are called "cold start" in retail and they are NOT the same
thing. This module keeps them apart everywhere:

    cold registered customer  a customer id we have never seen buy anything
                              before the cut
    guest checkout            a transaction with no customer id at all

They cannot be added together, and a sentence that says "cold start" without
saying which one it means is not a measurement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, models
from .matrix import Split


# ── Who can be served ───────────────────────────────────────────────────────

def cold_start_census(frame: pd.DataFrame, split: Split) -> dict:
    """Count both populations separately, in the test window, and price them."""
    train_customers = set(split.train_rows["customer_id"].dropna().astype(int))
    test_customers = set(split.test_rows["customer_id"].dropna().astype(int))
    servable = set(split.users)

    cold = test_customers - train_customers
    thin = (test_customers & train_customers) - servable
    unservable = cold | thin

    test_revenue = float(split.test_rows["revenue"].sum())
    cold_revenue = float(
        split.test_rows[split.test_rows["customer_id"].isin(cold)]["revenue"].sum())

    train_items = set(split.train_rows["stock_code"])
    test_items = set(split.test_rows["stock_code"])
    cold_items = test_items - train_items
    cold_item_revenue = float(
        split.test_rows[split.test_rows["stock_code"].isin(cold_items)]["revenue"].sum())

    after_cut = frame[frame["invoice_ts"] > split.cut]
    guest = after_cut[after_cut["customer_id"].isna()]

    return {
        "registered_customers_active_in_test": int(len(test_customers)),
        "cold_registered_customers": int(len(cold)),
        "cold_registered_share": float(len(cold) / len(test_customers)),
        "cold_registered_revenue_share": float(cold_revenue / test_revenue),
        "thin_history_customers": int(len(thin)),
        "thin_history_share": float(len(thin) / len(test_customers)),
        "unservable_customers": int(len(unservable)),
        "unservable_share": float(len(unservable) / len(test_customers)),
        "products_sold_in_test": int(len(test_items)),
        "cold_products": int(len(cold_items)),
        "cold_product_share": float(len(cold_items) / len(test_items)),
        "cold_product_revenue_share": float(cold_item_revenue / test_revenue),
        "guest_rows_in_test": int(len(guest)),
        "all_rows_in_test": int(len(after_cut)),
        "guest_row_share": float(len(guest) / len(after_cut)),
        "guest_baskets_in_test": int(guest["invoice"].nunique()),
        "guest_revenue_share": float(guest["revenue"].sum() / after_cut["revenue"].sum()),
        "warning": (
            "The cold-registered share and the guest share are different "
            "populations measured against different denominators. They must "
            "never be added together or used interchangeably."
        ),
    }


def cold_user_behavior() -> pd.DataFrame:
    """What each model returns when it is handed an empty history."""
    rows = [
        (config.POPULARITY_LABEL,
         "defined - it never looked at the customer",
         "works, but it is not personalization"),
        (config.DEPLOYED_MODEL_LABEL,
         "R[u] is an all-zero row, so R[u] @ S is the zero vector",
         "an arbitrary tie-break over 4,443 products, not a recommendation"),
        (config.SVD_LABEL,
         "no customer factor exists; folding in a zero row gives the zero factor",
         "the same - zero scores in an arbitrary order"),
        (config.REORDER_LABEL,
         "there is nothing to reorder",
         "undefined"),
    ]
    return pd.DataFrame(rows, columns=["Model", "What happens on an empty history",
                                       "What it actually returns"])


# ── Choosing the fallback by measurement ────────────────────────────────────

def fallback_candidates(split: Split, k: int = config.SLOTS) -> dict[str, list[str]]:
    """Five plausible generic lists, so the chosen one is chosen, not assumed."""
    train = split.train_rows
    candidates = {
        "All-time popular (by baskets)":
            train.groupby("stock_code")["invoice"].nunique()
                 .sort_values(ascending=False).head(k).index.tolist(),
    }
    for days in (14, 28, 56):
        window = train[train["invoice_ts"] > split.cut - pd.Timedelta(days=days)]
        candidates[f"Recent trending, last {days} days (by baskets)"] = (
            window.groupby("stock_code")["invoice"].nunique()
                  .sort_values(ascending=False).head(k).index.tolist())
    window = train[train["invoice_ts"] > split.cut - pd.Timedelta(days=config.FALLBACK_WINDOW_DAYS)]
    candidates[f"Recent revenue, last {config.FALLBACK_WINDOW_DAYS} days"] = (
        window.groupby("stock_code")["revenue"].sum()
              .sort_values(ascending=False).head(k).index.tolist())
    return candidates


def fallback_sweep(split: Split, k: int = config.SLOTS) -> pd.DataFrame:
    """Score every candidate on what the cold customers really bought next.

    The denominator is the cold registered customers who bought anything in the
    test window - not the servable population, and not the guests.
    """
    train_customers = set(split.train_rows["customer_id"].dropna().astype(int))
    test_rows = split.test_rows
    cold = test_rows[~test_rows["customer_id"].isin(train_customers)]
    truth = cold.groupby("customer_id")["stock_code"].apply(set)

    rows = []
    for name, items in fallback_candidates(split, k).items():
        chosen = set(items)
        hit_rate = float(np.mean([len(chosen & bought) > 0 for bought in truth]))
        precision = float(np.mean([len(chosen & bought) / k for bought in truth]))
        rows.append({"Fallback rule": name, "HR@10": hit_rate,
                     "Precision@10": precision, "Cold customers scored": int(len(truth))})
    return pd.DataFrame(rows).sort_values("HR@10", ascending=False).reset_index(drop=True)


def fallback_list(split: Split, descriptions: pd.Series,
                  k: int = config.SLOTS) -> pd.DataFrame:
    """The chosen fallback, rendered as the ten products a shopper would see."""
    codes = models.fallback_items(split, config.FALLBACK_WINDOW_DAYS, k)
    window = split.train_rows[
        split.train_rows["invoice_ts"] > split.cut - pd.Timedelta(days=config.FALLBACK_WINDOW_DAYS)]
    revenue = window.groupby("stock_code")["revenue"].sum()
    return pd.DataFrame({
        "Slot": np.arange(1, len(codes) + 1),
        "Stock code": codes,
        "Product": [descriptions.get(code, "") for code in codes],
        "Revenue in the last 28 training days": [float(revenue.get(code, 0.0)) for code in codes],
    })


# ── What the policy does to the whole test window ───────────────────────────

def policy_outcomes(frame: pd.DataFrame, split: Split,
                    fitted: models.Fitted, k: int = config.SLOTS) -> dict:
    """Who gets personalized, who gets the fallback, and how many slots each."""
    test_customers = sorted(split.test_rows["customer_id"].dropna().astype(int).unique())
    servable = set(split.users)
    personalized = [c for c in test_customers if c in servable]
    fallback = [c for c in test_customers if c not in servable]

    rows = [split.user_index[c] for c in personalized]
    scores = models.score(fitted, split, rows)
    for position, user in enumerate(rows):
        scores[position, list(split.seen[user])] = -np.inf
    positive = (scores > 0).sum(axis=1)
    backfilled_slots = int(np.clip(k - positive, 0, k).sum())

    after_cut = frame[frame["invoice_ts"] > split.cut]
    guest = after_cut[after_cut["customer_id"].isna()]
    total_slots = len(test_customers) * k
    return {
        "test_window_customers": int(len(test_customers)),
        "personalized_customers": int(len(personalized)),
        "personalized_share": float(len(personalized) / len(test_customers)),
        "fallback_customers": int(len(fallback)),
        "fallback_share": float(len(fallback) / len(test_customers)),
        "customers_needing_partial_backfill": int((positive < k).sum()),
        "partial_backfill_share": float((positive < k).mean()),
        "slots_total": int(total_slots),
        "slots_from_fallback": int(len(fallback) * k + backfilled_slots),
        "fallback_slot_share": float((len(fallback) * k + backfilled_slots) / total_slots),
        "guest_baskets_in_test": int(guest["invoice"].nunique()),
        "guest_revenue_share_of_test": float(
            guest["revenue"].sum() / after_cut["revenue"].sum()),
        "guest_fallback_share": 1.0,
    }


def policy_statement() -> str:
    """The written rule, exactly as it is exported to the service."""
    return f"""\
{config.SLOTS} slots, module titled "{config.MODULE_TITLE}"

for each shopper:
    if the shopper is in the training matrix
       ({config.PERSONALIZE_IF}):
        rank = {config.DEPLOYED_MODEL} scored over
               {config.ELIGIBILITY}
        remove anything on the merchandiser's exclusion list
        fill {config.SLOTS} slots
        if fewer than {config.SLOTS} products score above zero, backfill from the
           fallback list and re-label the backfilled slots
    else:
        show the fallback list, labeled "{config.FALLBACK_TITLE}"
        - NOT "{config.MODULE_TITLE}"

fallback = {config.FALLBACK_RULE}, refreshed {config.FALLBACK_REFRESH}

Products the shopper already owns are never eligible for these slots. They
belong to a separate "{config.REORDER_TITLE}" strip, which is a replenishment
reminder and is never counted, measured or reported as personalization.

{config.HUMAN_AUTHORITY}."""
