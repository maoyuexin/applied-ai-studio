"""Convert raw Sparkov generator output into the two committed parquet files.

The generator is a third-party MIT project and is not vendored here. Regenerate
the raw CSVs with:

    git clone https://github.com/namebrandon/Sparkov_Data_Generation.git
    cd Sparkov_Data_Generation
    pip install "Faker>=13,<26" "numpy<2"
    python datagen.py -n 500 -seed 42 -o /tmp/sparkov_out 07-01-2024 08-31-2026

then point this script at that folder:

    python scripts/build_dataset.py /tmp/sparkov_out

Splitting the generator's single wide row into a customer table and a
transaction table is not decoration: Sparkov repeats every customer attribute on
every transaction row, so normalising it back apart is the shape the data would
really arrive in, and the join is the first thing the notebook teaches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fraudlab import config  # noqa: E402

CUSTOMER_COLUMNS = [
    "cc_num", "first", "last", "gender", "street", "city", "state", "zip",
    "lat", "long", "city_pop", "job", "dob",
]

TRANSACTION_COLUMNS = [
    "trans_num", "cc_num", "trans_date_trans_time", "unix_time", "category",
    "amt", "merchant", "merch_lat", "merch_long", "is_fraud",
]


def read_generator_output(raw_dir: Path) -> pd.DataFrame:
    files = sorted(p for p in raw_dir.glob("*.csv") if p.name != "customers.csv")
    if not files:
        raise SystemExit(f"No generator CSVs found in {raw_dir}")

    # The generator chunks by customer profile, so some chunks come out empty.
    frames = [pd.read_csv(f, sep="|", dtype={"cc_num": str, "zip": str}) for f in files]
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True)
    print(f"Read {len(files)} files ({len(frames)} non-empty) -> {len(df):,} transactions")
    return df


def build(raw_dir: Path) -> None:
    df = read_generator_output(raw_dir)

    df["trans_date_trans_time"] = pd.to_datetime(
        df["trans_date"] + " " + df["trans_time"]
    )
    df["dob"] = pd.to_datetime(df["dob"])
    df["is_fraud"] = df["is_fraud"].astype("int8")

    # The card number is the only field that looks like a real payment
    # credential. It is synthetic, but nothing in this repo should ever carry a
    # PAN-shaped column, so it becomes an opaque surrogate immediately.
    card_ids = {num: f"CARD_{i:04d}" for i, num in enumerate(sorted(df["cc_num"].unique()))}
    df["cc_num"] = df["cc_num"].map(card_ids)

    customers = (
        df[CUSTOMER_COLUMNS]
        .drop_duplicates(subset="cc_num")
        .sort_values("cc_num")
        .reset_index(drop=True)
    )

    transactions = (
        df[TRANSACTION_COLUMNS]
        .sort_values("trans_date_trans_time")
        .reset_index(drop=True)
    )

    # A chargeback lands about two months after the transaction. Storing the date
    # the label becomes trustworthy is what lets the notebook show that the most
    # recent weeks cannot be trained on.
    transactions["label_available_date"] = transactions[
        "trans_date_trans_time"
    ].dt.normalize() + pd.Timedelta(days=config.LABEL_LAG_DAYS)
    transactions["label_matured"] = (
        transactions["label_available_date"] <= config.AS_OF_DATE
    )

    for col in ("category", "merchant"):
        transactions[col] = transactions[col].astype("category")
    for col in ("gender", "state", "job", "city"):
        customers[col] = customers[col].astype("category")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers.to_parquet(config.CUSTOMERS_PARQUET, compression="zstd", index=False)
    transactions.to_parquet(config.TRANSACTIONS_PARQUET, compression="zstd", index=False)

    cust_mb = config.CUSTOMERS_PARQUET.stat().st_size / 1e6
    txn_mb = config.TRANSACTIONS_PARQUET.stat().st_size / 1e6

    print(f"customers.parquet    : {len(customers):>8,} rows  {cust_mb:>6.1f} MB")
    print(f"transactions.parquet : {len(transactions):>8,} rows  {txn_mb:>6.1f} MB")
    print(f"total                : {cust_mb + txn_mb:>21.1f} MB")
    print(
        f"fraud rate           : {transactions['is_fraud'].mean():.3%} "
        f"({int(transactions['is_fraud'].sum()):,} of {len(transactions):,})"
    )
    print(
        f"date range           : {transactions['trans_date_trans_time'].min():%Y-%m-%d} "
        f"to {transactions['trans_date_trans_time'].max():%Y-%m-%d}"
    )
    print(f"labels not matured   : {(~transactions['label_matured']).sum():,}")

    if cust_mb + txn_mb > 45:
        print("\nWARNING: over the 45 MB budget for a committed file. Shorten the window.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path, help="Folder of Sparkov generator CSVs")
    build(parser.parse_args().raw_dir)
