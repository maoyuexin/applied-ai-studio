"""Turn 1-minute sensor readings into hourly features a maintenance planner
would recognize.

The physics of an air leak, stated once: if air escapes, the compressor has to
work more often and for longer to hold pressure in the panel. So it rests
less, runs hotter, and panel pressure both swings less and bleeds away faster
when it does stop. Every feature below names one of those directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# Descriptive columns computed for teaching, beyond the six the model uses.
DESCRIPTIVE_DISPLAY = {
    "load_share": "Share of the hour the compressor is working hard",
    "motor_on_share": "Share of the hour the motor is running at all",
    "cycles_per_hour": "Compressor starts per hour",
    "mean_load_minutes": "Average minutes per working burst",
    "mean_rest_minutes": "Average minutes of rest between bursts (rest samples only)",
    "oil_temp_mean": "Average oil temperature (C)",
    "pressure_drop_rate": "Pressure change while resting (bar/min, rest samples only)",
    "pressure_recovery_rate": "Pressure rebuilt while working (bar/min)",
    "tp3_std": "Swing in panel air pressure (bar)",
    "tp3_mean": "Average panel air pressure (bar)",
    "lps_share": "Share of the hour panel pressure is below 7 bar",
    "dv_pressure_mean": "Average dryer discharge pressure (bar)",
    "motor_current_mean": "Average motor current (A)",
    "coverage": "Share of the hour with sensor data",
}


def _run_lengths(flag: np.ndarray, step_seconds: int) -> tuple[int, float, float]:
    """Count starts and mean run lengths (minutes) in a boolean sequence."""
    values = flag.astype(np.int8)
    if len(values) == 0:
        return 0, np.nan, np.nan
    change = np.diff(values, prepend=values[0])
    starts = int((change == 1).sum())
    boundaries = np.flatnonzero(np.diff(values) != 0) + 1
    segments = np.split(values, boundaries)
    on = [len(s) for s in segments if len(s) and s[0] == 1]
    off = [len(s) for s in segments if len(s) and s[0] == 0]
    mean_on = np.mean(on) * step_seconds / 60 if on else np.nan
    mean_off = np.mean(off) * step_seconds / 60 if off else np.nan
    return starts, mean_on, mean_off


def hourly_features(
    minutes: pd.DataFrame,
    step_seconds: int = config.MINUTE_SECONDS,
    min_coverage: float = config.MIN_HOUR_COVERAGE,
) -> pd.DataFrame:
    """Aggregate the regular minute grid into one row per clock hour.

    An hour is kept only if at least ``min_coverage`` of its minutes carry a
    reading, so a mostly empty hour never becomes a confident-looking number.
    """
    frame = minutes.copy()
    valid = frame["Motor_current"].notna()
    per_hour = 3600.0 / step_seconds

    current = frame["Motor_current"]
    frame["_loaded"] = (current > config.MOTOR_LOAD_THRESHOLD).astype(float).where(valid)
    frame["_on"] = (current > config.MOTOR_OFF_THRESHOLD).astype(float).where(valid)

    # Change in panel pressure per minute, split by what the compressor is doing.
    slope = frame["TP3"].diff() / (step_seconds / 60.0)
    frame["_falling"] = slope.where(valid & (frame["_loaded"] == 0))
    frame["_rebuilding"] = slope.where(valid & (frame["_loaded"] == 1))

    grouped = frame.resample("1h")
    out = pd.DataFrame(index=grouped.size().index)
    out["coverage"] = grouped["Motor_current"].count() / per_hour
    out["load_share"] = grouped["_loaded"].mean()
    out["motor_on_share"] = grouped["_on"].mean()
    out["oil_temp_mean"] = grouped["Oil_temperature"].mean()
    out["oil_temp_max"] = grouped["Oil_temperature"].max()
    out["tp3_mean"] = grouped["TP3"].mean()
    out["tp3_std"] = grouped["TP3"].std()
    out["reservoir_mean"] = grouped["Reservoirs"].mean()
    out["dv_pressure_mean"] = grouped["DV_pressure"].mean()
    out["motor_current_mean"] = grouped["Motor_current"].mean()
    out["lps_share"] = grouped["LPS"].mean()
    out["oil_low_share"] = 1 - grouped["Oil_level"].mean()
    out["pressure_drop_rate"] = grouped["_falling"].mean()
    out["pressure_recovery_rate"] = grouped["_rebuilding"].mean()

    def _slope(series: pd.Series) -> float:
        series = series.dropna()
        if len(series) < 3:
            return np.nan
        hours = (series.index - series.index[0]).total_seconds().to_numpy() / 3600.0
        return float(np.polyfit(hours, series.to_numpy(), 1)[0])

    out["oil_temp_rise_c_per_h"] = grouped["Oil_temperature"].apply(_slope)

    cycles = []
    for stamp, chunk in frame.groupby(pd.Grouper(freq="1h")):
        loaded = chunk["_loaded"].dropna().to_numpy()
        cycles.append((stamp,) + _run_lengths(loaded > 0.5, step_seconds))
    cycle_frame = pd.DataFrame(
        cycles, columns=["ts", "cycles_per_hour", "mean_load_minutes", "mean_rest_minutes"]
    ).set_index("ts")
    out = out.join(cycle_frame)
    return out[out["coverage"] >= min_coverage]


def model_matrix(hourly: pd.DataFrame) -> pd.DataFrame:
    """The six model features, defined so ``NaN`` can only mean 'no data'.

    Two of the six need care. 'Minutes of rest' and 'how fast pressure falls
    while resting' both look natural if you compute them from resting samples
    only - and then they are undefined exactly when the compressor never rests,
    which is what a bad air leak looks like. Here they are defined for every
    hour that has data:

    - rest minutes per cycle = the part of the hour NOT spent compressing,
      divided by the number of starts (at least one), so a fully loaded hour
      scores 0 minutes of rest rather than 'unknown';
    - pressure fall rate = 0 bar/min when there was no resting stretch to
      measure, because no rest means no observed decay.
    """
    matrix = pd.DataFrame(index=hourly.index)
    matrix["load_share"] = hourly["load_share"]
    matrix["cycles_per_hour"] = hourly["cycles_per_hour"]
    starts = hourly["cycles_per_hour"].clip(lower=1.0)
    matrix["rest_minutes_per_cycle"] = (1.0 - hourly["load_share"]) * 60.0 / starts
    matrix["oil_temp_mean"] = hourly["oil_temp_mean"]
    matrix["tp3_std"] = hourly["tp3_std"].fillna(0.0)
    matrix["pressure_fall_rate"] = hourly["pressure_drop_rate"].abs().fillna(0.0)
    return matrix[config.MODEL_FEATURES]


def naive_model_matrix(hourly: pd.DataFrame) -> pd.DataFrame:
    """The first version of the feature set - the one with the bug.

    Identical to ``model_matrix`` except that rest minutes and pressure fall
    rate are read straight off the resting samples. Both are ``NaN`` in an
    hour with no resting samples at all.
    """
    matrix = pd.DataFrame(index=hourly.index)
    matrix["load_share"] = hourly["load_share"]
    matrix["cycles_per_hour"] = hourly["cycles_per_hour"]
    matrix["rest_minutes_per_cycle"] = hourly["mean_rest_minutes"]
    matrix["oil_temp_mean"] = hourly["oil_temp_mean"]
    matrix["tp3_std"] = hourly["tp3_std"]
    matrix["pressure_fall_rate"] = hourly["pressure_drop_rate"].abs()
    return matrix[config.MODEL_FEATURES]


def failure_mask(index: pd.DatetimeIndex, pre_hours: float = 0.0, post_hours: float = 0.0) -> pd.Series:
    """True where a timestamp falls inside a documented failure window."""
    mask = pd.Series(False, index=index)
    for _name, start, end, _note in config.failure_windows():
        mask |= (index >= start - pd.Timedelta(hours=pre_hours)) & (
            index <= end + pd.Timedelta(hours=post_hours)
        )
    return mask


def dropna_damage(hourly: pd.DataFrame) -> pd.DataFrame:
    """What a naive ``dropna()`` deletes, per documented failure.

    The teaching number: the two worst failures lose every one of their hours,
    because during them the compressor never rests.
    """
    naive = naive_model_matrix(hourly)
    fixed = model_matrix(hourly)
    kept = naive.dropna().index
    rows = []
    for name, start, end, _note in config.failure_windows():
        window = fixed.index[(fixed.index >= start) & (fixed.index <= end)]
        survived = len(window.intersection(kept))
        rows.append({
            "Failure": name,
            "Hours with data": len(window),
            "Hours surviving dropna()": survived,
            "Hours silently deleted": len(window) - survived,
        })
    total = pd.DataFrame(rows)
    return total


def effect_sizes(hourly: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    """Cohen's d and AUC for each feature, during a failure and 24 h before it.

    Cohen's d is the gap between two group means measured in pooled standard
    deviations: d = 1 means the two groups sit one standard deviation apart.
    AUC here is the chance that a randomly picked failure hour scores higher
    than a randomly picked baseline hour, 0.5 being a coin flip.

    Denominator for both: baseline = every hour from 2020-02-01 to 2020-04-10
    that has data (n is reported in the table).
    """
    baseline_end = pd.Timestamp("2020-04-10")
    baseline_idx = matrix.index[(matrix.index >= config.TRAIN_START) & (matrix.index < baseline_end)]
    during_idx = matrix.index[failure_mask(matrix.index).to_numpy()]

    rows = []
    for column in config.MODEL_FEATURES:
        base = matrix.loc[baseline_idx, column].dropna()
        during = matrix.loc[during_idx, column].dropna()
        pooled = np.sqrt((base.std() ** 2 + during.std() ** 2) / 2)
        pre = []
        for _name, start, _end, _note in config.failure_windows():
            pre.append(matrix.loc[
                (matrix.index >= start - pd.Timedelta(hours=24)) & (matrix.index < start), column
            ])
        prior = pd.concat(pre).dropna()
        pooled_pre = np.sqrt((base.std() ** 2 + prior.std() ** 2) / 2)
        rows.append({
            "feature": column,
            "display": config.FEATURE_DISPLAY_NAMES[column],
            "baseline_mean": float(base.mean()),
            "during_mean": float(during.mean()),
            "cohens_d_during": float((during.mean() - base.mean()) / pooled) if pooled else np.nan,
            "auc_during": _auc(during.to_numpy(), base.to_numpy()),
            "cohens_d_24h_before": float((prior.mean() - base.mean()) / pooled_pre) if pooled_pre else np.nan,
            "baseline_hours": int(len(base)),
            "failure_hours": int(len(during)),
            "pre_onset_hours": int(len(prior)),
        })
    return pd.DataFrame(rows)


def _auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """Rank-based AUC without a sklearn round trip."""
    from scipy.stats import rankdata

    combined = np.concatenate([positive, negative])
    ranks = rankdata(combined)
    n_pos, n_neg = len(positive), len(negative)
    return float((ranks[:n_pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def monthly_means(matrix: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    """Monthly feature means, and the same distances in training standard
    deviations. This is the evidence that the world moved, not the machine."""
    monthly = matrix.resample("1ME").mean()
    monthly.index = monthly.index.to_period("M").astype(str)
    shifted = (monthly - training.mean()) / training.std()
    out = monthly.round(3).add_suffix("")
    return out, shifted.round(2)
