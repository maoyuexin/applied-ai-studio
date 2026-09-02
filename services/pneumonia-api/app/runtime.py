from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import (
    DatasetInfo,
    HoldoutMetrics,
    ModelInfo,
    QualityInfo,
    QueueItem,
    QueueSummary,
    ReviewQueue,
    SampleStudy,
    ScoreRequest,
    ScoreResponse,
)


SCORE_NOTE = (
    "An uncalibrated image-model score used with a validation-selected cutoff to route "
    "review. It is not a diagnosis or treatment recommendation."
)
RETROSPECTIVE_NOTE = (
    "Dataset labels are visible because these are historical held-out examples. A live "
    "queue would not know the outcome before qualified interpretation."
)
INFLUENCE_NOTE = (
    "The overlay marks image regions that influenced this model score. It does not locate "
    "disease, prove medical reasoning, or explain a diagnosis."
)


class PneumoniaRuntime:
    def __init__(self, notebook_dir: Path, artifact_dir: Path) -> None:
        self.notebook_dir = notebook_dir
        self.artifact_dir = artifact_dir
        if str(notebook_dir) not in sys.path:
            sys.path.insert(0, str(notebook_dir))

        from pneumonialab import data, explain, handoff, models

        self.data = data
        self.explain = explain
        self.models = models
        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.policy = json.loads((artifact_dir / "operating_policy.json").read_text())
        self.evaluation = json.loads((artifact_dir / "evaluation.json").read_text())
        self.manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
        self.model = handoff.load_model(artifact_dir)
        self.test = data.load_splits()["test"]
        self.threshold = float(self.policy["threshold"])
        self._rows = self.manifest.set_index("sample_id", drop=False)

    def model_info(self) -> ModelInfo:
        measured = self.card["measured_on_untouched_test"]
        dataset = self.card["dataset"]
        return ModelInfo(
            model_name=self.card["model_name"],
            model_version=self.card["model_version"],
            framework=self.card["framework"],
            packaging=self.card["packaging"],
            architecture=self.card["architecture"],
            trainable_parameters=int(self.card["trainable_parameters"]),
            input_shape=self.card["input"]["shape"],
            threshold=self.threshold,
            target_validation_sensitivity=float(self.policy["target_sensitivity"]),
            score_note=SCORE_NOTE,
            intended_use=self.card["intended_use"],
            metrics=HoldoutMetrics(
                sensitivity=float(measured["sensitivity"]),
                specificity=float(measured["specificity"]),
                precision=float(measured["precision"]),
                accuracy=float(measured["accuracy"]),
                roc_auc=float(measured["roc_auc"]),
                average_precision=float(measured["average_precision"]),
                true_positives=int(measured["tp"]),
                false_positives=int(measured["fp"]),
                false_negatives=int(measured["fn"]),
                true_negatives=int(measured["tn"]),
                priority_review_rate=float(measured["review_rate"]),
            ),
            dataset=DatasetInfo(
                name=dataset["name"],
                source=dataset["source"],
                license=dataset["license"],
                population=dataset["population"],
                archive_md5=dataset["archive_md5"],
                split_counts=dataset["split_counts"],
                class_counts=dataset["class_counts"],
            ),
            limitations=self.card["limitations"],
            excluded_uses=self.card["excluded_uses"],
            robustness=self.evaluation["robustness"],
        )

    def samples(self, limit: int = 12) -> list[SampleStudy]:
        labels = {
            "true_positive": (
                "Pneumonia label / priority",
                "The label and queue route align, but the model still did not diagnose the patient.",
            ),
            "false_positive": (
                "Normal label / priority",
                "Earlier review adds workload even though the retrospective label is normal.",
            ),
            "false_negative": (
                "Pneumonia label / standard",
                "Standard review is not clearance; the study still requires interpretation.",
            ),
            "true_negative": (
                "Normal label / standard",
                "The study remains in standard review and is not declared healthy or cleared.",
            ),
        }
        per_group = max(1, min(3, (limit + 3) // 4))
        selected = []
        for comparison in labels:
            group = self.manifest[self.manifest["comparison"] == comparison].copy()
            group["distance_to_threshold"] = abs(group["model_score"] - self.threshold)
            selected.extend(group.nsmallest(per_group, "distance_to_threshold").to_dict("records"))
        studies = []
        for row in selected[:limit]:
            scenario_label, learning_note = labels[str(row["comparison"])]
            index = int(row["source_index"])
            studies.append(
                SampleStudy(
                    sample_id=str(row["sample_id"]),
                    scenario_label=scenario_label,
                    learning_note=learning_note,
                    dataset_label=str(row["dataset_label"]),
                    comparison=str(row["comparison"]),
                    model_score=float(row["model_score"]),
                    route=str(row["queue_action"]),
                    image_data_uri=self.explain.png_data_uri(self.test.images[index]),
                )
            )
        return studies

    def score(self, request: ScoreRequest) -> ScoreResponse:
        row = self._row(request.sample_id)
        index = int(row["source_index"])
        transformed = bool(request.blur_radius or request.exposure_shift)
        image = self.data.transform_image(
            self.test.images[index],
            blur_radius=request.blur_radius,
            exposure_shift=request.exposure_shift,
        )
        quality = self.data.image_quality(image)
        quality_info = QualityInfo(
            status=quality.status,
            mean_intensity=quality.mean_intensity,
            focus_score=quality.focus_score,
            reasons=list(quality.reasons),
        )
        if quality.status == "insufficient":
            return ScoreResponse(
                sample_id=request.sample_id,
                transformed=transformed,
                image_data_uri=self.explain.png_data_uri(image),
                overlay_data_uri=None,
                dataset_label=None if transformed else str(row["dataset_label"]),
                label_note=(
                    "No known outcome applies after transformation."
                    if transformed
                    else RETROSPECTIVE_NOTE
                ),
                model_score=None,
                threshold=self.threshold,
                route="quality_hold",
                route_label="Quality hold - recapture or qualified manual handling",
                model_name=self.card["model_name"],
                model_version=self.card["model_version"],
                score_note="The quality gate stopped ordinary scoring and queue routing.",
                quality=quality_info,
                influence_note=None,
            )

        heatmap, score = self.explain.grad_cam(self.model, image)
        route = "priority_review" if score >= self.threshold else "standard_review"
        overlay = self.explain.overlay(image, heatmap)
        return ScoreResponse(
            sample_id=request.sample_id,
            transformed=transformed,
            image_data_uri=self.explain.png_data_uri(image),
            overlay_data_uri=self.explain.png_data_uri(overlay),
            dataset_label=None if transformed else str(row["dataset_label"]),
            label_note=(
                "No known outcome applies after transformation."
                if transformed
                else RETROSPECTIVE_NOTE
            ),
            model_score=score,
            threshold=self.threshold,
            route=route,
            route_label=(
                "Priority review - earlier radiologist interpretation"
                if route == "priority_review"
                else "Standard review - radiologist interpretation still required"
            ),
            model_name=self.card["model_name"],
            model_version=self.card["model_version"],
            score_note=SCORE_NOTE,
            quality=quality_info,
            influence_note=INFLUENCE_NOTE,
        )

    def review_queue(self, limit: int = 25) -> ReviewQueue:
        priority = self.manifest[self.manifest["queue_action"] == "priority_review"]
        standard = self.manifest[self.manifest["queue_action"] == "standard_review"]
        items = priority.nlargest(limit, "model_score")
        teaching = pd.concat(
            [
                self.manifest[self.manifest["comparison"] == "false_positive"].nsmallest(
                    3, "model_score"
                ),
                self.manifest[self.manifest["comparison"] == "false_negative"].nlargest(
                    3, "model_score"
                ),
            ],
            ignore_index=True,
        )
        return ReviewQueue(
            summary=QueueSummary(
                heldout_studies=len(self.manifest),
                priority_review=len(priority),
                standard_review=len(standard),
                quality_hold=int((self.manifest["quality_status"] == "insufficient").sum()),
                threshold=self.threshold,
                priority_review_rate=len(priority) / len(self.manifest),
                pneumonia_labeled_in_priority=int((priority["dataset_label_id"] == 1).sum()),
                normal_labeled_in_priority=int((priority["dataset_label_id"] == 0).sum()),
            ),
            items=[self._queue_item(row) for row in items.to_dict("records")],
            teaching_cases=[self._queue_item(row) for row in teaching.to_dict("records")],
            retrospective_note=RETROSPECTIVE_NOTE,
        )

    def _row(self, sample_id: str) -> pd.Series:
        if sample_id not in self._rows.index:
            raise ValueError(f"Unknown packaged sample '{sample_id}'.")
        row = self._rows.loc[sample_id]
        if isinstance(row, pd.DataFrame):
            raise ValueError(f"Sample identifier '{sample_id}' is not unique.")
        return row

    @staticmethod
    def _queue_item(row: dict) -> QueueItem:
        route = str(row["queue_action"])
        return QueueItem(
            sample_id=str(row["sample_id"]),
            dataset_label=str(row["dataset_label"]),
            model_score=float(row["model_score"]),
            route=route,
            route_label="Priority review" if route == "priority_review" else "Standard review",
            comparison=str(row["comparison"]),
        )