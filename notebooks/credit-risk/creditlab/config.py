"""Single source of truth for paths, the frozen spike decisions, and constants.

Every number a notebook cell, chart, or exported artifact quotes should come
from here, so there is one place to change it and no chance of two artefacts
disagreeing. The modeling choices (engineered-7 features, 60/20/20 stratified
split, HistGradientBoosting with no calibration wrapper, the expected-cost
policy at NT$10,000) were frozen by the Module 4 technical spike and must not
drift without re-running that evidence.
"""

from __future__ import annotations

from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

ACCOUNTS_PARQUET = DATA_DIR / "accounts.parquet"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "UCI Default of Credit Card Clients"
DATASET_UCI_ID = 350
DATASET_URL = "https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients"
DATASET_LICENSE = "CC BY 4.0"
DATASET_CITATION = (
    "Yeh, I-C. & Lien, C-H. (2009). The comparisons of data mining techniques "
    "for the predictive accuracy of probability of default of credit card "
    "clients. Expert Systems with Applications, 36(2), 2473-2480."
)
DATASET_SOURCE_FILE = "default of credit card clients.xls"
DATASET_XLS_SHA256 = "30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933"
DATASET_POPULATION = (
    "30,000 existing credit-card customers of one Taiwanese issuer, "
    "observed April-September 2005"
)
EXPECTED_ROWS = 30_000
EXPECTED_DEFAULT_RATE = 0.2212

# ── Split (row-level stratified; one row = one customer = one entity) ───────
RANDOM_STATE = 42
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20
TEST_FRACTION = 0.20
EXPECTED_SPLIT_COUNTS = {"train": 18_000, "validation": 6_000, "test": 6_000}

# ── Columns ─────────────────────────────────────────────────────────────────
TARGET = "DEFAULT"

# Present in the data, deliberately excluded from model features. Kept only to
# audit the finished model's behavior across groups (US fair-lending law
# restricts using them in the credit decision itself).
PROTECTED_ATTRIBUTES = ["SEX", "MARRIAGE", "AGE"]

SEX_LABELS = {1: "male", 2: "female"}
EDUCATION_LABELS = {1: "graduate school", 2: "university", 3: "high school", 4: "other"}
MARRIAGE_LABELS = {1: "married", 2: "single", 3: "other"}
AGE_BAND_EDGES = [20, 30, 40, 50, 60, 100]
AGE_BAND_LABELS = ["20-29", "30-39", "40-49", "50-59", "60+"]

# ── The engineered-7 features (order is frozen: pipeline + SHAP rely on it) ─
FEATURE_DISPLAY_NAMES = {
    "months_late_now": "How many months behind on payments right now",
    "worst_delay_6m": "Worst payment delay in the last 6 months",
    "num_late_months_6m": "Number of late months in the last 6 months",
    "utilization": "Share of the credit limit currently used",
    "payment_ratio_6m": "Share of billed amounts actually paid (6 months)",
    "bill_trend_6m": "Balance growth over 6 months, relative to the limit",
    "credit_limit": "Credit limit",
}

# ── Operating policy ────────────────────────────────────────────────────────
# All dollar values are SYNTHETIC CLASSROOM ASSUMPTIONS in New Taiwan dollars
# (NT$). They make the cost trade-off concrete; they are not measured costs
# from any real bank.
LOSS_GIVEN_DEFAULT = 0.5           # share of the exposed balance lost if the account defaults
REVIEW_COST_NT = 10_000            # frozen: fully loaded cost of one analyst review + outreach
REVIEW_COST_SWEEP_NT = [1_000, 2_000, 3_000, 5_000, 8_000, 10_000, 12_000, 15_000, 20_000]
POLICY_RULE = "flag for review when p(default) x exposure x LGD > review_cost"
EXPOSURE_DEFINITION = "BILL_AMT1 clipped to [0, LIMIT_BAL]"
ROUTE_FLAGGED = "priority_review"
ROUTE_SAFE = "standard_monitoring"

# ── Sample manifest for the app ─────────────────────────────────────────────
MANIFEST_TOTAL = 60
MANIFEST_FLAGGED = 15
TOP_REASONS = 3

# ── Presentation (palette shared with the fraud lab) ────────────────────────
COLOR_DEFAULT = "#EF553B"   # accounts that defaulted / risk-raising
COLOR_REPAID = "#636EFA"    # accounts that paid / risk-lowering
COLOR_ACCENT = "#00CC96"    # policy and selection marks
COLOR_WARN = "#FFA15A"      # warnings, secondary series
COLOR_MUTED = "#B6B6C4"     # context series
PLOT_TEMPLATE = "plotly_white"


def describe() -> str:
    """One-paragraph summary of the configuration, for the notebook header."""
    return (
        f"Dataset      : {DATASET_NAME} (UCI id {DATASET_UCI_ID}, {DATASET_LICENSE})\n"
        f"Population   : {DATASET_POPULATION}\n"
        f"Split        : {TRAIN_FRACTION:.0%}/{VALIDATION_FRACTION:.0%}/{TEST_FRACTION:.0%} "
        f"stratified on {TARGET}, seed {RANDOM_STATE}\n"
        f"Model input  : 7 engineered behavior features; {', '.join(PROTECTED_ATTRIBUTES)} excluded\n"
        f"Policy       : {POLICY_RULE} "
        f"(LGD {LOSS_GIVEN_DEFAULT}, review cost NT${REVIEW_COST_NT:,}; classroom assumptions)"
    )
