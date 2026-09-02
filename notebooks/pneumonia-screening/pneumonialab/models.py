"""Compact CPU-friendly CNN training and reproducible prediction helpers."""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from . import config, data


class SmallPneumoniaCNN(nn.Module):
    """A compact CNN for one narrow educational image-classification task."""

    def __init__(self, pixel_mean: float, pixel_std: float) -> None:
        super().__init__()
        self.register_buffer("pixel_mean", torch.tensor(pixel_mean, dtype=torch.float32))
        self.register_buffer("pixel_std", torch.tensor(pixel_std, dtype=torch.float32))
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 96, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Linear(96, 1)

    @property
    def gradcam_layer(self) -> nn.Module:
        """Return the final convolutional feature layer."""
        return self.features[12]

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        normalized = (images - self.pixel_mean) / torch.clamp(self.pixel_std, min=1e-6)
        features = self.features(normalized)
        return self.classifier(features.flatten(1)).squeeze(1)


@dataclass
class TrainingResult:
    model: SmallPneumoniaCNN
    history: list[dict[str, float]]
    runtime_seconds: float
    best_epoch: int
    stopped_early: bool


def set_seed(seed: int = config.RANDOM_STATE) -> None:
    """Set all random sources used by this package."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def fit_small_cnn(
    splits: dict[str, data.ImageSplit],
    max_epochs: int = config.MAX_EPOCHS,
    patience: int = config.EARLY_STOPPING_PATIENCE,
    device_name: str = "cpu",
) -> TrainingResult:
    """Train with validation-loss early stopping and restore the best epoch."""
    set_seed()
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    device = torch.device(device_name)
    pixel_mean, pixel_std = data.training_normalization(splits["train"])
    model = SmallPneumoniaCNN(pixel_mean, pixel_std).to(device)
    train_dataset = data.PneumoniaDataset(splits["train"], augment=True)
    validation_dataset = data.PneumoniaDataset(splits["validation"])
    generator = torch.Generator().manual_seed(config.RANDOM_STATE)
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset, batch_size=config.BATCH_SIZE, shuffle=False, num_workers=0
    )

    positives = int(np.count_nonzero(splits["train"].labels == 1))
    negatives = len(splits["train"].labels) - positives
    positive_weight = torch.tensor([negatives / positives], dtype=torch.float32, device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=positive_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    best_loss = float("inf")
    best_epoch = 0
    best_state = copy.deepcopy(model.state_dict())
    epochs_without_improvement = 0
    history: list[dict[str, float]] = []
    started = time.perf_counter()

    for epoch in range(1, max_epochs + 1):
        model.train()
        train_loss = 0.0
        for images, labels in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(images.to(device))
            loss = criterion(logits, labels.to(device))
            loss.backward()
            optimizer.step()
            train_loss += float(loss.item()) * len(images)

        model.eval()
        validation_loss = 0.0
        with torch.inference_mode():
            for images, labels in validation_loader:
                logits = model(images.to(device))
                loss = criterion(logits, labels.to(device))
                validation_loss += float(loss.item()) * len(images)

        train_loss /= len(train_dataset)
        validation_loss /= len(validation_dataset)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": train_loss,
                "validation_loss": validation_loss,
            }
        )
        if validation_loss < best_loss - 1e-4:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.load_state_dict(best_state)
    model.to("cpu").eval()
    return TrainingResult(
        model=model,
        history=history,
        runtime_seconds=time.perf_counter() - started,
        best_epoch=best_epoch,
        stopped_early=len(history) < max_epochs,
    )


def predict_scores(
    model: SmallPneumoniaCNN,
    images: np.ndarray,
    batch_size: int = 128,
) -> np.ndarray:
    """Return positive-class model scores for uint8 images."""
    model.eval()
    scores = []
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            batch = torch.from_numpy(images[start : start + batch_size]).float().unsqueeze(1) / 255.0
            scores.append(torch.sigmoid(model(batch)).cpu().numpy())
    return np.concatenate(scores).astype(float)


def model_parameter_count(model: nn.Module) -> int:
    """Return the number of trainable model parameters."""
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)