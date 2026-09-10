from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import REPOSITORY_ROOT
from .schemas import (
    AccountInput,
    ConfusionCounts,
    DatasetInfo,
    FairnessAudit,
    FeatureInfo,
    ModelInfo,
    PackagedAccount,
    PolicyInfo,
    PolicySweepRow,
    PopulationResult,
    QueueItem,
    QueueSummary,
    ReasonCode,
    ReviewQueue,
    ScoreResponse,
    SixMonthBehavior,
    SliceGroup,
    SliceRow,
    TestMetrics,
)

# The exported pipeline pickles a *reference* to creditlab.features.build_features,
# so the notebook package has to be importable before joblib.load runs. Serving
# therefore reuses the notebook's own feature and reason-code code rather than a
# second copy that could drift from it.
NOTEBOOK_ROOT = REPOSITORY_ROOT / "notebooks" / "credit-risk"
if str(NOTEBOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTEBOOK_ROOT))

from creditlab import explain, features  # noqa: E402

ARTIFACT_FILES = (
    "model.joblib",
    "model_card.json",
    "evaluation.json",
    "operating_policy.json",
    "sample_manifest.parquet",
)

SCORE_NOTE = (
    "An estimated probability used to rank accounts for review. It is not a default "
    "determination; a credit analyst reviews the account and decides."
)

ROUTE_LABELS = {
    "priority_review": "Send to an analyst this month",
    "standard_monitoring": "Keep in ordinary monitoring",
}

OUTCOME_LABELS = {1: "Later missed the payment", 0: "Later paid"}

# Fields a caller can change. Changing any of them makes the request a what-if,
# because the packaged account's recorded history no longer describes it.
COMPARED_FIELDS = {
    "credit_limit": "Credit limit",
    "current_bill": "Current bill",
    "last_payment": "Last payment",
    "months_late_now": "Months behind now",
    "worst_delay_6m": "Worst delay in the last 6 months",
    "num_late_months_6m": "Late months in the last 6 months",
    "payment_ratio_6m": "Share of billed amounts paid",
    "bill_trend_6m": "Balance growth over 6 months",
}

SCENARIO_GROUPS = (
    (
        "flagged-missed",
        "Flagged, later missed the payment",
        "The queue earned its place: this account was reviewed and did miss the next payment.",
        True,
        1,
    ),
    (
        "flagged-paid",
        "Flagged, later paid",
        "A false alarm. The analyst spent a review on an account that paid anyway; the policy "
        "accepts these because a missed payment costs far more than a review.",
        True,
        0,
    ),
    (
        "monitored-missed",
        "Not flagged, later missed the payment",
        "A miss. Expected loss stayed under the review cost, so nobody looked, and the payment "
        "was missed anyway.",
        False,
        1,
    ),
    (
        "monitored-paid",
        "Not flagged, later paid",
        "The ordinary case: low risk or little money exposed, left in routine monitoring.",
        False,
        0,
    ),
)


class CreditRuntime:
    def __init__(self, artifact_dir: Path, review_capacity: int = 15):
        self.artifact_dir = artifact_dir
        self.capacity = int(review_capacity)
        missing = [name for name in ARTIFACT_FILES if not (artifact_dir / name).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing credit artifacts in {artifact_dir}: {', '.join(missing)}."
            )

        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.evaluation = json.loads((artifact_dir / "evaluation.json").read_text())
        self.policy = json.loads((artifact_dir / "operating_policy.json").read_text())
        self.pipeline = joblib.load(artifact_dir / "model.joblib")
        self.model = self.pipeline.named_steps["model"]
        self.explainer = explain.build_explainer(self.model)

        self.review_cost = float(self.policy["parameters"]["review_cost_NT"])
        self.loss_given_default = float(self.policy["parameters"]["loss_given_default"])
        self.currency = str(self.policy["parameters"]["currency"])

        manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
        manifest["account_id"] = manifest["account_id"].astype(str)
        exposure = np.clip(
            manifest["BILL_AMT1"].to_numpy(np.float64),
            0.0,
            manifest["LIMIT_BAL"].to_numpy(np.float64),
        )
        manifest["_exposure"] = exposure
        manifest["_expected_loss"] = (
            manifest["probability"].to_numpy(np.float64) * exposure * self.loss_given_default
        )
        self.manifest = manifest
        self.accounts = {row["account_id"]: row for _, row in manifest.iterrows()}

        sweep_costs = [int(row["review_cost_NT"]) for row in self.evaluation["policy_sweep"]]
        self.min_review_cost = float(min(sweep_costs))
        self.max_review_cost = float(max(sweep_costs))

    # ── Scoring ─────────────────────────────────────────────────────────────

    def _matrix(self, payload: AccountInput) -> np.ndarray:
        """Rebuild the engineered row in the notebook's frozen feature order."""
        utilization = float(np.clip(payload.current_bill / payload.credit_limit, 0.0, 2.0))
        values = {
            "months_late_now": payload.months_late_now,
            "worst_delay_6m": payload.worst_delay_6m,
            "num_late_months_6m": payload.num_late_months_6m,
            "utilization": utilization,
            "payment_ratio_6m": payload.payment_ratio_6m,
            "bill_trend_6m": payload.bill_trend_6m,
            "credit_limit": payload.credit_limit,
        }
        return np.array([[float(values[name]) for name in features.ENGINEERED]], dtype=np.float64)

    def score(self, payload: AccountInput) -> ScoreResponse:
        packaged = self.accounts.get(payload.account_id)
        if packaged is None:
            known = ", ".join(sorted(self.accounts)[:5])
            raise ValueError(
                f"Unknown account '{payload.account_id}'. This service scores only the "
                f"{len(self.accounts)} packaged held-out accounts, for example: {known}."
            )

        changed = [
            label
            for field, label in COMPARED_FIELDS.items()
            if getattr(payload, field) != self._packaged_value(packaged, field)
        ]
        is_what_if = bool(changed)

        matrix = self._matrix(payload)
        probability = float(self.model.predict_proba(matrix)[0, 1])
        exposure = float(np.clip(payload.current_bill, 0.0, payload.credit_limit))
        expected_loss = probability * exposure * self.loss_given_default
        route = (
            "priority_review"
            if expected_loss > self.review_cost
            else "standard_monitoring"
        )

        contributions = explain.shap_matrix(self.explainer, matrix)[0]
        reasons = [ReasonCode(**reason) for reason in explain.top_reasons(contributions, matrix[0])]

        return ScoreResponse(
            account_id=payload.account_id,
            probability=probability,
            route=route,
            route_label=ROUTE_LABELS[route],
            route_action=self.policy["routes"][route],
            exposure_NT=exposure,
            expected_loss_NT=expected_loss,
            review_cost_NT=self.review_cost,
            loss_given_default=self.loss_given_default,
            currency=self.currency,
            reasons=reasons,
            behavior=self._behavior(payload),
            is_what_if=is_what_if,
            changed_inputs=changed,
            # A changed input has no known history, so the historical outcome is
            # withheld rather than shown next to a number it no longer describes.
            actual_outcome=None if is_what_if else OUTCOME_LABELS[int(packaged["actual_outcome"])],
            outcome_note=(
                "You changed "
                + ", ".join(changed).lower()
                + ". This account never existed, so there is no later outcome to compare with."
                if is_what_if
                else "The packaged account, unchanged, next to what actually happened afterwards."
            ),
            model_version=str(self.card["model_version"]),
            score_note=SCORE_NOTE,
        )

    @staticmethod
    def _packaged_value(row: pd.Series, field: str) -> float:
        source = {
            "credit_limit": "credit_limit",
            "current_bill": "BILL_AMT1",
            "last_payment": "PAY_AMT1",
            "months_late_now": "months_late_now",
            "worst_delay_6m": "worst_delay_6m",
            "num_late_months_6m": "num_late_months_6m",
            "payment_ratio_6m": "payment_ratio_6m",
            "bill_trend_6m": "bill_trend_6m",
        }[field]
        return float(row[source])

    @staticmethod
    def _behavior(payload: AccountInput) -> SixMonthBehavior:
        utilization = float(np.clip(payload.current_bill / payload.credit_limit, 0.0, 2.0))
        return SixMonthBehavior(
            credit_limit_NT=payload.credit_limit,
            current_bill_NT=payload.current_bill,
            # bill_trend_6m is (this month's bill - the bill six months ago) / limit,
            # so the starting balance is recoverable from the model's own input.
            bill_six_months_ago_NT=payload.current_bill - payload.bill_trend_6m * payload.credit_limit,
            last_payment_NT=payload.last_payment,
            utilization=utilization,
            months_late_now=payload.months_late_now,
            worst_delay_6m=payload.worst_delay_6m,
            num_late_months_6m=payload.num_late_months_6m,
            payment_ratio_6m=payload.payment_ratio_6m,
            bill_trend_6m=payload.bill_trend_6m,
            derivation_note=(
                "The balance six months ago is recomputed from the balance-growth input. "
                "The packaged handoff carries the six-month summary the model uses, not "
                "each of the six monthly statements."
            ),
        )

    def _inputs(self, row: pd.Series) -> AccountInput:
        return AccountInput(
            account_id=str(row["account_id"]),
            credit_limit=float(row["credit_limit"]),
            current_bill=float(row["BILL_AMT1"]),
            last_payment=float(row["PAY_AMT1"]),
            months_late_now=float(row["months_late_now"]),
            worst_delay_6m=float(row["worst_delay_6m"]),
            num_late_months_6m=float(row["num_late_months_6m"]),
            payment_ratio_6m=float(row["payment_ratio_6m"]),
            bill_trend_6m=float(row["bill_trend_6m"]),
        )

    # ── Packaged accounts ───────────────────────────────────────────────────

    def samples(self, limit: int = 12) -> list[PackagedAccount]:
        """Packaged accounts spanning both routes and both later outcomes."""
        flagged = self.manifest["route"].eq("priority_review")
        outcome = self.manifest["actual_outcome"].astype(int)
        per_group = max(1, (limit + len(SCENARIO_GROUPS) - 1) // len(SCENARIO_GROUPS))

        chosen: list[PackagedAccount] = []
        for prefix, label, note, want_flag, want_outcome in SCENARIO_GROUPS:
            mask = (flagged == want_flag) & (outcome == want_outcome)
            rows = self.manifest.loc[mask].sort_values("_expected_loss", ascending=False)
            for index, (_, row) in enumerate(rows.head(per_group).iterrows(), start=1):
                chosen.append(self._packaged_account(row, f"{prefix}-{index}", label, note))
        chosen.sort(key=lambda account: account.expected_loss_NT, reverse=True)
        return chosen[:limit]

    def _packaged_account(
        self, row: pd.Series, scenario_id: str, label: str, note: str
    ) -> PackagedAccount:
        inputs = self._inputs(row)
        return PackagedAccount(
            scenario_id=scenario_id,
            scenario_label=label,
            learning_note=note,
            account_id=str(row["account_id"]),
            route=str(row["route"]),
            route_label=ROUTE_LABELS[str(row["route"])],
            probability=float(row["probability"]),
            exposure_NT=float(row["_exposure"]),
            expected_loss_NT=float(row["_expected_loss"]),
            actual_outcome=OUTCOME_LABELS[int(row["actual_outcome"])],
            behavior=self._behavior(inputs),
            inputs=inputs,
        )

    # ── Review queue ────────────────────────────────────────────────────────

    def review_queue(self, limit: int = 25, review_cost: float | None = None) -> ReviewQueue:
        cost = self.review_cost if review_cost is None else float(review_cost)
        cost = max(self.min_review_cost, min(cost, self.max_review_cost))

        flagged = self.manifest.loc[self.manifest["_expected_loss"] > cost]
        flagged = flagged.sort_values("_expected_loss", ascending=False)
        capacity = self.capacity

        items = [
            QueueItem(
                rank=rank,
                account_id=str(row["account_id"]),
                probability=float(row["probability"]),
                exposure_NT=float(row["_exposure"]),
                expected_loss_NT=float(row["_expected_loss"]),
                months_late_now=float(row["months_late_now"]),
                utilization=float(row["utilization"]),
                within_capacity=rank <= capacity,
                actual_outcome=OUTCOME_LABELS[int(row["actual_outcome"])],
            )
            for rank, (_, row) in enumerate(flagged.head(limit).iterrows(), start=1)
        ]

        test = self.evaluation["test_frozen"]
        return ReviewQueue(
            summary=QueueSummary(
                review_cost_NT=cost,
                frozen_review_cost_NT=self.review_cost,
                loss_given_default=self.loss_given_default,
                currency=self.currency,
                rule=(
                    "Flag an account when its expected loss - the chance it misses the payment, "
                    "times the money exposed, times the share lost - is worth more than one "
                    f"review at {self.currency.split(' ')[0]}{cost:,.0f}."
                ),
                packaged_accounts=int(len(self.manifest)),
                flagged_accounts=int(len(flagged)),
                total_expected_loss_NT=float(flagged["_expected_loss"].sum()),
                review_capacity=capacity,
                accounts_over_capacity=max(0, int(len(flagged)) - capacity),
                capacity_note=(
                    f"Classroom assumption: this team can review {capacity} accounts a month. "
                    "Lower the review cost and the queue outgrows the people who work it."
                ),
                assumption_note=str(self.policy["parameters"]["note"]),
                selection_note=(
                    f"These {len(self.manifest)} accounts were packaged to span both routes, so "
                    "the share flagged here is not the share flagged across the whole test set. "
                    "The figures for the full test set are alongside."
                ),
            ),
            population=PopulationResult(
                accounts=int(self.evaluation["split_counts"]["test"]["n"]),
                flagged=int(test["flagged"]),
                flagged_share=float(test["flagged_share"]),
                precision=float(test["precision"]),
                recall=float(test["recall"]),
                net_savings_NT=float(test["net_savings_NT"]),
                review_cost_NT=int(test["review_cost_NT"]),
                note=(
                    "Measured once on the untouched test split at the frozen review cost. "
                    "Moving the control above does not change these; they are the frozen record."
                ),
            ),
            policy_sweep=[
                PolicySweepRow(
                    review_cost_NT=int(row["review_cost_NT"]),
                    flagged=int(row["flagged"]),
                    flagged_share=float(row["flagged_share"]),
                    precision=float(row["precision"]),
                    recall=float(row["recall"]),
                    net_savings_NT=float(row["net_savings_NT"]),
                )
                for row in self.evaluation["policy_sweep"]
            ],
            items=items,
        )

    # ── Model card and governance ───────────────────────────────────────────

    def model_info(self) -> ModelInfo:
        test = self.evaluation["test_frozen"]
        fairness = self.evaluation["fairness"]
        excluded = self.card["protected_attributes_excluded"]
        parameters = self.policy["parameters"]

        return ModelInfo(
            model_name=str(self.card["model_name"]),
            model_version=str(self.card["model_version"]),
            framework=str(self.card["framework"]),
            packaging=str(self.card["packaging"]),
            estimator=str(self.card["estimator"]),
            intended_use=str(self.card["intended_use"]),
            score_note=SCORE_NOTE,
            reason_code_mechanism=str(self.card["reason_codes"]["mechanism"]),
            features=[
                FeatureInfo(name=name, display_name=display)
                for name, display in self.card["features"].items()
            ],
            dataset=DatasetInfo(
                name=str(self.card["dataset"]["name"]),
                url=str(self.card["dataset"]["url"]),
                license=str(self.card["dataset"]["license"]),
                citation=str(self.card["dataset"]["citation"]),
                population=str(self.card["dataset"]["population"]),
                split_counts=self.card["dataset"]["split_counts"],
            ),
            test_metrics=TestMetrics(
                auc=float(test["auc"]),
                pr_auc=float(test["pr_auc"]),
                brier=float(test["brier"]),
                review_cost_NT=int(test["review_cost_NT"]),
                flagged=int(test["flagged"]),
                flagged_share=float(test["flagged_share"]),
                precision=float(test["precision"]),
                recall=float(test["recall"]),
                net_savings_NT=float(test["net_savings_NT"]),
                confusion=ConfusionCounts(**test["confusion"]),
                review_everybody_NT=float(test["baselines_NT"]["review_everybody"]),
                review_nobody_NT=float(test["baselines_NT"]["review_nobody"]),
            ),
            policy=PolicyInfo(
                name=str(self.policy["name"]),
                rule=str(self.policy["rule"]),
                plain_rule=(
                    "Work out what an account is likely to cost: the chance it misses the "
                    "payment, times the balance at risk, times the share that would be lost. "
                    f"If that is more than the {parameters['currency'].split(' ')[0]}"
                    f"{float(parameters['review_cost_NT']):,.0f} it costs to review one account, "
                    "an analyst looks at it this month."
                ),
                loss_given_default=float(parameters["loss_given_default"]),
                review_cost_NT=float(parameters["review_cost_NT"]),
                currency=str(parameters["currency"]),
                parameter_note=str(parameters["note"]),
                exposure=str(self.policy["exposure"]),
                selected_on=str(self.policy["selected_on"]),
                route_priority_review=str(self.policy["routes"]["priority_review"]),
                route_standard_monitoring=str(self.policy["routes"]["standard_monitoring"]),
                fallback=str(self.policy["fallback"]),
                boundary=str(self.policy["boundary"]),
            ),
            fairness=FairnessAudit(
                excluded_columns=list(excluded["columns"]),
                exclusion_reason=str(excluded["reason"]),
                auc_without_protected=float(fairness["auc_without_protected"]),
                auc_with_protected=float(fairness["auc_with_protected"]),
                delta_auc=float(fairness["delta_auc"]),
                delta_note=(
                    "Adding sex, marital status, and age back as inputs moved ranking quality by "
                    f"{float(fairness['delta_auc']):.4f} AUC. That is the measured price of "
                    "leaving them out, and it is small enough that the legal answer costs "
                    "almost nothing here."
                ),
                slices=[
                    SliceGroup(
                        key=key,
                        label=label,
                        rows=[
                            SliceRow(
                                group=str(row[key]),
                                accounts=int(row["accounts"]),
                                mean_score=float(row["mean_score"]),
                                flagged_share=float(row["flagged_share"]),
                                actual_default_rate=float(row["actual_default_rate"]),
                            )
                            for row in fairness["slice_audit"][key]
                        ],
                    )
                    for key, label in (("sex", "Sex"), ("age_band", "Age band"))
                ],
                note=str(fairness["note"]),
                module_10_preview=(
                    "Module 10 takes this further: comparing outcomes across groups, choosing "
                    "which fairness definition a decision needs, and deciding what to do when "
                    "two of them cannot both hold."
                ),
            ),
            limitations=list(self.card["limitations"]),
            excluded_uses=list(self.card["excluded_uses"]),
            environment={key: str(value) for key, value in self.card["environment"].items()},
        )

    def artifact_readiness(self) -> dict[str, bool]:
        return {name: (self.artifact_dir / name).exists() for name in ARTIFACT_FILES}
