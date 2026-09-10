"""Single source of truth for paths, provenance, and the frozen Module 6 decisions.

Every number a notebook cell, chart, or exported artifact quotes comes from
here or is measured at run time, so there is one place to change a constant and
no chance of two artifacts disagreeing.

The modeling choices below were frozen by the Module 6 technical spike and must
not drift without re-running that evidence:

    weekly grain (the retailer is closed Saturdays, so a daily model learns a
    spurious weekly zero) -> dense product x week panel -> drop the two partial
    edge weeks -> 102 weeks -> cohort = products selling in at least 90% of the
    76 TRAINING weeks -> 76/26 chronological split -> point forecast = mean of
    the last 8 observed weeks -> interval = that product's own empirical
    residual quantiles, clipped at zero -> order = the newsvendor quantile
    cu / (cu + co).
"""

from __future__ import annotations

from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

WEEKLY_CSV = DATA_DIR / "online_retail_weekly.csv.gz"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "Online Retail II"
DATASET_UCI_ID = 502
DATASET_URL = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
DATASET_DOWNLOAD = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
DATASET_LICENSE = "CC BY 4.0"
DATASET_DOI = "10.24432/C5CG6D"
DATASET_CITATION = (
    "Chen, D. (2019). Online Retail II. UCI Machine Learning Repository. "
    "https://doi.org/10.24432/C5CG6D"
)
DATASET_ZIP_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"
DATASET_ZIP_BYTES = 45_622_418
DATASET_SOURCE_FILE = "online_retail_II.xlsx"
DATASET_XLSX_BYTES = 45_622_278
DATASET_SHEETS = ("Year 2009-2010", "Year 2010-2011")
DATASET_POPULATION = (
    "one UK-registered, non-store online gift wholesaler selling mainly to small "
    "business retailers, recorded 2009-12-01 to 2011-12-09"
)

# Measured on the raw workbook by scripts/build_dataset.py. Each of these is a
# quirk the notebook states out loud in Stage 1 rather than quietly cleaning.
RAW_ROWS = 1_067_371
RAW_COLUMNS = 8
RAW_SPAN_DAYS = 739
RAW_INVOICES = 53_628
RAW_CUSTOMERS = 5_942
RAW_COUNTRIES = 43
RAW_UK_ROW_SHARE = 0.919
DUPLICATE_ROWS = 34_335            # exact duplicate rows, kept once
CANCELLATION_ROWS = 19_494         # invoice numbers beginning with "C"
NONPOSITIVE_QUANTITY_ROWS = 22_950
NONPOSITIVE_PRICE_ROWS = 6_207
GUEST_ROWS = 243_007               # no Customer ID at all
GUEST_SHARE = 0.2277
TRADING_DAYS = 604                 # calendar days with at least one clean sale
SATURDAYS_OPEN = 1                 # the whole reason this lab aggregates weekly
SATURDAY_OPEN_DATE = "2009-12-05"
TRADING_DAYS_BY_WEEKDAY = {
    "Monday": 94, "Tuesday": 104, "Wednesday": 104, "Thursday": 103,
    "Friday": 99, "Saturday": 1, "Sunday": 99,
}
# Stock codes that are charges, adjustments or test rows rather than products.
NON_PRODUCT_CODES = (
    "POST", "D", "DOT", "M", "C2", "BANK CHARGES", "PADS", "ADJUST",
    "TEST001", "TEST002",
)
# Codes that survive that list and are still not products. Left in on purpose:
# Stage 1 shows them, and the cohort rule is what actually keeps them out.
SURVIVING_NON_PRODUCT_CODES = ("AMAZONFEE", "B", "S", "ADJUST2", "gift_0001_*")

# ── The committed weekly file ───────────────────────────────────────────────
WEEKLY_CSV_BYTES = 952_490
WEEKLY_CSV_ROWS = 197_951
WEEKLY_CSV_SHA256 = "85e552d7bacde057ef2013f5815289533a508460eb238fe616393e2884c07352"
WEEKLY_COLUMNS = ("StockCode", "description", "week", "units", "unit_price")
CLEAN_ROWS = 1_003_427             # transaction lines behind the weekly file
WEEKS_IN_FILE = 104                # before the partial edge weeks are dropped

# ── Frozen panel and split ──────────────────────────────────────────────────
DROP_EDGE_WEEKS = True             # first and last week are partial-coverage edges
TOTAL_WEEKS = 102
TOTAL_PRODUCTS = 4_871
N_TRAIN = 76
N_TEST = 26
TRAIN_START, TRAIN_END = "2009-12-07", "2011-05-30"
TEST_START, TEST_END = "2011-06-06", "2011-11-28"

# ── Frozen cohort ───────────────────────────────────────────────────────────
COHORT_MIN_NONZERO = 0.90          # share of TRAIN weeks with a sale
COHORT_SIZE = 469
COHORT_SIZE_LEAKY = 442            # same rule applied to all 102 weeks - leakage
INTERMITTENT_BAND = (0.35, 0.50)   # the contrast set, never deployed
INTERMITTENT_SIZE = 653

# ── Frozen model ────────────────────────────────────────────────────────────
WINDOW = 8                         # weeks in the moving average
NOMINAL_LO, NOMINAL_HI = 0.10, 0.90
NOMINAL_COVERAGE = 0.80
MODEL_VERSION = "M06-fc-1.0"
POLICY_VERSION = "M06-policy-1.0"
SEED = 42                          # only the gradient-boosting comparison uses it

# ── Frozen policy ───────────────────────────────────────────────────────────
CO_FRACTION = 0.10                 # CLASSROOM ASSUMPTION: overstock cost per unit-week
RATIOS_TAUGHT = (2, 4, 9)
RATIOS_SWEPT = (2, 3, 4, 6, 9, 19)
COST_CURVE_QUANTILES = (0.30, 0.40, 0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)

COST_ASSUMPTION_NOTE = (
    "CLASSROOM ASSUMPTION - not any real retailer's economics. Overstock co = "
    "0.10 x unit_price per unit per week (one week of storage plus markdown "
    "risk). Understock cu = ratio x co; at 4:1 that is 0.40 x unit_price, "
    "exactly a 40% gross margin lost on every unit not on the shelf."
)
HUMAN_AUTHORITY = (
    "The proposed quantity is a suggestion to a planner. The planner approves, "
    "adjusts or overrides it. The system never places an order."
)
PROHIBITED_CLAIMS = (
    "The forecast is not a promise.",
    "The interval is not a guarantee; it is a range that held 84% of the time on "
    "held-out weeks against a promised 80%.",
    "Neither figure is a statement about any real retailer's operations.",
)

# ── Named products the deck and the demo walk through ───────────────────────
# Every code below was resolved against the committed file and asserted at run
# time by ``config.check_named_products``. The spike report named three of them
# by a stock code that belongs to a different product; the codes here are the
# ones whose measured numbers the spike actually reports.
DEMO_PRODUCTS = ("85099B", "82494L", "35961")   # fan chart, best case, the trap
D06_PRODUCTS = {
    "85099B": "JUMBO BAG RED RETROSPOT",          # -29.0%
    "82494L": "WOODEN FRAME ANTIQUE WHITE",       # -47.5%
    "85099C": "JUMBO  BAG BAROQUE BLACK WHITE",   # -38.3% (two spaces in the source)
    "22112": "CHOCOLATE HOT WATER BOTTLE",        # -23.1%
}
# 84029E is RED WOOLLY HOTTIE WHITE HEART. in this dataset. The spike report
# labels this code "KNITTED UNION FLAG HOT WATER BOTTLE", which is 84029G; the
# 80.8% / five-misses-all-high week-by-week table it prints is 84029E's, and
# the spike's own demo manifest names 84029E correctly. Code wins over label.
CHRISTMAS_PRODUCT = "84029E"       # RED WOOLLY HOTTIE WHITE HEART.
CHRISTMAS_PRODUCT_NAME = "RED WOOLLY HOTTIE WHITE HEART."
POLICY_LOSER = "22084"             # PAPER CHAIN KIT EMPIRE, +384% at 4:1
# Ten products packaged into sample_manifest.parquet, chosen by rule.
MANIFEST_PRODUCTS = {
    "22197": "steady seller",
    "85099B": "steady seller",
    "84879": "steady seller",
    "84029E": "Christmas spike - the coverage failure",
    "22112": "Christmas spike",
    "21484": "Christmas spike - the steepest Q4 skew in the cohort",
    "35961": "point forecast fine, band dangerous",
    "22188": "point forecast fine, band dangerous",
    "22084": "the policy LOSES money here",
    "82494L": "the policy's cleanest win",
}
SEASONAL_TOP_N = 50                # products used for the Q4 coverage slice
Q4_RAMP_MONTHS = (10, 11)          # the Oct-Nov ramp inside the test window

# ── Frozen holdout targets, scored once by the spike ────────────────────────
# The notebook asserts against these. A mismatch means something drifted.
FROZEN = {
    "n_products": 469,
    "n_test_weeks": 26,
    "n_rows": 12_194,
    "MAE": 51.567,
    "RMSE": 133.264,
    "coverage_80": 0.8406,
    "median_band": 88.08,
    "band_over_median_demand": 2.59,
    "pinball_10": 8.894,
    "pinball_50": 25.783,
    "pinball_90": 19.027,
}

# ── Chart palette ───────────────────────────────────────────────────────────
COLOR_ACTUAL = "#20242B"     # what really happened
COLOR_FORECAST = "#636EFA"   # the point forecast
COLOR_BAND = "#636EFA"       # the interval, drawn at low opacity
COLOR_MISS = "#EF553B"       # an actual outside the band / a cost we paid
COLOR_ACCENT = "#00CC96"     # policy and selection marks
COLOR_WARN = "#FFA15A"       # secondary series, cautions
COLOR_MUTED = "#B6B6C4"      # context series
PLOT_TEMPLATE = "plotly_white"


def describe() -> str:
    """One block printed by the notebook's setup cell."""
    return (
        f"Module 6 demand-forecasting lab\n"
        f"  data      {WEEKLY_CSV.name} ({WEEKLY_CSV_BYTES:,} bytes, "
        f"{WEEKLY_CSV_ROWS:,} product-weeks)\n"
        f"  source    {DATASET_NAME}, UCI {DATASET_UCI_ID}, {DATASET_LICENSE}\n"
        f"  panel     {TOTAL_WEEKS} complete weeks x {TOTAL_PRODUCTS:,} products, "
        f"weekly grain\n"
        f"  split     {N_TRAIN} train weeks ({TRAIN_START} to {TRAIN_END}) / "
        f"{N_TEST} test weeks ({TEST_START} to {TEST_END})\n"
        f"  cohort    products selling in >= {COHORT_MIN_NONZERO:.0%} of TRAIN weeks "
        f"({COHORT_SIZE} products)\n"
        f"  forecast  mean of the last {WINDOW} weeks + that product's own residual "
        f"quantiles at {NOMINAL_LO:g}/{NOMINAL_HI:g}\n"
        f"  policy    order at the newsvendor quantile cu / (cu + co); "
        f"co = {CO_FRACTION:.2f} x unit price (classroom assumption)\n"
        f"  model     {MODEL_VERSION}   policy {POLICY_VERSION}   seed {SEED}"
    )


def check_named_products(names, cohort) -> str:
    """Assert every hard-coded stock code is the product we say it is.

    A stock code that has quietly drifted onto another product is the one bug
    a teaching notebook cannot survive: every number stays plausible and every
    sentence becomes false. This runs in the notebook's setup cell.
    """
    inside = set(cohort)
    expected = dict(D06_PRODUCTS)
    expected[CHRISTMAS_PRODUCT] = CHRISTMAS_PRODUCT_NAME
    expected[POLICY_LOSER] = "PAPER CHAIN KIT EMPIRE"
    problems = []
    for code, wanted in expected.items():
        actual = str(names.get(code, "<absent>")).strip()
        if actual.upper() != wanted.strip().upper():
            problems.append(f"{code}: expected {wanted!r}, found {actual!r}")
    for code in set(expected) | set(MANIFEST_PRODUCTS) | set(DEMO_PRODUCTS):
        if code not in inside:
            problems.append(f"{code} is not in the deployed cohort")
    if problems:
        raise AssertionError("Named-product check failed:\n  " + "\n  ".join(problems))
    checked = set(expected) | set(MANIFEST_PRODUCTS) | set(DEMO_PRODUCTS)
    return (f"OK - all {len(checked)} named stock codes resolve to the product "
            "they are supposed to be, and every one is in the deployed cohort.")
