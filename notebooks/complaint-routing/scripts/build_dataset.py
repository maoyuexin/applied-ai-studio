"""Rebuild the committed complaint splits from the official CFPB bulk file.

PROVENANCE
==========

    Database : CFPB Consumer Complaint Database
    Publisher: Consumer Financial Protection Bureau, a US federal agency
    Home     : https://www.consumerfinance.gov/data-research/consumer-complaints/
    Bulk file: https://files.consumerfinance.gov/ccdb/complaints.csv.zip
    Retrieved: 2026-09-01
    Size     : 1.42 GB zip / 9.2 GB CSV / 17,456,743 rows / 16 columns
    Rights   : US Government public data. No copyright; free to use and redistribute.
    Narrative: opt-in. The consumer must consent to publication, and the CFPB
               scrubs personal details before publishing, replacing them with
               runs of "XXXX". 3,846,323 rows (22.0%) carry one.

THIS SCRIPT NEVER DOWNLOADS ANYTHING. The 1.42 GB bulk file is not fetched at
setup, in class, or on import. Running the script with no arguments only checks
the parquets that are already committed beside the notebook. Rebuilding requires
you to download the bulk file yourself and pass its path.

WHAT THE REBUILD DOES (frozen by the Module 4 spike; changing any step
invalidates the numbers the notebook prints)
==========================================================================

1. Stream the zipped CSV in 500,000-row chunks so the 9.2 GB file is never
   loaded whole. Keep only rows with a non-empty narrative.
2. Keep complaints received on or after 2023-01-01. Product labels were renamed
   in 2023 and volume roughly quadrupled between 2022 and 2025, so older rows
   describe a different mix of companies, products, and consumer language.
   2,640,147 rows survive this filter.
3. Map the CFPB ``Product`` label onto one of eight specialist teams
   (``complaintlab.config.TEAM_MAP``). The same complaints appear under two
   credit-reporting spellings and three credit-card spellings because the
   agency renamed categories over the years; consolidating them is the point.
   "Debt or credit management" (5,545 rows) maps to no team and is dropped: it
   is a small 2023 category whose complaints read as a mix of the other eight.
4. DEDUPE BEFORE SPLITTING, and only before splitting:
   ``drop_duplicates(subset="narrative", keep="first")``.
   41.5% of the mapped rows in the window (1,093,131 of 2,634,602) are exact
   copies of an earlier narrative, because credit-repair services file the same
   template letter for thousands of consumers. The first build of this dataset
   skipped this step: 17.0% of its test narratives appeared verbatim in
   training, and the reported test accuracy was 84.3% where the honest number
   was 81.9%. Deduping after splitting does not fix that - the copies have to
   be gone before the split is drawn.
5. Cap Credit reporting at 1.5x the second-largest team, then scale every team
   proportionally to a total of at most 58,000 with a 2,000-row floor. Only
   Student loans reaches the floor. Without the cap, credit reporting is 4.8x
   debt collection and 31x student loans, and the smaller teams never get
   enough examples to learn from. This is a disclosed classroom display choice,
   not the real-world mix.
6. Split 70/15/15 stratified by team with ``random_state=42``, in two stages
   (70/30, then 50/50), and write three zstd parquets.

Result: 58,185 complaints - 40,729 train / 8,728 validation / 8,728 test,
about 25 MB of parquet.

USAGE
=====

    # verify what is committed (no network, no bulk file)
    python scripts/build_dataset.py

    # rebuild from a bulk file you downloaded yourself
    python scripts/build_dataset.py /path/to/complaints.csv.zip

Rebuilding against a newer bulk file will NOT reproduce the committed rows: the
CFPB adds hundreds of thousands of complaints a month, so the sampled ids and
every downstream metric will shift. The committed parquets are the frozen
evidence the notebook and its exported artifacts refer to.
"""

from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaintlab import config, data  # noqa: E402

CHUNK_ROWS = 500_000
SOURCE_COLUMNS = [
    "Complaint ID",
    "Date received",
    "Product",
    "Issue",
    "Consumer complaint narrative",
    "State",
    "Company response to consumer",
    "Timely response?",
]
COLUMN_RENAMES = {
    "Complaint ID": "complaint_id",
    "Date received": "date_received",
    "Product": "product_original",
    "Issue": "issue",
    "Consumer complaint narrative": "narrative",
    "State": "state",
    "Company response to consumer": "company_response",
    "Timely response?": "timely_response",
}
OUTPUT_COLUMNS = [
    "complaint_id",
    "date_received",
    "team",
    "product_original",
    "issue",
    "narrative",
    "state",
    "company_response",
    "timely_response",
]
TARGET_TOTAL_MAX = 58_000


def verify_committed() -> None:
    """Default action: check the committed parquets, download nothing."""
    splits = data.load_splits()
    print(config.describe())
    print()
    print(data.provenance_summary(splits).to_string(index=False))
    print()
    print(data.split_summary(splits).to_string(index=False))
    for name, path in (
        ("train", config.TRAIN_PARQUET),
        ("validation", config.VAL_PARQUET),
        ("test", config.TEST_PARQUET),
    ):
        print(f"  {name:<11} {path.name:<26} {path.stat().st_size / 1e6:5.1f} MB")
    print("\nCommitted splits verified. Nothing was downloaded.")


def stream_window(zip_path: Path) -> pd.DataFrame:
    """Step 1-2: stream the zipped CSV and keep in-window narrative rows."""
    start = time.perf_counter()
    kept: list[pd.DataFrame] = []
    scanned = 0
    with zipfile.ZipFile(zip_path) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            reader = pd.read_csv(
                handle, chunksize=CHUNK_ROWS, dtype=str, usecols=SOURCE_COLUMNS
            )
            for chunk in reader:
                scanned += len(chunk)
                narrative = chunk["Consumer complaint narrative"]
                chunk = chunk[narrative.notna() & (narrative.str.strip() != "")]
                chunk = chunk[chunk["Date received"] >= config.DATE_WINDOW_START]
                if len(chunk):
                    kept.append(chunk)
                print(f"\r  scanned {scanned:,} rows", end="", flush=True)
    window = pd.concat(kept, ignore_index=True)
    print(
        f"\n  {scanned:,} rows scanned in {time.perf_counter() - start:.0f}s; "
        f"{len(window):,} in-window narrative rows"
    )
    return window


def consolidate_and_dedupe(window: pd.DataFrame) -> pd.DataFrame:
    """Steps 3-4: map labels onto teams, drop unmapped rows, then dedupe."""
    window = window.copy()
    window["team"] = window["Product"].map(config.TEAM_MAP)
    dropped = window[window["team"].isna()]["Product"].value_counts().to_dict()
    mapped = window.dropna(subset=["team"])
    print(f"  dropped, no team owns them: {dropped}")

    before = len(mapped)
    deduped = mapped.drop_duplicates(subset="Consumer complaint narrative", keep="first")
    removed = before - len(deduped)
    print(
        f"  exact-duplicate narratives removed: {removed:,} of {before:,} "
        f"({removed / before:.1%}) - template letters"
    )
    return deduped


def sample_and_split(deduped: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Steps 5-6: cap the dominant team, sample, and split 70/15/15."""
    counts = deduped["team"].value_counts()
    second_largest = counts.drop("Credit reporting").max()
    cap = int(second_largest * config.CREDIT_REPORTING_CAP_MULTIPLE)
    plan = {
        team: (min(count, cap) if team == "Credit reporting" else count)
        for team, count in counts.items()
    }
    total = sum(plan.values())
    if total > TARGET_TOTAL_MAX:
        scale = TARGET_TOTAL_MAX / total
        plan = {
            team: max(config.SAMPLE_FLOOR_PER_TEAM, int(count * scale))
            if count * scale < count
            else count
            for team, count in plan.items()
        }
        plan = {team: min(plan[team], counts[team]) for team in plan}
    print(f"  credit-reporting cap: {cap:,};  sample plan: {plan}")

    parts = [
        group.sample(n=plan[team], random_state=config.RANDOM_STATE)
        if plan[team] < len(group)
        else group
        for team, group in deduped.groupby("team")
    ]
    sample = (
        pd.concat(parts)
        .sample(frac=1.0, random_state=config.RANDOM_STATE)
        .reset_index(drop=True)
        .rename(columns=COLUMN_RENAMES)[OUTPUT_COLUMNS]
    )

    train, rest = train_test_split(
        sample,
        test_size=0.30,
        random_state=config.RANDOM_STATE,
        stratify=sample[config.TARGET],
    )
    validation, test = train_test_split(
        rest,
        test_size=0.50,
        random_state=config.RANDOM_STATE,
        stratify=rest[config.TARGET],
    )
    return {"train": train, "validation": validation, "test": test}


def rebuild(zip_path: Path) -> None:
    if not zip_path.exists():
        raise SystemExit(f"No such file: {zip_path}")
    print(f"Streaming {zip_path} in {CHUNK_ROWS:,}-row chunks (nothing is downloaded)...")
    window = stream_window(zip_path)
    deduped = consolidate_and_dedupe(window)
    splits = sample_and_split(deduped)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "train": config.TRAIN_PARQUET,
        "validation": config.VAL_PARQUET,
        "test": config.TEST_PARQUET,
    }
    for name, part in splits.items():
        path = paths[name]
        part.reset_index(drop=True).to_parquet(path, compression="zstd", index=False)
        print(f"  {path.name:<26} {len(part):>7,} complaints  {path.stat().st_size / 1e6:5.1f} MB")
    overlap = set(splits["train"]["narrative"]) & set(splits["test"]["narrative"])
    print(f"  narratives shared verbatim between train and test: {len(overlap)}")
    print("\nRebuilt. Re-run scripts/build_embeddings.py so the embeddings match these rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify the committed complaint splits, or rebuild them from a local bulk file.",
    )
    parser.add_argument(
        "bulk_zip",
        type=Path,
        nargs="?",
        help="Path to a complaints.csv.zip you downloaded yourself. Omit to verify only.",
    )
    arguments = parser.parse_args()
    if arguments.bulk_zip is None:
        verify_committed()
    else:
        rebuild(arguments.bulk_zip)
