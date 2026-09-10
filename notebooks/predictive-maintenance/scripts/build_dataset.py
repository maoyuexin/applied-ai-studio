"""Rebuild ``data/metropt_1min.parquet`` from the official MetroPT-3 CSV.

This script is run ONCE, by hand, against a raw file you already downloaded.
It never downloads anything itself, and nothing in the lab's setup path calls
it - the 4.9 MB parquet it produces is committed beside the notebook so a
classroom with no network still works.

Provenance
----------
    Dataset  : MetroPT-3 (Air Compressor), UCI Machine Learning Repository id 791
    Page     : https://archive.ics.uci.edu/dataset/791/metropt+3+dataset
    Download : https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip
    License  : CC BY 4.0
    File     : MetroPT3(AirCompressor).csv, 218,300,507 bytes
    SHA-256  : db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24
    Rows     : 1,516,948 readings x 17 columns, 2020-02-01 to 2020-09-01
    Citation : Veloso, B., Ribeiro, R., Gama, J. & Pereira, P. (2022). MetroPT-3
               Dataset. UCI Machine Learning Repository.
               https://doi.org/10.24432/C5VW3R
    Equipment: the Air Production Unit (APU) of one Metro do Porto passenger
               train - a real compressor on a real vehicle, not a simulation.

A correction we are obliged to make
-----------------------------------
The UCI page states the readings were "collected at 1Hz". **They were not.**
Measured on the raw timestamps in this file: the spacing between consecutive
readings is irregular with a MEDIAN of 10 seconds, and 1,337,521 of the
1,516,947 intervals are exactly 10 seconds. At a true 1 Hz the seven-month
span would hold roughly 18 million rows, not 1.5 million. This script prints
the measured interval distribution so the correction is reproducible rather
than asserted, and no teaching material in this lab repeats the 1 Hz claim.

What this script changes, and what it does not
----------------------------------------------
1. Verify the SHA-256 of the raw CSV. Refuse to continue on a mismatch.
2. Measure and print the true sampling interval and the recorder gaps.
3. Resample to 1-minute means on a regular grid. This is a MEASURED choice,
   not a convenience: at 1 minute the hourly features reproduce their
   10-second values at correlation >= 0.95 on 10 of 11 features, while at
   5 minutes the compressor's duty cycle is aliased away (starts per hour
   collapse from 2.70 to 0.18).
4. Keep the 10 sensors the lab uses and drop 5 the model never reads
   (DV_eletric, Towers, MPG, Pressure_switch, Caudal_impulses).
5. Store as float32 with zstd compression, and drop minutes that carry no
   reading at all - the loader puts them back as NaN, so a recorder gap stays
   visible instead of quietly closing.

No value is altered, no row is interpolated, no gap is filled.

Usage
-----
    python scripts/build_dataset.py "/path/to/MetroPT3(AirCompressor).csv"
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pdmlab import config  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build(csv_path: Path, skip_checksum: bool = False) -> None:
    if not skip_checksum:
        print(f"Checksumming {csv_path.name} ({csv_path.stat().st_size:,} bytes)...")
        digest = _sha256(csv_path)
        if digest != config.DATASET_CSV_SHA256:
            raise SystemExit(
                f"Checksum mismatch for {csv_path}.\n"
                f"  expected {config.DATASET_CSV_SHA256}\n"
                f"  found    {digest}\n"
                "Re-download the official file before converting."
            )
        print(f"SHA-256 verified: {digest}")

    started = time.time()
    raw = pd.read_csv(csv_path, index_col=0, parse_dates=["timestamp"])
    print(f"Read {len(raw):,} rows x {raw.shape[1]} columns in {time.time() - started:.1f}s")
    if len(raw) != config.DATASET_RAW_ROWS:
        raise SystemExit(f"Expected {config.DATASET_RAW_ROWS:,} raw rows, found {len(raw):,}.")

    raw = raw.set_index("timestamp").sort_index()
    if raw.index.duplicated().any():
        raise SystemExit("Duplicate raw timestamps - the file is not the official release.")

    # --- The sampling-rate correction, measured on this file -----------------
    spacing = raw.index.to_series().diff().dt.total_seconds()
    exactly_ten = int((spacing == 10).sum())
    print("\nMeasured sampling interval (seconds between consecutive readings):")
    print(f"  median            {spacing.median():.0f}")
    print(f"  exactly 10 s      {exactly_ten:,} of {int(spacing.notna().sum()):,} intervals")
    print(f"  25th / 75th pct   {spacing.quantile(0.25):.0f} / {spacing.quantile(0.75):.0f}")
    print("  UCI's page says 1 Hz. It is not 1 Hz. Do not repeat that claim.")

    gaps = spacing[spacing > 60]
    print(f"\nRecorder gaps longer than one minute: {len(gaps):,}, "
          f"totalling {gaps.sum() / 3600:,.1f} hours")
    print("  five largest, in hours:",
          ", ".join(f"{v / 3600:.1f}" for v in gaps.sort_values(ascending=False).head(5)))

    # --- Resample and trim ---------------------------------------------------
    minutes = raw.resample("1min").mean()
    print(f"\n1-minute grid: {len(minutes):,} minutes, "
          f"{int(minutes['TP2'].isna().sum()):,} of them with no reading")

    missing = [c for c in config.COMMITTED_COLUMNS if c not in minutes.columns]
    if missing:
        raise SystemExit(f"Columns absent from the raw file: {missing}")
    kept = minutes[config.COMMITTED_COLUMNS].astype("float32").dropna(how="all")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    kept.to_parquet(config.MINUTES_PARQUET, compression="zstd")
    size_mb = config.MINUTES_PARQUET.stat().st_size / 1e6

    print(f"\nWrote {config.MINUTES_PARQUET.relative_to(PROJECT_DIR)}")
    print(f"  rows      {len(kept):,} (minutes carrying at least one reading)")
    print(f"  columns   {len(config.COMMITTED_COLUMNS)}  kept: {', '.join(config.COMMITTED_COLUMNS)}")
    print(f"  dropped   {', '.join(config.DROPPED_COLUMNS)}")
    print(f"  range     {kept.index.min()} -> {kept.index.max()}")
    print(f"  size      {size_mb:.2f} MB (float32, zstd)")
    if len(kept) != config.EXPECTED_MINUTE_ROWS:
        print(f"  WARNING: expected {config.EXPECTED_MINUTE_ROWS:,} rows; config.py needs updating.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild the committed 1-minute parquet from the official MetroPT-3 CSV."
    )
    parser.add_argument("csv_path", type=Path, help="Path to MetroPT3(AirCompressor).csv")
    parser.add_argument("--skip-checksum", action="store_true",
                        help="Skip the SHA-256 check (for a knowingly modified copy).")
    arguments = parser.parse_args()
    build(arguments.csv_path, arguments.skip_checksum)
