"""Three ways to put a band around a forecast, measured against each other.

The deployed method (A) is ten lines of numpy. The comparisons are here so the
choice is argued rather than asserted:

    A  empirical residual quantiles - this product's own past errors
    B  quantile gradient boosting   - one fitted model per quantile
    C  split conformal              - a distribution-free half-width

Coverage is the comparison that decides it. A method that promises an 80% band
and delivers 75% is not a better model; it is a worse promise.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config, metrics

QUANTILES = (config.NOMINAL_LO, 0.5, config.NOMINAL_HI)


def _score(name: str, actual, low, median, high, fit_seconds: float,
           note: str = "") -> dict:
    """Clip at zero, keep the three quantiles in order, then measure."""
    low = np.maximum(low, 0.0)
    high = np.maximum(high, low)
    median = np.clip(median, low, high)
    return {
        "method": name,
        "coverage": metrics.coverage(actual, low, high),
        "median_band": float(np.median(high - low)),
        "pinball_10": metrics.pinball(actual, low, 0.1),
        "pinball_50": metrics.pinball(actual, median, 0.5),
        "pinball_90": metrics.pinball(actual, high, 0.9),
        "MAE_of_median": metrics.mae(actual, median),
        "fit_seconds": round(fit_seconds, 3),
        "note": note,
    }


def per_product_residual_quantiles(design: dict, point_column: str,
                                   label: str) -> tuple[dict, dict]:
    """Method A: each product's own residual percentiles added to its forecast."""
    features = design["features"]
    index = features.index(point_column)
    started = time.time()
    residuals = design["y_train"] - design["x_train"][:, index]
    products = design["product_train"]
    n_products = len(design["cohort"])
    table = np.array([np.quantile(residuals[products == p], QUANTILES)
                      for p in range(n_products)])
    elapsed = time.time() - started
    forecast = design["x_test"][:, index]
    rows = design["product_test"]
    parts = {"low": forecast + table[rows, 0], "median": forecast + table[rows, 1],
             "high": forecast + table[rows, 2]}
    return (_score(label, design["y_test"], parts["low"], parts["median"],
                   parts["high"], elapsed), parts)


def pooled_residual_quantiles(design: dict, point_column: str, label: str) -> dict:
    """Method A, pooled: one set of percentiles for the whole cohort."""
    index = design["features"].index(point_column)
    started = time.time()
    residuals = design["y_train"] - design["x_train"][:, index]
    low, median, high = np.quantile(residuals, QUANTILES)
    elapsed = time.time() - started
    forecast = design["x_test"][:, index]
    return _score(label, design["y_test"], forecast + low, forecast + median,
                  forecast + high, elapsed,
                  "one band shape for 469 different products")


def gradient_boosting_quantiles(design: dict) -> tuple[list[dict], dict]:
    """Method B: HistGradientBoostingRegressor, one fit per quantile.

    Three separate models, so nothing forces q10 <= q50 <= q90 and nothing tells
    any of them that units cannot be negative. Both defects are measured below.
    """
    predictions, seconds = {}, 0.0
    for quantile in QUANTILES:
        started = time.time()
        model = HistGradientBoostingRegressor(
            loss="quantile", quantile=quantile, max_iter=300, learning_rate=0.06,
            max_depth=6, min_samples_leaf=40, random_state=config.SEED)
        model.fit(design["x_train"], design["y_train"])
        predictions[quantile] = model.predict(design["x_test"])
        seconds += time.time() - started

    raw = np.column_stack([predictions[q] for q in QUANTILES])
    ordered = np.sort(raw, axis=1)
    rows = [
        _score("B1 - gradient boosting, as fitted", design["y_test"],
               raw[:, 0], raw[:, 1], raw[:, 2], seconds,
               "quantiles can cross; predictions can be negative"),
        _score("B2 - gradient boosting, sorted and clipped", design["y_test"],
               ordered[:, 0], ordered[:, 1], ordered[:, 2], seconds,
               "both defects repaired in two lines"),
    ]
    return rows, {"raw": raw, "sorted": ordered, "fit_seconds": seconds}


def gradient_boosting_defects(boosted: dict) -> pd.DataFrame:
    """What the fitted booster does that a demand model must not do."""
    raw = boosted["raw"]
    total = len(raw)
    crossing = (raw[:, 2] < raw[:, 1]) | (raw[:, 1] < raw[:, 0])
    negative_low = raw[:, 0] < 0
    negative_median = raw[:, 1] < 0
    rows = [
        ("Rows where the quantiles cross (q90 < q50 or q50 < q10)",
         int(crossing.sum()), f"{crossing.mean():.2%}",
         f"Worst crossing {float(np.max(np.maximum(raw[:, 1] - raw[:, 2], raw[:, 0] - raw[:, 1]))):.2f} "
         "units. Fixed by sorting the three numbers per row."),
        ("Rows where the lower edge is NEGATIVE demand",
         int(negative_low.sum()), f"{negative_low.mean():.2%}",
         f"Floor {raw[:, 0].min():.1f} units. The model has no idea units cannot "
         "be negative."),
        ("Rows where the MIDDLE forecast is negative",
         int(negative_median.sum()), f"{negative_median.mean():.2%}",
         f"Floor {raw[:, 1].min():.1f} units. Clipping at zero is a modeling "
         "assumption you must state."),
    ]
    return pd.DataFrame(rows, columns=["Defect", "Rows", "Share of 12,194 rows",
                                       "What it means"])


def split_conformal(design: dict, point_column: str = "ma8") -> list[dict]:
    """Method C: a half-width calibrated on held-back training weeks.

    C1 gives every product the same half-width. C2 divides each residual by that
    product's own typical error first, so a volatile product gets a wider band.
    """
    index = design["features"].index(point_column)
    x_train, y_train, t_train = design["x_train"], design["y_train"], design["t_train"]
    forecast = design["x_test"][:, index]
    n_products = len(design["cohort"])
    alpha = 1 - config.NOMINAL_COVERAGE

    weeks = np.unique(t_train)
    cut = weeks[int(len(weeks) * 0.7)]
    fit_mask, calibrate_mask = t_train < cut, t_train >= cut

    started = time.time()
    absolute = np.abs(y_train[calibrate_mask] - x_train[calibrate_mask, index])
    rank = min(int(np.ceil((absolute.size + 1) * (1 - alpha))) - 1, absolute.size - 1)
    half_width = np.sort(absolute)[rank]
    global_seconds = time.time() - started

    started = time.time()
    fit_errors = np.abs(y_train[fit_mask] - x_train[fit_mask, index])
    fit_products = design["product_train"][fit_mask]
    scale = np.array([max(1.0, fit_errors[fit_products == p].mean())
                      for p in range(n_products)])
    calibrate_products = design["product_train"][calibrate_mask]
    scaled = absolute / scale[calibrate_products]
    rank = min(int(np.ceil((scaled.size + 1) * (1 - alpha))) - 1, scaled.size - 1)
    normalized = np.sort(scaled)[rank]
    width = normalized * scale[design["product_test"]]
    local_seconds = time.time() - started

    return [
        _score("C1 - split conformal, one width for everyone", design["y_test"],
               forecast - half_width, forecast, forecast + half_width,
               global_seconds, f"half-width {half_width:.1f} units for all 469 products"),
        _score("C2 - split conformal, scaled per product", design["y_test"],
               forecast - width, forecast, forecast + width, local_seconds,
               f"scale factor {normalized:.2f} x each product's own mean error"),
    ]


def comparison_table(design: dict) -> tuple[pd.DataFrame, dict]:
    """Every interval method on the same held-out weeks, with fit times."""
    rows = []
    deployed, deployed_parts = per_product_residual_quantiles(
        design, "ma8", "A3 - residual quantiles on MA8, per product (DEPLOYED)")
    naive_a, _ = per_product_residual_quantiles(
        design, "lag1", "A1 - residual quantiles on last week, per product")
    rows.append(naive_a)
    rows.append(pooled_residual_quantiles(design, "lag1",
                                          "A2 - residual quantiles on last week, pooled"))
    rows.append(deployed)
    boosted_rows, boosted = gradient_boosting_quantiles(design)
    rows.extend(boosted_rows)
    rows.extend(split_conformal(design))
    table = pd.DataFrame(rows)
    table["coverage"] = table["coverage"].round(4)
    return table, {"boosted": boosted, "deployed_parts": deployed_parts}


def readable_comparison(table: pd.DataFrame) -> pd.DataFrame:
    """The comparison table formatted the way it goes on a slide."""
    display = pd.DataFrame({
        "Method": table["method"],
        "Coverage (promised 80%)": (table["coverage"] * 100).map("{:.1f}%".format),
        "Median band (units)": table["median_band"].round(1),
        "Pinball @0.1": table["pinball_10"].round(3),
        "Pinball @0.9": table["pinball_90"].round(3),
        "MAE of the middle line": table["MAE_of_median"].round(2),
        "Fit time (s)": table["fit_seconds"],
    })
    return display


def coverage_by_week(scored: pd.DataFrame, boosted: dict | None = None) -> pd.DataFrame:
    """Coverage week by week, so a seasonal failure cannot hide in an average."""
    frame = scored.copy()
    frame["covered"] = ((frame["actual"] >= frame["low"])
                        & (frame["actual"] <= frame["high"]))
    grouped = frame.groupby("week")
    table = grouped.agg(actual_units=("actual", "sum"),
                        coverage=("covered", "mean"),
                        mean_bias=("median", "mean")).reset_index()
    table["mean_bias"] = (grouped["median"].mean() - grouped["actual"].mean()).values
    if boosted is not None:
        ordered = boosted["sorted"]
        weeks = frame["week"].to_numpy()
        actual = frame["actual"].to_numpy()
        inside = (actual >= np.maximum(ordered[:, 0], 0)) & (actual <= ordered[:, 2])
        table["coverage_boosted"] = [float(inside[weeks == week].mean())
                                     for week in table["week"]]
    return table


def seasonal_coverage(scored: pd.DataFrame, skew: pd.Series,
                      top_n: int = config.SEASONAL_TOP_N,
                      ramp_months=config.Q4_RAMP_MONTHS) -> pd.DataFrame:
    """Coverage inside the autumn ramp against coverage outside it.

    Denominator for each cell: the held-out product-weeks in that slice. The
    aggregate 84% is an average over 12,194 rows; this table asks whether the
    average holds where the money is.
    """
    frame = scored.copy()
    frame["covered"] = ((frame["actual"] >= frame["low"])
                        & (frame["actual"] <= frame["high"]))
    frame["ramp"] = frame["week"].dt.month.isin(ramp_months)
    seasonal = set(skew.head(top_n).index)
    frame["seasonal"] = frame["StockCode"].isin(seasonal)

    rows = []
    for label, mask in [
        ("All 469 products, weeks outside the ramp (Jun-Sep)",
         ~frame["ramp"]),
        ("All 469 products, ramp weeks (Oct-Nov)", frame["ramp"]),
        (f"The {top_n} most Q4-skewed products, outside the ramp",
         frame["seasonal"] & ~frame["ramp"]),
        (f"The {top_n} most Q4-skewed products, RAMP WEEKS",
         frame["seasonal"] & frame["ramp"]),
    ]:
        slice_ = frame[mask]
        misses = slice_[~slice_["covered"]]
        above = (misses["actual"] > misses["high"]).mean() if len(misses) else float("nan")
        rows.append({
            "Slice": label,
            "Product-weeks": f"{len(slice_):,}",
            "Coverage (promised 80%)": f"{slice_['covered'].mean():.1%}",
            "Misses that were ABOVE the band": f"{above:.0%}",
        })
    return pd.DataFrame(rows)


def product_week_table(scored: pd.DataFrame, code: str) -> pd.DataFrame:
    """One product's held-out weeks, one row per week, with the verdict spelled out."""
    frame = scored[scored["StockCode"] == code].sort_values("week")
    verdict = np.where(frame["actual"] > frame["high"], "MISS - above the band",
                       np.where(frame["actual"] < frame["low"],
                                "MISS - below the band", "covered"))
    return pd.DataFrame({
        "Week": [week.date() for week in frame["week"]],
        "Actual units": frame["actual"].astype(int).to_numpy(),
        "Forecast": frame["point"].round(1).to_numpy(),
        "Band low": frame["low"].round(1).to_numpy(),
        "Band high": frame["high"].round(1).to_numpy(),
        "Result": verdict,
    })
