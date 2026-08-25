"""Feature engineering.

Two rules govern everything in this module.

**Causality.** Every feature is computed from information that exists at the
moment the customer presses Buy. A value recorded later -- a refund, a dispute,
an analyst's review note -- predicts fraud beautifully in validation and is
simply absent in production.

**One definition.** This module is the only place a feature is defined. The
FastAPI scoring service imports these same functions rather than
reimplementing them, because a feature computed one way in a notebook and
another way in a service is the most common reason a deployed model quietly
stops matching its validation score.

Note on serving: the velocity and trailing-average features need the card's
recent history, so a real service keeps a running per-card profile rather than
recomputing from scratch. That requirement is the honest reason feature stores
exist.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NUMERIC_FEATURES = [
    "amt",
    "log_amt",
    "amt_ratio_to_card_mean",
    "card_txn_count_1h",
    "card_txn_count_24h",
    "minutes_since_prev_txn",
    "distance_km",
    "customer_age",
    "log_city_pop",
    "hour",
    "is_night",
    "is_weekend",
]

CATEGORICAL_FEATURES = ["category"]

MODEL_FEATURE_CATALOG = {
    "amt": ("Direct numeric", "Transaction amount", "amt"),
    "log_amt": ("Engineered", "Amount with large values compressed", "amt"),
    "amt_ratio_to_card_mean": ("Engineered", "Amount compared with this card's earlier average", "amt + cc_num + unix_time"),
    "card_txn_count_1h": ("Engineered", "Earlier transactions on this card in one hour", "cc_num + unix_time"),
    "card_txn_count_24h": ("Engineered", "Earlier transactions on this card in 24 hours", "cc_num + unix_time"),
    "minutes_since_prev_txn": ("Engineered", "Minutes since this card's previous purchase", "cc_num + unix_time"),
    "distance_km": ("Engineered", "Distance from home to merchant", "lat + long + merch_lat + merch_long"),
    "customer_age": ("Engineered", "Cardholder age when the purchase occurred", "dob + trans_date_trans_time"),
    "log_city_pop": ("Engineered", "Home-city population with large values compressed", "city_pop"),
    "hour": ("Engineered", "Local hour of purchase", "trans_date_trans_time"),
    "is_night": ("Engineered", "Whether the purchase occurred late at night", "trans_date_trans_time"),
    "is_weekend": ("Engineered", "Whether the purchase occurred on a weekend", "trans_date_trans_time"),
    "category": ("Direct category", "Type of merchant; expanded into one yes/no column per category", "category"),
}

# The feature that ruins everything, kept deliberately so section 6 can show what
# leakage looks like from the inside.
LEAKY_FEATURE = "flagged_by_dispute_team"

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance between the cardholder's home and the merchant."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _prior_count_within(seconds_col: np.ndarray, window_seconds: int) -> np.ndarray:
    """Count earlier transactions inside the window. Excludes the row itself."""
    left = np.searchsorted(seconds_col, seconds_col - window_seconds, side="left")
    return np.arange(len(seconds_col)) - left


def add_velocity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-card counts and gaps, using only transactions that already happened.

    One purchase is a purchase. Nine in ten minutes is somebody testing a stolen
    card until it works. Same records, entirely different meaning -- and the
    difference exists only because a person thought to compute it.
    """
    df = df.sort_values(["cc_num", "unix_time"], kind="mergesort").reset_index(drop=True)

    counts_1h, counts_24h, gaps, ratios = [], [], [], []
    for _, group in df.groupby("cc_num", observed=True, sort=False):
        seconds = group["unix_time"].to_numpy()
        counts_1h.append(_prior_count_within(seconds, 3_600))
        counts_24h.append(_prior_count_within(seconds, 86_400))
        gaps.append(np.diff(seconds, prepend=np.nan) / 60.0)

        amounts = group["amt"]
        prior_mean = amounts.shift(1).expanding().mean()
        ratios.append((amounts / prior_mean).to_numpy())

    df["card_txn_count_1h"] = np.concatenate(counts_1h)
    df["card_txn_count_24h"] = np.concatenate(counts_24h)
    df["minutes_since_prev_txn"] = np.concatenate(gaps)
    df["amt_ratio_to_card_mean"] = np.concatenate(ratios)

    # A card's first transaction has no history. Saying "unknown" with a neutral
    # value is honest; inventing a ratio is not.
    df["minutes_since_prev_txn"] = df["minutes_since_prev_txn"].fillna(60 * 24 * 30)
    df["amt_ratio_to_card_mean"] = df["amt_ratio_to_card_mean"].fillna(1.0)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn joined transaction records into the columns a model can actually use.

    A model cannot consume "a transaction". It consumes a row of numbers computed
    from that transaction, and choosing them is the craft.
    """
    out = add_velocity_features(df)
    ts = out["trans_date_trans_time"]

    out["log_amt"] = np.log1p(out["amt"])
    out["distance_km"] = haversine_km(
        out["lat"], out["long"], out["merch_lat"], out["merch_long"]
    )
    out["customer_age"] = (ts - out["dob"]).dt.days / 365.25
    out["log_city_pop"] = np.log1p(out["city_pop"].astype(float))
    out["hour"] = ts.dt.hour
    out["is_night"] = ((out["hour"] < 6) | (out["hour"] >= 22)).astype(int)
    out["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

    return out.sort_values("trans_date_trans_time").reset_index(drop=True)


def add_leaky_feature(df: pd.DataFrame, noise: float = 0.03, seed: int = 42) -> pd.DataFrame:
    """Attach the column that is not there when you need it.

    "Flagged by the disputes team" is recorded weeks after the transaction, and
    only *because* the transaction turned out to be fraud. In training it is
    nearly a perfect predictor. At 2:14pm on a Tuesday, the instant the customer
    presses Buy, the column is empty.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()
    flag = out["is_fraud"].to_numpy().astype(float)
    flip = rng.random(len(out)) < noise
    out[LEAKY_FEATURE] = np.where(flip, 1 - flag, flag).astype(int)
    return out


def feature_matrix(
    df: pd.DataFrame, include_leak: bool = False
) -> tuple[pd.DataFrame, pd.Series]:
    """The exact (X, y) the models see. One-hot on category, nothing implicit."""
    numeric = list(NUMERIC_FEATURES)
    if include_leak:
        numeric = numeric + [LEAKY_FEATURE]

    x = pd.get_dummies(
        df[numeric + CATEGORICAL_FEATURES],
        columns=CATEGORICAL_FEATURES,
        prefix="cat",
        dtype=float,
    )
    return x, df["is_fraud"].astype(int)


def align_columns(x: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Guarantee the test matrix has exactly the training columns, in order."""
    return x.reindex(columns=reference.columns, fill_value=0.0)


def model_feature_catalog() -> pd.DataFrame:
    """The conceptual model inputs and the source columns behind each one."""
    names = list(NUMERIC_FEATURES) + list(CATEGORICAL_FEATURES)
    return pd.DataFrame(
        [
            {
                "Model input": name,
                "Kind": MODEL_FEATURE_CATALOG[name][0],
                "Plain meaning": MODEL_FEATURE_CATALOG[name][1],
                "Built from source column(s)": MODEL_FEATURE_CATALOG[name][2],
            }
            for name in names
        ]
    )


# ── Association analysis ────────────────────────────────────────────────────

def correlation_frame(
    frame: pd.DataFrame, method: str = "pearson", include_target: bool = True
) -> pd.DataFrame:
    """Correlation among numeric model features and, optionally, the binary target."""
    columns = list(NUMERIC_FEATURES)
    if include_target:
        columns.append("is_fraud")
    return frame[columns].corr(method=method)


def single_feature_signal(
    x: pd.DataFrame, y: pd.Series, column: str, budget: float = 0.03
) -> dict[str, float]:
    """What one feature achieves on its own, used alone as the score.

    Reported as **lift over chance**: spending a 3% review budget at random
    catches roughly 3% of fraud, so lift is recall divided by the budget. A lift
    near 1.0 means the column carries no usable signal by itself -- which is a
    real finding, not a failure, and quite different from it being useless in
    combination with others.

    Direction is unknown in advance, so both orientations are tried and the
    better one reported.
    """
    from .metrics import evaluate_at_budget

    values = x[column].to_numpy(dtype=float)
    values = np.nan_to_num(values, nan=float(np.nanmedian(values)))

    best = None
    for oriented in (values, -values):
        result = evaluate_at_budget(y.to_numpy(), oriented, budget=budget)
        if best is None or result["recall"] > best["recall"]:
            best = result

    best["lift"] = best["recall"] / budget if budget else 0.0
    return best


def describe_signal(x: pd.DataFrame, y: pd.Series, column: str, budget: float = 0.03) -> str:
    """One line a non-programmer can read."""
    signal = single_feature_signal(x, y, column, budget)
    verdict = (
        "strong signal on its own"
        if signal["lift"] >= 3
        else "some signal on its own"
        if signal["lift"] >= 1.5
        else "almost no signal on its own"
    )
    return (
        f"Alone, this feature catches {signal['recall']:.1%} of fraud at a {budget:.0%} "
        f"review budget.\nSpending that budget at random would catch about {budget:.0%}, "
        f"so this is {signal['lift']:.1f}x chance -- {verdict}."
    )
