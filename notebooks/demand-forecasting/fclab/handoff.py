"""Export and verify the narrow artifact contract a planning service consumes.

Five files leave the notebook, and nothing else:

- ``forecaster.joblib``       the fitted forecaster: per-product residuals, last
                              8-week window, names, prices, version
- ``model_card.json``         intended use, provenance, measured results, limits
- ``evaluation.json``         every table the governance view needs
- ``operating_policy.json``   the cohort rule, the split, the cost assumptions,
                              the critical ratios, the human-authority statement
- ``sample_manifest.parquet`` ten packaged products with their week-by-week bands

The forecaster is about a hundred kilobytes because it is 469 products x 68
residuals and nothing else - no weights, no trees. A student can open the policy
JSON and read the entire operating decision.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from . import config, forecast, metrics, policy

ARTIFACT_NAMES = (
    "forecaster.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)


# ── Frozen-number check ─────────────────────────────────────────────────────

def check_frozen(summary: dict, tolerance: float = 0.01) -> pd.DataFrame:
    """Every headline number against the value the spike froze.

    Tolerance is absolute and deliberately tight. A drift larger than 0.01 in
    MAE means the panel, the cohort or the split changed, and every sentence in
    the notebook that quotes a number is now wrong.
    """
    rows = []
    for key, expected in config.FROZEN.items():
        found = summary[key]
        if isinstance(expected, int):
            ok = int(found) == expected
            difference = int(found) - expected
        else:
            difference = float(found) - float(expected)
            ok = abs(difference) <= tolerance
        rows.append({
            "metric": key,
            "frozen": expected,
            "measured": round(float(found), 6) if not isinstance(expected, int)
            else int(found),
            "difference": round(float(difference), 6),
            "status": "OK" if ok else "DRIFTED",
        })
    return pd.DataFrame(rows)


def assert_frozen(summary: dict, tolerance: float = 0.01) -> pd.DataFrame:
    """``check_frozen``, but it raises rather than printing a red row."""
    table = check_frozen(summary, tolerance)
    drifted = table[table["status"] != "OK"]
    if len(drifted):
        raise AssertionError(
            "The frozen holdout numbers no longer reproduce:\n"
            + drifted.to_string(index=False)
        )
    return table


# ── Sample manifest ─────────────────────────────────────────────────────────

def sample_manifest(panel: pd.DataFrame, scored: pd.DataFrame,
                    per_product: pd.DataFrame, names: pd.Series,
                    prices: pd.Series,
                    products: dict[str, str] | None = None) -> pd.DataFrame:
    """The ten products the demo ships with, chosen by rule, not by taste.

    Three steady sellers, three Christmas spikes, two where the point forecast
    looks fine and the band is dangerous, the product where the policy LOSES
    money, and the policy's cleanest win. The last two rows are the reason the
    manifest exists: a demo that only carries wins teaches nothing.

    ``per_product`` is ``PolicyBoard.per_product(4)``; every cost below is that
    product's whole 26-week holdout at the 4:1 classroom ratio.
    """
    products = products or config.MANIFEST_PRODUCTS
    train = panel.columns[: config.N_TRAIN]
    outcomes = per_product.set_index("StockCode")

    rows = []
    for code, purpose in products.items():
        if code not in scored["StockCode"].values:
            raise ValueError(f"{code} is not in the scored holdout; the manifest "
                             "cannot package a product the model never forecast.")
        frame = scored[scored["StockCode"] == code].sort_values("week")
        actual = frame["actual"].to_numpy(dtype=float)
        low = frame["low"].to_numpy(dtype=float)
        high = frame["high"].to_numpy(dtype=float)
        covered = (actual >= low) & (actual <= high)
        width = high - low
        outcome = outcomes.loc[code]
        nonzero_train = float((panel.loc[code, train] > 0).mean())

        rows.append({
            "StockCode": code,
            "product": str(names.get(code, "")),
            "why_this_product": purpose,
            "unit_price": round(float(prices.get(code, np.nan)), 2),
            "train_nonzero_share": round(nonzero_train, 4),
            "test_weeks": int(len(frame)),
            "test_mean_units": round(float(actual.mean()), 1),
            "point_mean": round(float(frame["point"].mean()), 1),
            "band_low_mean": round(float(low.mean()), 1),
            "band_high_mean": round(float(high.mean()), 1),
            "band_over_demand": round(float(width.mean() / max(actual.mean(), 1e-9)), 2),
            "coverage": round(float(covered.mean()), 4),
            "misses": int((~covered).sum()),
            "misses_above_band": int((actual > high).sum()),
            "units_short_point": round(float(outcome["short_point"]), 1),
            "units_short_quantile": round(float(outcome["short_quantile"]), 1),
            "units_excess_point": round(float(outcome["excess_point"]), 1),
            "units_excess_quantile": round(float(outcome["excess_quantile"]), 1),
            "cost_point": round(float(outcome["cost_point"]), 2),
            "cost_quantile": round(float(outcome["cost_quantile"]), 2),
            "cost_change_pct": round(float(-outcome["saving_pct"]), 2),
            "policy_is_cheaper": bool(outcome["saving"] > 0),
            "weekly": json.dumps([
                {
                    "week": str(pd.Timestamp(week).date()),
                    "actual": round(float(a), 1),
                    "point": round(float(p), 1),
                    "low": round(float(lo), 1),
                    "high": round(float(hi), 1),
                    "covered": bool(lo <= a <= hi),
                }
                for week, a, p, lo, hi in zip(
                    frame["week"], actual, frame["point"].to_numpy(dtype=float),
                    low, high)
            ]),
        })
    manifest = pd.DataFrame(rows)
    if len(manifest) != len(products):
        raise ValueError("The manifest lost a product on the way out.")
    return manifest


# ── Evidence ────────────────────────────────────────────────────────────────

def _records(frame: pd.DataFrame) -> list[dict]:
    """A DataFrame as JSON-safe records: no numpy scalars, no NaN, no Timestamps."""
    def clean(value):
        if isinstance(value, (np.floating, float)):
            return None if pd.isna(value) else round(float(value), 6)
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.bool_, bool)):
            return bool(value)
        if isinstance(value, pd.Timestamp):
            return str(value.date())
        return value
    return [{k: clean(v) for k, v in record.items()}
            for record in frame.to_dict("records")]


def assemble_evidence(
    provenance: pd.DataFrame,
    panel_summary: pd.DataFrame,
    cohort_rules: pd.DataFrame,
    leakage: dict,
    baselines: pd.DataFrame,
    interval_comparison: pd.DataFrame,
    summary: dict,
    mape_demo: dict,
    coverage_weekly: pd.DataFrame,
    seasonal_coverage: pd.DataFrame,
    sweep: pd.DataFrame,
    cost_curve: pd.DataFrame,
    outcome_split: pd.DataFrame,
    frozen_check: pd.DataFrame,
    runtime_seconds: float,
) -> dict:
    """The complete ``evaluation.json`` payload, assembled in one place."""
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_provenance": {
            "summary": _records(provenance),
            "dataset": config.DATASET_NAME,
            "uci_id": config.DATASET_UCI_ID,
            "license": config.DATASET_LICENSE,
            "doi": config.DATASET_DOI,
            "url": config.DATASET_URL,
            "citation": config.DATASET_CITATION,
            "source_zip_sha256": config.DATASET_ZIP_SHA256,
            "committed_file_sha256": config.WEEKLY_CSV_SHA256,
            "population": config.DATASET_POPULATION,
            "note": (
                f"The retailer was open on a Saturday exactly {config.SATURDAYS_OPEN} "
                f"time in {config.TRADING_DAYS} trading days. A daily model would "
                "learn that closure as a weekly demand collapse, which is why this "
                "lab works at a weekly grain."
            ),
        },
        "panel_and_split": {
            "summary": _records(panel_summary),
            "total_weeks": config.TOTAL_WEEKS,
            "weeks_in_committed_file": config.WEEKS_IN_FILE,
            "edge_weeks_dropped": config.DROP_EDGE_WEEKS,
            "train_window": [config.TRAIN_START, config.TRAIN_END],
            "test_window": [config.TEST_START, config.TEST_END],
            "chronological": True,
            "note": (
                "The first and last weeks of the source window are partial and are "
                "dropped; 104 weeks become 102. The split is chronological and is "
                "never shuffled."
            ),
        },
        "cohort_selection": {
            "rule": f">= {config.COHORT_MIN_NONZERO:.0%} non-zero weeks, measured on "
                    f"the {config.N_TRAIN} TRAINING weeks only",
            "size": config.COHORT_SIZE,
            "candidate_rules": _records(cohort_rules),
            "leakage_evidence": {k: (round(float(v), 6) if isinstance(v, float) else v)
                                 for k, v in leakage.items()},
            "note": (
                f"The same rule applied to all {config.TOTAL_WEEKS} weeks admits "
                f"{config.COHORT_SIZE_LEAKY} products instead of {config.COHORT_SIZE}. "
                "That rule has read the test weeks, and the difference is the leak."
            ),
        },
        "point_forecast_baselines": _records(baselines),
        "interval_method_comparison": _records(interval_comparison),
        "holdout_frozen": {
            "scored_once": True,
            "rows": summary["n_rows"],
            "products": summary["n_products"],
            "test_weeks": summary["n_test_weeks"],
            "MAE": round(summary["MAE"], 4),
            "RMSE": round(summary["RMSE"], 4),
            "MAE_of_point_forecast": round(summary["MAE_point"], 4),
            "MAE_of_flat_zero": round(summary["MAE_flat_zero"], 4),
            "coverage_at_nominal_80": round(summary["coverage_80"], 4),
            "median_band_units": round(summary["median_band"], 4),
            "band_over_median_demand": round(summary["band_over_median_demand"], 4),
            "pinball_10": round(summary["pinball_10"], 4),
            "pinball_50": round(summary["pinball_50"], 4),
            "pinball_90": round(summary["pinball_90"], 4),
            "frozen_target_check": _records(frozen_check),
        },
        "mape_is_a_failure": {
            "MAPE_of_the_point_forecast": summary["MAPE_sklearn"],
            "MAPE_of_a_flat_zero_forecast": summary["MAPE_flat_zero"],
            "MAPE_nonzero_rows_only": summary["MAPE_nonzero_only"],
            "demonstration": {
                "intermittent": mape_demo["intermittent"],
                "cohort": mape_demo["cohort"],
            },
            "note": (
                "MAPE divides by the actual. On weeks where the actual is zero the "
                "denominator becomes the smallest float the machine holds, and a "
                "forecast of nothing at all wins the metric. This number is reported "
                "here so nobody quotes it as a result."
            ),
        },
        "where_the_average_hides_a_failure": {
            "coverage_by_week": _records(coverage_weekly),
            "seasonal_slices": _records(seasonal_coverage),
            "note": (
                f"The headline {summary['coverage_80']:.2%} is an average over "
                f"{summary['n_rows']:,} rows. Sliced to the most seasonal products "
                "inside the Oct-Nov ramp it falls, and the misses are above the band, "
                "which is the direction that empties a shelf."
            ),
        },
        "policy": {
            "costs_are_classroom_assumptions": True,
            "cost_assumption": config.COST_ASSUMPTION_NOTE,
            "newsvendor_sweep": _records(sweep),
            "cost_curve": _records(cost_curve),
            "per_product_outcomes": _records(outcome_split),
            "note": (
                "Ordering at the critical-ratio quantile instead of the point "
                "forecast is cheaper on most products and MORE expensive on a real "
                "minority. Both are in the manifest."
            ),
        },
        "runtime_seconds_end_to_end": round(float(runtime_seconds), 2),
        "environment": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "seed": config.SEED,
        },
    }


def build_model_card(forecaster, evidence: dict, prices: pd.Series) -> dict:
    """Intended use, how it works, what it was measured at, and what it is not."""
    held_out = evidence["holdout_frozen"]
    return {
        "model_name": "Online Retail II weekly demand forecaster",
        "version": forecaster.version,
        "course": "ITAI 2372 Module 6 - AI in Retail and Supply Chain",
        "intended_use": (
            "Give a buyer, for one product and one coming week, a point forecast of "
            "units and a range wide enough to be honest, so a human can decide how "
            "many to order."
        ),
        "not_for": [
            "Any product outside the deployed cohort - most of this catalog sells "
            "too rarely to forecast, and the model says so by refusing it.",
            "Placing an order. The quantity is a suggestion to a planner.",
            "Horizons beyond one week. Every number here is one-step-ahead.",
            "Any retailer other than this one, on any other product mix.",
            "Pricing, promotion planning, or any decision about a person.",
        ],
        "authority_boundary": config.HUMAN_AUTHORITY,
        "prohibited_claims": list(config.PROHIBITED_CLAIMS),
        "model_type": "8-week moving average with per-product empirical residual "
                      "quantiles",
        "how_it_works": (
            f"The point forecast is the mean of this product's last {config.WINDOW} "
            "observed weeks. The band is that same forecast plus the "
            f"{config.NOMINAL_LO:.0%} and {config.NOMINAL_HI:.0%} percentiles of how "
            "wrong the same rule was on this product's own training weeks, with the "
            "lower edge clipped at zero because demand cannot be negative. There are "
            "no learned weights: the whole fit is a subtraction and a percentile."
        ),
        "fitted_state": {
            "products": len(forecaster.product_ids),
            "residuals_per_product": int(config.N_TRAIN - config.WINDOW),
            "window_weeks": config.WINDOW,
            "nominal_quantiles": [config.NOMINAL_LO, 0.5, config.NOMINAL_HI],
            "nominal_coverage": config.NOMINAL_COVERAGE,
            "median_unit_price": round(float(
                prices.reindex(forecaster.product_ids).median()), 2),
        },
        "training_data": {
            "dataset": config.DATASET_NAME,
            "uci_id": config.DATASET_UCI_ID,
            "license": config.DATASET_LICENSE,
            "doi": config.DATASET_DOI,
            "url": config.DATASET_URL,
            "citation": config.DATASET_CITATION,
            "committed_file": config.WEEKLY_CSV.name,
            "committed_file_sha256": config.WEEKLY_CSV_SHA256,
            "grain": "one product, one week, units shipped",
            "training_window": [config.TRAIN_START, config.TRAIN_END],
            "cohort_rule": f">= {config.COHORT_MIN_NONZERO:.0%} non-zero weeks over "
                           f"the {config.N_TRAIN} training weeks",
            "population": config.DATASET_POPULATION,
        },
        "evaluation": {
            "held_out_window": [config.TEST_START, config.TEST_END],
            "scored_once": True,
            "rows": held_out["rows"],
            "MAE_units": held_out["MAE"],
            "RMSE_units": held_out["RMSE"],
            "MAE_of_a_flat_zero_forecast": held_out["MAE_of_flat_zero"],
            "coverage_delivered": held_out["coverage_at_nominal_80"],
            "coverage_promised": config.NOMINAL_COVERAGE,
            "median_band_units": held_out["median_band_units"],
            "band_over_median_demand": held_out["band_over_median_demand"],
            "pinball_10_50_90": [held_out["pinball_10"], held_out["pinball_50"],
                                 held_out["pinball_90"]],
            "metric_not_reported": (
                "MAPE. On this data a flat-zero forecast beats the model on MAPE. "
                "See evaluation.json."
            ),
        },
        "known_limitations": [
            f"The band is {held_out['band_over_median_demand']:.2f}x the median "
            "non-zero week. An honest interval on weekly retail demand is wider than "
            "the forecast, and a buyer has to be told that before they see it.",
            "Coverage falls inside the Oct-Nov ramp on the most seasonal products, "
            "and the misses there are above the band - the direction that empties a "
            "shelf.",
            "One year of history means seasonal-naive has one noisy observation per "
            "week, so the model carries no explicit seasonality at all.",
            f"{config.TOTAL_PRODUCTS - config.COHORT_SIZE:,} of "
            f"{config.TOTAL_PRODUCTS:,} products are refused, not forecast badly. "
            "That is the honest answer for them, and it is also a limitation.",
            "The residual quantiles assume this product's past errors describe its "
            "future errors. A new product, a promotion, or a price change breaks it.",
            "Every cost figure is a labeled classroom assumption and none of it is "
            "any real retailer's economics.",
        ],
        "monitoring": (
            "Refit weekly. Re-check coverage on a rolling 13-week window: if it drops "
            "below 75% against a promised 80%, the residual quantiles no longer "
            "describe the errors and the band must be rebuilt before it is shown to "
            "a buyer."
        ),
    }


def build_operating_policy(forecaster, prices: pd.Series) -> dict:
    """The order rule, its economics, and the sentence about who decides."""
    median_price = float(prices.reindex(forecaster.product_ids).median())
    return {
        "policy_version": config.POLICY_VERSION,
        "model_version": forecaster.version,
        "decision": (
            "Order the quantity at the newsvendor critical ratio cu / (cu + co), read "
            "off this product's own residual band."
        ),
        "critical_ratios": {
            f"{ratio}:1": round(policy.critical_ratio(ratio, 1.0), 4)
            for ratio in config.RATIOS_TAUGHT
        },
        "ratios_swept": list(config.RATIOS_SWEPT),
        "overstock_cost_co": {
            "formula": f"{config.CO_FRACTION} x unit_price per unit per week",
            "median_product": round(config.CO_FRACTION * median_price, 4),
            "is_a_classroom_assumption": True,
        },
        "understock_cost_cu": {
            "formula": "ratio x co",
            "at_4_to_1_median_product": round(4 * config.CO_FRACTION * median_price, 4),
            "is_a_classroom_assumption": True,
        },
        "cost_assumption_note": config.COST_ASSUMPTION_NOTE,
        "costs_are_classroom_assumptions": True,
        "cohort_rule": {
            "min_nonzero_share": config.COHORT_MIN_NONZERO,
            "measured_on": f"the {config.N_TRAIN} training weeks only",
            "size": len(forecaster.product_ids),
            "products_refused": config.TOTAL_PRODUCTS - len(forecaster.product_ids),
        },
        "forecast_rule": {
            "window_weeks": config.WINDOW,
            "nominal_low": config.NOMINAL_LO,
            "nominal_high": config.NOMINAL_HI,
            "nominal_coverage": config.NOMINAL_COVERAGE,
            "clipped_at_zero": True,
            "horizon_weeks": 1,
        },
        "split": {
            "train": [config.TRAIN_START, config.TRAIN_END],
            "test": [config.TEST_START, config.TEST_END],
            "shuffled": False,
        },
        "human_authority": config.HUMAN_AUTHORITY,
        "prohibited_claims": list(config.PROHIBITED_CLAIMS),
        "fallback": (
            "A product outside the cohort gets no forecast and no order quantity. It "
            "is returned as 'not forecastable' and routed to a buyer, never given a "
            "silent zero."
        ),
        "recalibration": (
            "Refit weekly on the latest 76 weeks. Rebuild the band whenever rolling "
            "13-week coverage falls below 75%."
        ),
    }


# ── Export and verify ───────────────────────────────────────────────────────

def export(forecaster, evidence: dict, manifest: pd.DataFrame, prices: pd.Series,
           artifact_dir: Path = config.ARTIFACT_DIR) -> dict[str, str]:
    """Write the five artifacts. Nothing else leaves the notebook."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # compress=3: the state is 469 x 68 float64 residuals, which zlib halves.
    # Compression is lossless, so ``verify`` still has to land bitwise-identical.
    joblib.dump(forecaster, artifact_dir / "forecaster.joblib", compress=3)
    (artifact_dir / "evaluation.json").write_text(
        json.dumps(evidence, indent=1), encoding="utf-8")
    (artifact_dir / "operating_policy.json").write_text(
        json.dumps(build_operating_policy(forecaster, prices), indent=1),
        encoding="utf-8")
    (artifact_dir / "model_card.json").write_text(
        json.dumps(build_model_card(forecaster, evidence, prices), indent=1),
        encoding="utf-8")
    manifest.to_parquet(artifact_dir / "sample_manifest.parquet",
                        compression="zstd", index=False)

    return {name: f"{(artifact_dir / name).stat().st_size:,} bytes"
            for name in ARTIFACT_NAMES}


def verify(panel: pd.DataFrame, scored: pd.DataFrame, forecaster=None,
           artifact_dir: Path = config.ARTIFACT_DIR) -> dict:
    """Reload the exported forecaster and re-score the whole holdout.

    The check is bitwise, not approximate, and it covers the two things a
    planning service actually reads: the point forecast and both edges of the
    band. A saved model that returns a band one unit wider than the one the
    notebook measured is a model whose coverage number is a fiction.
    """
    artifact_dir = Path(artifact_dir)
    reloaded = joblib.load(artifact_dir / "forecaster.joblib")
    saved_policy = json.loads(
        (artifact_dir / "operating_policy.json").read_text(encoding="utf-8"))
    saved_card = json.loads(
        (artifact_dir / "model_card.json").read_text(encoding="utf-8"))
    saved_manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")

    rescored = forecast.score_holdout(panel, reloaded)
    columns = ["point", "low", "median", "high"]
    reference = scored.sort_values(["StockCode", "week"]).reset_index(drop=True)
    fresh = rescored.sort_values(["StockCode", "week"]).reset_index(drop=True)

    aligned = bool(
        (reference["StockCode"].to_numpy() == fresh["StockCode"].to_numpy()).all()
        and (reference["week"].to_numpy() == fresh["week"].to_numpy()).all()
    )
    differences = {column: float(np.max(np.abs(reference[column].to_numpy()
                                               - fresh[column].to_numpy())))
                   for column in columns}
    identical = aligned and all(
        bool((reference[column].to_numpy() == fresh[column].to_numpy()).all())
        for column in columns
    )

    # The order quantity is what the service actually returns, so check it too:
    # the in-memory forecaster against the one that came back off the disk.
    order_differences = {}
    if forecaster is not None:
        for ratio in config.RATIOS_TAUGHT:
            critical = policy.critical_ratio(ratio, 1.0)
            before = np.array([forecaster.quantile(code, critical)
                               for code in forecaster.product_ids])
            after = np.array([reloaded.quantile(code, critical)
                              for code in forecaster.product_ids])
            order_differences[f"{ratio}:1"] = float(np.max(np.abs(before - after)))
            identical = identical and bool((before == after).all())

    summary = metrics.score_frame(fresh)
    result = {
        "rows_rescored": int(len(fresh)),
        "products": int(fresh["StockCode"].nunique()),
        "rows_aligned": aligned,
        "max_abs_difference": differences,
        "max_abs_order_difference": order_differences,
        "forecasts_bitwise_identical": identical,
        "coverage_after_reload": round(summary["coverage_80"], 6),
        "MAE_after_reload": round(summary["MAE"], 6),
        "version_from_disk": reloaded.version,
        "policy_version_from_disk": saved_policy["policy_version"],
        "critical_ratios_from_disk": saved_policy["critical_ratios"],
        "model_card_version": saved_card["version"],
        "manifest_rows": int(len(saved_manifest)),
        "status": "identical" if identical else "DRIFTED",
    }
    if not identical:
        raise AssertionError(
            "The reloaded forecaster does not reproduce the notebook's forecasts:\n"
            + json.dumps(result, indent=1)
        )
    return result
