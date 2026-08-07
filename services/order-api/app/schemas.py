from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    category: str
    price_cents: int
    image_url: str
    quantity_available: int


class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: EmailStr
    address_line: str = Field(min_length=5, max_length=240)
    city: str = Field(min_length=2, max_length=100)
    region: str = Field(min_length=2, max_length=80)
    postal_code: str = Field(min_length=3, max_length=20)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=12)
    scenario: str = Field(default="happy-path", pattern=r"^[a-z0-9-]+$")


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    address_line: str
    city: str
    region: str
    postal_code: str


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    quantity: int
    unit_price_cents: int
    product: ProductRead


class WorkflowEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    event_type: str
    stage: str
    actor: str
    summary: str
    details: dict[str, object]
    occurred_at: datetime


class DecisionSignalRead(BaseModel):
    label: str
    value: str
    influence: Literal["raises", "lowers", "neutral"]
    contribution: str
    explanation: str


class DecisionThresholdRead(BaseModel):
    label: str
    range: str
    outcome: str


class DecisionImpactRead(BaseModel):
    question: str
    model_name: str
    model_version: str
    model_kind: str
    output_name: str
    output_value: float
    output_unit: str
    output_label: str
    thresholds: list[DecisionThresholdRead]
    selected_branch: str
    process_effect: str
    business_effect: str
    human_boundary: str
    counterfactual: str
    input_signals: list[DecisionSignalRead]


class AlgorithmFeatureRead(BaseModel):
    name: str
    kind: str
    source: str
    role: str


class AlgorithmMetricRead(BaseModel):
    name: str
    target: str
    why: str


class AlgorithmProfileRead(BaseModel):
    title: str
    category: str
    implementation_status: str
    purpose: str
    algorithm: str
    why_fit: str
    output: str
    training_required: bool
    training_approach: str
    training_data: str
    target_definition: str
    split_strategy: str
    preprocessing: list[str]
    features: list[AlgorithmFeatureRead]
    metrics: list[AlgorithmMetricRead]
    testing: list[str]
    monitoring: list[str]
    limitations: list[str]


class OrderDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_type: str
    method: str
    recommendation: str
    score: float | None
    status: str
    evidence: list[str]
    impact: DecisionImpactRead | None
    algorithm_profile: AlgorithmProfileRead | None
    decided_by: str
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_id: str
    status: str
    scenario: str
    subtotal_cents: int
    shipping_cents: int
    total_cents: int
    version: int
    created_at: datetime
    updated_at: datetime
    customer: CustomerRead
    items: list[OrderItemRead]
    events: list[WorkflowEventRead]
    decisions: list[OrderDecisionRead]


class OrderList(BaseModel):
    items: list[OrderRead]
    total: int
