"""Single source of truth for paths, dates, and the business constants.

Every number a notebook cell or slide quotes should come from here, so there is
one place to change it and no chance of two artefacts disagreeing.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ── Paths ───────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"

CUSTOMERS_PARQUET = DATA_DIR / "customers.parquet"
TRANSACTIONS_PARQUET = DATA_DIR / "transactions.parquet"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "Sparkov synthetic card transactions"
DATASET_GENERATOR = "github.com/namebrandon/Sparkov_Data_Generation (MIT)"
DATASET_SEED = 42
DATASET_CUSTOMERS = 500

# ── The clock ───────────────────────────────────────────────────────────────
# Everything downstream is expressed relative to "today", so the notebook tells
# the same story whenever it is run.
AS_OF_DATE = pd.Timestamp("2026-08-31")

# A chargeback is only confirmed once the customer disputes it and the bank
# agrees. That takes about two months, which is why the most recent data has no
# trustworthy label.
LABEL_LAG_DAYS = 60
LABEL_MATURE_BEFORE = AS_OF_DATE - pd.Timedelta(days=LABEL_LAG_DAYS)

# ── The split, by time and never at random ──────────────────────────────────
TRAIN_START = pd.Timestamp("2024-07-01")
TRAIN_END = pd.Timestamp("2025-12-31")
TEST_START = pd.Timestamp("2026-01-01")
TEST_END = pd.Timestamp("2026-06-30")

# Real transactions whose labels have not matured. Never scored for metrics --
# they exist to make the label-lag lesson concrete.
FRONTIER_START = pd.Timestamp("2026-07-01")

N_CV_SPLITS = 4

# ── The operating point ─────────────────────────────────────────────────────
# Models are compared at the threshold that spends the same review budget, not
# at a fixed 0.5 cutoff. Six models put their scores in six different places on
# the 0-1 line, so a fixed cutoff would measure score distribution, not skill.
REVIEW_BUDGET = 0.03

# What one flagged transaction costs to look at.
REVIEW_MINUTES_PER_TXN = 4
ANALYST_HOURLY_RATE = 60.0

RANDOM_STATE = 42

# ── Presentation ────────────────────────────────────────────────────────────
COLOR_FRAUD = "#EF553B"
COLOR_LEGIT = "#636EFA"
COLOR_ACCENT = "#00CC96"
COLOR_WARN = "#FFA15A"
COLOR_MUTED = "#B6B6C4"
PLOT_TEMPLATE = "plotly_white"


def describe() -> str:
    """One-paragraph summary of the configuration, for the notebook header."""
    return (
        f"Dataset      : {DATASET_NAME} ({DATASET_CUSTOMERS} customers, seed {DATASET_SEED})\n"
        f"Generator    : {DATASET_GENERATOR}\n"
        f"Today        : {AS_OF_DATE:%Y-%m-%d}\n"
        f"Label lag    : {LABEL_LAG_DAYS} days -> labels trustworthy before "
        f"{LABEL_MATURE_BEFORE:%Y-%m-%d}\n"
        f"Train window : {TRAIN_START:%Y-%m-%d} to {TRAIN_END:%Y-%m-%d}\n"
        f"Test window  : {TEST_START:%Y-%m-%d} to {TEST_END:%Y-%m-%d}\n"
        f"Frontier     : {FRONTIER_START:%Y-%m-%d} onward (real, but not yet labelled)\n"
        f"Review budget: {REVIEW_BUDGET:.0%} of transactions"
    )
