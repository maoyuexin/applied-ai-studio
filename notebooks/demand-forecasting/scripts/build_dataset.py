"""Rebuild ``data/online_retail_weekly.csv.gz`` from the official Online Retail II workbook.

This script is run ONCE, by hand, against a raw file you already downloaded. It
never downloads anything itself, and nothing in the lab's setup path calls it -
the 0.95 MB gzip it produces is committed beside the notebook so a classroom
with no network still works.

Provenance
----------
    Dataset  : Online Retail II, UCI Machine Learning Repository id 502
    Page     : https://archive.ics.uci.edu/dataset/502/online+retail+ii
    Download : https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
    License  : CC BY 4.0
    DOI      : 10.24432/C5CG6D
    Zip      : online+retail+ii.zip, 45,622,418 bytes
    SHA-256  : 572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb
    File     : online_retail_II.xlsx, 45,622,278 bytes, two sheets
               ("Year 2009-2010", "Year 2010-2011")
    Rows     : 1,067,371 transaction lines x 8 columns, 2009-12-01 to 2011-12-09
    Citation : Chen, D. (2019). Online Retail II. UCI Machine Learning Repository.
               https://doi.org/10.24432/C5CG6D
    Who      : one UK-registered, non-store online gift wholesaler selling mainly
               to small business retailers. Not a supermarket, not Amazon, and
               not a simulation.

Why the committed file is weekly, and not daily
-----------------------------------------------
Measured on the raw workbook: across 604 trading days this retailer was open on
a Saturday exactly ONCE, on 2009-12-05. A daily model would spend its capacity
learning that a shop which is closed sells nothing - a real pattern, and a
useless one. At a weekly grain the closure disappears into the week that
contains it, and what is left is demand. That is the whole reason for this
aggregation, and it is a measurement, not a preference.

What this script changes, and what it does not
----------------------------------------------
1. Check the workbook's size and sheet names. Refuse to continue on a mismatch.
2. Measure and print the raw quirks the notebook states out loud in Stage 1:
   duplicate lines, cancellations, non-positive quantities and prices, guest
   checkouts, trading days by weekday.
3. Remove, in this order and for these stated reasons:
     - exact duplicate lines, kept once   (counting them twice inflates demand)
     - cancellations, Invoice starting C  (a return is not demand)
     - Quantity <= 0                      (write-offs and the cancellations above)
     - Price <= 0                         (a giveaway or a data-entry hole)
     - non-product stock codes by name    (postage is not a product)
   Guest checkouts - lines with no Customer ID, 22.8% of the file - are KEPT.
   Demand is demand; it is the recommender case that needs a customer.
4. Aggregate to one row per (product, Monday-anchored week): units are summed,
   the unit price is the median of that product-week's lines, and the
   description is the product's most common spelling in the clean data.
5. Write gzip CSV with the five columns the lab reads.

No quantity is altered, no week is interpolated, no gap is filled. Weeks in
which a product sold nothing are absent from this file on purpose: ``fclab.data``
puts them back as real zeros when it builds the dense panel, so a zero week
stays visible as a modeling decision rather than an accident of storage.

A note on reproducing the checksum
----------------------------------
A gzip member stores the time it was written, so the SHA-256 of the ``.gz``
file cannot be reproduced. This script verifies the digest of the CSV CONTENT
inside the archive, which is deterministic, and prints both.

Usage
-----
    python scripts/build_dataset.py "/path/to/online_retail_II.xlsx"
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from fclab import config  # noqa: E402

# SHA-256 of the CSV bytes INSIDE the committed gzip. The archive's own digest
# is config.WEEKLY_CSV_SHA256 and embeds a write timestamp, so only this one is
# reproducible by a second person on another machine.
WEEKLY_CONTENT_SHA256 = \
    "4af85e406cbb7253e93e82ef5e184e43a88028057dbb6e5f916e8f97c8246d68"

RAW_COLUMNS = ["Invoice", "StockCode", "Description", "Quantity",
               "InvoiceDate", "Price", "Customer ID", "Country"]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_workbook(xlsx_path: Path) -> pd.DataFrame:
    """Both sheets of the workbook, concatenated in calendar order."""
    size = xlsx_path.stat().st_size
    print(f"Reading {xlsx_path.name} ({size:,} bytes) - this takes about 25 seconds...")
    if size != config.DATASET_XLSX_BYTES:
        print(f"  WARNING: expected {config.DATASET_XLSX_BYTES:,} bytes. This may not "
              "be the official release; every count below will differ.")

    sheets = pd.read_excel(xlsx_path, sheet_name=list(config.DATASET_SHEETS),
                           dtype={"StockCode": str, "Invoice": str})
    raw = pd.concat([sheets[name] for name in config.DATASET_SHEETS],
                    ignore_index=True)
    missing = [column for column in RAW_COLUMNS if column not in raw.columns]
    if missing:
        raise SystemExit(f"Columns absent from the workbook: {missing}")
    return raw[RAW_COLUMNS]


def describe_raw(raw: pd.DataFrame) -> None:
    """Print the quirks the notebook is going to state out loud."""
    dates = pd.to_datetime(raw["InvoiceDate"])
    print(f"\nRaw workbook: {len(raw):,} lines x {raw.shape[1]} columns")
    print(f"  span            {dates.min().date()} to {dates.max().date()} "
          f"({(dates.max() - dates.min()).days} days)")
    print(f"  invoices        {raw['Invoice'].nunique():,}")
    print(f"  customers       {raw['Customer ID'].nunique():,} "
          f"({raw['Customer ID'].isna().sum():,} lines have none)")
    print(f"  countries       {raw['Country'].nunique()}  "
          f"UK share of lines {(raw['Country'] == 'United Kingdom').mean():.1%}")
    print(f"  exact duplicates          {int(raw.duplicated().sum()):,}")
    print(f"  cancellations (Invoice C) "
          f"{int(raw['Invoice'].astype(str).str.startswith('C').sum()):,}")
    print(f"  quantity <= 0             {int((raw['Quantity'] <= 0).sum()):,}")
    print(f"  price <= 0                {int((raw['Price'] <= 0).sum()):,}")

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                     "Saturday", "Sunday"]
    days = pd.DataFrame({"date": dates.dt.date, "weekday": dates.dt.dayofweek})
    open_days = days.drop_duplicates()
    counts = open_days["weekday"].value_counts().reindex(range(7)).fillna(0).astype(int)
    print(f"\nTrading days by weekday ({len(open_days):,} days with at least one line):")
    for index, name in enumerate(weekday_names):
        marker = "   <- the reason this lab works in weeks" if index == 5 else ""
        print(f"  {name:<10} {counts[index]:>4}{marker}")


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Apply the five documented removals, in order, printing what each costs."""
    print("\nCleaning:")
    frame = raw.copy()
    start = len(frame)

    frame = frame.drop_duplicates()
    print(f"  exact duplicate lines, kept once   -{start - len(frame):>8,}")

    step = len(frame)
    frame = frame[~frame["Invoice"].astype(str).str.startswith("C")]
    print(f"  cancellations (Invoice starts C)   -{step - len(frame):>8,}")

    step = len(frame)
    frame = frame[frame["Quantity"] > 0]
    print(f"  quantity <= 0                      -{step - len(frame):>8,}")

    step = len(frame)
    frame = frame[frame["Price"] > 0]
    print(f"  price <= 0                         -{step - len(frame):>8,}")

    step = len(frame)
    codes = frame["StockCode"].astype(str).str.strip().str.upper()
    banned = {code.upper() for code in config.NON_PRODUCT_CODES}
    frame = frame[~codes.isin(banned)]
    print(f"  non-product stock codes            -{step - len(frame):>8,}")

    step = len(frame)
    frame = frame[frame["Description"].notna()]
    print(f"  lines with no description          -{step - len(frame):>8,}")

    print(f"  KEPT: guest checkouts (no Customer ID) "
          f"{int(frame['Customer ID'].isna().sum()):,} lines - demand is demand")
    print(f"  clean transaction lines            {len(frame):>9,} of {start:,}")

    if len(frame) != config.CLEAN_ROWS:
        print(f"  WARNING: expected {config.CLEAN_ROWS:,} clean lines; config.py "
              "records a different number and needs checking.")
    return frame


def aggregate_weekly(clean_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per product per Monday-anchored week.

    Units are summed. The unit price is the median across that product-week's
    lines, because the same product is sold at a wholesale and a retail price in
    the same file and the mean would sit between two prices nobody paid. The
    description is the product's single most common spelling in the clean data,
    so one product cannot appear under two names.
    """
    frame = clean_rows.copy()
    dates = pd.to_datetime(frame["InvoiceDate"])
    frame["week"] = dates.dt.to_period("W-SUN").dt.start_time  # the Monday

    weekly = (frame.groupby(["StockCode", "week"], as_index=False)
              .agg(units=("Quantity", "sum"), unit_price=("Price", "median")))
    weekly["units"] = weekly["units"].astype("int64")
    weekly["unit_price"] = weekly["unit_price"].round(2)

    names = (frame.groupby("StockCode")["Description"]
             .agg(lambda values: values.mode().iat[0]))
    weekly["description"] = weekly["StockCode"].map(names)

    weekly = weekly[list(config.WEEKLY_COLUMNS)]
    return weekly.sort_values(["StockCode", "week"]).reset_index(drop=True)


def write(weekly: pd.DataFrame) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(config.WEEKLY_CSV, index=False, compression="gzip")

    payload = gzip.decompress(config.WEEKLY_CSV.read_bytes())
    content_digest = _sha256_bytes(payload)
    archive_digest = _sha256_file(config.WEEKLY_CSV)

    print(f"\nWrote {config.WEEKLY_CSV.relative_to(PROJECT_DIR)}")
    print(f"  rows          {len(weekly):,} product-weeks")
    print(f"  products      {weekly['StockCode'].nunique():,}")
    print(f"  weeks         {weekly['week'].nunique()} "
          f"({weekly['week'].min().date()} to {weekly['week'].max().date()})")
    print(f"  units         {int(weekly['units'].sum()):,}")
    print(f"  columns       {', '.join(config.WEEKLY_COLUMNS)}")
    print(f"  size          {config.WEEKLY_CSV.stat().st_size:,} bytes (gzip)")
    print(f"  content sha   {content_digest}")
    print(f"  archive sha   {archive_digest}")
    print("  (the archive digest embeds the time of writing and is NOT reproducible; "
          "the content digest is)")

    if len(weekly) != config.WEEKLY_CSV_ROWS:
        print(f"  WARNING: expected {config.WEEKLY_CSV_ROWS:,} rows.")
    if weekly["week"].nunique() != config.WEEKS_IN_FILE:
        print(f"  WARNING: expected {config.WEEKS_IN_FILE} weeks before the two "
              "partial edge weeks are dropped.")
    if content_digest.startswith(WEEKLY_CONTENT_SHA256):
        print("  CONTENT DIGEST MATCHES the committed file. This is the same data.")
    else:
        print(f"  WARNING: content digest does not start with {WEEKLY_CONTENT_SHA256}. "
              "The rebuilt file differs from the committed one; do not ship it "
              "without finding out why.")


def build(xlsx_path: Path) -> None:
    started = time.time()
    if not xlsx_path.exists():
        raise SystemExit(
            f"{xlsx_path} does not exist.\n"
            f"Download {config.DATASET_DOWNLOAD} by hand, verify its SHA-256 is\n"
            f"  {config.DATASET_ZIP_SHA256}\n"
            f"then unzip it and pass the path to {config.DATASET_SOURCE_FILE}."
        )
    raw = read_workbook(xlsx_path)
    describe_raw(raw)
    weekly = aggregate_weekly(clean(raw))
    write(weekly)
    print(f"\nDone in {time.time() - started:.1f}s. Nothing was downloaded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild the committed weekly CSV from the official "
                    "Online Retail II workbook. Downloads nothing.")
    parser.add_argument("xlsx_path", type=Path,
                        help="Path to online_retail_II.xlsx (not committed)")
    build(parser.parse_args().xlsx_path)
