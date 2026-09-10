"""Single source of truth for paths, the frozen spike decisions, and constants.

Every number a notebook cell, chart, or exported artifact quotes comes from
here or is measured live, so there is one place to change it and no chance of
two artifacts disagreeing.

The modeling choices - the global time split at 2011-09-09, the minimum of five
distinct training products per customer, item-item cosine truncated to fifteen
neighbours as the deployed ranking model, TruncatedSVD with 64 components as
the matrix-factorization comparison, ten slots, discovery-only eligibility, and
a fallback of recent revenue over the last 28 training days - were frozen by
the Module 6 technical spike and must not drift without re-running that
evidence.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ── Paths ───────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

INTERACTIONS_PARQUET = DATA_DIR / "interactions.parquet"
DESCRIPTIONS_PARQUET = DATA_DIR / "item_descriptions.parquet"
CLEANING_LEDGER = DATA_DIR / "cleaning_ledger.json"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "Online Retail II"
DATASET_UCI_ID = 502
DATASET_URL = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
DATASET_DOWNLOAD = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
DATASET_LICENSE = "CC BY 4.0"
DATASET_DOI = "https://doi.org/10.24432/C5CG6D"
DATASET_CITATION = (
    "Chen, D. (2019). Online Retail II. UCI Machine Learning Repository. "
    "https://doi.org/10.24432/C5CG6D"
)
DATASET_SOURCE_FILE = "online_retail_II.xlsx"
DATASET_BYTES = 45_622_278
DATASET_SHA256 = "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"
DATASET_RAW_ROWS = 1_067_371
DATASET_POPULATION = (
    "one UK-registered, non-store online retailer selling giftware, mostly to "
    "wholesale buyers, 2009-12-01 to 2011-12-09"
)
# The demand-forecasting lab in this same module reads the same workbook and
# asks a different question. Say so out loud in Stage 1.
SIBLING_LAB = "notebooks/demand-forecasting"
SIBLING_QUESTION = "how many units of this product will we sell next week?"
OUR_QUESTION = "which products should we show this shopper?"

# ── Cleaning (frozen; applied by scripts/build_dataset.py) ──────────────────
# Stock codes that are not products. Postage, carriage, bank charges, manual
# adjustments, samples and the retailer's own test rows.
NON_PRODUCT_CODES = {
    "POST", "D", "DOT", "M", "C2", "BANK CHARGES", "PADS", "ADJUST",
    "TEST001", "TEST002", "AMAZONFEE",
}
NON_PRODUCT_MEANING = {
    "POST": "postage charged on an order",
    "DOT": "DOTCOM postage",
    "D": "a discount line",
    "M": "a manual adjustment",
    "C2": "carriage",
    "BANK CHARGES": "bank charges",
    "PADS": "pads to match all cushions - a packing line",
    "ADJUST": "a stock adjustment",
    "TEST001": "the retailer's own test row",
    "TEST002": "the retailer's own test row",
    "AMAZONFEE": "an Amazon marketplace fee",
}
EXPECTED_CLEAN_ROWS = 1_003_424      # invoice lines surviving the five rules
EXPECTED_COMMITTED_ROWS = 992_123    # after collapsing to one row per (invoice, product)
EXPECTED_PRODUCTS = 4_904
EXPECTED_BASKETS = 39_523
EXPECTED_REGISTERED_CUSTOMERS = 5_852

# ── The split (frozen before any model was fitted) ──────────────────────────
SPLIT_CUT = pd.Timestamp("2011-09-09")
MIN_TRAIN_ITEMS_PER_USER = 5   # fewer than this and there is nothing to learn from
SEED = 42

EXPECTED_MATRIX_SHAPE = (4_962, 4_443)
EXPECTED_SPARSITY_PCT = 98.228
EXPECTED_TRAIN_PAIRS = 390_571
EXPECTED_TEST_PAIRS = 94_118
EXPECTED_STANDARD_USERS = 2_244
EXPECTED_DISCOVERY_USERS = 2_168

# ── Models ──────────────────────────────────────────────────────────────────
ITEM_NEIGHBOURS = 15           # measured peak: accuracy AND coverage AND size
SVD_COMPONENTS = 64            # measured peak across 16/32/64/128/256
K = 10                         # slots, and the K in every @K metric

DEPLOYED_MODEL = "item_item_cosine_top15"
DEPLOYED_MODEL_LABEL = "Item-item CF (top-15)"
POPULARITY_LABEL = "Popularity"
SVD_LABEL = "TruncatedSVD (64)"
REORDER_LABEL = "Reorder (already-bought)"
FALLBACK_LABEL = "Fallback: recent revenue 28d"
ITEMITEM_FULL_LABEL = "Item-item CF (full matrix)"
RANDOM_LABEL = "Random 10"

MODEL_ORDER = [
    RANDOM_LABEL, POPULARITY_LABEL, FALLBACK_LABEL, ITEMITEM_FULL_LABEL,
    DEPLOYED_MODEL_LABEL, SVD_LABEL, REORDER_LABEL,
]

MODEL_ONE_LINERS = {
    POPULARITY_LABEL: "Count how many customers bought each product. Show the same ten to everyone.",
    ITEMITEM_FULL_LABEL: "Products that are bought by the same customers are similar. Rank by similarity to what this customer already bought.",
    DEPLOYED_MODEL_LABEL: "The same idea, but each product keeps only its 15 closest neighbours and forgets the rest.",
    SVD_LABEL: "Compress 4,443 products into 64 numbers per customer, then rebuild the missing entries.",
    REORDER_LABEL: "Show the customer the things they already buy, most-ordered first. No learning at all.",
    FALLBACK_LABEL: "The ten products with the most revenue in the last 28 days of training. No customer input.",
    RANDOM_LABEL: "Ten products drawn uniformly at random. The floor any model has to clear.",
}

# ── Evaluation protocols ────────────────────────────────────────────────────
PROTOCOL_STANDARD = "standard"
PROTOCOL_DISCOVERY = "discovery"
PROTOCOL_INCOHERENT = "incoherent-middle"

PROTOCOL_DEFINITIONS = {
    PROTOCOL_STANDARD: {
        "name": "Standard next-purchase",
        "ground_truth": "every product the customer bought in the test window, repeats included",
        "candidates": "the whole catalog; products the customer already owns are NOT masked",
        "question": "did we predict what this customer bought next?",
    },
    PROTOCOL_DISCOVERY: {
        "name": "Discovery",
        "ground_truth": "only products the customer had NEVER bought before the cut",
        "candidates": "the catalog minus everything in the customer's training history",
        "question": "did we predict something this customer would not otherwise have found?",
    },
    PROTOCOL_INCOHERENT: {
        "name": "The incoherent middle",
        "ground_truth": "every product bought in the test window, repeats included",
        "candidates": "the catalog minus the customer's history - so 38.4% of the truth is unreachable",
        "question": "none that is answerable - this is the protocol bug to recognize",
    },
}

# ── Operating policy (frozen) ───────────────────────────────────────────────
SLOTS = 10
MODULE_TITLE = "Recommended for you"
FALLBACK_TITLE = "Popular right now"
REORDER_TITLE = "Buy it again"
FALLBACK_WINDOW_DAYS = 28
FALLBACK_RULE = "recent revenue, last 28 days of the training window"
FALLBACK_REFRESH = "weekly"

ELIGIBILITY = "products the customer has NEVER purchased in the training window"
PERSONALIZE_IF = (
    f"the customer appears in the training matrix - at least "
    f"{MIN_TRAIN_ITEMS_PER_USER} distinct products bought before the cut"
)
HUMAN_AUTHORITY = (
    "merchandisers own the exclusion list and the placement; the model only "
    "ranks products within the rules they set"
)
CLAIM_BOUNDARY = (
    "an offline ranking score is not evidence of revenue; the model ranks "
    "within a merchandiser's rules and never decides what a shopper needs"
)
CLAIM_BOUNDARY_LONG = (
    "This system orders a list of products for one merchandising slot. Its "
    "hit rate is measured against what customers happened to buy next in one "
    "13-week window of one retailer's history. That is not a revenue "
    "measurement and it is not a causal claim: the best model here reaches "
    "3.53% of the revenue available on products new to the customer, against "
    "2.81% for a list with no personalization in it at all, and even that gap "
    "is an upper bound because it credits the model for purchases the customer "
    "may have made anyway. A recommendation is not a statement about what the "
    "shopper needs. Merchandisers own placement and exclusions. Nothing here "
    "describes any real retailer's current operations."
)
PROHIBITED_CLAIMS = [
    "offline ranking scores are not evidence of revenue",
    "a recommendation is not a statement about what the shopper needs",
    "a hit rate measured on one 13-week window is not a business case",
    "nothing here is a statement about any real retailer's operations",
    "the 5%-conversion feedback-loop simulation is a labeled classroom "
    "assumption, not a measurement",
]

# ── Exposure-loop simulation (a labeled classroom assumption) ───────────────
FEEDBACK_ROUNDS = 10
FEEDBACK_CONVERSION = 0.05
FEEDBACK_ASSUMPTION_NOTE = (
    "5% of shown slots convert. This is a classroom assumption chosen to make "
    "the mechanism visible in ten rounds. It is NOT measured from this data and "
    "must be captioned as an assumption anywhere it appears."
)

# ── Discussion persona ──────────────────────────────────────────────────────
DISCUSSION_CUSTOMER = 17841
DISCUSSION_NOTE = (
    "1,934 distinct products across 167 baskets - 44% of the whole catalog. "
    "After the cut this account buys 893 distinct products, of which 865 are in "
    "the catalog and only 153 are new to it. Collaborative filtering scores 0 of "
    "10 on discovery; the reorder baseline scores 10 of 10. This account is a "
    "wholesaler restocking inventory, not a shopper browsing."
)

# ── Demo samples ────────────────────────────────────────────────────────────
SAMPLE_COUNT = 10
RELOAD_CHECK_USERS = 200

# ── Presentation (palette shared with every other lab in this course) ───────
COLOR_RISK = "#EF553B"      # the trap, the bias, the thing to distrust
COLOR_MODEL = "#636EFA"     # the personalized models
COLOR_ACCENT = "#00CC96"    # the deployed choice and policy marks
COLOR_WARN = "#FFA15A"      # baselines and secondary series
COLOR_MUTED = "#B6B6C4"     # context
COLOR_PURPLE = "#AB63FA"    # the matrix-factorization comparison
PLOT_TEMPLATE = "plotly_white"

MODEL_COLORS = {
    RANDOM_LABEL: COLOR_MUTED,
    POPULARITY_LABEL: COLOR_WARN,
    FALLBACK_LABEL: COLOR_WARN,
    ITEMITEM_FULL_LABEL: COLOR_MODEL,
    DEPLOYED_MODEL_LABEL: COLOR_ACCENT,
    SVD_LABEL: COLOR_PURPLE,
    REORDER_LABEL: COLOR_RISK,
}


def describe() -> str:
    """One-paragraph summary of the configuration, for the notebook header."""
    return (
        f"Dataset      : {DATASET_NAME} (UCI id {DATASET_UCI_ID}, {DATASET_LICENSE})\n"
        f"Population   : {DATASET_POPULATION}\n"
        f"Committed    : one row per product per basket, {EXPECTED_COMMITTED_ROWS:,} rows, zstd parquet\n"
        f"Question     : {OUR_QUESTION}\n"
        f"Split        : global time split at {SPLIT_CUT.date()} - never random; "
        f"customers need >= {MIN_TRAIN_ITEMS_PER_USER} distinct training products\n"
        f"Models       : popularity, item-item cosine (top-{ITEM_NEIGHBOURS}), "
        f"TruncatedSVD ({SVD_COMPONENTS}), reorder baseline, recent-revenue fallback\n"
        f"Protocols    : BOTH reported, always - standard next-purchase and discovery\n"
        f"Policy       : {SLOTS} slots, eligibility = {ELIGIBILITY}; "
        f'fallback "{FALLBACK_TITLE}" = {FALLBACK_RULE}\n'
        f"Seed         : {SEED}"
    )
