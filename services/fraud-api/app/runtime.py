from __future__ import annotations

import json
import sys
from pathlib import Path

import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
import pandas as pd
import shap

from .config import REPOSITORY_ROOT
from .schemas import (
    ContextSignal,
    FeatureInfo,
    HoldoutMetrics,
    LocalContribution,
    LocalExplanation,
    ModelInfo,
    QueueItem,
    QueueSummary,
    ReviewQueue,
    SampleTransaction,
    ScoreResponse,
    TransactionInput,
)

NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "fraud-detection"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from fraudlab import features  # noqa: E402


SCORE_NOTE = (
    "An uncalibrated model estimate used to rank transactions. It is not proof that "
    "fraud occurred; a reviewer makes the final determination."
)


def format_multiple(value: float) -> str:
    digits = 2 if value < 0.1 else 1
    return f"{value:.{digits}f}x"

EXPLANATION_GROUPS = {
    "amount": ("Purchase amount", ("amt", "log_amt")),
    "amount_ratio_to_card_mean": (
        "Compared with card average",
        ("amt_ratio_to_card_mean",),
    ),
    "card_transactions_1h": ("Earlier transactions in 1 hour", ("card_txn_count_1h",)),
    "card_transactions_24h": (
        "Earlier transactions in 24 hours",
        ("card_txn_count_24h",),
    ),
    "minutes_since_previous": ("Minutes since previous", ("minutes_since_prev_txn",)),
    "distance_from_home_km": ("Distance from home", ("distance_km",)),
    "customer_age": ("Customer age", ("customer_age",)),
    "city_population": ("Home-city population", ("log_city_pop",)),
    "occurred_at": ("Purchase date and time", ("hour", "is_night", "is_weekend")),
    "category": ("Merchant category", ()),
}


class FraudRuntime:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = artifact_dir
        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.model = mlflow.pyfunc.load_model(artifact_dir / "mlflow_model")
        explanation_pipeline = mlflow.sklearn.load_model(artifact_dir / "mlflow_model")
        explanation_model = explanation_pipeline.named_steps["model"]
        self.feature_columns = list(self.card["feature_columns"])
        self.threshold = float(self.card["operating_point"]["threshold"])
        self.categories = sorted(
            column.removeprefix("cat_")
            for column in self.feature_columns
            if column.startswith("cat_")
        )
        self.stream = pd.read_parquet(artifact_dir / "test_stream.parquet")
        matrix, _ = features.feature_matrix(self.stream)
        matrix = matrix.reindex(columns=self.feature_columns, fill_value=0.0).astype(float)
        background = matrix.sample(n=min(64, len(matrix)), random_state=42)
        self.explainer = shap.TreeExplainer(
            explanation_model,
            data=background,
            feature_perturbation="interventional",
            model_output="probability",
        )
        self.stream = self.stream.assign(_fraud_score=self._positive_scores(self.model.predict(matrix)))

    @staticmethod
    def _positive_scores(probabilities) -> np.ndarray:
        values = np.asarray(probabilities, dtype=float)
        if values.ndim == 2 and values.shape[1] == 2:
            return values[:, 1]
        if values.ndim == 1:
            return values
        raise ValueError(f"Expected one score or two class probabilities; received {values.shape}.")

    def _matrix(self, transaction: TransactionInput) -> pd.DataFrame:
        hour = transaction.occurred_at.hour
        frame = pd.DataFrame(
            [
                {
                    "amt": transaction.amount,
                    "log_amt": np.log1p(transaction.amount),
                    "amt_ratio_to_card_mean": transaction.amount_ratio_to_card_mean,
                    "card_txn_count_1h": transaction.card_transactions_1h,
                    "card_txn_count_24h": transaction.card_transactions_24h,
                    "minutes_since_prev_txn": transaction.minutes_since_previous,
                    "distance_km": transaction.distance_from_home_km,
                    "customer_age": transaction.customer_age,
                    "log_city_pop": np.log1p(transaction.city_population),
                    "hour": hour,
                    "is_night": int(hour < 6 or hour >= 22),
                    "is_weekend": int(transaction.occurred_at.weekday() >= 5),
                    "category": transaction.category,
                    "is_fraud": 0,
                }
            ]
        )
        matrix, _ = features.feature_matrix(frame)
        return matrix.reindex(columns=self.feature_columns, fill_value=0.0).astype(float)

    def score(self, transaction: TransactionInput) -> ScoreResponse:
        if transaction.category not in self.categories:
            raise ValueError(
                f"Unknown category '{transaction.category}'. Choose one of: "
                f"{', '.join(self.categories)}."
            )
        matrix = self._matrix(transaction)
        score = float(self._positive_scores(self.model.predict(matrix))[0])
        review = score >= self.threshold
        return ScoreResponse(
            transaction_id=transaction.transaction_id,
            fraud_score=score,
            threshold=self.threshold,
            decision="review" if review else "normal",
            decision_label="Send to review" if review else "Not flagged for review",
            model_name=self.card["model_name"],
            model_version=self.card["created_utc"],
            score_note=SCORE_NOTE,
            context=self._context(transaction),
            explanation=self._explanation(transaction, matrix),
        )

    def _explanation(
        self,
        transaction: TransactionInput,
        matrix: pd.DataFrame,
    ) -> LocalExplanation:
        shap_values = np.asarray(self.explainer.shap_values(matrix, check_additivity=True))
        if shap_values.ndim == 3:
            positive_values = shap_values[0, :, 1]
        elif shap_values.ndim == 2:
            positive_values = shap_values[0]
        else:
            raise ValueError(f"Unexpected SHAP values shape: {shap_values.shape}.")

        expected_value = np.asarray(self.explainer.expected_value, dtype=float).reshape(-1)
        baseline_score = float(expected_value[-1])
        by_column = dict(zip(self.feature_columns, positive_values, strict=True))
        display_values = self._explanation_values(transaction)
        contributions = []
        for feature, (label, columns) in EXPLANATION_GROUPS.items():
            grouped_columns = columns or tuple(
                column for column in self.feature_columns if column.startswith("cat_")
            )
            contribution = float(sum(by_column[column] for column in grouped_columns))
            contributions.append(
                LocalContribution(
                    feature=feature,
                    label=label,
                    value=display_values[feature],
                    contribution=contribution,
                    direction="toward_review" if contribution >= 0 else "away_from_review",
                )
            )
        contributions.sort(key=lambda item: abs(item.contribution), reverse=True)
        return LocalExplanation(
            method="Tree SHAP",
            baseline_score=baseline_score,
            contributions=contributions,
            note=(
                "Local score contributions from this packaged forest. Positive values push the "
                "score toward review; negative values push it away. They describe the model, "
                "not the cause of fraud."
            ),
        )

    @staticmethod
    def _explanation_values(transaction: TransactionInput) -> dict[str, str]:
        return {
            "amount": f"${transaction.amount:,.2f}",
            "amount_ratio_to_card_mean": (
                f"{format_multiple(transaction.amount_ratio_to_card_mean)} usual"
            ),
            "card_transactions_1h": str(transaction.card_transactions_1h),
            "card_transactions_24h": str(transaction.card_transactions_24h),
            "minutes_since_previous": f"{transaction.minutes_since_previous:,.1f} min",
            "distance_from_home_km": f"{transaction.distance_from_home_km:,.1f} km",
            "customer_age": f"{transaction.customer_age:.0f} years",
            "city_population": f"{transaction.city_population:,}",
            "occurred_at": transaction.occurred_at.strftime("%a, %-I:%M %p"),
            "category": transaction.category.replace("_", " "),
        }

    @staticmethod
    def _context(transaction: TransactionInput) -> list[ContextSignal]:
        time_label = transaction.occurred_at.strftime("%a, %-I:%M %p")
        return [
            ContextSignal(
                label="Amount compared with usual",
                value=format_multiple(transaction.amount_ratio_to_card_mean),
                note="Uses the card's earlier average; it does not look ahead.",
            ),
            ContextSignal(
                label="Recent card activity",
                value=f"{transaction.card_transactions_24h} in 24 hours",
                note=f"{transaction.card_transactions_1h} occurred in the previous hour.",
            ),
            ContextSignal(
                label="Distance from home",
                value=f"{transaction.distance_from_home_km:,.0f} km",
                note="A transaction can be far from home and still be normal.",
            ),
            ContextSignal(
                label="Transaction time",
                value=time_label,
                note="The model receives hour, night, and weekend indicators.",
            ),
        ]

    def model_info(self) -> ModelInfo:
        measured = self.card["measured_on_holdout"]
        catalog = features.model_feature_catalog()
        return ModelInfo(
            model_name=self.card["model_name"],
            model_version=self.card["created_utc"],
            packaging="MLflow pyfunc with skops safe serialization",
            balancing_treatment=self.card["balancing_treatment"],
            threshold=self.threshold,
            review_budget=float(self.card["operating_point"]["review_budget"]),
            score_note=SCORE_NOTE,
            training_window=self.card["windows"]["train"],
            test_window=self.card["windows"]["test"],
            metrics=HoldoutMetrics(
                recall=float(measured["recall"]),
                precision=float(measured["precision"]),
                false_positives=int(measured["fp"]),
                false_negatives=int(measured["fn"]),
                fraud_caught=int(measured["tp"]),
                fraud_missed=int(measured["fn"]),
            ),
            features=[
                FeatureInfo(
                    name=row["Model input"],
                    kind=row["Kind"],
                    meaning=row["Plain meaning"],
                    source_columns=row["Built from source column(s)"],
                )
                for row in catalog.to_dict(orient="records")
            ],
            categories=self.categories,
        )

    def samples(self, limit: int = 12) -> list[SampleTransaction]:
        reviewed = self.stream["_fraud_score"] >= self.threshold
        fraud = self.stream["is_fraud"].astype(bool)
        groups = [
            ("caught-fraud", "Caught fraud", "Known fraud routed to review.", fraud & reviewed, False),
            (
                "reviewed-normal",
                "Reviewed normal transaction",
                "A false positive: the score crossed the cutoff, but the known outcome was normal.",
                ~fraud & reviewed,
                True,
            ),
            (
                "missed-fraud",
                "Missed fraud",
                "A false negative: known fraud stayed below the review cutoff.",
                fraud & ~reviewed,
                False,
            ),
            (
                "normal-transaction",
                "Normal transaction",
                "A normal purchase that stayed out of the review queue.",
                ~fraud & ~reviewed,
                True,
            ),
        ]
        per_group = max(1, min(3, (limit + len(groups) - 1) // len(groups)))
        samples: list[SampleTransaction] = []
        for prefix, label, note, mask, ascending in groups:
            rows = self.stream.loc[mask].sort_values("_fraud_score", ascending=ascending).head(per_group)
            for index, (_, row) in enumerate(rows.iterrows(), start=1):
                samples.append(self._sample(row, f"{prefix}-{index}", label, note))
        return samples[:limit]

    def _sample(self, row: pd.Series, scenario_id: str, label: str, note: str) -> SampleTransaction:
        occurred_at = pd.Timestamp(row["trans_date_trans_time"]).to_pydatetime()
        transaction_id = str(row["trans_num"])
        return SampleTransaction(
            scenario_id=scenario_id,
            scenario_label=label,
            learning_note=note,
            merchant=str(row["merchant"]).replace("fraud_", ""),
            location=f"{row['city']}, {row['state']}",
            card_last4=str(row["cc_num"])[-4:],
            known_outcome="Fraud" if int(row["is_fraud"]) else "Normal transaction",
            transaction=TransactionInput(
                transaction_id=transaction_id,
                occurred_at=occurred_at,
                amount=float(row["amt"]),
                category=str(row["category"]),
                amount_ratio_to_card_mean=float(row["amt_ratio_to_card_mean"]),
                card_transactions_1h=int(row["card_txn_count_1h"]),
                card_transactions_24h=int(row["card_txn_count_24h"]),
                minutes_since_previous=float(row["minutes_since_prev_txn"]),
                distance_from_home_km=float(row["distance_km"]),
                customer_age=float(row["customer_age"]),
                city_population=max(1, int(round(np.expm1(float(row["log_city_pop"]))))),
            ),
        )

    def review_queue(self, limit: int = 25) -> ReviewQueue:
        reviewed = self.stream[self.stream["_fraud_score"] >= self.threshold]
        rows = reviewed.sort_values("_fraud_score", ascending=False).head(limit)
        return ReviewQueue(
            summary=QueueSummary(
                review_budget=float(self.card["operating_point"]["review_budget"]),
                threshold=self.threshold,
                heldout_transactions=len(self.stream),
                transactions_routed_to_review=len(reviewed),
                known_fraud_in_review=int(reviewed["is_fraud"].sum()),
            ),
            items=[
                QueueItem(
                    transaction_id=str(row["trans_num"]),
                    occurred_at=pd.Timestamp(row["trans_date_trans_time"]).to_pydatetime(),
                    merchant=str(row["merchant"]).replace("fraud_", ""),
                    location=f"{row['city']}, {row['state']}",
                    amount=float(row["amt"]),
                    category=str(row["category"]),
                    fraud_score=float(row["_fraud_score"]),
                    decision_label="Send to review",
                    known_outcome="Fraud" if int(row["is_fraud"]) else "Normal transaction",
                )
                for _, row in rows.iterrows()
            ],
        )