"""Influence overlays that explain the model without claiming medical causality."""

from __future__ import annotations

import base64
import io

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image

from . import models


def early_feature_maps(
    model: models.SmallPneumoniaCNN,
    image: np.ndarray,
    count: int = 6,
) -> list[np.ndarray]:
    """Return display-ready responses from the CNN's first convolution block."""
    model.eval()
    tensor = torch.from_numpy(np.asarray(image)).float().unsqueeze(0).unsqueeze(0)
    if tensor.max() > 1:
        tensor = tensor / 255.0
    normalized = (tensor - model.pixel_mean) / torch.clamp(model.pixel_std, min=1e-6)
    with torch.inference_mode():
        activations = model.features[:3](normalized)[0, :count].cpu().numpy()

    maps = []
    for activation in activations:
        values = activation - activation.min()
        maximum = float(values.max())
        if maximum > 0:
            values /= maximum
        maps.append(np.rint(values * 255).astype(np.uint8))
    return maps


def grad_cam(model: models.SmallPneumoniaCNN, image: np.ndarray) -> tuple[np.ndarray, float]:
    """Return a Grad-CAM map and positive-class score for one image."""
    model.eval()
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def capture(_module, _inputs, output: torch.Tensor) -> None:
        activations.append(output)
        output.register_hook(lambda value: gradients.append(value))

    handle = model.gradcam_layer.register_forward_hook(capture)
    tensor = torch.from_numpy(np.asarray(image)).float().unsqueeze(0).unsqueeze(0)
    if tensor.max() > 1:
        tensor = tensor / 255.0
    model.zero_grad(set_to_none=True)
    logit = model(tensor)
    logit[0].backward()
    handle.remove()

    weights = gradients[0].mean(dim=(2, 3), keepdim=True)
    heatmap = torch.relu((weights * activations[0]).sum(dim=1, keepdim=True))
    heatmap = functional.interpolate(
        heatmap, size=np.asarray(image).shape, mode="bilinear", align_corners=False
    )[0, 0]
    heatmap -= heatmap.min()
    heatmap /= torch.clamp(heatmap.max(), min=1e-8)
    return heatmap.detach().numpy(), float(torch.sigmoid(logit[0]).detach())


def overlay(image: np.ndarray, heatmap: np.ndarray, opacity: float = 0.42) -> np.ndarray:
    """Blend a model-influence heatmap over the grayscale image."""
    grayscale = np.asarray(image, dtype=np.float32)
    if grayscale.max(initial=0.0) > 1.0:
        grayscale /= 255.0
    base = np.repeat(grayscale[..., None], 3, axis=2)
    colors = plt.get_cmap("inferno")(np.clip(heatmap, 0.0, 1.0))[..., :3]
    strength = np.clip(heatmap[..., None] * opacity, 0.0, opacity)
    return np.rint(np.clip(base * (1.0 - strength) + colors * strength, 0.0, 1.0) * 255).astype(
        np.uint8
    )


def png_data_uri(image: np.ndarray) -> str:
    """Encode an image for a self-contained API response."""
    buffer = io.BytesIO()
    Image.fromarray(np.asarray(image).astype(np.uint8)).save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")