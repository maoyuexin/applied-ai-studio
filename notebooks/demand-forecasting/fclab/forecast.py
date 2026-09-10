"""The deployed forecaster, and the baselines it had to beat.

The whole model is two sentences:

1. **The point forecast** is the mean of this product's last 8 observed weeks.
2. **The band** is that same point forecast plus the 10th, 50th and 90th
   percentiles of how wrong the same rule was on this product's training
   weeks, with the lower edge clipped at zero because demand cannot be negative.

Everything below is bookkeeping around those two sentences.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


class WeeklyQuantileForecaster:
    """MA8 point forecast plus per-product empirical residual quantiles.

    Stored state, and nothing else: for each product, its training residuals,
    its last observed 8-week window, its name and its unit price. There are no
    learned weights - the "fit" is a subtraction and a percentile.
    """

    WINDOW = config.WINDOW

    def __init__(self, product_ids, residuals, last_window,
                 names=None, prices=None, version=config.MODEL_VERSION):
        self.product_ids = list(product_ids)
        self.residuals = residuals        # code -> training residuals (actual - MA8)
        self.last_window = last_window    # code -> last WINDOW observed weeks
        self.names = names or {}
        self.prices = prices or {}
        self.version = version

    # ── the two sentences ───────────────────────────────────────────────────
    def point(self, code: str, history=None) -> float:
        """Mean of the last 8 observed weeks."""
        window = np.asarray(self.last_window[code] if history is None else history,
                            dtype=float)
        return float(window[-self.WINDOW:].mean())

    def quantile(self, code: str, q: float, history=None) -> float:
        """Point forecast plus the q-th percentile of this product's own errors."""
        return float(max(0.0, self.point(code, history)
                         + np.quantile(self.residuals[code], q)))

    def interval(self, code: str, low=config.NOMINAL_LO, high=config.NOMINAL_HI,
                 history=None) -> tuple[float, float, float]:
        """(low, median, high). Clipped at zero, and kept in order."""
        forecast = self.point(code, history)
        residuals = self.residuals[code]
        lo, med, hi = forecast + np.quantile(residuals, [low, 0.5, high])
        lo = max(lo, 0.0)
        hi = max(hi, lo)
        return lo, min(max(med, lo), hi), hi

    def order_quantity(self, code: str, cu: float, co: float,
                       history=None) -> tuple[float, float]:
        """The newsvendor order: read the band at the critical ratio cu/(cu+co)."""
        critical_ratio = cu / (cu + co)
        return self.quantile(code, critical_ratio, history), critical_ratio

    # ── convenience ─────────────────────────────────────────────────────────
    def name(self, code: str) -> str:
        return str(self.names.get(code, ""))

    def price(self, code: str) -> float:
        return float(self.prices.get(code, np.nan))

    def residual_table(self, code: str) -> pd.DataFrame:
        residuals = np.asarray(self.residuals[code], dtype=float)
        percentiles = [10, 25, 50, 75, 90]
        return pd.DataFrame({
            "percentile": [f"{p}th" for p in percentiles],
            "residual_units": np.percentile(residuals, percentiles).round(2),
        })


def fit(panel: pd.DataFrame, cohort: pd.Index, names: pd.Series,
        prices: pd.Series) -> WeeklyQuantileForecaster:
    """Build the forecaster from the TRAINING weeks only.

    For every product, walk the training weeks from week 8 onward, forecast each
    one with the mean of the 8 weeks before it, and keep the error. That is 68
    residuals per product, and they are the entire uncertainty model.
    """
    block = panel.loc[cohort]
    values = block.values.astype(float)
    window = config.WINDOW
    residuals, last_window = {}, {}
    for row, code in enumerate(cohort):
        errors = [values[row, t] - values[row, t - window:t].mean()
                  for t in range(window, config.N_TRAIN)]
        residuals[code] = np.asarray(errors, dtype=float)
        last_window[code] = values[row, config.N_TRAIN - window:config.N_TRAIN].copy()
    return WeeklyQuantileForecaster(
        list(cohort), residuals, last_window,
        names=names.reindex(cohort).to_dict(),
        prices=prices.reindex(cohort).to_dict(),
    )


def score_holdout(panel: pd.DataFrame, forecaster: WeeklyQuantileForecaster,
                  low=config.NOMINAL_LO, high=config.NOMINAL_HI) -> pd.DataFrame:
    """One-step-ahead rolling forecast over every held-out week.

    Rolling origin: the forecast for week t reads the actuals through week t-1
    and nothing later. That is the real reorder cadence, and it is why the
    holdout is 12,194 product-weeks rather than 469 single predictions.
    """
    cohort = forecaster.product_ids
    block = panel.loc[cohort]
    values = block.values.astype(float)
    weeks = list(block.columns)
    window = config.WINDOW
    records = []
    for t in range(config.N_TRAIN, values.shape[1]):
        for row, code in enumerate(cohort):
            history = values[row, t - window:t]
            lo, med, hi = forecaster.interval(code, low, high, history=history)
            records.append((code, weeks[t], values[row, t],
                            max(float(history.mean()), 0.0), lo, med, hi))
    return pd.DataFrame(records, columns=["StockCode", "week", "actual",
                                          "point", "low", "median", "high"])


def baseline_forecasts(panel: pd.DataFrame, cohort: pd.Index) -> dict:
    """Six candidate point forecasts on the same held-out weeks.

    Same rolling origin for all six, so the comparison is fair.
    """
    values = panel.loc[cohort].values.astype(float)
    n_weeks = values.shape[1]
    targets = range(config.N_TRAIN, n_weeks)

    actual, naive, seasonal, ma4, ma8, train_mean = [], [], [], [], [], []
    per_product_mean = values[:, :config.N_TRAIN].mean(axis=1)
    for t in targets:
        actual.append(values[:, t])
        naive.append(values[:, t - 1])
        seasonal.append(values[:, t - 52])
        ma4.append(values[:, t - 4:t].mean(axis=1))
        ma8.append(values[:, t - config.WINDOW:t].mean(axis=1))
        train_mean.append(per_product_mean)
    stack = lambda blocks: np.concatenate(blocks)  # noqa: E731
    actual = stack(actual)
    return {
        "actual": actual,
        "Moving average, 8 weeks (MA8)": stack(ma8),
        "Moving average, 4 weeks": stack(ma4),
        "Naive (last week's units)": stack(naive),
        "Seasonal-naive (same week last year)": stack(seasonal),
        "Flat zero (forecast nothing, ever)": np.zeros_like(actual),
        "Train mean for this product": stack(train_mean),
    }


def baseline_table(panel: pd.DataFrame, cohort: pd.Index) -> pd.DataFrame:
    """The baseline leaderboard, worst-to-best by MAE, with the verdicts."""
    from . import metrics

    forecasts = baseline_forecasts(panel, cohort)
    actual = forecasts.pop("actual")
    notes = {
        "Moving average, 8 weeks (MA8)":
            "ADOPTED. Slow enough to ignore one loud week, fast enough to follow a trend.",
        "Moving average, 4 weeks":
            "Close behind. Reacts faster, and pays for it on noisy products.",
        "Naive (last week's units)":
            "One week of noise becomes next week's plan.",
        "Seasonal-naive (same week last year)":
            "THE FAILURE. One year of history gives one noisy number per week, "
            "not a season.",
        "Flat zero (forecast nothing, ever)":
            "Not a forecast. It is here because it beats seasonal-naive.",
        "Train mean for this product":
            "'Order the average.' The business grew and the test window is the "
            "autumn ramp, so the average is always short.",
    }
    rows = [(name, metrics.mae(actual, forecast), metrics.rmse(actual, forecast),
             notes[name]) for name, forecast in forecasts.items()]
    table = pd.DataFrame(rows, columns=["Point forecast", "MAE", "RMSE", "Verdict"])
    return table.sort_values("MAE").reset_index(drop=True)
