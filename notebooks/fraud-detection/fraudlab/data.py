"""Loading, joining, splitting -- everything that happens before a feature exists."""

from __future__ import annotations

import pandas as pd

from . import config


SOURCE_COLUMN_CATALOG = {
    "transactions": {
        "trans_num": ("Unique transaction identifier", "Reference only; not a model input"),
        "cc_num": ("Card account identifier", "Joins tables and builds card-history features"),
        "trans_date_trans_time": ("Date and time of purchase", "Splits by date and builds time and age features"),
        "unix_time": ("Purchase time stored as seconds", "Orders card history and builds activity features"),
        "category": ("Type of merchant purchase", "Direct model input; expanded into category columns"),
        "amt": ("Transaction amount in dollars", "Direct model input and source for amount features"),
        "merchant": ("Merchant name", "Shown to the analyst; not a model input"),
        "merch_lat": ("Merchant latitude", "Builds distance from the cardholder's home"),
        "merch_long": ("Merchant longitude", "Builds distance from the cardholder's home"),
        "is_fraud": ("Fraud answer: 1 fraud, 0 normal", "Target used to train and evaluate; never a model input"),
        "label_available_date": ("Date the fraud answer becomes available", "Explains label delay; not a model input"),
        "label_matured": ("Whether the fraud answer is ready", "Checks label readiness; not a model input"),
    },
    "customers": {
        "cc_num": ("Card account identifier", "Joins tables and builds card-history features"),
        "first": ("Cardholder first name", "Available but not used by this model"),
        "last": ("Cardholder last name", "Available but not used by this model"),
        "gender": ("Cardholder gender", "Available but not used by this model"),
        "street": ("Home street", "Available but not used by this model"),
        "city": ("Home city", "Available but not used by this model"),
        "state": ("Home state", "Available but not used by this model"),
        "zip": ("Home ZIP code", "Available but not used by this model"),
        "lat": ("Home latitude", "Builds distance from home to merchant"),
        "long": ("Home longitude", "Builds distance from home to merchant"),
        "city_pop": ("Population of the home city", "Builds the log city-population feature"),
        "job": ("Cardholder occupation", "Available but not used by this model"),
        "dob": ("Date of birth", "Builds customer age"),
    },
}


def _plain_dtype(series: pd.Series) -> str:
    if isinstance(series.dtype, pd.CategoricalDtype):
        return "category"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date/time"
    if pd.api.types.is_bool_dtype(series):
        return "true/false"
    if pd.api.types.is_integer_dtype(series):
        return "whole number"
    if pd.api.types.is_float_dtype(series):
        return "decimal number"
    return "text or identifier"


def profile_source_columns(frame: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """One row per source column: quality, meaning, and downstream use."""
    catalog = SOURCE_COLUMN_CATALOG[table_name]
    rows = []
    for column in frame.columns:
        meaning, usage = catalog.get(column, ("Not documented", "Review before use"))
        missing = int(frame[column].isna().sum())
        rows.append(
            {
                "Column": column,
                "Plain meaning": meaning,
                "Type": _plain_dtype(frame[column]),
                "Missing": f"{missing:,} ({missing / len(frame):.1%})",
                "Unique values": f"{frame[column].nunique(dropna=True):,}",
                "How this notebook uses it": usage,
            }
        )
    return pd.DataFrame(rows)


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
