"""The five scorers, each one small enough to read.

Every model turns the training matrix into something that can produce a score
for every (customer, product) cell. Scoring is always **batched** - one matrix
multiply for all evaluated customers at once - never a Python loop over
customers. On this data the difference is 0.3 s against 28 s, and it is the
only reason a live classroom can re-run the whole leaderboard.

    Popularity     count of training customers per product
    Item-item      L2-normalize product columns, S = Rn @ Rn.T, zero the diagonal
    Item-item(15)  the same S with all but each product's 15 closest neighbours zeroed
    SVD-64         TruncatedSVD(64): scores = U @ V
    Reorder        the customer's own history, ranked by how many baskets it appeared in
    Fallback       the ten products with the most revenue in the last 28 training days
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from . import config
from .matrix import Split


@dataclass
class Fitted:
    """One fitted scorer plus the seconds it took."""

    label: str
    kind: str
    payload: object
    fit_seconds: float


# ── Fits ────────────────────────────────────────────────────────────────────

def fit_popularity(split: Split) -> Fitted:
    started = time.time()
    counts = np.asarray(split.R.sum(0)).ravel().astype(np.float64)
    return Fitted(config.POPULARITY_LABEL, "popularity", counts, time.time() - started)


def item_similarity(R: sp.csr_matrix) -> np.ndarray:
    """Cosine similarity between products, as a dense float32 square.

    Each product is a column of R - the set of customers who bought it. Two
    products are similar when the same customers bought both. The diagonal is
    zeroed because a product is not its own recommendation.
    """
    normalized = normalize(R.T.tocsr())          # rows = products, unit length
    similarity = (normalized @ normalized.T).toarray().astype(np.float32)
    np.fill_diagonal(similarity, 0.0)
    return similarity


def truncate(similarity: np.ndarray, neighbours: int) -> sp.csr_matrix:
    """Keep each product's ``neighbours`` strongest links, drop the rest."""
    kept = similarity.copy()
    weak = np.argpartition(-kept, neighbours, axis=1)[:, neighbours:]
    np.put_along_axis(kept, weak, 0.0, axis=1)
    return sp.csr_matrix(kept)


def fit_item_item(split: Split, neighbours: int | None = None,
                  label: str | None = None,
                  similarity: np.ndarray | None = None) -> Fitted:
    started = time.time()
    dense = item_similarity(split.R) if similarity is None else similarity
    if neighbours is None:
        payload = dense
        name = label or config.ITEMITEM_FULL_LABEL
    else:
        payload = truncate(dense, neighbours)
        name = label or config.DEPLOYED_MODEL_LABEL
    return Fitted(name, "item_item", payload, time.time() - started)


def fit_svd(split: Split, components: int = config.SVD_COMPONENTS) -> Fitted:
    started = time.time()
    model = TruncatedSVD(n_components=components, random_state=config.SEED)
    U = model.fit_transform(split.R)
    V = model.components_.astype(np.float32)
    payload = {"U": U, "V": V, "model": model}
    return Fitted(config.SVD_LABEL, "svd", payload, time.time() - started)


def fit_reorder(split: Split) -> Fitted:
    """The baseline that has to be in the room: recommend what they already buy.

    Score for a (customer, product) the customer has bought = the number of
    distinct training baskets it appeared in, plus half a point of recency so
    ties break toward the recent. Nothing is learned. Nothing generalizes. For
    a product the customer has never bought, the score is exactly zero.
    """
    started = time.time()
    rows = split.train_rows.copy()
    rows["u"] = rows["customer_id"].map(split.user_index)
    rows["i"] = rows["stock_code"].map(split.item_index)
    rows = rows.dropna(subset=["u", "i"])
    grouped = rows.groupby(["u", "i"]).agg(baskets=("invoice", "nunique"),
                                           last=("invoice_ts", "max")).reset_index()
    span = (grouped["last"].max() - grouped["last"].min()).total_seconds() or 1.0
    recency = (grouped["last"] - grouped["last"].min()).dt.total_seconds() / span
    values = grouped["baskets"].to_numpy(dtype=np.float64) + 0.5 * recency.to_numpy()
    payload = sp.csr_matrix(
        (values, (grouped["u"].astype(int), grouped["i"].astype(int))),
        shape=split.R.shape)
    return Fitted(config.REORDER_LABEL, "reorder", payload, time.time() - started)


def fallback_items(split: Split, days: int = config.FALLBACK_WINDOW_DAYS,
                   k: int = config.SLOTS) -> list[str]:
    """The ten products with the most revenue in the last ``days`` of training.

    Revenue, not basket count. This retailer sells to wholesale buyers: a cheap
    item that appears in many baskets is not the item a new buyer opens with.
    """
    window = split.train_rows[split.train_rows["invoice_ts"] > split.cut - pd.Timedelta(days=days)]
    return (window.groupby("stock_code")["revenue"].sum()
            .sort_values(ascending=False).head(k).index.tolist())


def fit_fallback(split: Split, days: int = config.FALLBACK_WINDOW_DAYS) -> Fitted:
    started = time.time()
    codes = fallback_items(split, days)
    indices = [split.item_index[code] for code in codes if code in split.item_index]
    return Fitted(config.FALLBACK_LABEL, "fixed_list",
                  {"codes": codes, "indices": indices}, time.time() - started)


def fit_random(split: Split) -> Fitted:
    """The floor every other model must clear.

    The payload is the *seed*, not a generator. A single generator held here
    would be advanced by each ``score`` call, so the discovery leaderboard
    would come out differently depending on whether the standard leaderboard
    had been scored first. Seeding fresh inside ``score`` makes the random
    baseline reproducible and order-independent, which is the whole point of
    having a floor.
    """
    started = time.time()
    return Fitted(config.RANDOM_LABEL, "random", config.SEED, time.time() - started)


# ── Scoring ─────────────────────────────────────────────────────────────────

def score(fitted: Fitted, split: Split, users: list[int]) -> np.ndarray:
    """Scores for ``users`` x every product, as one dense array.

    Every branch is a single matrix operation over all requested customers.
    """
    R = split.R
    if fitted.kind == "popularity":
        return np.tile(fitted.payload, (len(users), 1))
    if fitted.kind == "item_item":
        product = R[users] @ fitted.payload
        return np.asarray(product.todense()) if sp.issparse(product) else np.asarray(product)
    if fitted.kind == "svd":
        return fitted.payload["U"][users] @ fitted.payload["V"]
    if fitted.kind == "reorder":
        return np.asarray(fitted.payload[users].todense())
    if fitted.kind == "fixed_list":
        board = np.zeros((len(users), R.shape[1]))
        indices = fitted.payload["indices"]
        board[:, indices] = np.arange(len(indices), 0, -1)
        return board
    if fitted.kind == "random":
        # Fresh generator per call - see fit_random for why this must not be
        # a stored, stateful generator.
        return np.random.default_rng(fitted.payload).random((len(users), R.shape[1]))
    raise ValueError(f"unknown model kind {fitted.kind!r}")


def top_k(scores: np.ndarray, users: list[int], seen: list[set[int]],
          k: int = config.SLOTS, mask_seen: bool = True) -> dict[int, np.ndarray]:
    """Rank each row and take the best ``k`` product indices.

    ``mask_seen`` is the protocol switch. When it is on, everything the
    customer already bought is pushed to negative infinity and can never be
    recommended - which is what the discovery protocol means.
    """
    result: dict[int, np.ndarray] = {}
    for row, user in enumerate(users):
        row_scores = np.asarray(scores[row]).ravel().astype(np.float64).copy()
        if mask_seen and seen[user]:
            row_scores[list(seen[user])] = -np.inf
        partitioned = np.argpartition(-row_scores, k)[:k]
        result[user] = partitioned[np.argsort(-row_scores[partitioned])]
    return result


def fit_all(split: Split) -> dict[str, Fitted]:
    """Every model in the leaderboard, fitted once and reused everywhere.

    The full similarity matrix is computed once and shared, so the truncated
    model is not charged twice for the same multiply.
    """
    started = time.time()
    dense = item_similarity(split.R)
    similarity_seconds = time.time() - started

    full = fit_item_item(split, None, config.ITEMITEM_FULL_LABEL, similarity=dense)
    full.fit_seconds += similarity_seconds
    top15 = fit_item_item(split, config.ITEM_NEIGHBOURS,
                          config.DEPLOYED_MODEL_LABEL, similarity=dense)
    top15.fit_seconds += similarity_seconds

    return {
        config.RANDOM_LABEL: fit_random(split),
        config.POPULARITY_LABEL: fit_popularity(split),
        config.FALLBACK_LABEL: fit_fallback(split),
        config.ITEMITEM_FULL_LABEL: full,
        config.DEPLOYED_MODEL_LABEL: top15,
        config.SVD_LABEL: fit_svd(split),
        config.REORDER_LABEL: fit_reorder(split),
    }


def neighbour_sweep(split: Split, values: list[int]) -> pd.DataFrame:
    """Artifact size for each truncation level - the size half of the trade."""
    dense = item_similarity(split.R)
    rows = []
    full_bytes = dense.nbytes
    for neighbours in values:
        truncated = truncate(dense, neighbours)
        stored = (truncated.data.nbytes + truncated.indices.nbytes
                  + truncated.indptr.nbytes)
        rows.append({"neighbours": neighbours, "stored_links": int(truncated.nnz),
                     "megabytes": stored / 1e6, "shrink_vs_full": full_bytes / stored})
    return pd.DataFrame(rows)


def damped_similarities(split: Split, alphas: list[float]) -> dict[float, np.ndarray]:
    """Scale the product columns by ``1 / popularity**alpha``, then take cosine.

    This is the popularity-damping knob a student meets in every tutorial. It
    looks like it should push well-known products down the list. Scaling column
    i of R multiplies row i of R.T by a constant, and the L2 row-normalization
    inside the cosine divides that constant straight back out, so the knob is
    connected to nothing. One similarity matrix per alpha, so the caller can
    show that they are the same matrix.
    """
    popularity = np.maximum(split.popularity, 1)
    result: dict[float, np.ndarray] = {}
    for alpha in alphas:
        weights = sp.diags(1.0 / np.power(popularity, alpha))
        damped = split.R @ weights if alpha > 0 else split.R
        normalized = normalize(damped.T.tocsr())
        similarity = (normalized @ normalized.T).toarray().astype(np.float32)
        np.fill_diagonal(similarity, 0.0)
        result[alpha] = similarity
    return result
