from pydantic import BaseModel, ConfigDict, Field, field_validator


# The baseline leaderboard, the interval comparison and the seasonal coverage
# slices leave the notebook as records whose keys are themselves data - column
# labels like "Coverage (promised 80%)". Typing every key would freeze the
# notebook's table shapes into the service, so the rows travel as plain records
# and the page reads them by the keys the model card publishes.
TableRow = dict[str, str | float | int | None]

# The cost ratio a planner can try. 1:1 means a lost sale and a leftover unit
# hurt the same; past about 20:1 the implied cost of a stockout is many times
# the price of the item and the arithmetic stops meaning anything.
MIN_RATIO = 1.0
MAX_RATIO = 20.0


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    service: str
    model: str
    model_version: str
    policy_version: str
    packaged_products: int
    cohort_products: int
    scored_product_weeks: int
    artifacts: dict[str, bool]


# ── /api/forecast/model ─────────────────────────────────────────────────────


class DatasetInfo(BaseModel):
    dataset: str
    uci_id: int
    license: str
    doi: str
    url: str
    citation: str
    grain: str
    training_window: list[str]
    cohort_rule: str
    population: str


class EvaluationSummary(BaseModel):
    """The held-out numbers, scored once and never re-tuned."""

    held_out_window: list[str]
    scored_once: bool
    rows: int
    products: int
    test_weeks: int
    mae_units: float
    rmse_units: float
    mae_of_flat_zero: float
    coverage_delivered: float
    coverage_promised: float
    median_band_units: float
    band_over_median_demand: float
    pinball_10: float
    pinball_50: float
    pinball_90: float
    metric_not_reported: str
    mape_of_the_point_forecast: float
    mape_of_a_flat_zero_forecast: float
    mape_note: str


class PolicyInfo(BaseModel):
    policy_version: str
    decision: str
    plain_rule: str
    critical_ratios: dict[str, float]
    ratios_swept: list[int]
    overstock_formula: str
    understock_formula: str
    cost_assumption_note: str
    costs_are_classroom_assumptions: bool
    cohort_rule: str
    cohort_size: int
    products_refused: int
    window_weeks: int
    nominal_low: float
    nominal_high: float
    nominal_coverage: float
    horizon_weeks: int
    train_window: list[str]
    test_window: list[str]
    human_authority: str
    prohibited_claims: list[str]
    fallback: str
    recalibration: str


class SeasonalCoverage(BaseModel):
    """Where the average coverage stops describing anything useful."""

    slices: list[TableRow]
    ramp_months: str
    worst_slice_coverage: float
    worst_slice_label: str
    misses_above_band_share: str
    note: str


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
    forecast_note: str
    interval_note: str
    prohibited_claims: list[str]
    packaged_products: int
    cohort_products: int
    residuals_per_product: int
    median_unit_price: float
    dataset: DatasetInfo
    evaluation: EvaluationSummary
    policy: PolicyInfo
    newsvendor_sweep: list[TableRow]
    interval_methods: list[TableRow]
    point_baselines: list[TableRow]
    seasonal_coverage: SeasonalCoverage
    per_product_outcomes: list[TableRow]
    limitations: list[str]
    monitoring: str
    environment: dict[str, str]


# ── /api/forecast/products ──────────────────────────────────────────────────


class ProductSummary(BaseModel):
    product_id: str
    product: str
    why_this_product: str
    unit_price: float
    test_weeks: int
    train_nonzero_share: float
    mean_units_per_week: float
    point_mean: float
    band_low_mean: float
    band_high_mean: float
    band_over_demand: float
    coverage: float
    misses: int
    misses_above_band: int
    cost_point: float
    cost_quantile: float
    cost_change_pct: float
    policy_is_cheaper: bool
    demand_summary: str
    policy_outcome: str


# ── /api/forecast/plan ──────────────────────────────────────────────────────


class PlanRequest(BaseModel):
    """One packaged product, and optionally a cost ratio to try instead of 4:1."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=32)
    cost_ratio: float | None = Field(default=None)

    @field_validator("cost_ratio")
    @classmethod
    def clamp_cost_ratio(cls, value: float | None) -> float | None:
        # A slider on a page can be dragged anywhere. Out-of-range asks are
        # clamped rather than refused, the same way the maintenance threshold is.
        if value is None:
            return None
        return max(MIN_RATIO, min(MAX_RATIO, float(value)))


class HistoryWeek(BaseModel):
    week: str
    actual: float


class PlanWeek(BaseModel):
    week: str
    actual: float
    point: float
    low: float
    high: float
    covered: bool
    order_point: float
    order_quantile: float
    short_point: float
    short_quantile: float
    excess_point: float
    excess_quantile: float


class OrderOutcome(BaseModel):
    """What one ordering rule bought, and what the holdout charged it for."""

    rule: str
    plain_rule: str
    quantile: float | None
    units_ordered: float
    units_short: float
    units_excess: float
    cost: float
    fill_rate: float
    weeks_short: int
    weeks_left_over: int


class LatestWeek(BaseModel):
    week: str
    actual: float
    point: float
    low: float
    high: float
    band_width: float
    covered: bool
    order_point: float
    order_quantile: float
    extra_units: float


class PlanResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    product_id: str
    product: str
    why_this_product: str
    unit_price: float
    weeks_planned: int
    week_start: str
    week_end: str
    cost_ratio: float
    critical_ratio: float
    is_policy_ratio: bool
    ratio_note: str
    overstock_cost_per_unit_week: float
    understock_cost_per_unit: float
    cost_note: str
    history: list[HistoryWeek]
    weekly: list[PlanWeek]
    latest: LatestWeek
    point_plan: OrderOutcome
    quantile_plan: OrderOutcome
    cost_change_pct: float
    policy_is_cheaper: bool
    saving: float
    coverage: float
    misses: int
    misses_above_band: int
    band_over_demand: float
    mean_units_per_week: float
    boundary: str
    forecast_note: str
    interval_note: str
    model_version: str
    policy_version: str


# ── /api/forecast/policy-sweep ──────────────────────────────────────────────


class CohortOutcome(BaseModel):
    rule: str
    plain_rule: str
    units_ordered: float
    units_short: float
    units_excess: float
    cost: float
    fill_rate: float
    share_of_weeks_short: float


class LosingProduct(BaseModel):
    product_id: str
    product: str
    cost_point: float
    cost_quantile: float
    extra_cost: float
    change_pct: float
    actual_units: float
    ordered_units: float
    units_left_over: float


class PolicySweepResponse(BaseModel):
    cost_ratio: float
    critical_ratio: float
    is_policy_ratio: bool
    ratio_note: str
    products: int
    product_weeks: int
    test_weeks: int
    week_start: str
    week_end: str
    quantile_plan: CohortOutcome
    point_plan: CohortOutcome
    mean_plan: CohortOutcome
    units_uplift_pct: float
    vs_point_pct: float
    vs_mean_pct: float
    cheaper_than_point: bool
    cheaper_than_mean: bool
    products_cheaper: int
    products_worse: int
    products_worse_share: float
    extra_cost_on_losers: float
    worst_products: list[LosingProduct]
    best_products: list[LosingProduct]
    cost_note: str
    boundary: str
    note: str
