"""The two leaderboards, and every number that keeps them honest.

This module is the case. The models are ordinary; the point of the lab is that
the *same* models, on the *same* day, produce opposite verdicts depending on
what the analyst decides to count as a hit. So every table here carries its
protocol, and coverage and novelty are computed beside every accuracy number
rather than in a separate section nobody reaches.

Metrics, with their numerators and denominators stated once:

    HR@10        share of scored customers with at least one correct product in
                 ten slots. Numerator: customers with >= 1 hit. Denominator:
                 customers scored under this protocol.
    Precision@10 correct slots / 10, averaged over customers.
    Recall@10    correct slots / that customer's whole truth set, averaged.
    NDCG@10      like precision but a hit in slot 1 is worth more than slot 10,
                 normalized against the best possible ordering.
    Coverage     distinct products that appeared in ANY customer's ten slots,
                 divided by the 4,443 products in the catalog.
    Novelty      mean -log2(share of customers who bought the product). Higher
                 means the list is made of less-bought products.
    Mean pop rank average popularity rank of recommended products, 1 = the
                 single most-bought product in the catalog.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, models
from .matrix import Split, gini

DISCOUNTS = np.array([1.0 / np.log2(rank + 2) for rank in range(config.SLOTS)])


# ── One model, one protocol ─────────────────────────────────────────────────

def score_lists(top: dict[int, np.ndarray], truth: dict[int, set[int]],
                popularity: np.ndarray, n_items: int, n_users: int,
                k: int = config.SLOTS) -> dict:
    """Every metric for one set of ranked lists."""
    hits = precision = recall = ndcg = 0.0
    all_slots = []
    for user, slots in top.items():
        wanted = truth[user]
        all_slots.append(slots)
        relevant = np.array([1.0 if item in wanted else 0.0 for item in slots])
        n_hits = relevant.sum()
        hits += 1.0 if n_hits > 0 else 0.0
        precision += n_hits / k
        recall += n_hits / len(wanted)
        ideal = float(DISCOUNTS[:min(len(wanted), k)].sum())
        ndcg += float((relevant * DISCOUNTS).sum()) / ideal

    scored = len(top)
    slots = np.concatenate(all_slots)
    share = np.clip(popularity[slots] / n_users, 1e-9, None)
    ranks = pd.Series(popularity).rank(ascending=False, method="min").values
    return {
        "HR@10": hits / scored,
        "Precision@10": precision / scored,
        "Recall@10": recall / scored,
        "NDCG@10": ndcg / scored,
        "Coverage": len(np.unique(slots)) / n_items,
        "Novelty": float(np.mean(-np.log2(share))),
        "Mean pop rank": float(np.mean(ranks[slots])),
        "Customers scored": scored,
    }


def leaderboard(split: Split, fitted: dict[str, models.Fitted], protocol: str,
                include: list[str] | None = None,
                k: int = config.SLOTS) -> pd.DataFrame:
    """One leaderboard. The protocol decides the truth AND the candidate set."""
    truth, mask_seen = protocol_setup(split, protocol)
    users = sorted(truth)
    order = include or [name for name in config.MODEL_ORDER if name in fitted]
    popularity = split.popularity

    rows = []
    for name in order:
        model = fitted[name]
        scores = models.score(model, split, users)
        top = models.top_k(scores, users, split.seen, k, mask_seen)
        record = score_lists(top, truth, popularity, split.n_items, split.n_users, k)
        record["Model"] = name
        record["Fit seconds"] = round(model.fit_seconds, 3)
        rows.append(record)
        del scores

    frame = pd.DataFrame(rows)
    columns = ["Model", "HR@10", "Precision@10", "Recall@10", "NDCG@10",
               "Coverage", "Novelty", "Mean pop rank", "Customers scored", "Fit seconds"]
    return frame[columns]


def protocol_setup(split: Split, protocol: str) -> tuple[dict[int, set[int]], bool]:
    """(ground truth, whether the customer's history is masked out)."""
    if protocol == config.PROTOCOL_STANDARD:
        return split.truth_standard, False
    if protocol == config.PROTOCOL_DISCOVERY:
        return split.truth_discovery, True
    if protocol == config.PROTOCOL_INCOHERENT:
        return split.truth_standard, True
    raise ValueError(f"unknown protocol {protocol!r}")


def ranked_lists(split: Split, fitted: models.Fitted, protocol: str,
                 users: list[int] | None = None,
                 k: int = config.SLOTS) -> dict[int, np.ndarray]:
    """The ten slots each customer would actually be shown."""
    truth, mask_seen = protocol_setup(split, protocol)
    chosen = users if users is not None else sorted(truth)
    scores = models.score(fitted, split, chosen)
    return models.top_k(scores, chosen, split.seen, k, mask_seen)


# ── The comparison that is the lesson ───────────────────────────────────────

def two_table_comparison(standard: pd.DataFrame,
                         discovery: pd.DataFrame) -> pd.DataFrame:
    """The two leaderboards side by side, with each model's rank in both."""
    left = standard[["Model", "HR@10"]].rename(columns={"HR@10": "Standard HR@10"})
    right = discovery[["Model", "HR@10", "Coverage"]].rename(
        columns={"HR@10": "Discovery HR@10", "Coverage": "Discovery coverage"})
    merged = right.merge(left, on="Model", how="left")
    merged["Standard rank"] = merged["Standard HR@10"].rank(ascending=False).astype("Int64")
    merged["Discovery rank"] = merged["Discovery HR@10"].rank(ascending=False).astype("Int64")
    merged["Rank change"] = merged["Standard rank"] - merged["Discovery rank"]
    return merged[["Model", "Standard HR@10", "Standard rank",
                   "Discovery HR@10", "Discovery rank", "Rank change",
                   "Discovery coverage"]].sort_values("Standard HR@10", ascending=False)


def zero_score_diagnosis(split: Split, fitted: models.Fitted) -> dict:
    """Why the reorder baseline lands *below* random once history is masked.

    Mask a customer's own history and the reorder model's score vector is
    identically zero for every remaining product. What looks like a ranking is
    a deterministic tie-break over 4,443 items, and the tie-break is biased
    toward low indices, which on this catalog are the least-bought products.
    """
    users = sorted(split.truth_discovery)
    scores = models.score(fitted, split, users)
    masked = scores.copy()
    for row, user in enumerate(users):
        masked[row, list(split.seen[user])] = np.nan
    positive = np.nansum(masked > 0, axis=1)
    top = models.top_k(scores, users, split.seen, config.SLOTS, True)
    slots = np.concatenate(list(top.values()))
    ranks = split.popularity_rank
    return {
        "customers": int(len(users)),
        "customers_with_any_positive_score": int((positive > 0).sum()),
        "share_with_all_zero_scores": float((positive == 0).mean()),
        "mean_popularity_rank_of_slots": float(np.mean(ranks[slots])),
        "catalog_size": int(split.n_items),
        "explanation": (
            "With every already-bought product masked, this model scores zero "
            "everywhere. Its ten slots are the first ten products in index "
            "order, which is a tie-break, not a ranking - and a tie-break that "
            "lands in the least-bought tail of the catalog."
        ),
    }


# ── Leave-one-out: how much a leaky split flatters a model ──────────────────

def loo_inflation(frame: pd.DataFrame, split: Split,
                  k: int = config.SLOTS) -> pd.DataFrame:
    """Hold the targets fixed, vary only the training data, measure the gap.

    Comparing a global-time table against a leave-one-out table proves nothing,
    because the two have different target sets. So we fix the target at exactly
    one product per customer and change only what the model is allowed to
    train on:

      A honest : nothing after the cut, for anybody
      B leaky  : all history except the one held-out purchase - which leaves
                 every other customer's post-cut behavior in training

    The gap between A and B is the leak, and it scales with model capacity.
    """
    import scipy.sparse as sp

    registered = frame.dropna(subset=["customer_id"]).copy()
    registered["customer_id"] = registered["customer_id"].astype(int)
    registered["u"] = registered["customer_id"].map(split.user_index)
    registered["i"] = registered["stock_code"].map(split.item_index)
    registered = registered.dropna(subset=["u", "i"])
    registered["u"] = registered["u"].astype(int)
    registered["i"] = registered["i"].astype(int)
    first = registered.groupby(["u", "i"], as_index=False)["invoice_ts"].min()

    wanted = {(u, i) for u, items in split.truth_discovery.items() for i in items}
    is_target = [(u, i) in wanted for u, i in zip(first["u"], first["i"])]
    targets = first[is_target].sort_values("invoice_ts").groupby("u").tail(1)
    truth = {int(row.u): {int(row.i)} for row in targets.itertuples()}
    users = sorted(truth)
    held = {(int(row.u), int(row.i)) for row in targets.itertuples()}

    everything = {(int(u), int(i)) for u, i in zip(first["u"], first["i"])}
    honest = {(int(u), int(i)) for u, i in
              zip(split.train_pairs["customer_id"].map(split.user_index),
                  split.train_pairs["stock_code"].map(split.item_index))}

    variants = {
        "A - honest: nothing after the cut, for anyone": honest,
        "B - leave-one-out: everything except the held-out purchase": everything - held,
    }

    rows = []
    for label, pairs in variants.items():
        array = np.array(sorted(pairs))
        R = sp.csr_matrix((np.ones(len(array)), (array[:, 0], array[:, 1])),
                          shape=split.R.shape)
        R.sum_duplicates()
        variant = Split(train_rows=split.train_rows, test_rows=split.test_rows,
                        train_pairs=split.train_pairs, test_pairs=split.test_pairs,
                        items=split.items, users=split.users,
                        item_index=split.item_index, user_index=split.user_index,
                        R=R, seen=[set(R[u].indices.tolist()) for u in range(R.shape[0])],
                        truth_standard=truth, truth_discovery=truth, cut=split.cut)
        fits = {
            config.POPULARITY_LABEL: models.fit_popularity(variant),
            "Item-item CF": models.fit_item_item(variant, None, "Item-item CF"),
            config.SVD_LABEL: models.fit_svd(variant),
        }
        for name, model in fits.items():
            scores = models.score(model, variant, users)
            top = models.top_k(scores, users, variant.seen, k, True)
            record = score_lists(top, truth, variant.popularity, variant.n_items,
                                 variant.n_users, k)
            rows.append({"Training set": label, "Model": name,
                         "HR@10": record["HR@10"],
                         "Training interactions": int(R.nnz)})
    table = pd.DataFrame(rows)
    wide = table.pivot(index="Model", columns="Training set", values="HR@10")
    wide["Inflation"] = wide.iloc[:, 1] / wide.iloc[:, 0] - 1
    wide = wide.reindex([config.POPULARITY_LABEL, "Item-item CF", config.SVD_LABEL])
    return wide.reset_index()


# ── Popularity bias ─────────────────────────────────────────────────────────

def exposure_profile(split: Split, fitted: dict[str, models.Fitted],
                     protocol: str = config.PROTOCOL_DISCOVERY,
                     include: list[str] | None = None) -> pd.DataFrame:
    """What each model actually puts in front of people, product by product."""
    truth, mask_seen = protocol_setup(split, protocol)
    users = sorted(truth)
    ranks = split.popularity_rank
    order = include or [config.POPULARITY_LABEL, config.ITEMITEM_FULL_LABEL,
                        config.DEPLOYED_MODEL_LABEL, config.SVD_LABEL,
                        config.REORDER_LABEL]
    rows = []
    for name in order:
        scores = models.score(fitted[name], split, users)
        top = models.top_k(scores, users, split.seen, config.SLOTS, mask_seen)
        slots = np.concatenate(list(top.values()))
        counts = pd.Series(slots).value_counts()
        rows.append({
            "Model": name,
            "Coverage": len(np.unique(slots)) / split.n_items,
            "Recommendation Gini": gini(np.bincount(slots, minlength=split.n_items)),
            "% of slots from the top 100": float((ranks[slots] <= 100).mean()),
            "% of slots from the less-popular half":
                float((ranks[slots] > split.n_items / 2).mean()),
            "Median popularity rank": float(np.median(ranks[slots])),
            "Distinct products shown": int(len(np.unique(slots))),
            "Top product's share of all slots": float(counts.iloc[0] / len(slots)),
        })
        del scores
    return pd.DataFrame(rows)


def exposure_loop(split: Split, rounds: int = config.FEEDBACK_ROUNDS,
                  conversion: float = config.FEEDBACK_CONVERSION) -> pd.DataFrame:
    """Deploy popularity, let it feed itself, and watch the catalog collapse.

    A LABELED CLASSROOM ASSUMPTION, not a measurement: assume ``conversion`` of
    shown slots turn into a purchase. Retrain on the enlarged data, show again,
    repeat. Nothing about the products changed.
    """
    R = split.R.tolil(copy=True)
    popularity = split.popularity.astype(float).copy()
    rng = np.random.default_rng(config.SEED)

    def shares(counts: np.ndarray) -> np.ndarray:
        return np.sort(counts)[::-1].cumsum() / counts.sum()

    current = shares(popularity)
    history = [{"Round": 0, "Top-10 share": float(current[9]),
                "Top-100 share": float(current[99]), "Gini": gini(popularity),
                "Distinct products ever shown": 0}]
    shown: set[int] = set()
    for round_number in range(1, rounds + 1):
        slate = np.argsort(-popularity)[:config.SLOTS]
        shown |= set(slate.tolist())
        for user in range(R.shape[0]):
            for item in slate[rng.random(config.SLOTS) < conversion]:
                R[user, item] = 1
        popularity = np.asarray(R.tocsr().sum(0)).ravel().astype(float)
        current = shares(popularity)
        history.append({"Round": round_number, "Top-10 share": float(current[9]),
                        "Top-100 share": float(current[99]), "Gini": gini(popularity),
                        "Distinct products ever shown": len(shown)})
    return pd.DataFrame(history)


# ── The number that keeps everyone honest ───────────────────────────────────

def incremental_revenue(split: Split, fitted: dict[str, models.Fitted],
                        include: list[str] | None = None) -> pd.DataFrame:
    """An UPPER BOUND on what a recommender could be worth here.

    Of the revenue customers spent in the test window on products that were new
    to them, how much sits on a product the model happened to rank in a slot?
    This is an upper bound, not a measurement of value: it credits the model
    for revenue the customer generated anyway.
    """
    revenue = (split.test_rows.groupby(["customer_id", "stock_code"])["revenue"]
               .sum())
    lookup = {(split.user_index[c], split.item_index[s]): float(v)
              for (c, s), v in revenue.items()
              if c in split.user_index and s in split.item_index}
    truth = split.truth_discovery
    users = sorted(truth)
    available = sum(lookup.get((u, i), 0.0) for u in users for i in truth[u])

    order = include or [name for name in config.MODEL_ORDER if name in fitted]
    rows = []
    for name in order:
        scores = models.score(fitted[name], split, users)
        top = models.top_k(scores, users, split.seen, config.SLOTS, True)
        hits = sum(len(set(top[u].tolist()) & truth[u]) for u in users)
        realized = sum(lookup.get((u, int(i)), 0.0)
                       for u in users for i in top[u] if int(i) in truth[u])
        rows.append({
            "Model": name,
            "Discovery hits per customer": hits / len(users),
            "Revenue reached": realized,
            "Share of available new-product revenue": realized / available,
        })
        del scores
    frame = pd.DataFrame(rows)
    frame.attrs["available_revenue"] = available
    frame.attrs["customers"] = len(users)
    return frame


# ── Two engineering findings, each measured rather than asserted ────────────

def truncation_trade(split: Split, values: list[int]) -> pd.DataFrame:
    """Accuracy, coverage and stored size against the number of neighbours kept.

    Usually a smaller artifact costs accuracy. Here it does not, and the only
    way to say that honestly is to put all three columns in one table: discovery
    HR@10, catalog coverage, and the megabytes the similarity matrix occupies.
    The ``full matrix`` row is the same model with nothing thrown away.
    """
    truth = split.truth_discovery
    users = sorted(truth)
    popularity = split.popularity
    dense = models.item_similarity(split.R)
    dense_megabytes = dense.nbytes / 1e6

    def measure(payload, label: str, megabytes: float) -> dict:
        fitted = models.Fitted(label, "item_item", payload, 0.0)
        scores = models.score(fitted, split, users)
        top = models.top_k(scores, users, split.seen, config.SLOTS, True)
        record = score_lists(top, truth, popularity, split.n_items, split.n_users)
        return {
            "Neighbours kept": label,
            "Discovery HR@10": record["HR@10"],
            "Coverage": record["Coverage"],
            "Novelty": record["Novelty"],
            "Stored megabytes": megabytes,
            "Shrink vs the full matrix": dense_megabytes / megabytes,
        }

    rows = [measure(dense, "all 4,443 (full matrix)", dense_megabytes)]
    for neighbours in values:
        truncated = models.truncate(dense, neighbours)
        megabytes = (truncated.data.nbytes + truncated.indices.nbytes
                     + truncated.indptr.nbytes) / 1e6
        rows.append(measure(truncated, str(neighbours), megabytes))
    return pd.DataFrame(rows)


def damping_no_op_table(split: Split, alphas: list[float]) -> pd.DataFrame:
    """The tuning knob that is wired to nothing, measured to four decimals.

    Damping popularity by scaling the product columns before the cosine is
    undone exactly by the L2 row-normalization inside the cosine. Three values
    of alpha, three identical similarity matrices, three identical leaderboards.
    A student who does not check this can tune it forever.
    """
    truth = split.truth_discovery
    users = sorted(truth)
    popularity = split.popularity
    similarities = models.damped_similarities(split, alphas)
    baseline = similarities[alphas[0]]

    rows = []
    for alpha, similarity in similarities.items():
        fitted = models.Fitted(f"alpha={alpha}", "item_item", similarity, 0.0)
        scores = models.score(fitted, split, users)
        top = models.top_k(scores, users, split.seen, config.SLOTS, True)
        record = score_lists(top, truth, popularity, split.n_items, split.n_users)
        rows.append({
            "Damping alpha": alpha,
            "Discovery HR@10": round(record["HR@10"], 4),
            "NDCG@10": round(record["NDCG@10"], 4),
            "Coverage": round(record["Coverage"], 4),
            "Largest difference from alpha=0 in the similarity matrix":
                float(np.abs(similarity - baseline).max()),
        })
        del scores
    return pd.DataFrame(rows)
