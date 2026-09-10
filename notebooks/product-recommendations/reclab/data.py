"""Load the committed interaction log and describe what is in it.

Nothing here downloads, and nothing here cleans: the five cleaning rules ran
once in ``scripts/build_dataset.py`` and their ledger is committed beside the
parquet. What this module does instead is *verify* that the committed file
still satisfies every rule, so a student can see the guarantee tested rather
than asserted.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config


# ── Loading ─────────────────────────────────────────────────────────────────

def load_interactions() -> pd.DataFrame:
    """The committed log: one row per product per basket.

    Columns: ``invoice``, ``stock_code``, ``invoice_ts``, ``customer_id``
    (nullable - guest checkouts have none), ``revenue``.
    """
    frame = pd.read_parquet(config.INTERACTIONS_PARQUET)
    frame["invoice_ts"] = pd.to_datetime(frame["invoice_ts"])
    # StockCode is a string here and stays one. The raw column mixes integers
    # and strings; anything that sorts or sets over the mixture raises.
    frame["stock_code"] = frame["stock_code"].astype(str)
    return frame


def load_descriptions() -> pd.Series:
    """stock_code -> product description, one row per product."""
    frame = pd.read_parquet(config.DESCRIPTIONS_PARQUET)
    return pd.Series(frame["description"].astype(str).values,
                     index=frame["stock_code"].astype(str).values)


def load_ledger() -> dict:
    """The cleaning ledger written by scripts/build_dataset.py."""
    return json.loads(config.CLEANING_LEDGER.read_text())


# ── Provenance ──────────────────────────────────────────────────────────────

def provenance_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Verified facts about the committed file, measured now."""
    ledger = load_ledger()
    guests = int(frame["customer_id"].isna().sum())
    rows = [
        ("Source", f"{config.DATASET_NAME} (UCI id {config.DATASET_UCI_ID})"),
        ("License", config.DATASET_LICENSE),
        ("Raw invoice lines in the workbook", f"{ledger['raw_rows']:,}"),
        ("Lines surviving the five cleaning rules", f"{ledger['clean_rows']:,}"),
        ("Committed rows (one product per basket)", f"{len(frame):,}"),
        ("Baskets", f"{frame['invoice'].nunique():,}"),
        ("Products", f"{frame['stock_code'].nunique():,}"),
        ("Registered customers", f"{frame['customer_id'].nunique():,}"),
        ("Rows with no customer id (guest checkout)",
         f"{guests:,} ({guests / len(frame):.1%})"),
        ("First invoice", str(frame["invoice_ts"].min())),
        ("Last invoice", str(frame["invoice_ts"].max())),
        ("Total revenue in the file", f"{frame['revenue'].sum():,.0f}"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def cleaning_ledger_table() -> pd.DataFrame:
    """The five rules and what each one removed."""
    ledger = load_ledger()
    frame = pd.DataFrame(ledger["steps"])
    frame["share_of_raw"] = frame["removed"] / ledger["raw_rows"]
    return frame.rename(columns={"step": "Rule", "removed": "Rows removed",
                                 "remaining": "Rows remaining",
                                 "share_of_raw": "Share of raw"})


def verify_cleaning(frame: pd.DataFrame) -> pd.DataFrame:
    """Re-test every cleaning guarantee against the file we actually shipped."""
    codes = frame["stock_code"].str.upper()
    checks = [
        ("No credit notes",
         int(frame["invoice"].str.upper().str.startswith("C").sum())),
        ("No non-positive revenue", int((frame["revenue"] <= 0).sum())),
        ("No non-product stock codes",
         int(codes.isin(config.NON_PRODUCT_CODES).sum())),
        ("No duplicate (invoice, product) rows",
         int(frame.duplicated(["invoice", "stock_code"]).sum())),
        ("No missing timestamps", int(frame["invoice_ts"].isna().sum())),
    ]
    result = pd.DataFrame(checks, columns=["Guarantee", "Violations"])
    result["Holds"] = result["Violations"] == 0
    result.loc[len(result)] = ["stock_code is stored as text, not a number",
                               0, frame["stock_code"].dtype == object]
    return result


# ── Shape of the demand ─────────────────────────────────────────────────────

def guest_share(frame: pd.DataFrame) -> dict:
    """Guest checkouts: rows, baskets and revenue with no customer id at all."""
    guest = frame[frame["customer_id"].isna()]
    return {
        "guest_rows": int(len(guest)),
        "total_rows": int(len(frame)),
        "guest_row_share": float(len(guest) / len(frame)),
        "guest_baskets": int(guest["invoice"].nunique()),
        "total_baskets": int(frame["invoice"].nunique()),
        "guest_basket_share": float(guest["invoice"].nunique() / frame["invoice"].nunique()),
        "guest_revenue": float(guest["revenue"].sum()),
        "guest_revenue_share": float(guest["revenue"].sum() / frame["revenue"].sum()),
    }


def popularity_curve(frame: pd.DataFrame) -> pd.DataFrame:
    """Cumulative share of interactions held by the N most-bought products."""
    counts = (frame.dropna(subset=["customer_id"])
              .drop_duplicates(["customer_id", "stock_code"])
              .groupby("stock_code").size().sort_values(ascending=False))
    cumulative = counts.cumsum() / counts.sum()
    return pd.DataFrame({
        "rank": np.arange(1, len(counts) + 1),
        "interactions": counts.values,
        "cumulative_share": cumulative.values,
    })


def basket_profile(frame: pd.DataFrame) -> pd.DataFrame:
    """How often customers come back - the column that explains this whole case."""
    registered = frame.dropna(subset=["customer_id"])
    baskets = registered.groupby("customer_id")["invoice"].nunique()
    pairs = registered.groupby(["customer_id", "stock_code"])["invoice"].nunique()
    rows = [
        ("Distinct (customer, product) pairs", f"{len(pairs):,}"),
        ("... bought in more than one basket",
         f"{int((pairs > 1).sum()):,} = {(pairs > 1).mean():.1%}"),
        ("Mean baskets per (customer, product) pair", f"{pairs.mean():.2f}"),
        ("Most baskets for one (customer, product) pair", f"{int(pairs.max())}"),
        ("Baskets per customer: mean / median / 90th percentile",
         f"{baskets.mean():.1f} / {baskets.median():.0f} / {baskets.quantile(0.9):.0f}"),
        ("Customers with more than one basket", f"{(baskets > 1).mean():.1%}"),
    ]
    return pd.DataFrame(rows, columns=["Quantity", "Value"])


def one_row_example(frame: pd.DataFrame, descriptions: pd.Series,
                    n: int = 6) -> pd.DataFrame:
    """One real basket, rendered so 'what a row means' is concrete."""
    registered = frame.dropna(subset=["customer_id"])
    sizes = registered.groupby("invoice").size()
    invoice = sizes[(sizes >= n) & (sizes <= n + 4)].index[0]
    basket = frame[frame["invoice"] == invoice].head(n).copy()
    basket["description"] = basket["stock_code"].map(descriptions)
    return basket[["invoice", "invoice_ts", "customer_id", "stock_code",
                   "description", "revenue"]]
