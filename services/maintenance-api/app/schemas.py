from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Route = Literal["work_order", "watch", "no_action"]

# The drift, sweep and coverage tables come out of the notebook as records whose
# keys are data - month names like "2020-04", column labels like
# "false callouts @ 4". Typing every key would freeze the notebook's table
# shapes into the service, so the rows travel as plain records and the page
# reads them by the keys the model card publishes.
TableRow = dict[str, str | float | int | None]


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    service: str
    model: str
    model_version: str
    policy_version: str
    packaged_windows: int
    scored_hours: int
    artifacts: dict[str, bool]


class FeatureInfo(BaseModel):
    name: str
    display_name: str
    planner_question: str
    direction_that_means_trouble: str
    plain_direction: str
    training_normal: float
    training_normal_text: str
    training_scale: float


class DatasetInfo(BaseModel):
    dataset: str
    uci_id: int
    license: str
    url: str
    citation: str
    raw_sampling: str
    committed_resolution: str
    training_window: list[str]
    population: str


class PolicyInfo(BaseModel):
    policy_version: str
    threshold: float
    watch_threshold: float
    route_work_order: str
    route_watch: str
    route_no_action: str
    plain_rule: str
    response_hours: float
    merge_gap_hours: int
    threshold_selected_on: list[str]
    training_window: list[str]
    held_out_test: list[str]
    fallback: str
    recalibration: str
    boundary_statement: str
    costs_are_synthetic: bool
    costs: dict[str, float]
    cost_note: str


class FrozenTest(BaseModel):
    """The July-September window, scored once and never re-tuned."""

    window: list[str]
    threshold: float
    scored_hours: int
    alert_hours: int
    clean_hours: int
    false_alarm_hours: int
    false_alarm_rate_on_clean_hours: float
    false_callouts: int
    false_callouts_per_month: float
    months: float
    failures_detected: int
    failures_with_advance_warning: int
    first_alert: str | None
    lead_hours: float | None
    policy: TableRow
    never_alert: TableRow
    honest_roi_note: str


class DriftBlock(BaseModel):
    naive_single_feature_pct_clean_hours_alerting: list[TableRow]
    detector_false_callouts_by_month: list[TableRow]
    mitigations: list[TableRow]
    monthly_alert_load_at_operating_threshold: list[TableRow]
    cruel_interaction: str


class DiscussionCase(BaseModel):
    """The pair no threshold separates: a healthy busy day and a real failure."""

    healthy_window_id: str
    healthy_label: str
    healthy_peak_score: float
    failure_window_id: str
    failure_label: str
    failure_peak_score: float
    gap: float
    statement: str


class CoverageBlock(BaseModel):
    summary: list[TableRow]
    pre_onset_coverage: list[TableRow]
    note: str


class FeatureBug(BaseModel):
    description: str
    hours_deleted_per_failure: list[TableRow]


class TrainingWindowNotClean(BaseModel):
    training_hours: int
    hours_above_threshold: int
    share_above_threshold: float
    episodes: int
    peak_score: float
    peak_at: str
    episode_list: list[TableRow]


class ModelInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    model_version: str
    course: str
    model_type: str
    how_it_works: str
    intended_use: str
    not_for: list[str]
    authority_boundary: str
    boundary_short: str
    score_note: str
    packaged_windows: int
    scored_hours: int
    features: list[FeatureInfo]
    dataset: DatasetInfo
    policy: PolicyInfo
    frozen_test: FrozenTest
    drift: DriftBlock
    threshold_sweep: list[TableRow]
    baseline_policies: list[TableRow]
    full_period_policy: TableRow
    full_period_never_alert: TableRow
    feature_bug: FeatureBug
    training_window_not_clean: TrainingWindowNotClean
    data_coverage: CoverageBlock
    discussion_case: DiscussionCase
    limitations: list[str]
    monitoring: str
    environment: dict[str, str]


class SampleWindow(BaseModel):
    sample_id: str
    label: str
    purpose: str
    start: str
    end: str
    hours_with_data: int
    peak_score: float
    peak_at: str
    median_score: float
    work_order_hours: int
    watch_hours: int
    route_at_peak: Route
    route_label_at_peak: str
    top_driver_at_peak: str
    top_driver_z: float
    covers_documented_failure: bool


class ScoreRequest(BaseModel):
    """A packaged window id, and optionally a threshold to try instead of 6.0."""

    model_config = ConfigDict(extra="forbid")

    window_id: str = Field(min_length=1, max_length=64)
    threshold: float | None = Field(default=None)

    @field_validator("threshold")
    @classmethod
    def clamp_threshold(cls, value: float | None) -> float | None:
        # A control on a page can be dragged anywhere; the score scale only runs
        # to about 20, so an out-of-range request is clamped rather than refused.
        if value is None:
            return None
        return max(0.0, min(20.0, float(value)))


class HourScore(BaseModel):
    hour: str
    score: float
    route_at_policy: Route
    route_at_threshold: Route
    alerts: bool


class FeatureFact(BaseModel):
    name: str
    display_name: str
    planner_question: str
    reading: str
    normal: str
    plain_direction: str
    distance_from_normal: float
    share_of_score: float
    pushes_score_up: bool
    sentence: str


class SimulatorFeatureReading(BaseModel):
    name: str
    display_name: str
    value: float
    value_text: str
    typical_value: float
    typical_text: str
    direction_that_means_trouble: str


class SimulatorHour(BaseModel):
    hour: str
    features: list[SimulatorFeatureReading]
    score: float
    alert: bool
    reported_event: bool
    event_name: str | None


class SimulatorResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    window_id: str
    label: str
    purpose: str
    model_type: str
    model_version: str
    threshold: float
    feature_count: int
    hours: list[SimulatorHour]
    score_note: str
    authority_boundary: str


class ScoreResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    window_id: str
    label: str
    purpose: str
    start: str
    end: str
    hours_with_data: int
    threshold: float
    policy_threshold: float
    watch_threshold: float
    threshold_is_override: bool
    threshold_note: str
    hours: list[HourScore]
    peak_score: float
    peak_at: str
    median_score: float
    route_at_peak: Route
    route_label: str
    technician_action: str
    alert_hours: int
    watch_hours: int
    no_action_hours: int
    alerting_hours: list[str]
    first_alert_hour: str | None
    alert_hours_at_policy: int
    route_changed_by_threshold: bool
    drivers: list[FeatureFact]
    readings_at: str
    covers_documented_failure: bool
    boundary: str
    score_note: str
    model_version: str


class MonthlyLoadRow(BaseModel):
    month: str
    clean_hours: int
    alert_hours: int
    pct_of_clean_hours: float
    false_callouts: int


class BaselineCost(BaseModel):
    policy: str
    plain_name: str
    callouts: int
    technician_hours: float
    failures_caught: int
    failures_total: int
    callout_cost_usd: float
    fault_cost_usd: float
    total_cost_usd: float


class DriftSpread(BaseModel):
    busiest_month: str
    busiest_alert_hours: int
    quietest_month: str
    quietest_alert_hours: int
    sentence: str


class QueueResponse(BaseModel):
    threshold: float
    threshold_note: str
    is_operating_threshold: bool
    policy_threshold: float
    window_start: str
    window_end: str
    months: float
    alert_hours: int
    callouts: int
    false_callouts: int
    alerts_per_month: float
    technician_hours: float
    failures_caught: int
    failures_missed: int
    failures_total: int
    callout_cost_usd: float
    fault_cost_usd: float
    total_cost_usd: float
    never_alert: BaselineCost
    scheduled_inspection: BaselineCost
    net_vs_never_usd: float
    net_vs_scheduled_usd: float
    beats_never_alert: bool
    beats_scheduled_inspection: bool
    monthly_load: list[MonthlyLoadRow]
    drift: DriftSpread
    assumption_note: str
    boundary: str
