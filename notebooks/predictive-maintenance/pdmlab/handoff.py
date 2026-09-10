"""Export and verify the narrow artifact contract consumed by the PdM service.

Five files leave the notebook, and nothing else:

- ``model.joblib``            the fitted detector: six medians, six scales, six directions
- ``model_card.json``         intended use, provenance, measured results, limits
- ``evaluation.json``         every table the governance view needs
- ``operating_policy.json``   the threshold, the three routes, the costs, the boundary
- ``sample_manifest.parquet`` eight packaged windows with their hour-by-hour scores

The detector is about two kilobytes because it is twelve numbers. That is a
feature for a classroom, not a limitation: a student can open the policy JSON
and read the entire model.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from . import config, detect, metrics, policy


# ── Sample windows ──────────────────────────────────────────────────────────

def sample_windows(score: pd.Series) -> list[dict]:
    """The eight windows the demo ships with, chosen by rule, not by taste.

    Fixed by name: one clean training-era week, one clean post-drift week, and
    the 24 h before each documented failure through its documented end.
    Chosen by measurement: the strongest drift-induced false alarm on clean
    hours (S6), and the longest clean stretch that sits in the watch band
    without ever crossing (S7).
    """
    _credit, ambiguous = metrics.window_masks(score.index)
    clean = ~ambiguous
    scored = pd.DataFrame({"score": score, "clean": clean}).dropna()
    scored = scored[scored.index >= config.SCORED_START]

    alerting = scored[scored["clean"] & (scored["score"] >= config.THRESHOLD)]
    false_episodes = metrics.episodes(alerting.index)
    false_episodes.sort(key=lambda pair: -float(score[pair[0]:pair[1]].max()))
    worst_false = false_episodes[0]

    band = scored[scored["clean"] & (scored["score"] >= 4.0) & (scored["score"] < config.THRESHOLD)]
    band_runs = metrics.episodes(band.index)
    band_runs.sort(key=lambda pair: -(pair[1] - pair[0]))
    longest_band = band_runs[0]

    windows = [
        {
            "sample_id": "S1_clean_training_week",
            "label": "A clean week in the training months",
            "start": pd.Timestamp("2020-02-15"), "end": pd.Timestamp("2020-02-21 23:00"),
            "purpose": "What normal looks like. The score never leaves the no-action band.",
        },
        {
            "sample_id": "S2_F1_worst_failure",
            "label": "F1: 24 h before onset through the documented window",
            "start": pd.Timestamp("2020-04-18") - pd.Timedelta(hours=24),
            "end": pd.Timestamp("2020-04-18 23:59"),
            "purpose": "The year's most severe documented air leak.",
        },
        {
            "sample_id": "S3_F2_overnight_leak",
            "label": "F2: 24 h before onset through the documented window",
            "start": pd.Timestamp("2020-05-29 23:30") - pd.Timedelta(hours=24),
            "end": pd.Timestamp("2020-05-30 06:00"),
            "purpose": "Flat all day, then a step at the onset hour.",
        },
        {
            "sample_id": "S4_F3_zero_warning",
            "label": "F3: 24 h before onset through the documented window",
            "start": pd.Timestamp("2020-06-05 10:00") - pd.Timedelta(hours=24),
            "end": pd.Timestamp("2020-06-07 14:30"),
            "purpose": "The zero-warning case: 36 flat hours, then 3.4 to 11.6 in one hour.",
        },
        {
            "sample_id": "S5_F4_real_warning",
            "label": "F4: 24 h before onset through the documented window",
            "start": pd.Timestamp("2020-07-15 14:30") - pd.Timedelta(hours=24),
            "end": pd.Timestamp("2020-07-15 19:00"),
            "purpose": "The only genuine advance warning: crosses 6.0 fourteen and a half hours early.",
        },
        {
            "sample_id": "S6_drift_false_alarm",
            "label": "Drift-induced false alarm on a healthy machine",
            "start": worst_false[0] - pd.Timedelta(hours=6),
            "end": worst_false[1] + pd.Timedelta(hours=6),
            "purpose": "No documented failure. The compressor is simply busier than the February baseline.",
        },
        {
            "sample_id": "S7_borderline_watch",
            "label": "Borderline: sits in the watch band and never crosses",
            "start": longest_band[0] - pd.Timedelta(hours=6),
            "end": longest_band[1] + pd.Timedelta(hours=6),
            "purpose": "Move the threshold two points and this flips from logged to a callout.",
        },
        {
            "sample_id": "S8_clean_after_drift",
            "label": "A clean week after the operating regime changed",
            "start": pd.Timestamp("2020-08-08"), "end": pd.Timestamp("2020-08-14 23:00"),
            "purpose": "Same machine, healthy, but the summer duty cycle.",
        },
    ]
    return windows


def build_manifest(score: pd.Series, contributions: pd.DataFrame) -> pd.DataFrame:
    """One row per packaged window, carrying its hour-by-hour scores."""
    rows = []
    for window in sample_windows(score):
        hours = score[(score.index >= window["start"]) & (score.index <= window["end"])]
        if len(hours) == 0:
            raise ValueError(f"{window['sample_id']} selected an empty window.")
        peak_at = hours.idxmax()
        driver, driver_z = detect.top_driver(contributions, peak_at)
        routes = hours.map(policy.route)
        rows.append({
            "sample_id": window["sample_id"],
            "label": window["label"],
            "start": str(window["start"]),
            "end": str(window["end"]),
            "hours_with_data": int(len(hours)),
            "peak_score": round(float(hours.max()), 2),
            "peak_at": str(peak_at),
            "median_score": round(float(hours.median()), 2),
            "work_order_hours": int((routes == config.ROUTE_WORK_ORDER).sum()),
            "watch_hours": int((routes == config.ROUTE_WATCH).sum()),
            "route_at_peak": policy.route(float(hours.max())),
            "top_driver_at_peak": config.FEATURE_DISPLAY_NAMES[driver],
            "top_driver_z": driver_z,
            "covers_documented_failure": any(
                window["start"] <= end and start <= window["end"]
                for _n, start, end, _d in config.failure_windows()
            ),
            "purpose": window["purpose"],
            "hourly_scores": json.dumps([
                {"hour": str(stamp), "score": round(float(value), 3), "route": policy.route(float(value))}
                for stamp, value in hours.items()
            ]),
        })
    return pd.DataFrame(rows)


# ── Evidence ────────────────────────────────────────────────────────────────

def _records(frame: pd.DataFrame) -> list[dict]:
    def clean(value):
        if isinstance(value, (np.floating, float)):
            return None if pd.isna(value) else round(float(value), 4)
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (pd.Timestamp,)):
            return str(value)
        return value
    return [{k: clean(v) for k, v in record.items()} for record in frame.to_dict("records")]


def assemble_evidence(
    coverage: pd.DataFrame,
    pre_onset: pd.DataFrame,
    dropna_damage: pd.DataFrame,
    effects: pd.DataFrame,
    model_compare: pd.DataFrame,
    scaling: pd.DataFrame,
    lead_times: pd.DataFrame,
    sweep: pd.DataFrame,
    baselines: pd.DataFrame,
    naive_drift: pd.DataFrame,
    detector_drift: pd.DataFrame,
    mitigations: pd.DataFrame,
    monthly_load: pd.DataFrame,
    training_alerts: dict,
    dev_sweep: pd.DataFrame,
    test_detection: dict,
    test_policy: dict,
    test_never: dict,
    full_policy: dict,
    full_never: dict,
    runtime_seconds: float,
) -> dict:
    """The complete ``evaluation.json`` payload, assembled in one place."""
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_coverage": {
            "summary": _records(coverage),
            "pre_onset_coverage": _records(pre_onset),
            "note": (
                "Of the 5,116-hour calendar span, 700 hours (13.7%) carry no reading "
                "at all and a further 200 are under half covered, leaving 4,216 scorable "
                "hours (82.4%). Counted in minutes, 17.7% of the record is missing - the "
                "equivalent of 904 hours - across 331 separate recorder gaps longer than a "
                "minute. The gaps land in pre-onset windows: of the 24 hours before each "
                "failure, F1 and F2 have 20 with data, F4 has 18, and only F3 has all 24."
            ),
        },
        "feature_bug": {
            "description": (
                "Rest minutes and pressure fall rate are undefined exactly when the "
                "compressor never rests, which is what the two worst failures look like. "
                "A naive dropna() deletes those rows silently."
            ),
            "hours_deleted_per_failure": _records(dropna_damage),
        },
        "feature_effect_sizes": _records(effects),
        "model_comparison": _records(model_compare),
        "scaling_comparison": _records(scaling),
        "threshold_lead_times": _records(lead_times),
        "threshold_sweep_costs": _records(sweep),
        "baseline_policies": _records(baselines),
        "drift": {
            "naive_single_feature_pct_clean_hours_alerting": _records(naive_drift),
            "detector_false_callouts_by_month": _records(detector_drift),
            "mitigations": _records(mitigations),
            "monthly_alert_load_at_operating_threshold": _records(monthly_load),
            "cruel_interaction": (
                "The low threshold that buys lead time is the one that floods the queue. "
                "At threshold 3 the detector goes from 3 false callouts in April to 30 in "
                "August with no change in the machine; at threshold 6 it holds at 1-3 but "
                "gives advance warning on only one of the four failures."
            ),
        },
        "training_window_not_clean": training_alerts,
        "threshold_selection_on_dev": _records(dev_sweep),
        "test_frozen": {
            "window": [str(config.TEST_START.date()), str(config.TEST_END.date())],
            "scored_once": True,
            **{k: v for k, v in test_detection.items() if k != "per_failure"},
            "per_failure": test_detection["per_failure"],
            "policy": {k: v for k, v in test_policy.items() if k != "detail"},
            "policy_detail": test_policy["detail"],
            "never_alert_baseline": test_never,
            "honest_roi_note": (
                f"On the held-out window alone the detector costs "
                f"${test_policy['total_cost_usd']:,} against never-alert's "
                f"${test_never['total_cost_usd']:,}. It LOSES on cost here. The favorable "
                f"full-period figure (${full_policy['total_cost_usd']:,} against "
                f"${full_never['total_cost_usd']:,}) rests entirely on F3, a single "
                f"52.5-hour event. Four events cannot support an ROI claim."
            ),
        },
        "full_period_policy": {k: v for k, v in full_policy.items() if k != "detail"},
        "full_period_never_alert": full_never,
        "runtime_seconds_end_to_end": round(float(runtime_seconds), 2),
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "random_state": config.RANDOM_STATE,
        },
    }


def build_model_card(detector: detect.RobustZDetector, evidence: dict) -> dict:
    test = evidence["test_frozen"]
    return {
        "model_name": "MetroPT-3 compressor air-leak detector",
        "version": "1.0",
        "course": "ITAI 2372 Module 5 - AI in Manufacturing and Industrial Operations",
        "intended_use": (
            "Rank hours of compressor sensor data by how far they sit from the machine's "
            "own quiet-months normal, so a maintenance planner can decide which hours "
            "deserve a technician's attention."
        ),
        "not_for": [
            "Forecasting a failure days or weeks ahead.",
            "Locking out, stopping, or certifying equipment.",
            "Any decision about whether it is safe for a person to work on the machine.",
            "Any compressor other than this one, on any other duty cycle.",
        ],
        "authority_boundary": config.CLAIM_BOUNDARY_LONG,
        "model_type": config.MODEL_TYPE,
        "how_it_works": (
            "For each of six hourly features, measure how far this hour sits from the "
            "training median, in units of the training MAD x 1.4826. Keep only deviation "
            "in the direction that means trouble. Average the six. The entire fitted "
            "model is six medians and six scales."
        ),
        "features": [
            {
                "name": name,
                "display_name": config.FEATURE_DISPLAY_NAMES[name],
                "planner_question": config.FEATURE_QUESTION[name],
                "direction_that_means_trouble": "higher" if config.FEATURE_DIRECTION[name] > 0 else "lower",
                "training_median": round(float(detector.median_[name]), 6),
                "training_scale": round(float(detector.scale_[name]), 6),
            }
            for name in config.MODEL_FEATURES
        ],
        "training_data": {
            "dataset": config.DATASET_NAME,
            "uci_id": config.DATASET_UCI_ID,
            "license": config.DATASET_LICENSE,
            "url": config.DATASET_URL,
            "citation": config.DATASET_CITATION,
            "raw_sampling": config.RAW_SAMPLING_NOTE,
            "committed_resolution": "1-minute means, aggregated to hourly features",
            "training_window": [str(config.TRAIN_START.date()), str(config.TRAIN_END.date())],
            "population": config.DATASET_POPULATION,
        },
        "evaluation": {
            "ground_truth": "Four documented air-leak failures from the operator's maintenance reports.",
            "held_out_window": test["window"],
            "failures_detected": test["failures_detected"],
            "first_alert": test["per_failure"]["F4"].get("first_alert"),
            "lead_hours": test["per_failure"]["F4"].get("lead_hours"),
            "false_alarm_rate_on_clean_hours": test["false_alarm_rate_on_clean_hours"],
            "false_callouts_per_month": test["false_callouts_per_month"],
            "statistical_power": (
                "Four events. No confidence interval is possible, and none is quoted. "
                "Every number here is anecdotal evidence about one machine."
            ),
        },
        "known_limitations": [
            "Three of the four documented failures give zero advance warning.",
            "904 hours of the record are missing, and the gaps land in pre-onset windows.",
            "44 of the 1,227 'clean' training hours score above the operating threshold; "
            "we call them normal because nobody filed a work order.",
            "A healthy May day scores 12.07 while the year's worst failure scores 12.08.",
            "On the held-out window alone the detector costs more than never alerting.",
            "The score is dominated by the working-hard share feature, whose MAD is small "
            "because the compressor idles most nights.",
            "All cost figures are synthetic classroom assumptions.",
        ],
        "monitoring": config.RECALIBRATION,
    }


def build_operating_policy(detector: detect.RobustZDetector) -> dict:
    return {
        "policy_version": "1.0",
        "threshold": config.THRESHOLD,
        "watch_threshold": config.WATCH_THRESHOLD,
        "routes": config.ROUTES,
        "route_values": {
            "work_order": config.ROUTE_WORK_ORDER,
            "watch": config.ROUTE_WATCH,
            "no_action": config.ROUTE_NO_ACTION,
        },
        "merge_gap_hours": config.MERGE_GAP_HOURS,
        "response_hours": config.COSTS["response_hours"],
        "features": config.MODEL_FEATURES,
        "display_names": config.FEATURE_DISPLAY_NAMES,
        "direction_that_means_trouble": config.FEATURE_DIRECTION,
        "detector_state": detector.state(),
        "threshold_selected_on": [str(config.DEV_START.date()), str(config.DEV_END.date())],
        "training_window": [str(config.TRAIN_START.date()), str(config.TRAIN_END.date())],
        "held_out_test": [str(config.TEST_START.date()), str(config.TEST_END.date())],
        "costs_synthetic": config.COSTS,
        "costs_are_synthetic": True,
        "boundary_statement": config.CLAIM_BOUNDARY,
        "claim_boundary_long": config.CLAIM_BOUNDARY_LONG,
        "recalibration": config.RECALIBRATION,
        "fallback": (
            "An hour with less than 50% sensor coverage is not scored. It is reported as "
            "'no data' and routed to a human, never silently treated as normal."
        ),
    }


# ── Export and verify ───────────────────────────────────────────────────────

def export(detector, evidence: dict, manifest: pd.DataFrame,
           artifact_dir: Path = config.ARTIFACT_DIR) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.joblib"
    joblib.dump(detector, model_path)
    (artifact_dir / "evaluation.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
    (artifact_dir / "operating_policy.json").write_text(
        json.dumps(build_operating_policy(detector), indent=1), encoding="utf-8")
    (artifact_dir / "model_card.json").write_text(
        json.dumps(build_model_card(detector, evidence), indent=1), encoding="utf-8")
    manifest.to_parquet(artifact_dir / "sample_manifest.parquet", compression="zstd", index=False)

    sizes = {}
    for name in ("model.joblib", "model_card.json", "operating_policy.json",
                 "evaluation.json", "sample_manifest.parquet"):
        sizes[name] = f"{(artifact_dir / name).stat().st_size:,} bytes"
    return sizes


_VERIFY_SCRIPT = r"""
import json, sys
from pathlib import Path
project = Path(sys.argv[1])
sys.path.insert(0, str(project))
import joblib, pandas as pd
from pdmlab import config, data, features, policy

detector = joblib.load(config.ARTIFACT_DIR / "model.joblib")
saved_policy = json.loads((config.ARTIFACT_DIR / "operating_policy.json").read_text())
matrix = features.model_matrix(features.hourly_features(data.load_minutes())).dropna()
sample = matrix.iloc[: int(sys.argv[3])]
scores = detector.score(sample)
reference = pd.read_parquet(sys.argv[2])["score"]
identical = bool((scores.to_numpy() == reference.to_numpy()).all())
routes_new = scores.map(policy.route)
routes_old = reference.map(policy.route)
print(json.dumps({
    "rows": int(len(scores)),
    "max_abs_difference": float((scores - reference).abs().max()),
    "scores_bitwise_identical": identical,
    "route_changes": int((routes_new.to_numpy() != routes_old.to_numpy()).sum()),
    "threshold_from_disk": saved_policy["threshold"],
    "alerts_in_sample": int((scores >= saved_policy["threshold"]).sum()),
    "status": "identical" if identical else "DRIFTED",
}))
"""


def verify(matrix: pd.DataFrame, detector, rows: int = 500) -> dict:
    """Rebuild the features and rescore in a FRESH process, then compare.

    This is stronger than reloading in the same kernel. The subprocess reads
    the committed parquet, recomputes every feature from scratch, loads
    ``model.joblib`` from disk, and has to land on bitwise-identical scores.
    Anything less would mean the service could quietly compute a feature one
    way while the notebook computed it another.
    """
    reference = detector.score(matrix.iloc[:rows]).to_frame("score")
    with tempfile.TemporaryDirectory() as folder:
        reference_path = Path(folder) / "reference_scores.parquet"
        reference.to_parquet(reference_path)
        script_path = Path(folder) / "verify_fresh.py"
        script_path.write_text(_VERIFY_SCRIPT, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(script_path), str(config.PROJECT_DIR),
             str(reference_path), str(rows)],
            capture_output=True, text=True, check=True, cwd=str(config.PROJECT_DIR),
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])
