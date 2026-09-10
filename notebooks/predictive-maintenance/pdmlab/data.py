"""Load the committed 1-minute sensor file and describe what is in it.

The committed parquet stores only the minutes that actually carry a reading.
``load_minutes`` puts those readings back onto a regular 1-minute grid, so a
recorder gap shows up as rows of ``NaN`` instead of silently disappearing.
That matters: 904 hours of this seven-month record are missing, and a gap that
closes itself would make the machine look like it was running normally through
a period where nothing was measured at all.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def load_minutes() -> pd.DataFrame:
    """Read the committed parquet, validate it, and return the regular grid."""
    frame = pd.read_parquet(config.MINUTES_PARQUET)
    if len(frame) != config.EXPECTED_MINUTE_ROWS:
        raise ValueError(
            f"Expected {config.EXPECTED_MINUTE_ROWS:,} recorded minutes, found {len(frame):,}."
        )
    if list(frame.columns) != config.COMMITTED_COLUMNS:
        raise ValueError("Committed columns do not match the documented list.")
    frame.index = pd.to_datetime(frame.index)
    if frame.index.has_duplicates:
        raise ValueError("Duplicate minute timestamps in the committed file.")
    # float32 on disk keeps the file at 4.9 MB; float64 in memory keeps the
    # arithmetic below identical to the frozen spike.
    grid = frame.astype("float64").asfreq("1min")
    if len(grid) != config.EXPECTED_GRID_ROWS:
        raise ValueError(
            f"Expected a {config.EXPECTED_GRID_ROWS:,}-minute grid, built {len(grid):,}."
        )
    return grid


def provenance_summary(minutes: pd.DataFrame) -> pd.DataFrame:
    """The provenance facts shown at the top of the notebook."""
    recorded = int(minutes["Motor_current"].notna().sum())
    rows = [
        ("Source", f"{config.DATASET_NAME}, UCI Machine Learning Repository id {config.DATASET_UCI_ID}"),
        ("Download", config.DATASET_URL),
        ("License", config.DATASET_LICENSE),
        ("Original file", f"{config.DATASET_SOURCE_FILE} ({config.DATASET_CSV_BYTES / 1e6:.0f} MB, not committed)"),
        ("SHA-256 of original CSV", config.DATASET_CSV_SHA256),
        ("Raw readings", f"{config.DATASET_RAW_ROWS:,}"),
        ("Raw sampling", config.RAW_SAMPLING_NOTE),
        ("Equipment", config.DATASET_POPULATION),
        ("Committed file", f"1-minute means, {len(config.COMMITTED_COLUMNS)} sensors, float32 zstd parquet"),
        ("Minutes with a reading", f"{recorded:,}"),
        ("Minutes in the full grid", f"{len(minutes):,}"),
        ("Ground truth", f"{len(config.FAILURES)} documented air-leak failures from maintenance reports"),
        ("Citation", config.DATASET_CITATION),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Verified value"])


def sensor_dictionary() -> pd.DataFrame:
    """One row per committed sensor, in plain language."""
    return pd.DataFrame(
        [{"Column": name, "What it measures": meaning}
         for name, meaning in config.SENSOR_MEANING.items()]
    )


def failure_table() -> pd.DataFrame:
    """The four documented failures, with durations."""
    rows = []
    for name, start, end, note in config.failure_windows():
        rows.append({
            "Failure": name,
            "Documented start": str(start),
            "Documented end": str(end),
            "Hours": round((end - start).total_seconds() / 3600, 1),
            "Report": note,
        })
    return pd.DataFrame(rows)


# ── Missingness ─────────────────────────────────────────────────────────────

def hourly_coverage(minutes: pd.DataFrame) -> pd.Series:
    """Share of each clock hour that carries a sensor reading. Denominator: 60."""
    return minutes["Motor_current"].resample("1h").count() / 60.0


def coverage_summary(minutes: pd.DataFrame) -> pd.DataFrame:
    """How much of the record is missing, and how it is distributed."""
    coverage = hourly_coverage(minutes)
    total_hours = len(coverage)
    empty = int((coverage == 0).sum())
    thin = int(((coverage > 0) & (coverage < config.MIN_HOUR_COVERAGE)).sum())
    usable = int((coverage >= config.MIN_HOUR_COVERAGE).sum())
    missing_minutes = int(minutes["Motor_current"].isna().sum())
    rows = [
        ("Clock hours in the record", f"{total_hours:,}"),
        ("Hours with no reading at all", f"{empty:,} ({empty / total_hours:.1%})"),
        ("Hours under 50% covered (dropped)", f"{thin:,} ({thin / total_hours:.1%})"),
        ("Hours we can score", f"{usable:,} ({usable / total_hours:.1%})"),
        ("Missing minutes", f"{missing_minutes:,} ({missing_minutes / len(minutes):.1%})"),
        ("Missing hours, equivalent", f"{missing_minutes / 60:,.0f}"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def largest_gaps(minutes: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """The longest stretches with no reading at all."""
    missing = minutes["Motor_current"].isna()
    group = (missing != missing.shift()).cumsum()
    runs = missing.groupby(group)
    rows = []
    for _, run in runs:
        if not run.iloc[0]:
            continue
        rows.append({
            "Gap starts": str(run.index[0]),
            "Gap ends": str(run.index[-1]),
            "Hours missing": round(len(run) / 60, 1),
        })
    frame = pd.DataFrame(rows).sort_values("Hours missing", ascending=False)
    return frame.head(top).reset_index(drop=True)


def pre_onset_coverage(minutes: pd.DataFrame) -> pd.DataFrame:
    """Hours of data present in the 24 hours before each documented onset.

    This is the caveat that has to sit under every lead-time number: the one
    window where advance warning was found is also the emptiest.
    """
    coverage = hourly_coverage(minutes)
    rows = []
    for name, start, _end, _note in config.failure_windows():
        window = coverage[(coverage.index >= start - pd.Timedelta(hours=24)) & (coverage.index < start)]
        present = int((window >= config.MIN_HOUR_COVERAGE).sum())
        rows.append({
            "Failure": name,
            "Onset": str(start),
            "Hours with data (of 24)": present,
            "Share covered": round(present / 24, 2),
        })
    return pd.DataFrame(rows)


def one_hour_of_minutes(minutes: pd.DataFrame, start: str, hours: int = 6) -> pd.DataFrame:
    """A readable slice of raw minutes, for 'what does one row mean'."""
    begin = pd.Timestamp(start)
    return minutes.loc[begin:begin + pd.Timedelta(hours=hours) - pd.Timedelta(minutes=1)]


def split_windows() -> pd.DataFrame:
    """The three time-ordered windows, with which failures land in each."""
    windows = [
        ("train", config.TRAIN_START, config.TRAIN_END,
         "Fit the baseline. No failure is documented here."),
        ("threshold selection", config.DEV_START, config.DEV_END,
         "Choose the operating threshold. F1, F2, F3 live here."),
        ("held-out test", config.TEST_START, config.TEST_END,
         "Scored once, after everything above was frozen. F4 only."),
    ]
    rows = []
    for name, start, end, purpose in windows:
        inside = [n for n, a, _b, _d in config.failure_windows() if start <= a < end]
        rows.append({
            "Window": name,
            "From": str(start.date()),
            "To": str(end.date()),
            "Documented failures": ", ".join(inside) if inside else "none",
            "Purpose": purpose,
        })
    return pd.DataFrame(rows)


def daily_coverage_frame(minutes: pd.DataFrame) -> pd.DataFrame:
    """Per-day recorded-minute share, for the coverage chart. Denominator: 1,440."""
    counts = minutes["Motor_current"].resample("1D").count()
    return pd.DataFrame({"date": counts.index, "share_recorded": (counts / 1440.0).to_numpy()})


def motor_current_histogram(minutes: pd.DataFrame, bins: int = 90) -> pd.DataFrame:
    """Aggregated motor-current distribution: counts per 0.1 A bin."""
    values = minutes["Motor_current"].dropna().to_numpy()
    counts, edges = np.histogram(values, bins=bins, range=(0, 9))
    centers = (edges[:-1] + edges[1:]) / 2
    return pd.DataFrame({"amperes": centers, "minutes": counts})


def gap_facts(minutes: pd.DataFrame) -> dict:
    """Counts used in the coverage chart title and in evaluation.json."""
    missing = minutes["Motor_current"].isna()
    group = (missing != missing.shift()).cumsum()
    runs = [len(run) for _key, run in missing.groupby(group) if run.iloc[0]]
    return {
        "calendar_hours": int(len(minutes) / 60),
        "gap_count": int(len(runs)),
        "missing_hours": round(sum(runs) / 60, 1),
        "missing_share": round(sum(runs) / len(minutes), 4),
        "longest_gap_hours": round(max(runs) / 60, 1) if runs else 0.0,
    }
