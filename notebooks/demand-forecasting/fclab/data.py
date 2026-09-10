"""Load the committed weekly file and turn it into the dense demand panel.

One row of the committed CSV is **one product in one week**: how many units of
that product left the warehouse that week, with the product's median unit price
carried alongside. The panel is that same information as a rectangle -
one row per product, one column per week, a zero where nothing sold - because a
forecaster needs to see the weeks in which nothing happened.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from . import config


def load_weekly() -> pd.DataFrame:
    """Read the committed weekly CSV. Nothing downloads."""
    weekly = pd.read_csv(config.WEEKLY_CSV, dtype={"StockCode": str})
    weekly["week"] = pd.to_datetime(weekly["week"])
    return weekly


def file_digest() -> str:
    digest = hashlib.sha256()
    with config.WEEKLY_CSV.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def provenance_summary(weekly: pd.DataFrame) -> pd.DataFrame:
    """The facts a second person needs to prove they have the same data."""
    size = config.WEEKLY_CSV.stat().st_size
    rows = [
        ("Dataset", f"{config.DATASET_NAME} (UCI {config.DATASET_UCI_ID})"),
        ("Who is being measured", config.DATASET_POPULATION),
        ("License", f"{config.DATASET_LICENSE}, DOI {config.DATASET_DOI}"),
        ("Source workbook", f"{config.DATASET_SOURCE_FILE} "
                            f"({config.DATASET_XLSX_BYTES:,} bytes, not committed)"),
        ("Committed file", f"{config.WEEKLY_CSV.name} ({size:,} bytes)"),
        ("Committed SHA-256", file_digest()[:32] + "..."),
        ("Rows in the committed file", f"{len(weekly):,} product-weeks"),
        ("Products", f"{weekly['StockCode'].nunique():,}"),
        ("Weeks", f"{weekly['week'].nunique()} "
                  f"({weekly['week'].min().date()} to {weekly['week'].max().date()})"),
        ("Transaction lines behind it", f"{config.CLEAN_ROWS:,} of "
                                        f"{config.RAW_ROWS:,} raw lines"),
        ("Units sold in total", f"{int(weekly['units'].sum()):,}"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def quirks_table() -> pd.DataFrame:
    """What was in the raw workbook that a spreadsheet view would hide.

    Every count here was measured by ``scripts/build_dataset.py`` on the raw
    workbook; the shares are of the 1,067,371 raw transaction lines.
    """
    raw = config.RAW_ROWS
    rows = [
        ("Cancelled lines (invoice starts with C)", config.CANCELLATION_ROWS,
         "Removed. A return is not demand; counting it would forecast the refund."),
        ("Exact duplicate lines", config.DUPLICATE_ROWS,
         "Kept once. Counting them twice would inflate demand by roughly 3%."),
        ("Lines with quantity <= 0", config.NONPOSITIVE_QUANTITY_ROWS,
         "Removed. Mostly the cancellations above, plus stock write-offs."),
        ("Lines with price <= 0", config.NONPOSITIVE_PRICE_ROWS,
         "Removed. A zero price is a giveaway or a data-entry hole, not a sale."),
        ("Lines with no Customer ID (guest checkout)", config.GUEST_ROWS,
         f"Kept. {config.GUEST_SHARE:.0%} of lines. Demand is demand; the "
         "recommender case is the one that needs a customer."),
        ("Lines on non-product stock codes", None,
         "Removed by name: POST, DOT, M, C2, D, PADS, ADJUST, BANK CHARGES, "
         "TEST001/2. Postage is not a product."),
    ]
    table = []
    for what, count, note in rows:
        table.append({
            "What": what,
            "Raw lines": f"{count:,}" if count is not None else "see note",
            "Share of raw lines": f"{count / raw:.2%}" if count is not None else "-",
            "What we did and why": note,
        })
    frame = pd.DataFrame(table)
    return frame[["What", "Raw lines", "Share of raw lines", "What we did and why"]]


def trading_days_frame() -> pd.DataFrame:
    """Open trading days by weekday - the reason this lab works in weeks."""
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
    counts = [config.TRADING_DAYS_BY_WEEKDAY[day] for day in order]
    return pd.DataFrame({"weekday": order, "trading_days": counts})


def weekly_totals(weekly: pd.DataFrame) -> pd.DataFrame:
    """Catalog-wide units per week, with the two partial edge weeks flagged."""
    totals = weekly.groupby("week", as_index=False)["units"].sum()
    edges = {totals["week"].min(), totals["week"].max()}
    totals["edge_week"] = totals["week"].isin(edges)
    return totals


def build_panel(weekly: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Dense product x week panel of units, plus the name and price lookups.

    The first and last weeks are dropped: the source window begins on a Tuesday
    and ends on a Friday, so those two weeks are partial and would read as a
    demand collapse the model has to explain. 104 weeks become 102.
    """
    weeks = np.sort(weekly["week"].unique())
    kept = weeks[1:-1] if config.DROP_EDGE_WEEKS else weeks
    inside = weekly[weekly["week"].isin(kept)]

    panel = (inside.pivot_table(index="StockCode", columns="week", values="units",
                                aggfunc="sum")
             .reindex(columns=kept).fillna(0.0))
    names = inside.groupby("StockCode")["description"].agg(lambda s: s.mode().iat[0])
    prices = inside.groupby("StockCode")["unit_price"].median()
    return panel, names, prices


def split_columns(panel: pd.DataFrame) -> tuple[pd.Index, pd.Index]:
    """Chronological 76/26 split. No shuffling, ever, on a time series."""
    return panel.columns[: config.N_TRAIN], panel.columns[config.N_TRAIN:]


def panel_summary(panel: pd.DataFrame) -> pd.DataFrame:
    train, test = split_columns(panel)
    filled = int((panel.values > 0).sum())
    cells = panel.size
    rows = [
        ("Panel shape", f"{panel.shape[0]:,} products x {panel.shape[1]} weeks"),
        ("Cells in the panel", f"{cells:,} product-weeks"),
        ("Cells with a sale", f"{filled:,} ({filled / cells:.1%})"),
        ("Cells that are a real zero", f"{cells - filled:,} "
                                       f"({1 - filled / cells:.1%})"),
        ("Train window", f"{len(train)} weeks, {train[0].date()} to {train[-1].date()}"),
        ("Test window", f"{len(test)} weeks, {test[0].date()} to {test[-1].date()}"),
        ("Units in train", f"{int(panel[train].values.sum()):,}"),
        ("Units in test", f"{int(panel[test].values.sum()):,}"),
    ]
    return pd.DataFrame(rows, columns=["Fact", "Value"])


def product_weeks(panel: pd.DataFrame, code: str, names: pd.Series,
                  start: int = 0, n: int = 8) -> pd.DataFrame:
    """A few real weeks of one product, for reading a row out loud."""
    row = panel.loc[code].iloc[start:start + n]
    return pd.DataFrame({
        "week": [w.date() for w in row.index],
        "units": row.values.astype(int),
        "product": names.get(code, ""),
    })
