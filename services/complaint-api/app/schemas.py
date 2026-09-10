from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import MAX_NARRATIVE_CHARACTERS


Route = Literal["auto_route", "human_triage"]


class ClassifyRequest(BaseModel):
    """One complaint narrative, as plain text.

    The model reads nothing else: no company, no state, no issue field. The
    length cap and the blank check are enforced here rather than downstream, so
    a caller gets one sentence back that says what to change.
    """

    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(min_length=1, max_length=MAX_NARRATIVE_CHARACTERS)

    @field_validator("narrative", mode="before")
    @classmethod
    def check_narrative(cls, value: object) -> object:
        # A "before" validator runs ahead of the length constraint above, so both
        # rejections carry a message a beginner can act on rather than a schema
        # error about string bounds.
        if not isinstance(value, str):
            return value
        if not value.strip():
            raise ValueError(
                "There is no complaint text to read. A blank complaint is never scored: "
                "it goes straight to the human triage queue and is logged."
            )
        if len(value) > MAX_NARRATIVE_CHARACTERS:
            raise ValueError(
                f"This complaint is {len(value):,} characters long. This demo reads up to "
                f"{MAX_NARRATIVE_CHARACTERS:,}. Paste a shorter complaint, or trim this one."
            )
        return value


class TeamProbability(BaseModel):
    team: str
    description: str
    probability: float
    is_predicted: bool


class RoutingWord(BaseModel):
    word: str
    push: float


class ClassificationResult(BaseModel):
    predicted_team: str
    predicted_team_description: str
    confidence: float
    threshold: float
    route: Route
    route_label: str
    route_rule: str
    route_action: str
    probabilities: list[TeamProbability]
    routing_words: list[RoutingWord]
    routing_words_note: str
    characters: int
    words: int
    # Filled in only when the text is one of the packaged held-out complaints.
    # Pasted text has no recorded team, so nothing is offered next to it.
    is_packaged_complaint: bool
    known_team: str | None
    correct: bool | None
    outcome_note: str
    model_version: str
    score_note: str
    boundary: str


class PackagedComplaint(BaseModel):
    scenario_id: str
    scenario_label: str
    learning_note: str
    complaint_id: str
    date_received: str
    narrative: str
    characters: int
    issue: str
    known_team: str
    predicted_team: str
    confidence: float
    route: Route
    route_label: str
    correct: bool
    curated: bool
    is_misroute_example: bool
    top_words: list[RoutingWord]


class QueueComplaint(BaseModel):
    complaint_id: str
    date_received: str
    issue: str
    excerpt: str
    narrative: str
    characters: int
    predicted_team: str
    confidence: float
    route: Route
    known_team: str
    correct: bool
    curated: bool
    is_misroute_example: bool


class TeamQueue(BaseModel):
    team: str
    description: str
    complaints: int
    share_of_auto_routed: float
    misrouted: int
    items: list[QueueComplaint]


class TriageQueue(BaseModel):
    complaints: int
    share: float
    workload_note: str
    action: str
    items: list[QueueComplaint]


class FrozenTestRouting(BaseModel):
    complaints: int
    auto_routed: int
    coverage: float
    accuracy_among_auto_routed: float
    triage_rows: int
    triage_share: float
    accuracy_among_triage: float
    note: str


class QueueSummary(BaseModel):
    packaged_complaints: int
    auto_routed: int
    sent_to_triage: int
    triage_share: float
    misroutes_in_auto_routed: int
    threshold: float
    rule: str
    plain_rule: str
    workload_note: str
    selection_note: str
    boundary: str
    boundary_detail: str


class QueueBoard(BaseModel):
    summary: QueueSummary
    test: FrozenTestRouting
    teams: list[TeamQueue]
    triage: TriageQueue


class TeamInfo(BaseModel):
    name: str
    description: str
    precision: float
    recall: float
    f1: float
    complaints_in_test: int


class DatasetInfo(BaseModel):
    name: str
    publisher: str
    home: str
    retrieved: str
    rights: str
    window: str
    row_meaning: str
    narratives: str
    dedupe_rule: str
    class_cap: str
    split_counts: dict[str, int]


class TestMetrics(BaseModel):
    accuracy: float
    macro_f1: float
    threshold: float
    complaints: int
    auto_routed: int
    coverage: float
    accuracy_among_auto_routed: float
    triage_rows: int
    triage_share: float
    accuracy_among_triage: float
    baseline_accuracy: float
    baseline_macro_f1: float
    baseline_note: str
    note: str


class ConfusionMatrix(BaseModel):
    labels: list[str]
    rows_are_true_team: bool
    matrix: list[list[int]]


class PolicyInfo(BaseModel):
    name: str
    rule: str
    plain_rule: str
    confidence_threshold: float
    confidence_definition: str
    selected_on: str
    auto_route_when: str
    auto_route_action: str
    auto_route_coverage: float
    auto_route_accuracy: float
    triage_when: str
    triage_action: str
    triage_share: float
    triage_complaints: int
    fallback: str
    boundary: str
    boundary_detail: str


class RepresentationSettings(BaseModel):
    ngram_range: list[int]
    min_df: int
    max_features: int
    sublinear_tf: bool
    strip_accents: str


class RepresentationInfo(BaseModel):
    kind: str
    settings: RepresentationSettings
    columns_learned: int
    why_not_a_transformer: str


class RepresentationResult(BaseModel):
    model: str
    trained_on: int
    representation: str
    validation_accuracy: float
    validation_macro_f1: float
    fit_seconds: float
    explanation_available: str


class RepresentationComparison(BaseModel):
    design: str
    embedding_model: str
    embedding_facts: dict[str, str]
    results: list[RepresentationResult]
    winner: str
    accuracy_gap: float
    lesson: str


class DedupeTeamShare(BaseModel):
    team: str
    share_removed: float


class DedupeEvidence(BaseModel):
    rule: str
    mapped_rows_in_window: int
    rows_removed: int
    share_removed: float
    distinct_narratives: int
    narratives_filed_more_than_once: int
    share_removed_by_team: list[DedupeTeamShare]
    test_rows_seen_verbatim_in_train: float
    inflated_test_accuracy: float
    honest_test_accuracy: float
    inflation_percentage_points: float
    lesson: str


class ExplanationInfo(BaseModel):
    mechanism: str
    output: str
    note: str
    plain_mechanism: str


class ThresholdSweepRow(BaseModel):
    threshold: float
    coverage: float
    accuracy_among_auto_routed: float
    triage_share: float
    overall_accuracy: float
    is_chosen: bool


class PerTeamRow(BaseModel):
    team: str
    precision: float
    recall: float
    f1: float
    complaints: int


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    framework: str
    packaging: str
    estimator: str
    task: str
    input: str
    output: str
    intended_use: str
    score_note: str
    max_narrative_characters: int
    representation: RepresentationInfo
    explanation: ExplanationInfo
    teams: list[TeamInfo]
    per_team: list[PerTeamRow]
    confusion: ConfusionMatrix
    dataset: DatasetInfo
    test_metrics: TestMetrics
    policy: PolicyInfo
    threshold_sweep: list[ThresholdSweepRow]
    representation_comparison: RepresentationComparison
    dedupe: DedupeEvidence
    limitations: list[str]
    excluded_uses: list[str]
    environment: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str
    model_version: str
    packaged_complaints: int
    teams: int
    artifacts: dict[str, bool]
