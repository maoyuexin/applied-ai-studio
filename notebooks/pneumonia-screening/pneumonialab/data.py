"""Verified data loading, bounded transformations, and image-quality checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as functional
from PIL import Image, ImageFilter
from torch.utils.data import Dataset

from . import config


@dataclass(frozen=True)
class ImageSplit:
    """One source-defined dataset split."""

    name: str
    images: np.ndarray
    labels: np.ndarray


@dataclass(frozen=True)
class QualityResult:
    """Technical image-quality result used before model routing."""

    status: Literal["sufficient", "insufficient"]
    mean_intensity: float
    focus_score: float
    reasons: tuple[str, ...]


class PneumoniaDataset(Dataset):
    """Torch dataset with conservative train-only augmentation."""

    def __init__(self, split: ImageSplit, augment: bool = False) -> None:
        self.images = split.images
        self.labels = split.labels
        self.augment = augment

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        image = torch.from_numpy(self.images[index]).float().unsqueeze(0) / 255.0
        label = torch.tensor(float(self.labels[index]), dtype=torch.float32)
        if self.augment:
            image = self._augment(image)
        return image, label

    @staticmethod
    def _augment(image: torch.Tensor) -> torch.Tensor:
        """Apply slight translation and exposure jitter without mirroring anatomy."""
        padding = 4
        padded = functional.pad(image, (padding, padding, padding, padding), mode="reflect")
        top = int(torch.randint(0, padding * 2 + 1, (1,)).item())
        left = int(torch.randint(0, padding * 2 + 1, (1,)).item())
        cropped = padded[:, top : top + config.IMAGE_SIZE, left : left + config.IMAGE_SIZE]
        brightness = 0.9 + float(torch.rand(1).item()) * 0.2
        return torch.clamp(cropped * brightness, 0.0, 1.0)


def file_md5(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a streaming MD5 checksum for source verification."""
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path = config.DATA_ARCHIVE) -> dict[str, object]:
    """Verify source checksum, arrays, split counts, and class totals."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Prepare the committed dataset before class.")
    checksum = file_md5(path)
    if checksum != config.DATASET_MD5:
        raise ValueError(f"Dataset checksum mismatch: expected {config.DATASET_MD5}, got {checksum}.")

    expected_keys = {
        "train_images", "train_labels", "val_images", "val_labels", "test_images", "test_labels"
    }
    with np.load(path) as archive:
        if set(archive.files) != expected_keys:
            raise ValueError(f"Unexpected archive keys: {sorted(archive.files)}")
        split_counts = {
            "train": len(archive["train_images"]),
            "validation": len(archive["val_images"]),
            "test": len(archive["test_images"]),
        }
        labels = np.concatenate(
            [archive["train_labels"], archive["val_labels"], archive["test_labels"]]
        ).reshape(-1)
        class_counts = {
            config.CLASS_NAMES[class_id]: int(np.count_nonzero(labels == class_id))
            for class_id in range(len(config.CLASS_NAMES))
        }
        image_shapes = {
            split: tuple(archive[f"{source}_images"].shape)
            for split, source in (("train", "train"), ("validation", "val"), ("test", "test"))
        }
    if split_counts != config.EXPECTED_SPLIT_COUNTS:
        raise ValueError(f"Unexpected split counts: {split_counts}")
    if class_counts != config.EXPECTED_CLASS_COUNTS:
        raise ValueError(f"Unexpected class counts: {class_counts}")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "md5": checksum,
        "split_counts": split_counts,
        "class_counts": class_counts,
        "image_shapes": image_shapes,
    }


def load_splits(path: Path = config.DATA_ARCHIVE) -> dict[str, ImageSplit]:
    """Load source-defined splits into memory after verifying the archive."""
    verify_archive(path)
    with np.load(path) as archive:
        return {
            "train": ImageSplit(
                "train", archive["train_images"].copy(), archive["train_labels"].reshape(-1).copy()
            ),
            "validation": ImageSplit(
                "validation", archive["val_images"].copy(), archive["val_labels"].reshape(-1).copy()
            ),
            "test": ImageSplit(
                "test", archive["test_images"].copy(), archive["test_labels"].reshape(-1).copy()
            ),
        }


def split_summary(splits: dict[str, ImageSplit]) -> pd.DataFrame:
    """Return class counts and prevalence for notebook display."""
    rows = []
    for name, split in splits.items():
        for class_id, class_name in enumerate(config.CLASS_NAMES):
            count = int(np.count_nonzero(split.labels == class_id))
            rows.append(
                {
                    "Split": name.title(),
                    "Dataset label": class_name,
                    "Images": count,
                    "Share of split": count / len(split.labels),
                }
            )
    return pd.DataFrame(rows)


def image_statistics(split: ImageSplit) -> pd.DataFrame:
    """Summarize each image with simple technical measurements for EDA."""
    normalized = split.images.astype(np.float32) / 255.0
    horizontal_change = np.diff(normalized, axis=2)
    vertical_change = np.diff(normalized, axis=1)
    return pd.DataFrame(
        {
            "Dataset label": [config.CLASS_NAMES[int(label)] for label in split.labels],
            "Mean brightness": normalized.mean(axis=(1, 2)),
            "Contrast": normalized.std(axis=(1, 2)),
            "Edge variation": (
                horizontal_change.var(axis=(1, 2)) + vertical_change.var(axis=(1, 2))
            )
            * 10_000,
        }
    )


def training_normalization(split: ImageSplit) -> tuple[float, float]:
    """Compute pixel normalization from training images only."""
    pixels = split.images.astype(np.float32) / 255.0
    return float(pixels.mean()), float(pixels.std())


def image_quality(image: np.ndarray) -> QualityResult:
    """Apply a simple technical gate, not a diagnostic image-quality assessment."""
    normalized = _normalized_image(image)
    mean_intensity = float(normalized.mean())
    focus_score = float(
        (np.diff(normalized, axis=0).var() + np.diff(normalized, axis=1).var()) * 10_000
    )
    reasons = []
    if mean_intensity < config.MIN_MEAN_INTENSITY:
        reasons.append("Mean intensity is below the classroom quality range.")
    if mean_intensity > config.MAX_MEAN_INTENSITY:
        reasons.append("Mean intensity is above the classroom quality range.")
    if focus_score < config.MIN_FOCUS_SCORE:
        reasons.append("Edge variation is below the classroom focus range.")
    return QualityResult(
        status="insufficient" if reasons else "sufficient",
        mean_intensity=mean_intensity,
        focus_score=focus_score,
        reasons=tuple(reasons),
    )


def transform_image(
    image: np.ndarray,
    blur_radius: float = 0.0,
    exposure_shift: float = 0.0,
) -> np.ndarray:
    """Create a bounded what-if image for robustness teaching."""
    if not 0.0 <= blur_radius <= 12.0:
        raise ValueError("blur_radius must be between 0 and 12.")
    if not -100.0 <= exposure_shift <= 100.0:
        raise ValueError("exposure_shift must be between -100 and 100.")
    normalized = _normalized_image(image)
    if exposure_shift >= 0:
        normalized = normalized + (1.0 - normalized) * (0.85 * exposure_shift / 100.0)
    else:
        normalized = normalized * (1.0 + 0.85 * exposure_shift / 100.0)
    if blur_radius:
        pil_image = Image.fromarray(np.rint(normalized * 255).astype(np.uint8), mode="L")
        normalized = np.asarray(
            pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius)), dtype=np.float32
        ) / 255.0
    return np.rint(np.clip(normalized, 0.0, 1.0) * 255).astype(np.uint8)


def augmentation_examples(image: np.ndarray) -> tuple[list[np.ndarray], pd.DataFrame]:
    """Create deterministic examples of common image augmentations and their use status."""
    normalized = _normalized_image(image)
    original = _to_uint8(normalized)

    padded = np.pad(normalized, 4, mode="reflect")
    translated = _to_uint8(padded[1 : 1 + config.IMAGE_SIZE, 7 : 7 + config.IMAGE_SIZE])
    brighter = _to_uint8(normalized * 1.12)

    pil_image = Image.fromarray(original, mode="L")
    rotated = np.asarray(
        pil_image.rotate(
            5,
            resample=Image.Resampling.BILINEAR,
            fillcolor=int(np.median(original)),
        ),
        dtype=np.uint8,
    )
    zoom_size = int(round(config.IMAGE_SIZE * 1.08))
    zoomed = pil_image.resize((zoom_size, zoom_size), Image.Resampling.BILINEAR)
    crop_start = (zoom_size - config.IMAGE_SIZE) // 2
    zoomed = np.asarray(
        zoomed.crop(
            (
                crop_start,
                crop_start,
                crop_start + config.IMAGE_SIZE,
                crop_start + config.IMAGE_SIZE,
            )
        ),
        dtype=np.uint8,
    )
    image_mean = float(normalized.mean())
    higher_contrast = _to_uint8(image_mean + (normalized - image_mean) * 1.18)
    flipped = np.ascontiguousarray(np.fliplr(original))

    table = pd.DataFrame(
        [
            ("Original", "No transformation", "Reference", "The stored training image."),
            ("Translation", "Move a few pixels", "Used here", "Models small positioning differences."),
            ("Brightness jitter", "Lighten or darken", "Used here", "Models modest exposure differences."),
            ("Small rotation", "Rotate 5 degrees", "Possible", "Use only within plausible acquisition variation."),
            ("Small zoom / crop", "Zoom 8% and recrop", "Possible", "May remove edge information; validate carefully."),
            ("Contrast jitter", "Increase dark-light separation", "Possible", "May exaggerate subtle structures."),
            ("Horizontal flip", "Reverse left and right", "Avoid here", "Laterality can matter in medical images."),
        ],
        columns=["Technique", "What changes", "Status in this notebook", "Medical-image caution"],
    )
    return [original, translated, brighter, rotated, zoomed, higher_contrast, flipped], table


def sample_manifest(split: ImageSplit) -> pd.DataFrame:
    """Build stable sample identifiers without exposing hidden patient identifiers."""
    return pd.DataFrame(
        {
            "sample_id": [f"{split.name}-{index:04d}" for index in range(len(split.images))],
            "split": split.name,
            "source_index": np.arange(len(split.images), dtype=int),
            "dataset_label_id": split.labels.astype(int),
            "dataset_label": [config.CLASS_NAMES[int(label)] for label in split.labels],
        }
    )


def _normalized_image(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image)
    if values.shape != (config.IMAGE_SIZE, config.IMAGE_SIZE):
        raise ValueError(
            f"Expected one {config.IMAGE_SIZE} x {config.IMAGE_SIZE} image; got {values.shape}."
        )
    normalized = values.astype(np.float32)
    if normalized.max(initial=0.0) > 1.0:
        normalized /= 255.0
    return np.clip(normalized, 0.0, 1.0)


def _to_uint8(image: np.ndarray) -> np.ndarray:
    """Convert a normalized image to display-ready uint8 pixels."""
    return np.rint(np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)