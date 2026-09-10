"""Rebuild ``data/interactions.parquet`` from the official Online Retail II workbook.

This script is run ONCE, by hand, against a raw file you already downloaded. It
never downloads anything itself, and nothing in the lab's setup path calls it -
the ~3.2 MB parquet it produces is committed beside the notebook so a classroom
with no network still works.

Provenance
----------
    Dataset  : Online Retail II, UCI Machine Learning Repository id 502
    Page     : https://archive.ics.uci.edu/dataset/502/online+retail+ii
    Download : https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
    License  : CC BY 4.0
    File     : online_retail_II.xlsx, 45,622,278 bytes, two sheets
    Rows     : 1,067,371 invoice lines, 2009-12-01 to 2011-12-09
    Citation : Chen, D. (2019). Online Retail II. UCI Machine Learning Repository.
               https://doi.org/10.24432/C5CG6D
    Business : one UK-registered, non-store online retailer selling mostly
               giftware, largely to wholesale buyers. Real transactions, not a
               simulation.

The same workbook feeds the Module 6 demand-forecasting lab. That lab asks
"how many units will we sell next week?" and aggregates to a weekly panel per
product. This lab asks "which products should we show this shopper?" and keeps
the customer column instead. Same rows, different question, different file.

What this script changes, and what it does not
----------------------------------------------
1. Verify the SHA-256 of the raw workbook. Warn loudly on a mismatch.
2. Apply the five cleaning rules the Module 6 spike froze, counting every row
   each rule removes so the ledger is reproducible rather than asserted:
       a. drop credit notes - invoices whose number starts with "C"
       b. drop non-positive Quantity and non-positive Price
       c. drop rows with no Description
       d. drop non-product stock codes (postage, bank charges, test rows, ...)
       e. drop exact duplicate rows
   StockCode is cast to str and stripped FIRST. The raw column holds a mix of
   integers and strings; sorting it raises TypeError, and the whitespace
   variants would otherwise split one product into two.
3. Collapse repeated lines for the same product on the same invoice into one
   row, summing quantity. One committed row then means exactly one product on
   one basket.
4. Keep the five columns this lab reads and drop the rest. Descriptions go to
   a separate 4,904-row table because they are a property of the product, not
   of the purchase.

No value is invented, no row is imputed, no gap is filled.

Usage
-----
    python scripts/build_dataset.py "/path/to/online_retail_II.xlsx"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from reclab import config  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_workbook(path: Path) -> pd.DataFrame:
    """Both sheets, concatenated, with the column names the file ships with."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    frames = [frame for frame in sheets.values()]
    raw = pd.concat(frames, ignore_index=True)
    raw.columns = [str(name).strip() for name in raw.columns]
    return raw


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """The five frozen cleaning rules, each one counted."""
    frame = raw.copy()
    # Cast BEFORE anything else: the raw column mixes int and str, and any sort
    # or set operation over the mixture raises TypeError on Python 3.
    frame["StockCode"] = frame["StockCode"].astype(str).str.strip()
    frame["Invoice"] = frame["Invoice"].astype(str).str.strip()
    frame["Description"] = frame["Description"].astype("object")

    ledger: list[dict] = [{"step": "raw invoice lines in the workbook",
                           "removed": 0, "remaining": len(frame)}]

    def drop(mask: pd.Series, label: str) -> None:
        nonlocal frame
        removed = int(mask.sum())
        frame = frame[~mask].copy()
        ledger.append({"step": label, "removed": removed, "remaining": len(frame)})

    drop(frame["Invoice"].str.upper().str.startswith("C"),
         'credit notes (Invoice starts with "C") - returns, not purchases')
    drop((frame["Quantity"] <= 0) | (frame["Price"] <= 0),
         "non-positive quantity or price - adjustments, not purchases")
    drop(frame["Description"].isna(),
         "rows with no product description")
    drop(frame["StockCode"].str.upper().isin(config.NON_PRODUCT_CODES),
         "non-product stock codes (postage, bank charges, samples, test rows)")

    before = len(frame)
    frame = frame.drop_duplicates()
    ledger.append({"step": "exact duplicate rows", "removed": before - len(frame),
                   "remaining": len(frame)})
    return frame, ledger


def collapse(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per (invoice, product): the committed grain."""
    frame = frame.copy()
    frame["invoice_ts"] = pd.to_datetime(frame["InvoiceDate"])
    frame["revenue"] = frame["Quantity"] * frame["Price"]
    lines = (
        frame.groupby(["Invoice", "StockCode"], as_index=False)
        .agg(revenue=("revenue", "sum"),
             invoice_ts=("invoice_ts", "min"),
             customer_id=("Customer ID", "first"))
        .sort_values(["invoice_ts", "Invoice", "StockCode"])
        .reset_index(drop=True)
    )
    return pd.DataFrame({
        "invoice": lines["Invoice"].astype(str),
        "stock_code": lines["StockCode"].astype(str),
        "invoice_ts": lines["invoice_ts"].astype("datetime64[s]"),
        "customer_id": lines["customer_id"].astype("Int32"),
        "revenue": np.round(lines["revenue"], 2).astype("float32"),
    })


def descriptions(frame: pd.DataFrame) -> pd.DataFrame:
    """One description per product: the most frequent spelling wins."""
    counted = (
        frame.assign(description=frame["Description"].astype(str).str.strip())
        .groupby(["StockCode", "description"], as_index=False)
        .size()
        .sort_values(["StockCode", "size"], ascending=[True, False])
        .drop_duplicates("StockCode")
    )
    return pd.DataFrame({
        "stock_code": counted["StockCode"].astype(str),
        "description": counted["description"].astype(str),
    }).sort_values("stock_code").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="path to online_retail_II.xlsx")
    args = parser.parse_args()

    if not args.workbook.exists():
        raise SystemExit(f"{args.workbook} does not exist.")

    started = time.time()
    print(f"Reading {args.workbook} ({args.workbook.stat().st_size / 1e6:.1f} MB) ...")
    digest = sha256(args.workbook)
    print(f"  SHA-256 : {digest}")
    if digest != config.DATASET_SHA256:
        print(f"  WARNING : expected {config.DATASET_SHA256}. "
              "This is a different file; the committed numbers will not reproduce.")
    else:
        print("  SHA-256 matches the file the lab was built from.")

    raw = read_workbook(args.workbook)
    print(f"  {len(raw):,} raw invoice lines x {raw.shape[1]} columns "
          f"({time.time() - started:.0f} s to parse)")

    frame, ledger = clean(raw)
    print("\nCleaning ledger")
    print(pd.DataFrame(ledger).to_string(index=False))

    lines = collapse(frame)
    catalog = descriptions(frame)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines.to_parquet(config.INTERACTIONS_PARQUET, index=False,
                     compression="zstd", compression_level=19)
    catalog.to_parquet(config.DESCRIPTIONS_PARQUET, index=False,
                       compression="zstd", compression_level=19)

    ledger_payload = {
        "dataset": config.DATASET_NAME,
        "uci_id": config.DATASET_UCI_ID,
        "license": config.DATASET_LICENSE,
        "citation": config.DATASET_CITATION,
        "source_file": args.workbook.name,
        "source_bytes": args.workbook.stat().st_size,
        "source_sha256": digest,
        "raw_rows": int(len(raw)),
        "clean_rows": int(len(frame)),
        "committed_rows": int(len(lines)),
        "committed_grain": "one product on one invoice",
        "products": int(lines["stock_code"].nunique()),
        "baskets": int(lines["invoice"].nunique()),
        "registered_customers": int(lines["customer_id"].nunique()),
        "guest_rows": int(lines["customer_id"].isna().sum()),
        "first_invoice": str(lines["invoice_ts"].min()),
        "last_invoice": str(lines["invoice_ts"].max()),
        "steps": ledger,
    }
    config.CLEANING_LEDGER.write_text(json.dumps(ledger_payload, indent=2) + "\n")

    print(f"\nWrote {config.INTERACTIONS_PARQUET.relative_to(PROJECT_DIR)}  "
          f"({config.INTERACTIONS_PARQUET.stat().st_size / 1e6:.2f} MB, {len(lines):,} rows)")
    print(f"Wrote {config.DESCRIPTIONS_PARQUET.relative_to(PROJECT_DIR)}  "
          f"({config.DESCRIPTIONS_PARQUET.stat().st_size / 1e6:.2f} MB, {len(catalog):,} products)")
    print(f"Wrote {config.CLEANING_LEDGER.relative_to(PROJECT_DIR)}")
    print(f"\n{len(lines):,} rows | {ledger_payload['baskets']:,} baskets | "
          f"{ledger_payload['products']:,} products | "
          f"{ledger_payload['registered_customers']:,} registered customers | "
          f"{ledger_payload['guest_rows']:,} guest rows")
    print(f"Done in {time.time() - started:.0f} s.")


if __name__ == "__main__":
    main()
