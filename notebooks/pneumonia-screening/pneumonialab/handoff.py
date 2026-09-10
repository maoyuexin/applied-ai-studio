"""Export and verify the narrow contract consumed by the pneumonia API."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import torch

from . import config, data, evaluation as evaluation_helpers, metrics, models


def load_model(
    artifact_dir: Path = config.ARTIFACT_DIR,
) -> models.SmallPneumoniaCNN:
    """Reload the exact architecture and weights written by export."""
    package = torch.load(artifact_dir / "model.pt", map_location="cpu", weights_only=True)
    model = models.SmallPneumoniaCNN(
        pixel_mean=float(package["pixel_mean"]),
        pixel_std=float(package["pixel_std"]),
    )
    model.load_state_dict(package["state_dict"])
    return model.eval()


def export(
    training: models.TrainingResult,
    splits: dict[str, data.ImageSplit],
    validation_scores: np.ndarray,
    test_scores: np.ndarray,
    validation_policy: dict[str, float | int],
    test_result: dict[str, float | int],
    artifact_dir: Path = config.ARTIFACT_DIR,
) -> dict[str, str]:
    """Write the model, model card, policy, evaluation, and sample manifest."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.pt"
    card_path = artifact_dir / "model_card.json"
    policy_path = artifact_dir / "operating_policy.json"
    evaluation_path = artifact_dir / "evaluation.json"
    manifest_path = artifact_dir / "sample_manifest.parquet"

    torch.save(
        {
            "architecture": "SmallPneumoniaCNN",
            "state_dict": training.model.state_dict(),
            "pixel_mean": float(training.model.pixel_mean),
            "pixel_std": float(training.model.pixel_std),
        },
        model_path,
    )
    threshold = float(validation_policy["threshold"])
    manifest = data.sample_manifest(splits["test"])
    manifest["model_score"] = test_scores
    manifest["queue_action"] = np.where(
        test_scores >= threshold, "priority_review", "standard_review"
    )
    manifest["comparison"] = np.select(
        [
            (manifest["dataset_label_id"] == 1) & (manifest["queue_action"] == "priority_review"),
            (manifest["dataset_label_id"] == 0) & (manifest["queue_action"] == "priority_review"),
            (manifest["dataset_label_id"] == 1) & (manifest["queue_action"] == "standard_review"),
        ],
        ["true_positive", "false_positive", "false_negative"],
        default="true_negative",
    )
    quality = [data.image_quality(image) for image in splits["test"].images]
    manifest["quality_status"] = [result.status for result in quality]
    manifest["mean_intensity"] = [result.mean_intensity for result in quality]
    manifest["focus_score"] = [result.focus_score for result in quality]
    manifest.to_parquet(manifest_path, index=False, compression="zstd")

    policy = {
        "name": "Validation sensitivity objective",
        "selected_on": "validation split",
        "target_sensitivity": config.TARGET_VALIDATION_SENSITIVITY,
        "threshold": threshold,
        "quality_gate": {
            "min_focus_score": config.MIN_FOCUS_SCORE,
            "min_mean_intensity": config.MIN_MEAN_INTENSITY,
            "max_mean_intensity": config.MAX_MEAN_INTENSITY,
            "failure_action": "quality_hold",
        },
        "routes": {
            "quality_hold": "Recapture or qualified manual handling",
            "priority_review": "Earlier radiologist review",
            "standard_review": "Standard radiologist review",
        },
        "boundary": "Every study still requires qualified interpretation.",
    }
    policy_path.write_text(json.dumps(policy, indent=2))

    stress_test_results = evaluation_helpers.robustness_results(
        training.model,
        splits["test"].images,
        splits["test"].labels,
        threshold,
    )
    evaluation = {
        "majority_baseline_on_test": metrics.majority_baseline(splits["test"].labels),
        "validation_selected_policy": validation_policy,
        "test_at_validation_threshold": test_result,
        "robustness": stress_test_results,
        "training": {
            "history": training.history,
            "runtime_seconds": training.runtime_seconds,
            "best_epoch": training.best_epoch,
            "epochs_ran": len(training.history),
            "stopped_early": training.stopped_early,
        },
    }
    evaluation_path.write_text(json.dumps(evaluation, indent=2))

    archive = data.verify_archive()
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    card = {
        "model_name": "Compact pediatric chest X-ray prioritization CNN",
        "model_version": created,
        "created_utc": created,
        "framework": f"PyTorch {torch.__version__}",
        "packaging": "PyTorch state dictionary with shared architecture code",
        "architecture": "Four convolution blocks with global average pooling",
        "trainable_parameters": models.model_parameter_count(training.model),
        "input": {
            "shape": [1, config.IMAGE_SIZE, config.IMAGE_SIZE],
            "type": "grayscale image scaled to [0, 1]",
            "training_pixel_mean": float(training.model.pixel_mean),
            "training_pixel_std": float(training.model.pixel_std),
        },
        "dataset": {
            "name": config.DATASET_NAME,
            "version": config.DATASET_VERSION,
            "source": config.DATASET_SOURCE,
            "license": config.DATASET_LICENSE,
            "archive_md5": archive["md5"],
            "population": "Pediatric chest X-rays from the source study",
            "split_counts": archive["split_counts"],
            "class_counts": archive["class_counts"],
            "source_split_note": "The source study reports patient-separated training and test sets.",
        },
        "intended_use": (
            "Educational demonstration of ranking packaged, held-out images for earlier review."
        ),
        "measured_on_untouched_test": test_result,
        "operating_policy": policy,
        "limitations": [
            "Limited pediatric source population and clinical setting.",
            "The model sees pixels, not symptoms, vital signs, laboratory results, or history.",
            "Center-cropped and resized benchmark images do not reproduce a hospital imaging pipeline.",
            "Performance has not been externally or prospectively validated.",
            "Influence overlays describe model attention and do not prove medical reasoning.",
        ],
        "excluded_uses": [
            "Diagnosis, clearance, treatment selection, or treatment recommendation",
            "Use with real patient images",
            "Use outside this packaged educational dataset",
        ],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    card_path.write_text(json.dumps(card, indent=2))
    return {
        path.name: _formatted_size(path)
        for path in (model_path, card_path, policy_path, evaluation_path, manifest_path)
    }


def verify(
    splits: dict[str, data.ImageSplit] | None = None,
    artifact_dir: Path = config.ARTIFACT_DIR,
) -> dict[str, float | int | str]:
    """Reload artifacts and prove prediction, policy, and metric identity."""
    loaded_splits = splits or data.load_splits()
    model = load_model(artifact_dir)
    card = json.loads((artifact_dir / "model_card.json").read_text())
    policy = json.loads((artifact_dir / "operating_policy.json").read_text())
    manifest = pd.read_parquet(artifact_dir / "sample_manifest.parquet")
    scores = models.predict_scores(model, loaded_splits["test"].images)
    saved_scores = manifest["model_score"].to_numpy(dtype=float)
    max_score_delta = float(np.max(np.abs(scores - saved_scores)))
    threshold = float(policy["threshold"])
    reproduced = metrics.evaluate(loaded_splits["test"].labels, scores, threshold)
    claimed = card["measured_on_untouched_test"]
    count_drift = sum(abs(int(reproduced[key]) - int(claimed[key])) for key in ("tp", "fp", "fn", "tn"))
    decision_changes = int(
        np.count_nonzero((scores >= threshold) != (saved_scores >= threshold))
    )
    if max_score_delta > 1e-7 or count_drift or decision_changes:
        raise AssertionError("Reloaded artifacts do not reproduce the exported evaluation.")
    return {
        "status": "verified",
        "samples": len(scores),
        "max_score_delta": max_score_delta,
        "confusion_count_drift": count_drift,
        "decision_changes": decision_changes,
    }


def _formatted_size(path: Path) -> str:
    size = path.stat().st_size
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} KB"