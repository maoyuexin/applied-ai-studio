"""Loading, joining, splitting -- everything that happens before a feature exists."""

from __future__ import annotations

import pandas as pd

from . import config


def load_customers() -> pd.DataFrame:
    return pd.read_parquet(config.CUSTOMERS_PARQUET)


def load_transactions() -> pd.DataFrame:
    return pd.read_parquet(config.TRANSACTIONS_PARQUET)


def join(transactions: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Attach the cardholder record to every transaction."""
    joined = transactions.merge(customers, on="cc_num", how="left", validate="many_to_one")
    unmatched = joined["dob"].isna().sum()
    if unmatched:
        print(f"WARNING: {unmatched:,} transactions did not match a customer record")
    return joined


def label_maturity_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """How much of the history actually carries a trustworthy label today."""
    matured = transactions["label_matured"]
    return pd.DataFrame(
        {
            "Bucket": [
                f"Labelled (confirmed on or before {config.AS_OF_DATE:%Y-%m-%d})",
                f"Still waiting (up to {config.LABEL_LAG_DAYS} days behind)",
            ],
            "Transactions": [int(matured.sum()), int((~matured).sum())],
            "Share": [matured.mean(), (~matured).mean()],
        }
    )


def weekly_volume(transactions: pd.DataFrame) -> pd.DataFrame:
    """Transactions and fraud rate per week -- the drift picture, before modelling."""
    weekly = (
        transactions.set_index("trans_date_trans_time")
        .resample("W")
        .agg(transactions=("is_fraud", "size"), frauds=("is_fraud", "sum"))
        .reset_index()
    )
    weekly["fraud_rate"] = weekly["frauds"] / weekly["transactions"]
    return weekly


def split_by_time(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Train on the past, test on the future.

    A random split would let the model train on March and be tested on February.
    Fraud tactics move, so a model that has already seen next month's tricks
    scores far better in testing than it can ever do in production.
    """
    ts = df["trans_date_trans_time"]
    parts = {
        "train": df[(ts >= config.TRAIN_START) & (ts <= config.TRAIN_END)],
        "test": df[(ts >= config.TEST_START) & (ts <= config.TEST_END)],
    }
    return {name: part.reset_index(drop=True) for name, part in parts.items()}


def recent_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Transactions that arrived after the test window -- what the model scores now."""
    return (
        df[df["trans_date_trans_time"] >= config.PREDICT_START]
        .sort_values("trans_date_trans_time")
        .reset_index(drop=True)
    )


def split_summary(parts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, part in parts.items():
        rows.append(
            {
                "Split": name,
                "From": part["trans_date_trans_time"].min(),
                "To": part["trans_date_trans_time"].max(),
                "Transactions": len(part),
                "Frauds": int(part["is_fraud"].sum()),
                "Fraud rate": part["is_fraud"].mean(),
            }
        )
    return pd.DataFrame(rows)
