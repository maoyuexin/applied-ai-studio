"""Single source of truth for paths, the frozen spike decisions, and constants.

Every number a notebook cell, chart, or exported artifact quotes comes from
here, so there is one place to change it and no chance of two artifacts
disagreeing. The modeling choices (1-minute committed resolution, six
plain-language hourly features, a one-sided robust z-score centered on the
training median and scaled by MAD, the Feb-Mar training window, and the
operating threshold of 6.0) were frozen by the Module 5 technical spike and
must not drift without re-running that evidence.
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

MINUTES_PARQUET = DATA_DIR / "metropt_1min.parquet"

# ── Provenance ──────────────────────────────────────────────────────────────
DATASET_NAME = "MetroPT-3 (Air Compressor)"
DATASET_UCI_ID = 791
DATASET_URL = "https://archive.ics.uci.edu/dataset/791/metropt+3+dataset"
DATASET_DOWNLOAD = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
DATASET_LICENSE = "CC BY 4.0"
DATASET_CITATION = (
    "Veloso, B., Ribeiro, R., Gama, J. & Pereira, P. (2022). MetroPT-3 Dataset. "
    "UCI Machine Learning Repository. https://doi.org/10.24432/C5VW3R"
)
DATASET_SOURCE_FILE = "MetroPT3(AirCompressor).csv"
DATASET_CSV_BYTES = 218_300_507
DATASET_CSV_SHA256 = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
DATASET_RAW_ROWS = 1_516_948
DATASET_POPULATION = (
    "one Air Production Unit (APU) on a Metro do Porto passenger train, "
    "recorded 2020-02-01 to 2020-09-01"
)

# UCI's own page says the readings are "collected at 1Hz". They are not. The
# raw timestamps are irregular with a MEDIAN spacing of 10 s: 1,337,521 of the
# 1,516,947 gaps between consecutive rows are exactly 10 s. Never repeat the
# 1 Hz claim; it is wrong and it is a teachable provenance beat.
RAW_SAMPLING_NOTE = (
    "irregular, median 10 s between readings "
    "(1,337,521 of 1,516,947 intervals are exactly 10 s)"
)
RAW_SAMPLING_MEDIAN_SECONDS = 10
RAW_TEN_SECOND_INTERVALS = 1_337_521

# ── The committed 1-minute file ─────────────────────────────────────────────
MINUTE_SECONDS = 60
COMMITTED_COLUMNS = [
    "TP2", "TP3", "H1", "DV_pressure", "Reservoirs",
    "Oil_temperature", "Motor_current", "COMP", "LPS", "Oil_level",
]
DROPPED_COLUMNS = ["DV_eletric", "Towers", "MPG", "Pressure_switch", "Caudal_impulses"]
EXPECTED_MINUTE_ROWS = 252_720          # minutes that actually carry a reading
EXPECTED_GRID_ROWS = 306_960            # minutes between the first and last reading
EXPECTED_MISSING_MINUTES = EXPECTED_GRID_ROWS - EXPECTED_MINUTE_ROWS
RANGE_START = pd.Timestamp("2020-02-01 00:00")
RANGE_END = pd.Timestamp("2020-09-01 03:59")

SENSOR_MEANING = {
    "TP2": "Pressure measured on the compressor outlet (bar)",
    "TP3": "Pressure on the pneumatic panel that feeds the train (bar)",
    "H1": "Pressure downstream of the cyclonic separator valve (bar)",
    "DV_pressure": "Pressure dropped by the air-dryer towers when they discharge (bar)",
    "Reservoirs": "Downstream reservoir pressure (bar)",
    "Oil_temperature": "Oil temperature inside the compressor (degrees C)",
    "Motor_current": "Current drawn by the compressor motor (amperes)",
    "COMP": "Air-intake valve signal: 0 while the compressor is working",
    "LPS": "Low-pressure switch: 1 when panel pressure falls below 7 bar",
    "Oil_level": "Oil-level switch: 0 when the oil level is low",
}

# ── Ground truth: four documented air-leak failures ─────────────────────────
# Published by the dataset authors as maintenance reports, not model output.
FAILURES = [
    ("F1", "2020-04-18 00:00", "2020-04-18 23:59",
     "Air leak, compressor running almost continuously for a full day"),
    ("F2", "2020-05-29 23:30", "2020-05-30 06:00",
     "Air leak overnight, resolved the next morning"),
    ("F3", "2020-06-05 10:00", "2020-06-07 14:30",
     "The longest documented event: 52.5 hours of continuous running"),
    ("F4", "2020-07-15 14:30", "2020-07-15 19:00",
     "Short event, and the only one with real advance warning"),
]


def failure_windows() -> list[tuple[str, pd.Timestamp, pd.Timestamp, str]]:
    return [(n, pd.Timestamp(a), pd.Timestamp(b), d) for n, a, b, d in FAILURES]


# ── Motor-current regimes (amperes) ─────────────────────────────────────────
# Measured from the trimodal current histogram: a peak at ~0 (off), a peak at
# ~4 (spinning but not compressing), a peak at ~6-7 (compressing).
MOTOR_OFF_THRESHOLD = 1.0     # above this the motor is spinning at all
MOTOR_LOAD_THRESHOLD = 4.75   # above this the compressor is compressing air
FEATURE_GRAIN = "1 hour"
MIN_HOUR_COVERAGE = 0.5       # an hour needs half its minutes to be scored

# ── The six model features (order is frozen: the detector relies on it) ─────
MODEL_FEATURES = [
    "load_share", "cycles_per_hour", "rest_minutes_per_cycle",
    "oil_temp_mean", "tp3_std", "pressure_fall_rate",
]
FEATURE_DISPLAY_NAMES = {
    "load_share": "Share of the hour the compressor is working hard",
    "cycles_per_hour": "Compressor starts per hour",
    "rest_minutes_per_cycle": "Minutes of rest between working bursts",
    "oil_temp_mean": "Average oil temperature (C)",
    "tp3_std": "Swing in panel air pressure (bar)",
    "pressure_fall_rate": "How fast pressure falls while resting (bar/min)",
}
FEATURE_QUESTION = {
    "load_share": "How much of the hour was the compressor actually compressing?",
    "cycles_per_hour": "How often did it have to start up again?",
    "rest_minutes_per_cycle": "How long did it get to rest between bursts?",
    "oil_temp_mean": "Did it run hotter than usual?",
    "tp3_std": "Did panel pressure rise and fall normally, or sit pinned?",
    "pressure_fall_rate": "How fast did pressure bleed away while it rested?",
}
# +1 = higher than normal means trouble; -1 = lower than normal means trouble.
FEATURE_DIRECTION = {
    "load_share": +1,
    "cycles_per_hour": +1,
    "rest_minutes_per_cycle": -1,
    "oil_temp_mean": +1,
    "tp3_std": -1,
    "pressure_fall_rate": +1,
}

# ── Time-ordered splits (frozen before any threshold was chosen) ────────────
TRAIN_START, TRAIN_END = pd.Timestamp("2020-02-01"), pd.Timestamp("2020-04-01")
DEV_START, DEV_END = pd.Timestamp("2020-04-01"), pd.Timestamp("2020-07-01")
TEST_START, TEST_END = pd.Timestamp("2020-07-01"), pd.Timestamp("2020-09-02")
SCORED_START, SCORED_END = DEV_START, TEST_END

# ── Detector ────────────────────────────────────────────────────────────────
MODEL_TYPE = "one_sided_robust_z"
MAD_CONSTANT = 1.4826         # makes MAD comparable to a standard deviation
RANDOM_STATE = 42

# ── Operating policy ────────────────────────────────────────────────────────
THRESHOLD = 6.0               # frozen on Apr-Jun, never tuned on Jul-Sep
WATCH_THRESHOLD = 3.0
MERGE_GAP_HOURS = 6           # alerts this close together are one technician trip
PRE_CREDIT_HOURS = 24         # an alert this far ahead still counts as catching it
POST_WINDOW_HOURS = 6         # failure window extended past its documented end
AMBIGUOUS_PRE_HOURS = 72      # hours excluded from false-alarm accounting
AMBIGUOUS_POST_HOURS = 24

ROUTE_WORK_ORDER = "work_order"
ROUTE_WATCH = "watch"
ROUTE_NO_ACTION = "no_action"
ROUTES = {
    ROUTE_WORK_ORDER: "score >= 6.0 - raise a maintenance work order; a technician inspects within 4 hours",
    ROUTE_WATCH: "3.0 <= score < 6.0 - watch: log it to the shift report, no callout",
    ROUTE_NO_ACTION: "score < 3.0 - no action",
}
THRESHOLD_SWEEP = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12]

CLAIM_BOUNDARY = (
    "the system detects a developing fault; it does not forecast, "
    "and it never locks out equipment"
)
CLAIM_BOUNDARY_LONG = (
    "Detects a developing air leak within roughly one hour of onset and raises a work "
    "order for a person to act on. It does NOT forecast failures days or weeks ahead: "
    "real advance warning was found for 1 of the 4 documented failures. Evaluation is "
    "anecdotal - four events cannot support a confidence interval. The system never "
    "locks out equipment and never certifies a machine as safe to work on."
)
RECALIBRATION = (
    "Review the baseline with a human every month; refit if any feature's monthly median "
    "moves more than one training standard deviation. NOT an automatic rolling window - "
    "measured, a rolling baseline absorbs a slowly developing fault."
)

# ── SYNTHETIC classroom costs (US dollars) ──────────────────────────────────
# Anchored on the published fact that APU faults caused Metro do Porto to cancel
# 170+ trips in 2017. They are NOT that organization's actual figures and are
# labeled synthetic everywhere they appear.
COSTS = {
    "callout_usd": 400,               # one technician visit: 2 h at a $200/h loaded rate
    "technician_hours_per_callout": 2.0,
    "fault_usd_per_hour": 1_200,      # wasted energy and accelerated wear while a leak runs
    "service_interruption_usd": 22_000,  # charged once if a fault runs unaddressed past 12 h
    "interruption_after_hours": 12,
    "response_hours": 4.0,            # alert -> technician on site
}

# ── Demo samples ────────────────────────────────────────────────────────────
SAMPLE_COUNT = 8

# ── Presentation (palette shared with the fraud, credit and complaint labs) ─
COLOR_FAILURE = "#EF553B"   # documented failures / risk-raising
COLOR_NORMAL = "#636EFA"    # healthy operation
COLOR_ACCENT = "#00CC96"    # policy and selection marks
COLOR_WARN = "#FFA15A"      # watch band, secondary series
COLOR_MUTED = "#B6B6C4"     # context series
PLOT_TEMPLATE = "plotly_white"


def describe() -> str:
    """One-paragraph summary of the configuration, for the notebook header."""
    return (
        f"Dataset      : {DATASET_NAME} (UCI id {DATASET_UCI_ID}, {DATASET_LICENSE})\n"
        f"Population   : {DATASET_POPULATION}\n"
        f"Committed    : 1-minute means, {len(COMMITTED_COLUMNS)} sensors, float32 zstd parquet\n"
        f"Features     : {len(MODEL_FEATURES)} hourly features, {FEATURE_GRAIN} grain\n"
        f"Split        : train {TRAIN_START.date()}..{(TRAIN_END - pd.Timedelta(days=1)).date()} | "
        f"threshold chosen {DEV_START.date()}..{(DEV_END - pd.Timedelta(days=1)).date()} | "
        f"test {TEST_START.date()}..{TEST_END.date()} scored once\n"
        f"Model        : {MODEL_TYPE} (median center, MAD x {MAD_CONSTANT} scale), mean of "
        f"{len(MODEL_FEATURES)}\n"
        f"Policy       : work order at score >= {THRESHOLD}, watch from {WATCH_THRESHOLD}; "
        f"costs are synthetic classroom assumptions"
    )
