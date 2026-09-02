"""Single source of truth for the PneumoniaMNIST classroom workflow."""

from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
ARTIFACT_DIR = PROJECT_DIR / "artifacts"
BACKUP_DIR = PROJECT_DIR / "backup"

DATA_ARCHIVE = DATA_DIR / "pneumoniamnist_128.npz"
DATASET_URL = (
    "https://zenodo.org/records/10519652/files/pneumoniamnist_128.npz?download=1"
)
DATASET_MD5 = "05b46931834c231683c68f40c47b2971"
DATASET_NAME = "PneumoniaMNIST 128"
DATASET_VERSION = "v2"
DATASET_LICENSE = "CC BY 4.0"
DATASET_SOURCE = "MedMNIST+ / Kermany et al. pediatric chest X-rays"
DATASET_USE = "Educational demonstration; not intended for clinical use"

IMAGE_SIZE = 128
IMAGE_CHANNELS = 1
CLASS_NAMES = ("Normal", "Pneumonia-labeled")
EXPECTED_SPLIT_COUNTS = {"train": 4_708, "validation": 524, "test": 624}
EXPECTED_CLASS_COUNTS = {"Normal": 1_583, "Pneumonia-labeled": 4_273}

RANDOM_STATE = 42
BATCH_SIZE = 64
MAX_EPOCHS = 10
EARLY_STOPPING_PATIENCE = 3
TARGET_VALIDATION_SENSITIVITY = 0.90
MIN_FOCUS_SCORE = 0.5
MIN_MEAN_INTENSITY = 0.20
MAX_MEAN_INTENSITY = 0.90


def describe() -> str:
    """Return the stable configuration summary shown near the notebook start."""
    return (
        f"Dataset      : {DATASET_NAME} ({DATASET_VERSION})\n"
        f"Image input  : {IMAGE_SIZE} x {IMAGE_SIZE} grayscale\n"
        f"Splits       : {EXPECTED_SPLIT_COUNTS}\n"
        f"Policy target: at least {TARGET_VALIDATION_SENSITIVITY:.0%} validation sensitivity\n"
        f"Boundary     : {DATASET_USE}"
    )