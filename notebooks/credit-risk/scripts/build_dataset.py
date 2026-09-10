"""Convert the official UCI XLS into the committed ``data/accounts.parquet``.

One-time converter with documented provenance. The raw file is the official
UCI Machine Learning Repository release:

    Dataset : Default of Credit Card Clients (UCI id 350)
    Download: https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients
    License : CC BY 4.0
    File    : "default of credit card clients.xls" (5,539,328 bytes)
    SHA-256 : 30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933
    Citation: Yeh, I-C. & Lien, C-H. (2009), Expert Systems with Applications 36(2)

The XLS carries a two-row header (a generic "X1..X23" row above the real
column names) -- a small, honest data-ingestion lesson, handled here with
``header=1``. The only transformations are: verify the checksum, take the
second header row as column names, rename the target column
``default payment next month`` -> ``DEFAULT``, and write parquet. No row,
column, or value is altered, so the parquet is the XLS, byte-for-byte in
meaning.

Usage:

    python scripts/build_dataset.py "/path/to/default of credit card clients.xls"

Requires ``xlrd`` (legacy .xls reader) in the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from creditlab import config  # noqa: E402


def build(xls_path: Path) -> None:
    digest = hashlib.sha256(xls_path.read_bytes()).hexdigest()
    if digest != config.DATASET_XLS_SHA256:
        raise SystemExit(
            f"Checksum mismatch for {xls_path}.\n"
            f"  expected {config.DATASET_XLS_SHA256}\n"
            f"  found    {digest}\n"
            "Re-download the official file before converting."
        )
    print(f"SHA-256 verified: {digest}")

    accounts = pd.read_excel(xls_path, header=1)
    accounts = accounts.rename(columns={"default payment next month": config.TARGET})

    if len(accounts) != config.EXPECTED_ROWS:
        raise SystemExit(f"Expected {config.EXPECTED_ROWS:,} rows, found {len(accounts):,}.")
    if accounts.isna().any().any():
        raise SystemExit("Unexpected missing values in the official file.")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    accounts.to_parquet(config.ACCOUNTS_PARQUET, compression="zstd", index=False)

    size_mb = config.ACCOUNTS_PARQUET.stat().st_size / 1e6
    print(f"accounts.parquet : {len(accounts):,} rows x {accounts.shape[1]} columns  {size_mb:.1f} MB")
    print(
        f"default rate     : {accounts[config.TARGET].mean():.2%} "
        f"({int(accounts[config.TARGET].sum()):,} of {len(accounts):,})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xls_path", type=Path, help="Path to the official UCI XLS file")
    build(parser.parse_args().xls_path)
