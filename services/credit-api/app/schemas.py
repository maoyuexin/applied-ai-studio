from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Route = Literal["priority_review", "standard_monitoring"]
Outcome = Literal["Later missed the payment", "Later paid"]


class AccountInput(BaseModel):
    """One account's monthly snapshot, in the form the model actually consumes.

    Seven engineered behavior features leave the notebook, but ``utilization``
    is derived (bill / limit), so the service accepts the bill and the limit
    and rebuilds it with the notebook's own arithmetic. That keeps a what-if
    coherent: raising the bill raises both the utilization the model sees and
    the exposure the policy prices.
    """

    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=40)
    credit_limit: float = Field(ge=1_000, le=2_000_000)
    current_bill: float = Field(ge=-1_000_000, le=2_000_000)
    last_payment: float = Field(ge=0, le=2_000_000)
    months_late_now: float = Field(ge=0, le=9)
    worst_delay_6m: float = Field(ge=0, le=9)
    num_late_months_6m: float = Field(ge=0, le=6)
    payment_ratio_6m: float = Field(ge=0, le=2)
    bill_trend_6m: float = Field(ge=-2, le=2)

    @model_validator(mode="after")
    def validate_delay_history(self) -> "AccountInput":
        # Both hold by construction in the notebook's feature code: the worst
        # delay is a maximum over the six months that includes this one, and
        # being behind now is itself one late month.
        if self.months_late_now > self.worst_delay_6m:
            raise ValueError(
                "Months behind now cannot exceed the worst delay in the last 6 months."
            )
        if self.months_late_now >= 1 and self.num_late_months_6m < 1:
            raise ValueError(
                "An account behind on payments now has at least one late month in the last 6."
            )
        return self


class SixMonthBehavior(BaseModel):
    """What the analyst reads before looking at any score."""

    credit_limit_NT: float
    current_bill_NT: float
    bill_six_months_ago_NT: float
    last_payment_NT: float
    utilization: float
    months_late_now: float
    worst_delay_6m: float
    num_late_months_6m: float
    payment_ratio_6m: float
    bill_trend_6m: float
    derivation_note: str


class ReasonCode(BaseModel):
    feature: str
    display_name: str
    direction: Literal["raises risk"]
    contribution: float
    text: str


class PackagedAccount(BaseModel):
    scenario_id: str
    scenario_label: str
    learning_note: str
    account_id: str
    route: Route
    route_label: str
    probability: float
    exposure_NT: float
    expected_loss_NT: float
    actual_outcome: Outcome
    behavior: SixMonthBehavior
    inputs: AccountInput


class ScoreResponse(BaseModel):
    account_id: str
    probability: float
    route: Route
    route_label: str
    route_action: str
    exposure_NT: float
    expected_loss_NT: float
    review_cost_NT: float
    loss_given_default: float
    currency: str
    reasons: list[ReasonCode]
    behavior: SixMonthBehavior
    is_what_if: bool
    changed_inputs: list[str]
    actual_outcome: Outcome | None
    outcome_note: str
    model_version: str
    score_note: str


class QueueItem(BaseModel):
    rank: int
    account_id: str
    probability: float
    exposure_NT: float
    expected_loss_NT: float
    months_late_now: float
    utilization: float
    within_capacity: bool
    actual_outcome: Outcome


class QueueSummary(BaseModel):
    review_cost_NT: float
    frozen_review_cost_NT: float
    loss_given_default: float
    currency: str
    rule: str
    packaged_accounts: int
    flagged_accounts: int
    total_expected_loss_NT: float
    review_capacity: int
    accounts_over_capacity: int
    capacity_note: str
    assumption_note: str
    selection_note: str


class PolicySweepRow(BaseModel):
    review_cost_NT: int
    flagged: int
    flagged_share: float
    precision: float
    recall: float
    net_savings_NT: float


class PopulationResult(BaseModel):
    accounts: int
    flagged: int
    flagged_share: float
    precision: float
    recall: float
    net_savings_NT: float
    review_cost_NT: int
    note: str


class ReviewQueue(BaseModel):
    summary: QueueSummary
    population: PopulationResult
    policy_sweep: list[PolicySweepRow]
    items: list[QueueItem]


class FeatureInfo(BaseModel):
    name: str
    display_name: str


class DatasetInfo(BaseModel):
    name: str
    url: str
    license: str
    citation: str
    population: str
    split_counts: dict[str, dict[str, float]]


class ConfusionCounts(BaseModel):
    TP: int
    FP: int
    FN: int
    TN: int


class TestMetrics(BaseModel):
    auc: float
    pr_auc: float
    brier: float
    review_cost_NT: int
    flagged: int
    flagged_share: float
    precision: float
    recall: float
    net_savings_NT: float
    confusion: ConfusionCounts
    review_everybody_NT: float
    review_nobody_NT: float


class PolicyInfo(BaseModel):
    name: str
    rule: str
    plain_rule: str
    loss_given_default: float
    review_cost_NT: float
    currency: str
    parameter_note: str
    exposure: str
    selected_on: str
    route_priority_review: str
    route_standard_monitoring: str
    fallback: str
    boundary: str


class SliceRow(BaseModel):
    group: str
    accounts: int
    mean_score: float
    flagged_share: float
    actual_default_rate: float


class SliceGroup(BaseModel):
    key: str
    label: str
    rows: list[SliceRow]


class FairnessAudit(BaseModel):
    excluded_columns: list[str]
    exclusion_reason: str
    auc_without_protected: float
    auc_with_protected: float
    delta_auc: float
    delta_note: str
    slices: list[SliceGroup]
    note: str
    module_10_preview: str


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    framework: str
    packaging: str
    estimator: str
    intended_use: str
    score_note: str
    reason_code_mechanism: str
    features: list[FeatureInfo]
    dataset: DatasetInfo
    test_metrics: TestMetrics
    policy: PolicyInfo
    fairness: FairnessAudit
    limitations: list[str]
    excluded_uses: list[str]
    environment: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str
    model_version: str
    packaged_accounts: int
    artifacts: dict[str, bool]
