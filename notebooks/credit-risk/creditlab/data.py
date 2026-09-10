"""Load the committed account snapshot and produce the frozen three-way split."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from . import config, features


def load_accounts() -> pd.DataFrame:
    """Read the committed parquet and check it is the file we documented."""
    df = pd.read_parquet(config.ACCOUNTS_PARQUET)
    if len(df) != config.EXPECTED_ROWS:
        raise ValueError(f"Expected {config.EXPECTED_ROWS:,} accounts, found {len(df):,}.")
    if df.isna().any().any():
        raise ValueError("The committed dataset should contain no missing values.")
    if df["ID"].duplicated().any():
        raise ValueError("Account IDs must be unique (one row = one customer).")
    if round(float(df[config.TARGET].mean()), 4) != config.EXPECTED_DEFAULT_RATE:
        raise ValueError("Default rate does not match the documented 22.12%.")
    return df


def provenance_summary(df: pd.DataFrame) -> pd.DataFrame:
    """The provenance facts shown at the top of the notebook."""
    rows = [
        ("Source", f"{config.DATASET_NAME} (UCI id {config.DATASET_UCI_ID})"),
        ("Download", config.DATASET_URL),
        ("License", config.DATASET_LICENSE),
        ("Original file", f"{config.DATASET_SOURCE_FILE} (converted to parquet, values unchanged)"),
        ("SHA-256 of original XLS", config.DATASET_XLS_SHA256),
        ("Accounts", f"{len(df):,} (one row = one customer)"),
        ("Fields", f"{df.shape[1]} (ID + 23 features + {config.TARGET})"),
        ("Missing values", str(int(df.isna().sum().sum()))),
        ("Missed October 2005 payment", f"{int(df[config.TARGET].sum()):,} ({df[config.TARGET].mean():.1%})"),
        ("Citation", config.DATASET_CITATION),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Verified value"])


def split_accounts(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Stratified 60/20/20 split, frozen by the spike (seed 42, two stages).

    Undocumented category codes are consolidated first, exactly as the spike
    did, so every downstream number matches the frozen evidence. One row = one
    customer = one entity, so a row-level split has no entity leakage.
    """
    prepared = features.consolidate_codes(df)
    train_df, rest_df = train_test_split(
        prepared,
        test_size=config.VALIDATION_FRACTION + config.TEST_FRACTION,
        stratify=prepared[config.TARGET],
        random_state=config.RANDOM_STATE,
    )
    val_df, test_df = train_test_split(
        rest_df,
        test_size=0.5,
        stratify=rest_df[config.TARGET],
        random_state=config.RANDOM_STATE,
    )
    return {"train": train_df, "validation": val_df, "test": test_df}


def split_summary(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Accounts and default rate per split, for the stage 2 table."""
    rows = []
    for name, part in splits.items():
        rows.append(
            {
                "Split": name,
                "Accounts": len(part),
                "Missed next payment": int(part[config.TARGET].sum()),
                "Default rate": float(part[config.TARGET].mean()),
            }
        )
    return pd.DataFrame(rows)


def age_band(ages: pd.Series) -> pd.Series:
    """Group AGE into decade bands for the audit tables (display only)."""
    return pd.cut(
        ages,
        bins=config.AGE_BAND_EDGES,
        labels=config.AGE_BAND_LABELS,
        right=False,
    )
