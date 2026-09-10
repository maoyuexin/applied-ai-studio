"""The metric set this lab reports, and the two metrics it reports as failures.

Every function states its denominator in the docstring, because the whole
argument of Stage 4 is that a metric without a denominator is a rumor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def mae(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Mean absolute error, in units. Denominator: scored product-weeks."""
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(forecast))))


def rmse(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Root mean squared error, in units. Punishes the big misses hardest."""
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(forecast)) ** 2)))


def pinball(actual: np.ndarray, forecast: np.ndarray, quantile: float) -> float:
    """Pinball (quantile) loss: the score a quantile forecast is judged on.

    Being under by 1 unit costs ``q``; being over by 1 unit costs ``1 - q``.
    At q = 0.9 an under-forecast costs nine times an over-forecast, which is
    exactly the asymmetry a stockout has.
    """
    difference = np.asarray(actual) - np.asarray(forecast)
    return float(np.mean(np.maximum(quantile * difference,
                                    (quantile - 1) * difference)))


def coverage(actual: np.ndarray, low: np.ndarray, high: np.ndarray) -> float:
    """Share of scored product-weeks whose actual fell inside the band.

    Numerator: rows with low <= actual <= high. Denominator: all scored rows.
    """
    actual = np.asarray(actual)
    return float(np.mean((actual >= np.asarray(low)) & (actual <= np.asarray(high))))


def mape(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Mean absolute PERCENTAGE error, the way scikit-learn computes it.

    Taught here as a failure, not a metric. When an actual is zero, the
    denominator becomes the smallest positive float the machine can hold, and
    one row can dominate the whole average.
    """
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    return float(np.mean(np.abs(actual - forecast)
                         / np.maximum(np.abs(actual), np.finfo(np.float64).eps)))


def band_stats(scored: pd.DataFrame) -> dict:
    """Width of the band, and how it compares with the demand it covers."""
    width = (scored["high"] - scored["low"]).to_numpy()
    nonzero = scored.loc[scored["actual"] > 0, "actual"].to_numpy()
    return {
        "median_band": float(np.median(width)),
        "mean_band": float(np.mean(width)),
        "median_nonzero_demand": float(np.median(nonzero)),
        "band_over_median_demand": float(np.median(width) / np.median(nonzero)),
    }


def score_frame(scored: pd.DataFrame) -> dict:
    """Every headline number for one scored holdout, in one dictionary."""
    actual = scored["actual"].to_numpy()
    result = {
        "n_rows": int(len(scored)),
        "n_products": int(scored["StockCode"].nunique()),
        "n_test_weeks": int(scored["week"].nunique()),
        "MAE": mae(actual, scored["median"]),
        "RMSE": rmse(actual, scored["median"]),
        "MAE_point": mae(actual, scored["point"]),
        "coverage_80": coverage(actual, scored["low"], scored["high"]),
        "pinball_10": pinball(actual, scored["low"], 0.1),
        "pinball_50": pinball(actual, scored["median"], 0.5),
        "pinball_90": pinball(actual, scored["high"], 0.9),
        "MAE_flat_zero": mae(actual, np.zeros_like(actual)),
        # MAPE is a POINT metric, so it is computed against the point forecast,
        # which is the number a planner would have pasted into a report.
        "MAPE_sklearn": mape(actual, scored["point"]),
        "MAPE_nonzero_only": mape(actual[actual > 0],
                                  scored["point"].to_numpy()[actual > 0]),
        "MAPE_flat_zero": mape(actual, np.zeros_like(actual)),
        "MAPE_flat_zero_nonzero_only": mape(actual[actual > 0],
                                            np.zeros(int((actual > 0).sum()))),
    }
    result.update(band_stats(scored))
    return result


def metric_table(summary: dict) -> pd.DataFrame:
    """The frozen metric set, with what each one is for written beside it."""
    rows = [
        ("MAE (mean absolute error)", f"{summary['MAE']:.2f} units",
         "Typical miss. Half the weeks are missed by less than this."),
        ("RMSE (root mean squared error)", f"{summary['RMSE']:.2f} units",
         "Same idea, squared first: it reports the big misses, and the big "
         "misses are the stockouts."),
        (f"Coverage at nominal {config.NOMINAL_COVERAGE:.0%}",
         f"{summary['coverage_80']:.2%}",
         "Share of held-out product-weeks that landed inside the band. "
         "The one number the interval exists to earn."),
        ("Median band width", f"{summary['median_band']:.2f} units",
         f"{summary['band_over_median_demand']:.2f}x the median non-zero week. "
         "An honest interval here is wider than the forecast."),
        ("Pinball loss @ 0.1", f"{summary['pinball_10']:.3f}",
         "Scores the lower edge of the band."),
        ("Pinball loss @ 0.5", f"{summary['pinball_50']:.3f}",
         "Scores the middle line."),
        ("Pinball loss @ 0.9", f"{summary['pinball_90']:.3f}",
         "Scores the upper edge - the one the order quantity is read from."),
        ("MAE of a flat-zero forecast", f"{summary['MAE_flat_zero']:.2f} units",
         "Printed beside MAE on purpose. A model that does not clear this by a "
         "wide margin has learned nothing."),
        ("MAPE of the point forecast", f"{summary['MAPE_sklearn']:.3g}",
         "NEVER REPORT THIS. Stage 4 shows why: a flat-zero forecast scores "
         f"{summary['MAPE_flat_zero']:.4f} on the same rows and wins."),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value", "What it is for"])


def mape_demonstration(panel: pd.DataFrame, cohort: pd.Index,
                       intermittent: pd.Index, scored: pd.DataFrame) -> dict:
    """Two datasets, two forecasts, four metrics: MAPE ranks the useless one first.

    The intermittent forecast is deliberately the simplest possible: the mean
    of that product's last 8 training weeks, held flat across the holdout.
    """
    train_end = config.N_TRAIN
    block = panel.loc[intermittent].values.astype(float)
    actual_i = block[:, train_end:].ravel()
    forecast_i = np.repeat(block[:, train_end - config.WINDOW:train_end].mean(axis=1),
                           block.shape[1] - train_end)
    zeros_i = np.zeros_like(actual_i)

    actual_c = scored["actual"].to_numpy()
    forecast_c = scored["point"].to_numpy()
    zeros_c = np.zeros_like(actual_c)
    nonzero = actual_c > 0

    return {
        "intermittent": {
            "n_products": int(len(intermittent)),
            "zero_share_train": float(1 - (panel.loc[intermittent]
                                           .iloc[:, :train_end] > 0).mean(axis=1).mean()),
            "zero_share_scored": float(np.mean(actual_i == 0)),
            "MA8": {"MAE": mae(actual_i, forecast_i), "RMSE": rmse(actual_i, forecast_i),
                    "MAPE": mape(actual_i, forecast_i)},
            "flat_zero": {"MAE": mae(actual_i, zeros_i), "RMSE": rmse(actual_i, zeros_i),
                          "MAPE": mape(actual_i, zeros_i)},
        },
        "cohort": {
            "n_products": int(len(cohort)),
            "zero_share_scored": float(np.mean(actual_c == 0)),
            "deployed": {"MAE": mae(actual_c, forecast_c),
                         "MAPE": mape(actual_c, forecast_c),
                         "MAPE_nonzero_only": mape(actual_c[nonzero], forecast_c[nonzero])},
            "flat_zero": {"MAE": mae(actual_c, zeros_c),
                          "MAPE": mape(actual_c, zeros_c),
                          "MAPE_nonzero_only": mape(actual_c[nonzero], zeros_c[nonzero])},
        },
    }


def mape_table(demonstration: dict) -> pd.DataFrame:
    """The MAPE demonstration as one printable table."""
    inter = demonstration["intermittent"]
    cohort = demonstration["cohort"]
    rows = [
        (f"Intermittent set ({inter['n_products']} products, "
         f"{inter['zero_share_scored']:.0%} of scored weeks are zero)",
         "8-week moving average", f"{inter['MA8']['MAE']:.2f}",
         f"{inter['MA8']['RMSE']:.2f}", f"{inter['MA8']['MAPE']:.4g}"),
        ("", "flat zero (forecast nothing, ever)", f"{inter['flat_zero']['MAE']:.2f}",
         f"{inter['flat_zero']['RMSE']:.2f}", f"{inter['flat_zero']['MAPE']:.4g}"),
        (f"Deployed cohort ({cohort['n_products']} products, "
         f"{cohort['zero_share_scored']:.1%} of scored weeks are zero)",
         "deployed point forecast", f"{cohort['deployed']['MAE']:.2f}", "-",
         f"{cohort['deployed']['MAPE']:.4g}"),
        ("", "flat zero (forecast nothing, ever)", f"{cohort['flat_zero']['MAE']:.2f}",
         "-", f"{cohort['flat_zero']['MAPE']:.4g}"),
    ]
    return pd.DataFrame(rows, columns=["Data", "Forecast", "MAE", "RMSE", "MAPE"])
