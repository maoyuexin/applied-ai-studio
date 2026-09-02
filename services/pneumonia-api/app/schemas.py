from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


QueueRoute = Literal["priority_review", "standard_review", "quality_hold"]
DatasetLabel = Literal["Normal", "Pneumonia-labeled"]


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(pattern=r"^test-\d{4}$")
    blur_radius: float = Field(default=0.0, ge=0.0, le=12.0)
    exposure_shift: float = Field(default=0.0, ge=-100.0, le=100.0)


class QualityInfo(BaseModel):
    status: Literal["sufficient", "insufficient"]
    mean_intensity: float
    focus_score: float
    reasons: list[str]


class ScoreResponse(BaseModel):
    sample_id: str
    transformed: bool
    image_data_uri: str
    overlay_data_uri: str | None
    dataset_label: DatasetLabel | None
    label_note: str
    model_score: float | None
    threshold: float
    route: QueueRoute
    route_label: str
    model_name: str
    model_version: str
    score_note: str
    quality: QualityInfo
    influence_note: str | None


class SampleStudy(BaseModel):
    sample_id: str
    scenario_label: str
    learning_note: str
    dataset_label: DatasetLabel
    comparison: Literal["true_positive", "false_positive", "false_negative", "true_negative"]
    model_score: float
    route: Literal["priority_review", "standard_review"]
    image_data_uri: str


class HoldoutMetrics(BaseModel):
    sensitivity: float
    specificity: float
    precision: float
    accuracy: float
    roc_auc: float
    average_precision: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    priority_review_rate: float


class DatasetInfo(BaseModel):
    name: str
    source: str
    license: str
    population: str
    archive_md5: str
    split_counts: dict[str, int]
    class_counts: dict[str, int]


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    framework: str
    packaging: str
    architecture: str
    trainable_parameters: int
    input_shape: list[int]
    threshold: float
    target_validation_sensitivity: float
    score_note: str
    intended_use: str
    metrics: HoldoutMetrics
    dataset: DatasetInfo
    limitations: list[str]
    excluded_uses: list[str]
    robustness: list[dict[str, float | int | str]]


class QueueItem(BaseModel):
    sample_id: str
    dataset_label: DatasetLabel
    model_score: float
    route: Literal["priority_review", "standard_review"]
    route_label: str
    comparison: Literal["true_positive", "false_positive", "false_negative", "true_negative"]


class QueueSummary(BaseModel):
    heldout_studies: int
    priority_review: int
    standard_review: int
    quality_hold: int
    threshold: float
    priority_review_rate: float
    pneumonia_labeled_in_priority: int
    normal_labeled_in_priority: int


class ReviewQueue(BaseModel):
    summary: QueueSummary
    items: list[QueueItem]
    teaching_cases: list[QueueItem]
    retrospective_note: str