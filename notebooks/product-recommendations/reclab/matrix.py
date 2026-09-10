"""Turn the transaction log into a customer x product matrix and split it in time.

The split is the most consequential decision in this lab and it is made here,
once, before any model exists. It is a **global time split**: everything on or
before 2011-09-09 is training, everything after is test, for every customer at
once. A random split would put December's baskets in training and September's
in test - a question nobody can ask in production, and a model that has already
seen the future it is being graded on.

Two ground truths come out of the same test window, because this case turns on
the difference between them:

``truth_standard``   every product the customer bought after the cut
``truth_discovery``  only the ones they had never bought before it
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import config


@dataclass
class Split:
    """Everything downstream needs, built once."""

    train_rows: pd.DataFrame          # committed rows on or before the cut
    test_rows: pd.DataFrame           # committed rows after the cut
    train_pairs: pd.DataFrame         # deduped (customer, product), matrix members only
    test_pairs: pd.DataFrame          # deduped (customer, product) inside the matrix
    items: list[str]                  # column order: stock codes
    users: list[int]                  # row order: customer ids
    item_index: dict[str, int]
    user_index: dict[int, int]
    R: sp.csr_matrix                  # the customer x product matrix, 1 = bought
    seen: list[set[int]] = field(repr=False)
    truth_standard: dict[int, set[int]] = field(repr=False)
    truth_discovery: dict[int, set[int]] = field(repr=False)
    cut: pd.Timestamp = config.SPLIT_CUT

    # ── convenience ────────────────────────────────────────────────────────
    @property
    def n_users(self) -> int:
        return self.R.shape[0]

    @property
    def n_items(self) -> int:
        return self.R.shape[1]

    @property
    def popularity(self) -> np.ndarray:
        """Number of matrix customers who bought each product in training."""
        return np.asarray(self.R.sum(0)).ravel()

    @property
    def popularity_rank(self) -> np.ndarray:
        """1 = most bought. Ties share the lower rank."""
        return pd.Series(self.popularity).rank(ascending=False, method="min").values


def build_split(frame: pd.DataFrame, cut: pd.Timestamp = config.SPLIT_CUT,
                min_items: int = config.MIN_TRAIN_ITEMS_PER_USER) -> Split:
    """Global time split, registered customers only, >= ``min_items`` to qualify."""
    registered = frame.dropna(subset=["customer_id"]).copy()
    registered["customer_id"] = registered["customer_id"].astype(int)

    train_rows = registered[registered["invoice_ts"] <= cut]
    test_rows = registered[registered["invoice_ts"] > cut]

    train_pairs = train_rows.drop_duplicates(["customer_id", "stock_code"])
    counts = train_pairs.groupby("customer_id")["stock_code"].size()
    qualified = counts[counts >= min_items].index
    train_pairs = train_pairs[train_pairs["customer_id"].isin(qualified)]

    items = sorted(train_pairs["stock_code"].unique())
    users = sorted(train_pairs["customer_id"].unique())
    item_index = {code: i for i, code in enumerate(items)}
    user_index = {cid: i for i, cid in enumerate(users)}

    test_pairs = test_rows.drop_duplicates(["customer_id", "stock_code"])
    test_pairs = test_pairs[test_pairs["customer_id"].isin(user_index)
                            & test_pairs["stock_code"].isin(item_index)]

    R = sp.csr_matrix(
        (np.ones(len(train_pairs)),
         (train_pairs["customer_id"].map(user_index),
          train_pairs["stock_code"].map(item_index))),
        shape=(len(users), len(items)),
    )
    R.sum_duplicates()

    seen = [set(R[u].indices.tolist()) for u in range(R.shape[0])]
    truth_standard: dict[int, set[int]] = {}
    truth_discovery: dict[int, set[int]] = {}
    for u, i in zip(test_pairs["customer_id"].map(user_index).to_numpy(),
                    test_pairs["stock_code"].map(item_index).to_numpy()):
        u, i = int(u), int(i)
        truth_standard.setdefault(u, set()).add(i)
        if i not in seen[u]:
            truth_discovery.setdefault(u, set()).add(i)

    return Split(train_rows=train_rows, test_rows=test_rows,
                 train_pairs=train_pairs, test_pairs=test_pairs,
                 items=items, users=users, item_index=item_index,
                 user_index=user_index, R=R, seen=seen,
                 truth_standard=truth_standard, truth_discovery=truth_discovery,
                 cut=cut)


def split_summary(frame: pd.DataFrame, split: Split) -> pd.DataFrame:
    """The shape of the split, as a table the notebook prints once."""
    R = split.R
    density = R.nnz / (R.shape[0] * R.shape[1])
    rows = [
        ("Committed rows", f"{len(frame):,}"),
        ("Rows on or before the cut (training)", f"{len(split.train_rows):,}"),
        ("Rows after the cut (test)", f"{len(split.test_rows):,}"),
        ("Training (customer, product) pairs in the matrix", f"{len(split.train_pairs):,}"),
        ("Test (customer, product) pairs inside the matrix", f"{len(split.test_pairs):,}"),
        ("Matrix", f"{R.shape[0]:,} customers x {R.shape[1]:,} products"),
        ("Filled cells", f"{R.nnz:,}"),
        ("Density / sparsity", f"{density:.3%} / {1 - density:.3%}"),
        ("Customers scorable under the standard protocol", f"{len(split.truth_standard):,}"),
        ("Customers scorable under the discovery protocol", f"{len(split.truth_discovery):,}"),
        ("Training span",
         f"{split.train_rows['invoice_ts'].min().date()} to {split.cut.date()}"),
        ("Test span",
         f"{split.cut.date()} to {split.test_rows['invoice_ts'].max().date()}"),
    ]
    return pd.DataFrame(rows, columns=["Quantity", "Value"])


def repeat_purchase_profile(split: Split) -> dict:
    """How much of the test window is a customer buying something again.

    This one measurement explains the entire headline of the case: if a large
    share of the correct answers are products the customer already owns, a
    model that lists what they already own wins the accuracy table without
    learning anything.
    """
    total = sum(len(v) for v in split.truth_standard.values())
    new = sum(len(v) for v in split.truth_discovery.values())
    repeat = total - new

    owned = split.train_pairs[["customer_id", "stock_code"]].assign(_owned=1)
    marked = split.test_rows.merge(owned, on=["customer_id", "stock_code"], how="left")
    test_revenue = float(marked["revenue"].sum())
    repeat_revenue = float(marked.loc[marked["_owned"] == 1, "revenue"].sum())

    users_with_repeat = sum(
        1 for u, truth in split.truth_standard.items()
        if len(truth) > len(split.truth_discovery.get(u, set()))
    )
    return {
        "test_truth_pairs": int(total),
        "repeat_pairs": int(repeat),
        "repeat_share": float(repeat / total),
        "new_pairs": int(new),
        "new_share": float(new / total),
        "test_revenue": test_revenue,
        "repeat_revenue": repeat_revenue,
        "repeat_revenue_share": float(repeat_revenue / test_revenue),
        "users_with_a_repeat": int(users_with_repeat),
        "users_scored": int(len(split.truth_standard)),
        "users_with_a_repeat_share": float(users_with_repeat / len(split.truth_standard)),
    }


def concentration(split: Split) -> dict:
    """Gini and head-share of the training interactions themselves."""
    popularity = split.popularity
    ordered = np.sort(popularity)[::-1]
    cumulative = ordered.cumsum() / ordered.sum()
    return {
        "items": int(len(popularity)),
        "gini": gini(popularity),
        "top_10_share": float(cumulative[9]),
        "top_100_share": float(cumulative[99]),
        "top_500_share": float(cumulative[499]),
    }


def gini(values: np.ndarray) -> float:
    """0 = every product equally bought, 1 = one product takes everything."""
    ordered = np.sort(np.asarray(values, dtype=float))
    n = len(ordered)
    if ordered.sum() <= 0:
        return 0.0
    return float((2 * np.arange(1, n + 1) - n - 1).dot(ordered) / (n * ordered.sum()))


def leave_one_out_split(frame: pd.DataFrame,
                        min_items: int = config.MIN_TRAIN_ITEMS_PER_USER) -> dict:
    """The other split everybody uses, built so we can measure what it leaks.

    Leave-one-out holds out each customer's most recent first-purchase and
    trains on everything else - including every other customer's behavior after
    the cut, and this customer's own later baskets.
    """
    registered = frame.dropna(subset=["customer_id"]).copy()
    registered["customer_id"] = registered["customer_id"].astype(int)
    first = (registered.groupby(["customer_id", "stock_code"], as_index=False)
             .agg(invoice_ts=("invoice_ts", "min")))
    first = first.sort_values("invoice_ts")
    first["rank_from_end"] = first.groupby("customer_id")["invoice_ts"].rank(
        method="first", ascending=False)
    held = first[first["rank_from_end"] == 1]
    kept = first[first["rank_from_end"] > 1]
    counts = kept.groupby("customer_id")["stock_code"].size()
    kept = kept[kept["customer_id"].isin(counts[counts >= min_items].index)]
    held = held[held["customer_id"].isin(set(kept["customer_id"]))]
    return {"train": kept, "held_out": held}
