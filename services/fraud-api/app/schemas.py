from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    amount: float = Field(ge=0, le=10_000_000)
    category: str = Field(min_length=1, max_length=80)
    amount_ratio_to_card_mean: float = Field(ge=0, le=100_000)
    card_transactions_1h: int = Field(ge=0, le=100_000)
    card_transactions_24h: int = Field(ge=0, le=1_000_000)
    minutes_since_previous: float = Field(ge=0, le=10_000_000)
    distance_from_home_km: float = Field(ge=0, le=25_000)
    customer_age: float = Field(ge=0, le=130)
    city_population: int = Field(ge=1, le=100_000_000)

    @model_validator(mode="after")
    def validate_velocity_counts(self) -> "TransactionInput":
        if self.card_transactions_1h > self.card_transactions_24h:
            raise ValueError("Earlier transactions in 1 hour cannot exceed the 24-hour count.")
        return self


class SampleTransaction(BaseModel):
    scenario_id: str
    scenario_label: str
    learning_note: str
    merchant: str
    location: str
    card_last4: str
    known_outcome: Literal["Fraud", "Normal transaction"]
    transaction: TransactionInput


class ContextSignal(BaseModel):
    label: str
    value: str
    note: str


class LocalContribution(BaseModel):
    feature: str
    label: str
    value: str
    contribution: float
    direction: Literal["toward_review", "away_from_review"]


class LocalExplanation(BaseModel):
    method: Literal["Tree SHAP"]
    baseline_score: float
    contributions: list[LocalContribution]
    note: str


class ScoreResponse(BaseModel):
    transaction_id: str
    fraud_score: float
    threshold: float
    decision: Literal["review", "normal"]
    decision_label: str
    model_name: str
    model_version: str
    score_note: str
    context: list[ContextSignal]
    explanation: LocalExplanation


class FeatureInfo(BaseModel):
    name: str
    kind: str
    meaning: str
    source_columns: str


class HoldoutMetrics(BaseModel):
    recall: float
    precision: float
    false_positives: int
    false_negatives: int
    fraud_caught: int
    fraud_missed: int


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    packaging: str
    balancing_treatment: str
    threshold: float
    review_budget: float
    score_note: str
    training_window: list[str]
    test_window: list[str]
    metrics: HoldoutMetrics
    features: list[FeatureInfo]
    categories: list[str]


class QueueItem(BaseModel):
    transaction_id: str
    occurred_at: datetime
    merchant: str
    location: str
    amount: float
    category: str
    fraud_score: float
    decision_label: str
    known_outcome: Literal["Fraud", "Normal transaction"]


class QueueSummary(BaseModel):
    review_budget: float
    threshold: float
    heldout_transactions: int
    transactions_routed_to_review: int
    known_fraud_in_review: int


class ReviewQueue(BaseModel):
    summary: QueueSummary
    items: list[QueueItem]