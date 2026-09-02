"""Controlled robustness checks and representative retrospective cases."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, data, metrics, models


ROBUSTNESS_SCENARIOS = {
    "Original": {},
    "Severe blur": {"blur_radius": 12.0},
    "Underexposed": {"exposure_shift": -100.0},
    "Overexposed": {"exposure_shift": 100.0},
}


def transformed_examples(image: np.ndarray) -> tuple[list[np.ndarray], pd.DataFrame]:
    """Return one original and three severe incoming-image quality stress tests."""
    images = []
    rows = []
    for scenario, transformation in ROBUSTNESS_SCENARIOS.items():
        transformed = image if not transformation else data.transform_image(image, **transformation)
        quality = data.image_quality(transformed)
        images.append(transformed)
        rows.append(
            {
                "Scenario": scenario,
                "Purpose": (
                    "Reference incoming image"
                    if scenario == "Original"
                    else "Incoming-image stress test; not training augmentation"
                ),
                "Technical check": "Pass" if quality.status == "sufficient" else "Fail",
                "Workflow action": (
                    "Continue to model scoring"
                    if quality.status == "sufficient"
                    else "Stop ordinary scoring; recapture or qualified manual handling"
                ),
                "Measured evidence": _quality_evidence(quality),
            }
        )
    return images, pd.DataFrame(rows)


def _quality_evidence(quality: data.QualityResult) -> str:
    """Explain the classroom quality decision with the measured values and limits."""
    if quality.mean_intensity < config.MIN_MEAN_INTENSITY:
        return (
            f"Mean intensity {quality.mean_intensity:.3f} is below "
            f"{config.MIN_MEAN_INTENSITY:.3f}."
        )
    if quality.mean_intensity > config.MAX_MEAN_INTENSITY:
        return (
            f"Mean intensity {quality.mean_intensity:.3f} is above "
            f"{config.MAX_MEAN_INTENSITY:.3f}."
        )
    if quality.focus_score < config.MIN_FOCUS_SCORE:
        return (
            f"Focus score {quality.focus_score:.3f} is below "
            f"{config.MIN_FOCUS_SCORE:.3f}."
        )
    return (
        f"Mean intensity {quality.mean_intensity:.3f} and focus score "
        f"{quality.focus_score:.3f} are inside the classroom bounds."
    )


def robustness_results(
    model: models.SmallPneumoniaCNN,
    images: np.ndarray,
    labels: np.ndarray,
    threshold: float,
) -> list[dict[str, float | int | str]]:
    """Measure model behavior and quality routing under bounded transformations."""
    rows = []
    for scenario, transformation in ROBUSTNESS_SCENARIOS.items():
        transformed = (
            images
            if not transformation
            else np.stack([data.transform_image(image, **transformation) for image in images])
        )
        scores = models.predict_scores(model, transformed)
        result = metrics.evaluate(labels, scores, threshold)
        quality = [data.image_quality(image).status == "sufficient" for image in transformed]
        rows.append({"scenario": scenario, **result, "quality_pass_rate": float(np.mean(quality))})
    return rows


def representative_cases(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    per_group: int = 2,
) -> tuple[list[int], list[str]]:
    """Select cases nearest the cutoff from all four confusion-matrix cells."""
    truth = np.asarray(labels, dtype=int)
    predicted = np.asarray(scores) >= threshold
    groups = [
        ("True positive", (truth == 1) & predicted),
        ("False positive", (truth == 0) & predicted),
        ("False negative", (truth == 1) & ~predicted),
        ("True negative", (truth == 0) & ~predicted),
    ]
    selected: list[int] = []
    titles: list[str] = []
    for label, mask in groups:
        candidates = np.flatnonzero(mask)
        order = np.argsort(np.abs(np.asarray(scores)[candidates] - threshold))
        for index in candidates[order[:per_group]]:
            selected.append(int(index))
            titles.append(f"{label}<br>score {scores[index]:.3f}")
    return selected, titles