from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

from .config import REPOSITORY_ROOT
from .schemas import (
    BaselineCost,
    CoverageBlock,
    DatasetInfo,
    DiscussionCase,
    DriftBlock,
    DriftSpread,
    FeatureBug,
    FeatureFact,
    FeatureInfo,
    FrozenTest,
    HourScore,
    ModelInfo,
    MonthlyLoadRow,
    PolicyInfo,
    QueueResponse,
    SampleWindow,
    ScoreRequest,
    ScoreResponse,
    TrainingWindowNotClean,
)

# model.joblib pickles a *reference* to pdmlab.detect.RobustZDetector, so the
# notebook package has to be importable before joblib.load runs. Serving then
# rebuilds the hourly features with the notebook's own feature code and scores
# them with the notebook's own detector, rather than a second copy that could
# quietly drift away from the evidence the model card reports.
NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "predictive-maintenance"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from pdmlab import config as pdm, data, features, metrics  # noqa: E402
from pdmlab import policy as pdm_policy  # noqa: E402

ARTIFACT_FILES = (
    "model.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)

RECOVERY = (
    "Run notebooks/predictive-maintenance/01_pdm_build.ipynb or npm run prepare:pdm"
)

SCORE_NOTE = (
    "A distance from this compressor's own quiet-months normal, used to rank hours for "
    "attention. It is not a diagnosis and not a prediction that the machine will fail. "
    "A technician inspects the machine and decides."
)

BOUNDARY_SHORT = (
    "The system detects a fault developing now, within hours. It does not forecast days "
    "ahead, and it never locks out equipment. A technician inspects and decides."
)

ROUTE_LABELS = {
    "work_order": "Raise a work order",
    "watch": "Log it and watch",
    "no_action": "No action",
}

ROUTE_ACTIONS = {
    "work_order": (
        "A technician is called out and inspects the compressor within 4 hours. Nothing is "
        "shut down or locked out by the system; the technician decides what happens next."
    ),
    "watch": (
        "The hour is written into the shift report so the next shift sees it. Nobody is "
        "called out."
    ),
    "no_action": "Nothing happens. The hour looks like ordinary running for this machine.",
}

PLAIN_DIRECTION = {
    1: "Higher than usual means trouble",
    -1: "Lower than usual means trouble",
}


def _format_value(name: str, value: float) -> str:
    """One reading, in the units a maintenance planner would say out loud."""
    if name == "load_share":
        return f"{value * 100:.0f}% of the hour"
    if name == "cycles_per_hour":
        return f"{value:.0f} starts in the hour"
    if name == "rest_minutes_per_cycle":
        return f"{value:.1f} minutes of rest per start"
    if name == "oil_temp_mean":
        return f"{value:.1f} degrees C"
    if name == "tp3_std":
        return f"{value:.2f} bar of swing"
    if name == "pressure_fall_rate":
        return f"{value:.3f} bar per minute"
    return f"{value:.3f}"


def _month_name(period: str) -> str:
    """'2020-06' -> 'June 2020', so a sentence reads like a sentence."""
    return pd.Period(period, freq="M").strftime("%B %Y")


def _clean(value: object) -> object:
    """Make a notebook record safe for JSON: no NaN, no numpy scalars."""
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(rows: list[dict]) -> list[dict]:
    return [{key: _clean(item) for key, item in row.items()} for row in rows]


def _record(row: dict, drop: tuple[str, ...] = ()) -> dict:
    return {key: _clean(item) for key, item in row.items() if key not in drop}


class MaintenanceRuntime:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = Path(artifact_dir)
        missing = [name for name in ARTIFACT_FILES if not (self.artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing predictive-maintenance artifacts in {self.artifact_dir}: "
                f"{', '.join(missing)}. {RECOVERY}."
            )
        if not pdm.MINUTES_PARQUET.exists():
            raise FileNotFoundError(
                f"The committed 1-minute sensor file is missing at {pdm.MINUTES_PARQUET}. "
                f"{RECOVERY}."
            )

        self.card = json.loads((self.artifact_dir / "model_card.json").read_text())
        self.evaluation = json.loads((self.artifact_dir / "evaluation.json").read_text())
        self.policy = json.loads((self.artifact_dir / "operating_policy.json").read_text())
        self.detector = joblib.load(self.artifact_dir / "model.joblib")
        self.manifest = pd.read_parquet(self.artifact_dir / "sample_manifest.parquet")

        # The same three lines the notebook and prepare_app_artifacts.py run, in the
        # same order, so an hour scored here is the hour the evidence describes.
        minutes = data.load_minutes()
        hourly = features.hourly_features(minutes)
        self.matrix = features.model_matrix(hourly).dropna()
        self.hourly = hourly.loc[self.matrix.index]
        self.score = self.detector.score(self.matrix)
        self.contributions = self.detector.score_frame(self.matrix)

        self.threshold = float(self.policy["threshold"])
        self.watch_threshold = float(self.policy["watch_threshold"])
        self.window = (pdm.SCORED_START, pdm.SCORED_END)
        self.costs = {key: float(value) for key, value in self.policy["costs_synthetic"].items()}

    # ── readiness ───────────────────────────────────────────────────────────

    def artifact_readiness(self) -> dict[str, bool]:
        readiness = {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
        readiness["metropt_1min.parquet"] = pdm.MINUTES_PARQUET.exists()
        return readiness

    @property
    def model_version(self) -> str:
        return str(self.card["version"])

    # ── routing ─────────────────────────────────────────────────────────────

    def route_at(self, score: float, threshold: float) -> str:
        """The policy's own three-way rule, with the threshold made movable.

        The watch band keeps its width: move the callout line and the 'log it'
        line moves with it, so a low threshold cannot swallow the whole band.
        """
        watch = max(0.0, threshold - (self.threshold - self.watch_threshold))
        if score >= threshold:
            return pdm.ROUTE_WORK_ORDER
        if score >= watch:
            return pdm.ROUTE_WATCH
        return pdm.ROUTE_NO_ACTION

    # ── /api/maintenance/samples ────────────────────────────────────────────

    def samples(self, limit: int) -> list[SampleWindow]:
        rows = self.manifest.head(limit)
        return [
            SampleWindow(
                sample_id=str(row["sample_id"]),
                label=str(row["label"]),
                purpose=str(row["purpose"]),
                start=str(row["start"]),
                end=str(row["end"]),
                hours_with_data=int(row["hours_with_data"]),
                peak_score=float(row["peak_score"]),
                peak_at=str(row["peak_at"]),
                median_score=float(row["median_score"]),
                work_order_hours=int(row["work_order_hours"]),
                watch_hours=int(row["watch_hours"]),
                route_at_peak=str(row["route_at_peak"]),
                route_label_at_peak=ROUTE_LABELS[str(row["route_at_peak"])],
                top_driver_at_peak=str(row["top_driver_at_peak"]),
                top_driver_z=float(row["top_driver_z"]),
                covers_documented_failure=bool(row["covers_documented_failure"]),
            )
            for _, row in rows.iterrows()
        ]

    # ── /api/maintenance/score ──────────────────────────────────────────────

    def score_window(self, request: ScoreRequest) -> ScoreResponse:
        matches = self.manifest[self.manifest["sample_id"] == request.window_id]
        if matches.empty:
            known = ", ".join(self.manifest["sample_id"].astype(str))
            raise ValueError(
                f"Unknown packaged window '{request.window_id}'. Known windows: {known}."
            )
        row = matches.iloc[0]

        start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
        window = self.score[(self.score.index >= start) & (self.score.index <= end)]
        threshold = self.threshold if request.threshold is None else float(request.threshold)
        is_override = request.threshold is not None and threshold != self.threshold

        hours = [
            HourScore(
                hour=str(stamp),
                score=round(float(value), 3),
                route_at_policy=pdm_policy.route(float(value)),
                route_at_threshold=self.route_at(float(value), threshold),
                alerts=bool(float(value) >= threshold),
            )
            for stamp, value in window.items()
        ]
        alerting = [hour.hour for hour in hours if hour.alerts]
        peak_at = window.idxmax()
        peak_score = round(float(window.max()), 2)
        route_at_peak = self.route_at(float(window.max()), threshold)
        policy_route_at_peak = pdm_policy.route(float(window.max()))

        note = (
            f"Callout line moved to {threshold:g}. The frozen operating policy is "
            f"{self.threshold:g}; this is a what-if, not the policy."
            if is_override
            else f"The frozen operating policy: raise a work order at {self.threshold:g} or above."
        )

        return ScoreResponse(
            window_id=str(row["sample_id"]),
            label=str(row["label"]),
            purpose=str(row["purpose"]),
            start=str(row["start"]),
            end=str(row["end"]),
            hours_with_data=len(hours),
            threshold=threshold,
            policy_threshold=self.threshold,
            watch_threshold=self.watch_threshold,
            threshold_is_override=is_override,
            threshold_note=note,
            hours=hours,
            peak_score=peak_score,
            median_score=round(float(window.median()), 2),
            peak_at=str(peak_at),
            route_at_peak=route_at_peak,
            route_label=ROUTE_LABELS[route_at_peak],
            technician_action=ROUTE_ACTIONS[route_at_peak],
            alert_hours=len(alerting),
            watch_hours=sum(1 for hour in hours if hour.route_at_threshold == pdm.ROUTE_WATCH),
            no_action_hours=sum(
                1 for hour in hours if hour.route_at_threshold == pdm.ROUTE_NO_ACTION
            ),
            alerting_hours=alerting,
            first_alert_hour=alerting[0] if alerting else None,
            alert_hours_at_policy=int((window >= self.threshold).sum()),
            route_changed_by_threshold=route_at_peak != policy_route_at_peak,
            drivers=self._drivers(peak_at),
            readings_at=str(peak_at),
            covers_documented_failure=bool(row["covers_documented_failure"]),
            boundary=BOUNDARY_SHORT,
            score_note=SCORE_NOTE,
            model_version=self.model_version,
        )

    def _drivers(self, stamp: pd.Timestamp) -> list[FeatureFact]:
        """The six sensors behind one hour's score, in plain language."""
        contributions = self.contributions.loc[stamp]
        values = self.matrix.loc[stamp]
        total = float(contributions.sum())
        facts = []
        for name in pdm.MODEL_FEATURES:
            distance = float(contributions[name])
            reading = _format_value(name, float(values[name]))
            normal = _format_value(name, float(self.detector.median_[name]))
            direction = PLAIN_DIRECTION[pdm.FEATURE_DIRECTION[name]]
            if distance > 0:
                sentence = (
                    f"{reading}, against a normal of about {normal}. "
                    f"{direction} for this sensor, so this reading pushes the score up."
                )
            else:
                sentence = (
                    f"{reading}, against a normal of about {normal}. "
                    "This one is normal or better, so it adds nothing to the score."
                )
            facts.append(
                FeatureFact(
                    name=name,
                    display_name=pdm.FEATURE_DISPLAY_NAMES[name],
                    planner_question=pdm.FEATURE_QUESTION[name],
                    reading=reading,
                    normal=normal,
                    plain_direction=direction,
                    distance_from_normal=round(distance, 2),
                    share_of_score=round(100 * distance / total, 1) if total > 0 else 0.0,
                    pushes_score_up=distance > 0,
                    sentence=sentence,
                )
            )
        facts.sort(key=lambda fact: fact.distance_from_normal, reverse=True)
        return facts

    # ── /api/maintenance/queue ──────────────────────────────────────────────

    def queue(self, threshold: float | None) -> QueueResponse:
        chosen = self.threshold if threshold is None else max(0.0, min(20.0, float(threshold)))

        # Recomputed, never read from a stored table: the same policy arithmetic
        # the notebook ran, over the same scored window, at the threshold asked for.
        priced = pdm_policy.policy_cost(self.score, chosen, self.window, self.costs)
        priced.pop("detail", None)
        never = pdm_policy.never_alert(self.window, self.costs)
        scheduled = pdm_policy.scheduled_inspection(self.window, 30, self.costs)
        monthly = metrics.monthly_alert_load(self.score, chosen)

        series = self.score.dropna()
        series = series[(series.index >= self.window[0]) & (series.index < self.window[1])]
        months = round((series.index.max() - series.index.min()).days / 30.44, 2)
        alert_hours = int((series >= chosen).sum())

        rows = [
            MonthlyLoadRow(
                month=str(record["month"]),
                clean_hours=int(record["clean_hours"]),
                alert_hours=int(record["alert_hours"]),
                pct_of_clean_hours=float(record["pct_of_clean_hours"]),
                false_callouts=int(record["false_callouts"]),
            )
            for record in monthly.to_dict("records")
        ]
        busiest = max(rows, key=lambda row: row.alert_hours)
        quietest = min(rows, key=lambda row: row.alert_hours)

        total = float(priced["total_cost_usd"])
        never_total = float(never["total_cost_usd"])
        scheduled_total = float(scheduled["total_cost_usd"])

        return QueueResponse(
            threshold=chosen,
            threshold_note=(
                f"Alert on any hour scoring {chosen:g} or above."
                + (
                    ""
                    if chosen == self.threshold
                    else f" The frozen operating policy is {self.threshold:g}."
                )
            ),
            is_operating_threshold=chosen == self.threshold,
            policy_threshold=self.threshold,
            window_start=str(self.window[0]),
            window_end=str(self.window[1]),
            months=months,
            alert_hours=alert_hours,
            callouts=int(priced["callouts"]),
            false_callouts=int(priced["false_callouts"]),
            alerts_per_month=float(priced["callouts_per_month"]),
            technician_hours=float(priced["technician_hours"]),
            failures_caught=int(priced["failures_caught"]),
            failures_missed=int(priced["failures_total"]) - int(priced["failures_caught"]),
            failures_total=int(priced["failures_total"]),
            callout_cost_usd=float(priced["callout_cost_usd"]),
            fault_cost_usd=float(priced["fault_cost_usd"]),
            total_cost_usd=total,
            never_alert=BaselineCost(
                plain_name="Never alert: wait for the machine to fail", **never
            ),
            scheduled_inspection=BaselineCost(
                plain_name="A technician walks the machine every 30 days", **scheduled
            ),
            net_vs_never_usd=round(never_total - total, 2),
            net_vs_scheduled_usd=round(scheduled_total - total, 2),
            beats_never_alert=total < never_total,
            beats_scheduled_inspection=total < scheduled_total,
            monthly_load=rows,
            drift=DriftSpread(
                busiest_month=busiest.month,
                busiest_alert_hours=busiest.alert_hours,
                quietest_month=quietest.month,
                quietest_alert_hours=quietest.alert_hours,
                sentence=(
                    f"At the same callout line of {chosen:g}, "
                    f"{_month_name(busiest.month)} raises {busiest.alert_hours} alert "
                    f"{'hour' if busiest.alert_hours == 1 else 'hours'} on healthy running and "
                    f"{_month_name(quietest.month)} raises {quietest.alert_hours}. The machine "
                    "did not change; the season and the duty cycle did."
                ),
            ),
            assumption_note=(
                "Every dollar figure here is a synthetic classroom assumption: $"
                f"{self.costs['callout_usd']:,.0f} per callout, $"
                f"{self.costs['fault_usd_per_hour']:,.0f} per hour a fault runs unaddressed, and $"
                f"{self.costs['service_interruption_usd']:,.0f} once if it runs past "
                f"{self.costs['interruption_after_hours']:.0f} hours. They are not any "
                "operator's real numbers."
            ),
            boundary=BOUNDARY_SHORT,
        )

    # ── /api/maintenance/model ──────────────────────────────────────────────

    def _discussion_case(self) -> DiscussionCase:
        """Derived, not hardcoded: the closest healthy/failure pair in the manifest."""
        healthy = self.manifest[~self.manifest["covers_documented_failure"].astype(bool)]
        failures = self.manifest[self.manifest["covers_documented_failure"].astype(bool)]
        top_healthy = healthy.loc[healthy["peak_score"].astype(float).idxmax()]
        gaps = (failures["peak_score"].astype(float) - float(top_healthy["peak_score"])).abs()
        nearest = failures.loc[gaps.idxmin()]
        gap = round(abs(float(nearest["peak_score"]) - float(top_healthy["peak_score"])), 2)
        return DiscussionCase(
            healthy_window_id=str(top_healthy["sample_id"]),
            healthy_label=str(top_healthy["label"]),
            healthy_peak_score=float(top_healthy["peak_score"]),
            failure_window_id=str(nearest["sample_id"]),
            failure_label=str(nearest["label"]),
            failure_peak_score=float(nearest["peak_score"]),
            gap=gap,
            statement=(
                f"A healthy compressor on a busy day peaks at "
                f"{float(top_healthy['peak_score']):.2f}. A documented air leak peaks at "
                f"{float(nearest['peak_score']):.2f}. They sit {gap:.2f} apart, so no "
                "threshold anywhere separates them: any line that calls out the failure "
                "also calls out the healthy day."
            ),
        )

    def model_info(self) -> ModelInfo:
        card, evaluation = self.card, self.evaluation
        frozen = evaluation["test_frozen"]
        detected = [
            item for item in frozen["per_failure"].values() if item.get("detected")
        ]
        dataset = card["training_data"]

        return ModelInfo(
            model_name=card["model_name"],
            model_version=self.model_version,
            course=card["course"],
            model_type=card["model_type"],
            how_it_works=card["how_it_works"],
            intended_use=card["intended_use"],
            not_for=list(card["not_for"]),
            authority_boundary=card["authority_boundary"],
            boundary_short=BOUNDARY_SHORT,
            score_note=SCORE_NOTE,
            packaged_windows=len(self.manifest),
            scored_hours=len(self.score),
            features=[
                FeatureInfo(
                    name=feature["name"],
                    display_name=feature["display_name"],
                    planner_question=feature["planner_question"],
                    direction_that_means_trouble=feature["direction_that_means_trouble"],
                    plain_direction=PLAIN_DIRECTION[pdm.FEATURE_DIRECTION[feature["name"]]],
                    training_normal=float(feature["training_median"]),
                    training_normal_text=_format_value(
                        feature["name"], float(feature["training_median"])
                    ),
                    training_scale=float(feature["training_scale"]),
                )
                for feature in card["features"]
            ],
            dataset=DatasetInfo(
                dataset=dataset["dataset"],
                uci_id=int(dataset["uci_id"]),
                license=dataset["license"],
                url=dataset["url"],
                citation=dataset["citation"],
                raw_sampling=dataset["raw_sampling"],
                committed_resolution=dataset["committed_resolution"],
                training_window=list(dataset["training_window"]),
                population=dataset["population"],
            ),
            policy=PolicyInfo(
                policy_version=str(self.policy["policy_version"]),
                threshold=self.threshold,
                watch_threshold=self.watch_threshold,
                route_work_order=self.policy["routes"]["work_order"],
                route_watch=self.policy["routes"]["watch"],
                route_no_action=self.policy["routes"]["no_action"],
                plain_rule=(
                    f"Score {self.threshold:g} or above: raise a work order and a technician "
                    f"inspects within {float(self.policy['response_hours']):.0f} hours. Between "
                    f"{self.watch_threshold:g} and {self.threshold:g}: write it in the shift "
                    f"report, nobody is called out. Below {self.watch_threshold:g}: nothing "
                    "happens."
                ),
                response_hours=float(self.policy["response_hours"]),
                merge_gap_hours=int(self.policy["merge_gap_hours"]),
                threshold_selected_on=list(self.policy["threshold_selected_on"]),
                training_window=list(self.policy["training_window"]),
                held_out_test=list(self.policy["held_out_test"]),
                fallback=self.policy["fallback"],
                recalibration=self.policy["recalibration"],
                boundary_statement=self.policy["boundary_statement"],
                costs_are_synthetic=bool(self.policy["costs_are_synthetic"]),
                costs=self.costs,
                cost_note=(
                    "Synthetic classroom assumptions anchored on a published fact about one "
                    "transit operator. They are not that operator's real figures."
                ),
            ),
            frozen_test=FrozenTest(
                window=list(frozen["window"]),
                threshold=float(frozen["threshold"]),
                scored_hours=int(frozen["scored_hours"]),
                alert_hours=int(frozen["alert_hours"]),
                clean_hours=int(frozen["clean_hours"]),
                false_alarm_hours=int(frozen["false_alarm_hours"]),
                false_alarm_rate_on_clean_hours=float(frozen["false_alarm_rate_on_clean_hours"]),
                false_callouts=int(frozen["false_callouts"]),
                false_callouts_per_month=float(frozen["false_callouts_per_month"]),
                months=float(frozen["months"]),
                failures_detected=int(frozen["failures_detected"]),
                failures_with_advance_warning=int(frozen["failures_with_advance_warning"]),
                first_alert=detected[0]["first_alert"] if detected else None,
                lead_hours=float(detected[0]["lead_hours"]) if detected else None,
                policy=_record(frozen["policy"]),
                never_alert=_record(frozen["never_alert_baseline"]),
                honest_roi_note=frozen["honest_roi_note"],
            ),
            drift=DriftBlock(
                naive_single_feature_pct_clean_hours_alerting=_records(
                    evaluation["drift"]["naive_single_feature_pct_clean_hours_alerting"]
                ),
                detector_false_callouts_by_month=_records(
                    evaluation["drift"]["detector_false_callouts_by_month"]
                ),
                mitigations=_records(evaluation["drift"]["mitigations"]),
                monthly_alert_load_at_operating_threshold=_records(
                    evaluation["drift"]["monthly_alert_load_at_operating_threshold"]
                ),
                cruel_interaction=evaluation["drift"]["cruel_interaction"],
            ),
            threshold_sweep=_records(evaluation["threshold_sweep_costs"]),
            baseline_policies=_records(evaluation["baseline_policies"]),
            full_period_policy=_record(evaluation["full_period_policy"]),
            full_period_never_alert=_record(evaluation["full_period_never_alert"]),
            feature_bug=FeatureBug(
                description=evaluation["feature_bug"]["description"],
                hours_deleted_per_failure=_records(
                    evaluation["feature_bug"]["hours_deleted_per_failure"]
                ),
            ),
            training_window_not_clean=TrainingWindowNotClean(
                training_hours=int(evaluation["training_window_not_clean"]["training_hours"]),
                hours_above_threshold=int(
                    evaluation["training_window_not_clean"]["hours_above_threshold"]
                ),
                share_above_threshold=float(
                    evaluation["training_window_not_clean"]["share_above_threshold"]
                ),
                episodes=int(evaluation["training_window_not_clean"]["episodes"]),
                peak_score=float(evaluation["training_window_not_clean"]["peak_score"]),
                peak_at=str(evaluation["training_window_not_clean"]["peak_at"]),
                episode_list=_records(evaluation["training_window_not_clean"]["episode_list"]),
            ),
            data_coverage=CoverageBlock(
                summary=_records(evaluation["data_coverage"]["summary"]),
                pre_onset_coverage=_records(evaluation["data_coverage"]["pre_onset_coverage"]),
                note=evaluation["data_coverage"]["note"],
            ),
            discussion_case=self._discussion_case(),
            limitations=list(card["known_limitations"]),
            monitoring=card["monitoring"],
            environment={
                key: str(value) for key, value in evaluation.get("environment", {}).items()
            },
        )
