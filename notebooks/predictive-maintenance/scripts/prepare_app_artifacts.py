"""Run the full predictive-maintenance workflow headlessly and export artifacts.

Same steps and same frozen decisions as the notebook (committed parquet ->
hourly features -> detector fit on Feb-Mar -> threshold frozen on Apr-Jun ->
single scoring of Jul-Sep -> export -> fresh-process reload check), so a
`prepare:pdm` script reproduces the exact files the notebook commits evidence
for. Nothing downloads.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pdmlab import config, data, detect, features, handoff, metrics, policy  # noqa: E402


def main() -> None:
    started = time.time()
    print("Loading the committed 1-minute parquet and rebuilding the hourly grid...")
    minutes = data.load_minutes()
    hourly = features.hourly_features(minutes)
    matrix = features.model_matrix(hourly).dropna()
    print(f"  {len(minutes):,} minutes -> {len(hourly):,} scorable hours")

    print("Fitting the detector on February-March only...")
    detector = detect.fit_detector(matrix)
    score = detector.score(matrix)
    contributions = detector.score_frame(matrix)

    print("Measuring the comparison models and the drift tables...")
    model_compare = metrics.compare_models(detect.candidate_scores(matrix))
    scaling = metrics.scaling_comparison(detect.scaling_variants(matrix))
    lead_times = metrics.lead_time_table(score)
    effects = features.effect_sizes(hourly, matrix)

    full_window = (config.SCORED_START, config.SCORED_END)
    sweep = policy.threshold_sweep(score, full_window)
    baselines = policy.baseline_table(full_window)
    naive_drift = metrics.naive_single_feature_drift(contributions)
    detector_drift = metrics.detector_callouts_by_month(score)
    rolling = {f"Rolling {days}-day baseline": detect.rolling_baseline_score(matrix, days)
               for days in (7, 14, 28)}
    mitigations = metrics.mitigation_table(score, rolling, threshold=4.0, high_threshold=7.0)
    monthly_load = metrics.monthly_alert_load(score, config.THRESHOLD)
    training_alerts = metrics.training_window_alerts(score, config.THRESHOLD)

    print("Scoring the untouched July-September window once...")
    dev_sweep = policy.threshold_sweep(score, (config.DEV_START, config.DEV_END),
                                       [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    test_window = (config.TEST_START, config.TEST_END)
    test_detection = metrics.evaluate(score, config.THRESHOLD, test_window)
    test_policy = policy.policy_cost(score, config.THRESHOLD, test_window)
    test_never = policy.never_alert(test_window)
    full_policy = policy.policy_cost(score, config.THRESHOLD, full_window)
    full_never = policy.never_alert(full_window)

    evidence = handoff.assemble_evidence(
        data.coverage_summary(minutes), data.pre_onset_coverage(minutes),
        features.dropna_damage(hourly), effects, model_compare, scaling, lead_times,
        sweep, baselines, naive_drift, detector_drift, mitigations, monthly_load,
        training_alerts, dev_sweep, test_detection, test_policy, test_never,
        full_policy, full_never, time.time() - started,
    )

    print("Packaging the demo windows and exporting...")
    manifest = handoff.build_manifest(score, contributions)
    sizes = handoff.export(detector, evidence, manifest)
    identity = handoff.verify(matrix, detector)

    for name, size in sizes.items():
        print(f"  {name:<26} {size}")
    print(
        f"\nFrozen test: {test_detection['failures_detected']}/1 caught, "
        f"{test_detection['per_failure']['F4']['lead_hours']} h lead, "
        f"{test_detection['false_callouts']} false callouts in "
        f"{test_detection['months']} months, ${test_policy['total_cost_usd']:,} "
        f"against never-alert's ${test_never['total_cost_usd']:,}."
    )
    print(
        f"Reload: {identity['status']}, max difference {identity['max_abs_difference']:.3e}, "
        f"{identity['route_changes']} route changes."
    )
    print(f"Manifest: {len(manifest)} windows, "
          f"{int(manifest['covers_documented_failure'].sum())} on documented failures.")
    print(f"Ready in {time.time() - started:.1f}s.")


if __name__ == "__main__":
    main()
