from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# The protocol switch. It is a request field rather than a setting because the
# whole case is that the same customer, the same model and the same day produce
# opposite verdicts depending on which one the analyst picked.
Protocol = Literal["discovery", "standard"]

# Why a customer cannot be personalized, when they cannot.
ColdStartKind = Literal[
    "none",
    "no_history_before_the_cut",
    "history_below_the_threshold",
]

CustomerSource = Literal["manifest", "cold_start_example"]


class SlotsRequest(BaseModel):
    """One customer id and one evaluation protocol. Nothing else is accepted.

    ``extra="forbid"`` matters here: a caller who sends ``{"customer": 17841}``
    or ``{"customer_id": 17841, "protocol": "discovery", "model": "svd"}`` gets
    one sentence back naming the field, rather than a silently ignored key and
    a result that answers a different question.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(ge=0, description="A packaged customer id, or any customer in the data.")
    protocol: Protocol = Field(
        default="discovery",
        description=(
            "discovery ranks only products the customer has never bought - this is the "
            "shipping policy. standard ranks the whole catalog, repeats included, which "
            "is the other evaluation protocol and not what the storefront shows."
        ),
    )


# ── Catalog and history ─────────────────────────────────────────────────────


class HistoryProduct(BaseModel):
    stock_code: str
    description: str
    baskets: int
    popularity_rank: int


class HistorySummary(BaseModel):
    in_training_matrix: bool
    training_products: int
    training_baskets: int
    first_purchase: str | None
    last_purchase: str | None
    bought_after_the_cut: int
    new_to_them_after_the_cut: int
    top_products: list[HistoryProduct]
    note: str


# ── One filled slot ─────────────────────────────────────────────────────────


class BecauseYouBought(BaseModel):
    stock_code: str
    description: str
    contribution: float


class Slot(BaseModel):
    slot: int
    stock_code: str
    description: str
    score: float
    label: str
    from_fallback: bool
    already_owned: bool
    bought_after_the_cut: bool
    is_new_to_them: bool
    popularity_rank: int
    training_customers: int
    because_you_bought: BecauseYouBought | None
    reason: str


class ReorderItem(BaseModel):
    slot: int
    stock_code: str
    description: str
    baskets_bought_in: int
    score: float
    bought_after_the_cut: bool
    popularity_rank: int


class ReorderStrip(BaseModel):
    title: str
    available: bool
    rule: str
    never: str
    items: list[ReorderItem]
    hits_out_of_10_standard: int
    note: str


class ProtocolInfo(BaseModel):
    id: str
    name: str
    ground_truth: str
    candidates: str
    question: str


class SlotsResponse(BaseModel):
    customer_id: int
    persona: str
    is_discussion_case: bool
    discussion_note: str | None

    protocol: Protocol
    protocol_detail: ProtocolInfo

    module_title: str
    personalized: bool
    fallback_used: bool
    fallback_slots: int
    reason: str
    model_used: str
    score_basis: str

    slots: list[Slot]
    hits_out_of_10: int
    buy_it_again: ReorderStrip
    history: HistorySummary

    matches_shipping_policy: bool
    policy_note: str
    human_authority: str
    score_note: str
    boundary: str


# ── Packaged customers ──────────────────────────────────────────────────────


class PackagedCustomer(BaseModel):
    customer_id: int
    persona: str
    source: CustomerSource
    selection_rule: str
    cold_start: bool
    cold_start_kind: ColdStartKind
    is_discussion_case: bool
    discussion_note: str | None
    training_products: int
    training_baskets: int
    bought_after_the_cut: int
    new_to_them_after_the_cut: int
    discovery_hits_out_of_10: int | None
    reorder_hits_out_of_10_standard: int | None
    history_note: str


# ── The side-by-side comparison ─────────────────────────────────────────────


class CompareSlot(BaseModel):
    slot: int
    stock_code: str
    description: str
    score: float
    already_owned: bool
    bought_after_the_cut: bool


class CompareRanking(BaseModel):
    slots: list[CompareSlot]
    hits_out_of_10: int
    already_owned_in_slots: int
    # True when every one of the ten slots scored exactly zero. The ten products
    # are then an index-order tie-break rather than a ranking, and a page that
    # prints the hit count without printing this is reporting an accident.
    all_scores_zero: bool
    scores_note: str


class ModelComparison(BaseModel):
    model: str
    how_it_works: str
    is_deployed: bool
    standard: CompareRanking
    discovery: CompareRanking
    standard_hr10: float
    standard_rank: int
    discovery_hr10: float
    discovery_rank: int
    rank_change: int
    discovery_coverage: float


class CompareResponse(BaseModel):
    customer_id: int
    persona: str
    personalized: bool
    reason: str
    is_discussion_case: bool
    discussion_note: str | None
    truth_standard: int
    truth_discovery: int
    protocols: list[ProtocolInfo]
    models: list[ModelComparison]
    lesson: str
    score_note: str
    boundary: str


# ── The model card ──────────────────────────────────────────────────────────


class LeaderboardRow(BaseModel):
    model: str
    how_it_works: str
    hr_at_10: float
    precision_at_10: float
    recall_at_10: float
    ndcg_at_10: float
    coverage: float
    novelty: float
    mean_popularity_rank: float
    customers_scored: int
    fit_seconds: float
    rank: int
    is_deployed: bool


class SideBySideRow(BaseModel):
    model: str
    standard_hr10: float
    standard_rank: int
    discovery_hr10: float
    discovery_rank: int
    rank_change: int
    discovery_coverage: float
    is_deployed: bool


class ZeroScoreDiagnosis(BaseModel):
    customers: int
    customers_with_any_positive_score: int
    share_with_all_zero_scores: float
    mean_popularity_rank_of_slots: float
    catalog_size: int
    explanation: str


class Leaderboards(BaseModel):
    rule: str
    standard: list[LeaderboardRow]
    discovery: list[LeaderboardRow]
    side_by_side: list[SideBySideRow]
    reorder_zero_score_diagnosis: ZeroScoreDiagnosis


class RevenueRow(BaseModel):
    model: str
    discovery_hits_per_customer: float
    revenue_reached: float
    share_of_available_new_product_revenue: float
    is_deployed: bool


class IncrementalRevenue(BaseModel):
    available_new_product_revenue: float
    customers: int
    by_model: list[RevenueRow]
    deployed_share: float
    no_personalization_share: float
    gain_percentage_points: float
    upper_bound_note: str
    boundary: str


class InflationRow(BaseModel):
    model: str
    honest_hr10: float
    leave_one_out_hr10: float
    inflation: float


class LeaveOneOut(BaseModel):
    design: str
    plain_words: str
    by_model: list[InflationRow]


class ExposureRow(BaseModel):
    model: str
    coverage: float
    recommendation_gini: float
    share_from_the_top_100: float
    share_from_the_less_popular_half: float
    median_popularity_rank: float
    distinct_products_shown: int
    top_product_share_of_all_slots: float
    is_deployed: bool


class ExposureLoopRow(BaseModel):
    round: int
    top_10_share: float
    top_100_share: float
    gini: float
    distinct_products_ever_shown: int


class ExposureLoop(BaseModel):
    rounds: int
    assumed_conversion: float
    assumption_note: str
    history: list[ExposureLoopRow]
    start_top_10_share: float
    end_top_10_share: float


class PopularityBias(BaseModel):
    what_each_model_shows: list[ExposureRow]
    exposure_loop: ExposureLoop


class TruncationRow(BaseModel):
    neighbours_kept: str
    discovery_hr10: float
    coverage: float
    novelty: float
    stored_megabytes: float
    shrink_vs_the_full_matrix: float
    is_deployed: bool


class DampingRow(BaseModel):
    damping_alpha: float
    discovery_hr10: float
    ndcg_at_10: float
    coverage: float
    largest_difference_from_alpha_zero: float


class Engineering(BaseModel):
    truncation_trade: list[TruncationRow]
    popularity_damping_is_a_no_op: list[DampingRow]
    damping_note: str


class FallbackItem(BaseModel):
    slot: int
    stock_code: str
    description: str
    revenue_in_window: float


class FallbackSweepRow(BaseModel):
    rule: str
    hr_at_10: float
    precision_at_10: float
    cold_customers_scored: int
    is_chosen: bool


class FallbackPolicy(BaseModel):
    rule: str
    window_days: int
    refresh: str
    label: str
    never_label_it: str
    items: list[FallbackItem]
    sweep: list[FallbackSweepRow]


class ReorderSurface(BaseModel):
    title: str
    rule: str
    never: str


class PolicyOutcomes(BaseModel):
    test_window_customers: int
    personalized_customers: int
    personalized_share: float
    fallback_customers: int
    fallback_share: float
    customers_needing_partial_backfill: int
    partial_backfill_share: float
    slots_total: int
    slots_from_fallback: int
    fallback_slot_share: float
    guest_baskets_in_test: int
    guest_revenue_share_of_test: float
    guest_fallback_share: float


class PolicyInfo(BaseModel):
    slots: int
    module_title: str
    ranking_model: str
    eligibility: str
    personalize_if: str
    statement: str
    fallback: FallbackPolicy
    reorder_surface: ReorderSurface
    human_authority: str
    service_must: list[str]
    outcomes: PolicyOutcomes
    boundary: str


class ColdStart(BaseModel):
    registered_customers_active_in_test: int
    cold_registered_customers: int
    cold_registered_share: float
    cold_registered_revenue_share: float
    thin_history_customers: int
    thin_history_share: float
    unservable_customers: int
    unservable_share: float
    products_sold_in_test: int
    cold_products: int
    cold_product_share: float
    cold_product_revenue_share: float
    guest_baskets_in_test: int
    guest_revenue_share: float
    fallback_hr10: float
    warning: str


class RepeatPurchasing(BaseModel):
    test_truth_pairs: int
    repeat_pairs: int
    repeat_share: float
    new_pairs: int
    new_share: float
    test_revenue: float
    repeat_revenue: float
    repeat_revenue_share: float
    users_with_a_repeat: int
    users_scored: int
    users_with_a_repeat_share: float
    note: str


class SplitInfo(BaseModel):
    type: str
    cut: str
    min_training_products_per_customer: int
    users: int
    items: int
    training_pairs: int
    sparsity: float
    customers_scored_standard: int
    customers_scored_discovery: int
    why_not_random: str


class DatasetInfo(BaseModel):
    name: str
    license: str
    citation: str
    population: str
    raw_rows: int
    clean_rows: int
    committed_rows: int
    committed_grain: str
    products_in_the_catalog: int
    customers_in_the_matrix: int
    sibling_lab: dict[str, str]


class DeployedModel(BaseModel):
    id: str
    label: str
    how_it_works: str
    neighbours_kept: int
    scoring: str
    why_not_the_most_accurate_model: str
    stored_links: int
    stored_megabytes: float
    similarity_digest: str


class Concentration(BaseModel):
    items: int
    gini: float
    top_10_share: float
    top_100_share: float
    top_500_share: float


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    generated: str
    framework: str
    deployed_model: DeployedModel
    what_it_does: str
    what_it_does_not_do: list[str]
    intended_users: str
    boundary: str
    prohibited_claims: list[str]
    known_limits: list[str]
    dataset: DatasetInfo
    split: SplitInfo
    protocols: list[ProtocolInfo]
    leaderboards: Leaderboards
    incremental_revenue: IncrementalRevenue
    leave_one_out: LeaveOneOut
    popularity_bias: PopularityBias
    engineering: Engineering
    cold_start: ColdStart
    repeat_purchasing: RepeatPurchasing
    concentration: Concentration
    policy: PolicyInfo
    environment: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str
    model_version: str
    deployed_model: str
    packaged_customers: int
    catalog_products: int
    matrix_customers: int
    slots: int
    artifacts: dict[str, bool]
