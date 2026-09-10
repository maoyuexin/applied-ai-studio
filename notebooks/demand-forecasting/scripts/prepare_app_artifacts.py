"""Run the full demand-forecasting workflow headlessly and export the artifacts.

Same steps and the same frozen decisions as the notebook (committed weekly CSV
-> dense 102-week panel -> cohort chosen on the TRAINING weeks only -> MA8 fit
-> rolling one-step-ahead scoring of the 26 held-out weeks -> newsvendor sweep
-> export -> reload check), so a ``prepare:forecast`` script reproduces the exact
files the notebook commits evidence for.

Nothing downloads. The whole run is well under a minute.

    python scripts/prepare_app_artifacts.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from fclab import (config, data, features, forecast, handoff,  # noqa: E402
                   intervals, metrics, policy)


def main() -> None:
    started = time.time()

    print("Loading the committed weekly CSV and building the dense panel...")
    weekly = data.load_weekly()
    panel, names, prices = data.build_panel(weekly)
    print(f"  {len(weekly):,} product-weeks -> {panel.shape[0]:,} products x "
          f"{panel.shape[1]} complete weeks")
    if panel.shape[1] != config.TOTAL_WEEKS:
        raise SystemExit(f"Expected {config.TOTAL_WEEKS} weeks, found {panel.shape[1]}.")

    print(f"Selecting the cohort on the {config.N_TRAIN} TRAINING weeks only...")
    cohort = features.select_cohort(panel)
    intermittent = features.intermittent_set(panel)
    leakage = features.leakage_evidence(panel)
    print(f"  {len(cohort)} products kept, {panel.shape[0] - len(cohort):,} refused "
          f"(the same rule read over all {config.TOTAL_WEEKS} weeks would admit "
          f"{leakage['leaky_size']} - that difference is the leak)")
    print(" ", config.check_named_products(names, cohort))

    print("Fitting: one subtraction and one percentile per product...")
    forecaster = forecast.fit(panel, cohort, names, prices)

    print("Scoring the 26 held-out weeks, one step ahead, rolling origin...")
    scored = forecast.score_holdout(panel, forecaster)
    summary = metrics.score_frame(scored)
    frozen = handoff.assert_frozen(summary)
    print(f"  {summary['n_rows']:,} product-weeks scored once")

    print("Measuring the baselines and the three interval methods...")
    baselines = forecast.baseline_table(panel, cohort)
    design = features.design_matrix(panel, cohort)
    interval_table, _extra = intervals.comparison_table(design)

    print("Pricing the order: the newsvendor sweep and the cost curve...")
    board = policy.PolicyBoard(panel, scored, forecaster, prices)
    sweep = board.sweep()
    cost_curve = board.cost_curve()
    outcomes = board.outcome_split()
    per_product = board.per_product(4)

    print("Assembling the evidence and packaging the demo products...")
    evidence = handoff.assemble_evidence(
        data.provenance_summary(weekly),
        data.panel_summary(panel),
        features.cohort_rule_comparison(panel),
        leakage,
        baselines,
        interval_table,
        summary,
        metrics.mape_demonstration(panel, cohort, intermittent, scored),
        intervals.coverage_by_week(scored),
        intervals.seasonal_coverage(scored, features.q4_skew(panel, cohort)),
        sweep,
        cost_curve,
        outcomes,
        frozen,
        time.time() - started,
    )
    manifest = handoff.sample_manifest(panel, scored, per_product, names, prices)

    print("Exporting and reloading...")
    sizes = handoff.export(forecaster, evidence, manifest, prices)
    identity = handoff.verify(panel, scored, forecaster)

    # ── What was written ────────────────────────────────────────────────────
    print("\nArtifacts")
    for name, size in sizes.items():
        print(f"  {name:<24} {size}")

    print("\nFrozen holdout (scored once, never tuned)")
    print(f"  products x weeks          {summary['n_products']} x "
          f"{summary['n_test_weeks']} = {summary['n_rows']:,} rows")
    print(f"  MAE                       {summary['MAE']:.2f} units "
          f"(a flat-zero forecast: {summary['MAE_flat_zero']:.2f})")
    print(f"  RMSE                      {summary['RMSE']:.2f} units")
    print(f"  coverage @ nominal {config.NOMINAL_COVERAGE:.0%}    "
          f"{summary['coverage_80']:.2%}")
    print(f"  median band width         {summary['median_band']:.2f} units "
          f"({summary['band_over_median_demand']:.2f}x the median non-zero week)")
    print(f"  pinball @ 0.1 / 0.5 / 0.9 {summary['pinball_10']:.3f} / "
          f"{summary['pinball_50']:.3f} / {summary['pinball_90']:.3f}")
    print(f"  frozen-target check       "
          f"{'all OK' if (frozen['status'] == 'OK').all() else 'DRIFTED'} "
          f"({len(frozen)} numbers)")

    print("\nNewsvendor policy (CLASSROOM ASSUMPTION: co = "
          f"{config.CO_FRACTION:.2f} x unit price)")
    for ratio in config.RATIOS_TAUGHT:
        row = sweep[sweep["ratio"] == f"{ratio}:1"].iloc[0]
        print(f"  {ratio}:1  cr {row['critical_ratio']:.3f}  "
              f"cost {row['vs_point_pct']:+.1f}% vs point, "
              f"{row['vs_mean_pct']:+.1f}% vs mean  |  units short "
              f"{row['shortfall_point']:,.0f} -> {row['shortfall_quantile']:,.0f}")
    at_four = outcomes[outcomes["ratio"] == "4:1"].iloc[0]
    print(f"  at 4:1 the rule is cheaper on {at_four['cheaper']} of "
          f"{at_four['products']} products and MORE expensive on "
          f"{at_four['more_expensive']}")

    print("\nReload check (fresh object off the disk, whole holdout re-scored)")
    print(f"  status                    {identity['status']}")
    print(f"  rows re-scored            {identity['rows_rescored']:,}")
    print("  max difference            "
          + ", ".join(f"{k} {v:.3e}"
                      for k, v in identity["max_abs_difference"].items()))
    print("  order quantity difference "
          + ", ".join(f"{k} {v:.3e}"
                      for k, v in identity["max_abs_order_difference"].items()))
    print(f"  versions from disk        model {identity['version_from_disk']}, "
          f"policy {identity['policy_version_from_disk']}")
    print(f"  manifest                  {identity['manifest_rows']} products, "
          f"{int(manifest['policy_is_cheaper'].sum())} where the policy wins and "
          f"{int((~manifest['policy_is_cheaper']).sum())} where it loses")

    print(f"\nReady in {time.time() - started:.1f}s. Nothing downloaded.")


if __name__ == "__main__":
    main()
