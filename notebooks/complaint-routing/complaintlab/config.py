"""Single source of truth for paths, the frozen spike decisions, and constants.

Every number a notebook cell, chart, or exported artifact quotes should come
from here, so there is one place to change it and no chance of two artefacts
disagreeing.

The modeling choices below were frozen by the Module 4 technical spike and must
not drift without re-running that evidence:

- the 2023+ date window and the 8-team label mapping,
- exact-narrative dedupe **before** sampling and splitting,
- the credit-reporting cap at 1.5x the second-largest team,
- TF-IDF (1-2 grams, min_df=2, max_features 50,000) + LogisticRegression,
- the 0.55 confidence threshold that separates auto-routing from human triage,
- seed 42 everywhere, and one single scoring of the test split.
"""

from __future__ import annotations

from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

TRAIN_PARQUET = DATA_DIR / "complaints_train.parquet"
VAL_PARQUET = DATA_DIR / "complaints_val.parquet"
TEST_PARQUET = DATA_DIR / "complaints_test.parquet"
EMBEDDINGS_TRAIN_PARQUET = DATA_DIR / "embeddings_compare_train.parquet"
EMBEDDINGS_VAL_PARQUET = DATA_DIR / "embeddings_compare_val.parquet"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "CFPB Consumer Complaint Database"
DATASET_PUBLISHER = "Consumer Financial Protection Bureau (US federal agency)"
DATASET_HOME = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
DATASET_BULK_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
DATASET_RETRIEVED = "2026-09-01"
DATASET_LICENSE = "US Government public data; no copyright, free to use and redistribute"
DATASET_BULK_SIZE = "1.42 GB zip / 9.2 GB CSV / 16 columns"
DATASET_ROW_MEANING = (
    "one complaint a consumer submitted to the CFPB about one financial company"
)
NARRATIVE_NOTE = (
    "The narrative is opt-in: the consumer must consent to publication, and the "
    "CFPB scrubs personal details before publishing, replacing them with XXXX."
)

# Measured once during the spike by streaming the full bulk file. The committed
# parquets are a sample, so these totals are provenance facts, not numbers the
# notebook can recompute offline.
SOURCE_ROWS_SCANNED = 17_456_743
SOURCE_ROWS_WITH_NARRATIVE = 3_846_323
SOURCE_NARRATIVE_ROWS_IN_WINDOW = 2_640_147
SOURCE_NARRATIVE_ROWS_PER_YEAR = {
    "2022": 337_273,
    "2023": 487_410,
    "2024": 814_385,
    "2025": 1_222_049,
    "2026 (partial)": 116_303,
}

# ── The window ──────────────────────────────────────────────────────────────
DATE_WINDOW_START = "2023-01-01"
DATE_WINDOW_REASON = (
    "Recent complaints only. Product labels were renamed in 2023 and complaint "
    "volume roughly quadrupled between 2022 and 2025, so older rows describe a "
    "different mix of companies, products, and consumer language."
)

# ── Label consolidation: CFPB product label -> specialist team ──────────────
# The CFPB renamed and split product categories over the years. Mapping them to
# eight standing teams is the label-consolidation step of this lab. Labels in
# parentheses in the notebook table are pre-2017 spellings kept for robustness;
# they do not appear inside the 2023+ window.
TEAM_MAP = {
    "Credit reporting, credit repair services, or other personal consumer reports": "Credit reporting",
    "Credit reporting or other personal consumer reports": "Credit reporting",
    "Credit reporting": "Credit reporting",
    "Credit card": "Credit cards",
    "Credit card or prepaid card": "Credit cards",
    "Prepaid card": "Credit cards",
    "Checking or savings account": "Bank accounts",
    "Bank account or service": "Bank accounts",
    "Mortgage": "Mortgages",
    "Debt collection": "Debt collection",
    "Money transfer, virtual currency, or money service": "Money transfers",
    "Money transfers": "Money transfers",
    "Virtual currency": "Money transfers",
    "Vehicle loan or lease": "Loans",
    "Payday loan, title loan, or personal loan": "Loans",
    "Payday loan, title loan, personal loan, or advance loan": "Loans",
    "Payday loan": "Loans",
    "Consumer Loan": "Loans",
    "Student loan": "Student loans",
}

# Product labels present in the window that map to no team, with the counts that
# justified dropping them.
DROPPED_PRODUCTS = {"Debt or credit management": 5_545}
DROPPED_REASON = (
    "A category the CFPB introduced in 2023. It is small and its complaints "
    "read as a mix of the other eight, so no standing team owns it."
)

TEAMS = [
    "Bank accounts",
    "Credit cards",
    "Credit reporting",
    "Debt collection",
    "Loans",
    "Money transfers",
    "Mortgages",
    "Student loans",
]

TEAM_DESCRIPTIONS = {
    "Bank accounts": "checking and savings accounts, overdraft fees, closures",
    "Credit cards": "credit cards, prepaid and gift cards, card billing",
    "Credit reporting": "credit reports, disputes, inaccurate items, inquiries",
    "Debt collection": "collectors, validation of debts, collection lawsuits",
    "Loans": "vehicle, payday, title, and personal loans",
    "Money transfers": "payment apps, wire transfers, virtual currency",
    "Mortgages": "mortgage servicing, escrow, modification, foreclosure",
    "Student loans": "federal and private student loans, forbearance, servicers",
}

# ── Dedupe: the spike's biggest surprise, frozen as evidence ────────────────
DEDUPE_RULE = "drop_duplicates(subset='narrative', keep='first') before sampling and splitting"
DEDUPE_ROWS_IN_WINDOW = 2_634_602          # mapped rows in the window, before dedupe
DEDUPE_ROWS_REMOVED = 1_093_131
DEDUPE_SHARE_REMOVED = 0.4149
DEDUPE_DISTINCT_NARRATIVES = 1_541_471
DEDUPE_NARRATIVES_WITH_COPIES = 187_880
# Share of each team's rows in the window that were exact copies of an earlier row.
DEDUPE_SHARE_BY_TEAM = {
    "Credit reporting": 0.5237,
    "Money transfers": 0.2630,
    "Debt collection": 0.2347,
    "Credit cards": 0.0920,
    "Bank accounts": 0.0328,
    "Student loans": 0.0057,
    "Loans": 0.0054,
    "Mortgages": 0.0008,
}
DEDUPE_TEAM_ROWS_IN_WINDOW = {
    "Credit reporting": 1_896_931,
    "Debt collection": 245_247,
    "Credit cards": 141_000,
    "Bank accounts": 129_396,
    "Money transfers": 92_855,
    "Loans": 53_705,
    "Mortgages": 46_569,
    "Student loans": 28_899,
}
DEDUPE_TOP_TEMPLATE_COPIES = [27_496, 22_508, 18_443, 15_803, 12_204]

# What skipping the dedupe cost, measured on the spike's first (leaky) build.
LEAKAGE_TEST_ROWS_SEEN_IN_TRAIN = 0.170
LEAKAGE_INFLATED_TEST_ACCURACY = 0.843
LEAKAGE_HONEST_TEST_ACCURACY = 0.819
LEAKAGE_INFLATION_POINTS = 2.4

# One real template letter, quoted verbatim from two different complaint IDs
# filed nine days apart from two different states. Both rows are in the 2023+
# window of the source file; the committed sample keeps at most one of them.
DUPLICATE_EXAMPLE = {
    "copies_in_window": 27_496,
    "narrative": (
        "In accordance with the Fair Credit Reporting act. The List of accounts "
        "below has violated my federally protected consumer rights to privacy "
        "and confidentiality under 15 USC 1681.\n\n15 U.S.C 1681 section 602 A. "
        "States I have the right to privacy.\n\n15 U.S.C 1681 Section 604 A "
        "Section 2 : It also states a consumer reporting agency can not furnish "
        "a account without my written instructions 15 U.S.C 1681c. ( a ) ( 5 ) "
        "Section States : no consumer reporting agency may make any consumer "
        "report containing any of the following items of information Any other "
        "adverse item of information, other than records of convictions of "
        "crimes which antedates the report by more than seven years.\n\n15 "
        "U.S.C. 1681s-2 ( A ) ( 1 ) A person shall not furnish any information "
        "relating to a consumer to any consumer reporting agency if the person "
        "knows or has reasonable cause to believe that the information is "
        "inaccurate."
    ),
    "filings": [
        {"complaint_id": "6693377", "date_received": "2023-03-14", "state": "AL"},
        {"complaint_id": "6735947", "date_received": "2023-03-23", "state": "FL"},
    ],
}

# ── Sample and splits ───────────────────────────────────────────────────────
RANDOM_STATE = 42
CREDIT_REPORTING_CAP_MULTIPLE = 1.5
CAP_DISCLOSURE = (
    "Credit reporting was capped at 1.5x the second-largest team before "
    "sampling. In the real 2023+ window it is 4.8x larger than debt collection. "
    "The cap is a classroom display choice that keeps every team learnable; it "
    "means the team shares in this lab are not the real-world mix."
)
SAMPLE_FLOOR_PER_TEAM = 2_000
EXPECTED_SPLIT_ROWS = {"train": 40_729, "validation": 8_728, "test": 8_728}
EXPECTED_TOTAL_ROWS = 58_185
SPLIT_FRACTIONS = "70 / 15 / 15, stratified by team, seed 42"

TEXT_COLUMN = "narrative"
TARGET = "team"

# ── The representation comparison (matched rows, offline by construction) ───
# Both representations are fitted on the SAME 15,000 training complaints and
# scored on the SAME full validation split, so the comparison measures the
# representation and nothing else.
COMPARE_TRAIN_ROWS = 15_000
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_FACTS = {
    "Transformer layers": "6",
    "Attention heads per layer": "12",
    "Hidden size (numbers per token)": "384",
    "Feed-forward size inside a layer": "1,536",
    "Vocabulary": "30,522 wordpieces",
    "Parameters": "22,713,216 (~22.7M)",
    "Output vector per complaint": "384 numbers (mean-pooled, normalized)",
    "Longest input it reads": "256 wordpiece tokens, the rest is cut off",
    "Download size": "183.2 MB",
    "Encoding speed measured on a classroom CPU": "211 narratives per second",
}
EMBEDDING_DIM = 384
EMBEDDING_STORAGE = "float16"
EMBEDDING_NOT_PROVEN = (
    "The 384-number summary does not prove the model understood the complaint. "
    "It only places complaints that use similar language near each other. It "
    "carries no fact about the company, no legal judgement, and no evidence "
    "that the consumer is right."
)

# ── TF-IDF + logistic regression (the deployed model) ───────────────────────
TFIDF_NGRAM_RANGE = (1, 2)
TFIDF_MIN_DF = 2
TFIDF_MAX_FEATURES = 50_000
TFIDF_SUBLINEAR_TF = True
TFIDF_STRIP_ACCENTS = "unicode"
LR_C = 1.0
LR_MAX_ITER = 1_000

# ── Operating policy ────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.55
THRESHOLD_SWEEP = [0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
POLICY_RULE = (
    "auto-route to the predicted team when the highest team probability >= 0.55; "
    "otherwise send the complaint to the human triage queue"
)
ROUTE_AUTO = "auto_route"
ROUTE_TRIAGE = "human_triage"
POLICY_BOUNDARY = "the model routes; it never judges whether a complaint is valid"
ROUTE_ACTIONS = {
    ROUTE_AUTO: (
        "The complaint lands in that team's queue. The specialist who owns the "
        "product reads it, pulls the account, and writes the company response "
        "inside the regulatory clock."
    ),
    ROUTE_TRIAGE: (
        "The complaint goes to the triage queue. A clerk reads it, picks the "
        "team by hand, and the complaint continues from there. Nothing is "
        "closed, delayed, or dismissed by landing here."
    ),
}

# ── Sample manifest for the app ─────────────────────────────────────────────
MANIFEST_TOTAL = 60
MANIFEST_TRIAGE = 15
TOP_WORDS = 5

# The 12 test complaints the spike agent read in full and screened: all eight
# teams, confidence 0.363-0.996, two below the threshold, one deliberate
# above-threshold misroute. No distressing content, no template letters.
CURATED_COMPLAINT_IDS = [
    "11541129",  # Bank accounts, 0.986 - overdraft fee posting order
    "12115092",  # Credit cards, 0.993 - prepaid gift card declined everywhere
    "14745976",  # Credit reporting, 0.992 - fraudulent accounts opened
    "16976740",  # Debt collection, 0.996 - sued without debt validation
    "7425060",   # Loans, 0.989 - auto loan approved then rejected
    "11713834",  # Money transfers, 0.992 - payment-app fraud handling
    "11254302",  # Mortgages, 0.991 - escrow raised over a $1 tax increase
    "13661011",  # Student loans, 0.986 - interest during 0% forbearance
    "6398703",   # Bank accounts -> Credit cards, 0.666 - MISROUTE above threshold
    "14771564",  # Credit reporting, 0.593 - formal dispute letter, mid confidence
    "10154480",  # Money transfers, 0.545 - TRIAGE, unusual lockout story
    "7088278",   # Credit cards, 0.363 - TRIAGE, complaint about the process
]
MISROUTE_EXAMPLE_ID = "6398703"
WALKTHROUGH_IDS = ["11713834", "7088278", "6398703"]

# ── Frozen spike targets (the notebook must reproduce these) ────────────────
FROZEN_TEST_METRICS = {
    "accuracy": 0.8207,
    "macro_f1": 0.8097,
    "coverage": 0.7829,
    "accuracy_among_auto_routed": 0.8967,
}
MAJORITY_BASELINE_ACCURACY = 0.305

# ── Presentation (palette shared with the fraud, pneumonia, credit labs) ────
COLOR_PRIMARY = "#636EFA"   # the deployed model, correct routes
COLOR_ALERT = "#EF553B"     # errors, misroutes, duplicates
COLOR_ACCENT = "#00CC96"    # policy marks and the chosen threshold
COLOR_WARN = "#FFA15A"      # secondary series, triage
COLOR_MUTED = "#B6B6C4"     # context series
TEAM_COLORS = {
    "Bank accounts": "#636EFA",
    "Credit cards": "#EF553B",
    "Credit reporting": "#00CC96",
    "Debt collection": "#AB63FA",
    "Loans": "#FFA15A",
    "Money transfers": "#19D3F3",
    "Mortgages": "#FF6692",
    "Student loans": "#B6E880",
}
PLOT_TEMPLATE = "plotly_white"


def describe() -> str:
    """One-paragraph summary of the configuration, for the notebook header."""
    return (
        f"Dataset      : {DATASET_NAME} ({DATASET_PUBLISHER})\n"
        f"Window       : complaints received on or after {DATE_WINDOW_START}, "
        f"narrative present\n"
        f"Row meaning  : {DATASET_ROW_MEANING}\n"
        f"Labels       : {len(TEAMS)} specialist teams consolidated from CFPB product names\n"
        f"Sample       : {EXPECTED_TOTAL_ROWS:,} complaints, split {SPLIT_FRACTIONS}\n"
        f"Model        : TF-IDF ({TFIDF_NGRAM_RANGE[0]}-{TFIDF_NGRAM_RANGE[1]} grams, "
        f"max {TFIDF_MAX_FEATURES:,} features) + logistic regression\n"
        f"Policy       : {POLICY_RULE}"
    )
