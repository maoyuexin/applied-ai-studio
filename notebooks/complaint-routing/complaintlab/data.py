"""Load the committed complaint splits and describe where they came from.

The three parquets were produced once by ``scripts/build_dataset.py`` from the
official CFPB bulk file: filter to narratives received on or after 2023-01-01,
map product labels onto eight teams, drop exact-duplicate narratives, cap the
dominant class, then split 70/15/15 stratified by team with seed 42.

Splitting happened in the build script, not here, because the dedupe that makes
the split honest can only be done on the full window. What the notebook loads is
therefore already the frozen split, and no cell can accidentally reshuffle it.
"""

from __future__ import annotations

import pandas as pd

from . import config


def load_splits() -> dict[str, pd.DataFrame]:
    """Read the three committed parquets and check they are the documented files."""
    splits = {
        "train": pd.read_parquet(config.TRAIN_PARQUET),
        "validation": pd.read_parquet(config.VAL_PARQUET),
        "test": pd.read_parquet(config.TEST_PARQUET),
    }
    for name, part in splits.items():
        expected = config.EXPECTED_SPLIT_ROWS[name]
        if len(part) != expected:
            raise ValueError(f"{name}: expected {expected:,} complaints, found {len(part):,}.")
        if part[config.TEXT_COLUMN].isna().any() or (part[config.TEXT_COLUMN] == "").any():
            raise ValueError(f"{name}: every row must carry a narrative.")
        if sorted(part[config.TARGET].unique()) != config.TEAMS:
            raise ValueError(f"{name}: teams do not match the documented eight.")
    all_ids = pd.concat([part["complaint_id"] for part in splits.values()])
    if all_ids.duplicated().any():
        raise ValueError("A complaint id appears in more than one split.")
    return splits


def provenance_summary(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The provenance facts shown at the top of the notebook."""
    total = sum(len(part) for part in splits.values())
    rows = [
        ("Publisher", config.DATASET_PUBLISHER),
        ("Database", config.DATASET_NAME),
        ("Bulk file", config.DATASET_BULK_URL),
        ("Bulk file size", config.DATASET_BULK_SIZE),
        ("Retrieved", config.DATASET_RETRIEVED),
        ("Rights", config.DATASET_LICENSE),
        ("Rows in the source file", f"{config.SOURCE_ROWS_SCANNED:,}"),
        (
            "Rows carrying a narrative",
            f"{config.SOURCE_ROWS_WITH_NARRATIVE:,} "
            f"({config.SOURCE_ROWS_WITH_NARRATIVE / config.SOURCE_ROWS_SCANNED:.1%} - opt-in)",
        ),
        (
            f"Narratives received {config.DATE_WINDOW_START} or later",
            f"{config.SOURCE_NARRATIVE_ROWS_IN_WINDOW:,}",
        ),
        ("Committed here", f"{total:,} complaints across 3 files"),
        ("One row means", config.DATASET_ROW_MEANING),
        ("Personal details", config.NARRATIVE_NOTE),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Verified value"])


def split_summary(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Complaints, teams, date range, and median length per split."""
    rows = []
    for name, part in splits.items():
        lengths = part[config.TEXT_COLUMN].str.len()
        rows.append(
            {
                "Split": name,
                "Complaints": len(part),
                "Share of sample": len(part) / sum(len(p) for p in splits.values()),
                "Teams": part[config.TARGET].nunique(),
                "Earliest": part["date_received"].min(),
                "Latest": part["date_received"].max(),
                "Median characters": int(lengths.median()),
            }
        )
    return pd.DataFrame(rows)


def team_counts(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Complaints per team per split, in the frozen team order."""
    frame = pd.DataFrame(
        {
            name: part[config.TARGET].value_counts().reindex(config.TEAMS)
            for name, part in splits.items()
        }
    )
    frame.index.name = "Team"
    frame["total"] = frame.sum(axis=1)
    frame["share of sample"] = frame["total"] / frame["total"].sum()
    return frame.reset_index()


def label_consolidation_table(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """CFPB product names collapsed into teams, with rows kept per label.

    Counted from the committed sample, so students can verify the mapping
    against data they can open. The dropped-product counts come from
    ``config.DROPPED_PRODUCTS`` because those rows were never sampled.
    """
    combined = pd.concat(splits.values())
    counted = (
        combined.groupby([config.TARGET, "product_original"])
        .size()
        .rename("complaints in the sample")
        .reset_index()
        .rename(columns={config.TARGET: "Team", "product_original": "CFPB product label"})
    )
    counted = counted.sort_values(
        ["Team", "complaints in the sample"], ascending=[True, False]
    ).reset_index(drop=True)
    dropped = pd.DataFrame(
        [
            {
                "Team": "(dropped, no team owns it)",
                "CFPB product label": label,
                "complaints in the sample": 0,
            }
            for label in config.DROPPED_PRODUCTS
        ]
    )
    return pd.concat([counted, dropped], ignore_index=True)


def dedupe_summary() -> pd.DataFrame:
    """The template-letter discovery, as measured on the full 2023+ window."""
    rows = [
        ("Mapped complaints in the window", f"{config.DEDUPE_ROWS_IN_WINDOW:,}"),
        ("Distinct narratives among them", f"{config.DEDUPE_DISTINCT_NARRATIVES:,}"),
        (
            "Narratives filed more than once",
            f"{config.DEDUPE_NARRATIVES_WITH_COPIES:,}",
        ),
        (
            "Rows removed as exact copies",
            f"{config.DEDUPE_ROWS_REMOVED:,} ({config.DEDUPE_SHARE_REMOVED:.1%})",
        ),
        (
            "Largest single template",
            f"{config.DEDUPE_TOP_TEMPLATE_COPIES[0]:,} identical filings",
        ),
        ("Rule applied before splitting", config.DEDUPE_RULE),
    ]
    return pd.DataFrame(rows, columns=["Measured on the 2023+ window", "Value"])


def leakage_cost() -> pd.DataFrame:
    """What the first, un-deduped build reported and what it was really worth."""
    rows = [
        (
            "Test narratives that also appeared verbatim in training",
            f"{config.LEAKAGE_TEST_ROWS_SEEN_IN_TRAIN:.1%}",
        ),
        (
            "Test accuracy the leaky build reported",
            f"{config.LEAKAGE_INFLATED_TEST_ACCURACY:.1%}",
        ),
        (
            "Test accuracy on rows the model had not already seen",
            f"{config.LEAKAGE_HONEST_TEST_ACCURACY:.1%}",
        ),
        (
            "Accuracy the duplicates invented",
            f"{config.LEAKAGE_INFLATION_POINTS:.1f} percentage points",
        ),
    ]
    return pd.DataFrame(rows, columns=["Leakage check", "Value"])


def duplicate_example_table() -> pd.DataFrame:
    """Two filings of one template letter, side by side."""
    filings = config.DUPLICATE_EXAMPLE["filings"]
    narrative = config.DUPLICATE_EXAMPLE["narrative"]
    return pd.DataFrame(
        [
            {
                "Complaint ID": filing["complaint_id"],
                "Date received": filing["date_received"],
                "State": filing["state"],
                "First 90 characters of the narrative": narrative[:90] + " ...",
                "Characters": len(narrative),
            }
            for filing in filings
        ]
    )
