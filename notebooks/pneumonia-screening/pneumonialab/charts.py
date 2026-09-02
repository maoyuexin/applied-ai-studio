"""Plotly figures shared by the executable notebook and offline HTML."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config, data


COLOR_NORMAL = "#5B8FF9"
COLOR_PNEUMONIA = "#E8913C"
COLOR_POLICY = "#6ABF9B"
COLOR_MUTED = "#8A91A3"
TEMPLATE = "plotly_white"


def _layout(figure: go.Figure, title: str, height: int = 430) -> go.Figure:
    figure.update_layout(
        title=title,
        template=TEMPLATE,
        height=height,
        margin=dict(l=55, r=30, t=70, b=55),
        font=dict(family="Arial", size=13, color="#20242B"),
        hoverlabel=dict(font_size=13),
    )
    return figure


def class_balance(splits: dict[str, data.ImageSplit]) -> go.Figure:
    frame = data.split_summary(splits)
    figure = go.Figure()
    for class_name, color in zip(
        config.CLASS_NAMES, (COLOR_NORMAL, COLOR_PNEUMONIA), strict=True
    ):
        subset = frame[frame["Dataset label"] == class_name]
        figure.add_bar(
            x=subset["Split"],
            y=subset["Images"],
            name=class_name,
            marker_color=color,
            customdata=np.stack([subset["Share of split"]], axis=-1),
            hovertemplate="%{x}<br>%{y:,} images<br>%{customdata[0]:.1%} of split<extra></extra>",
        )
    figure.update_layout(barmode="stack", legend_title_text="Dataset label")
    figure.update_yaxes(title="Images")
    return _layout(figure, "Pneumonia-labeled images are the majority in every split")


def image_gallery(
    images: list[np.ndarray] | np.ndarray,
    titles: list[str],
    heading: str,
) -> go.Figure:
    count = len(images)
    columns = min(4, count)
    rows = int(np.ceil(count / columns))
    figure = make_subplots(rows=rows, cols=columns, subplot_titles=titles)
    for index, image in enumerate(images):
        row, column = divmod(index, columns)
        values = np.asarray(image)
        if values.ndim == 2:
            values = np.repeat(values[..., None], 3, axis=2)
        figure.add_trace(go.Image(z=values), row=row + 1, col=column + 1)
        figure.update_xaxes(showticklabels=False, row=row + 1, col=column + 1)
        figure.update_yaxes(showticklabels=False, row=row + 1, col=column + 1)
    for annotation in figure.layout.annotations:
        annotation.font.size = 13
    figure = _layout(figure, heading, height=280 * rows + 40)
    figure.update_layout(margin=dict(l=55, r=30, t=110, b=55))
    return figure


def pixel_grid(
    image: np.ndarray,
    top: int = 56,
    left: int = 56,
    size: int = 8,
) -> go.Figure:
    """Show one image beside the numeric values in a small pixel patch."""
    values = np.asarray(image)
    if values.ndim != 2:
        raise ValueError(f"Expected one grayscale image; got shape {values.shape}.")
    if top < 0 or left < 0 or top + size > values.shape[0] or left + size > values.shape[1]:
        raise ValueError("Pixel patch must stay inside the image.")

    rgb = np.repeat(values[..., None], 3, axis=2)
    patch = values[top : top + size, left : left + size]
    figure = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.54, 0.46],
        subplot_titles=("The complete 128 x 128 image", f"An {size} x {size} patch as numbers"),
        horizontal_spacing=0.1,
    )
    figure.add_trace(go.Image(z=rgb), row=1, col=1)
    figure.add_shape(
        type="rect",
        x0=left - 0.5,
        y0=top - 0.5,
        x1=left + size - 0.5,
        y1=top + size - 0.5,
        line=dict(color=COLOR_POLICY, width=3),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Heatmap(
            z=patch,
            x=list(range(left, left + size)),
            y=list(range(top, top + size)),
            zmin=0,
            zmax=255,
            colorscale="gray",
            text=patch,
            texttemplate="%{text}",
            textfont=dict(size=11),
            colorbar=dict(title="Intensity", thickness=14, len=0.8),
            hovertemplate="row %{y}, column %{x}<br>intensity %{z}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    figure.update_xaxes(showticklabels=False, row=1, col=1)
    figure.update_yaxes(showticklabels=False, row=1, col=1)
    figure.update_xaxes(title="Pixel column", side="bottom", row=1, col=2)
    figure.update_yaxes(title="Row", autorange="reversed", row=1, col=2)
    figure = _layout(figure, "A grayscale image is a grid of 16,384 numeric inputs", height=570)
    figure.update_layout(margin=dict(l=55, r=30, t=100, b=80))
    return figure


def image_summary_scatter(frame: pd.DataFrame, per_class: int = 750) -> go.Figure:
    """Plot simple image-level summaries to show variation and class overlap."""
    figure = go.Figure()
    for class_name, color in zip(
        config.CLASS_NAMES, (COLOR_NORMAL, COLOR_PNEUMONIA), strict=True
    ):
        group = frame[frame["Dataset label"] == class_name]
        displayed = group.sample(n=min(per_class, len(group)), random_state=42)
        figure.add_scatter(
            x=displayed["Mean brightness"],
            y=displayed["Contrast"],
            mode="markers",
            name=class_name,
            marker=dict(color=color, size=7, opacity=0.46),
            customdata=np.stack([displayed["Edge variation"]], axis=-1),
            hovertemplate=(
                "%{fullData.name}<br>mean brightness %{x:.3f}"
                "<br>contrast %{y:.3f}<br>edge variation %{customdata[0]:.2f}<extra></extra>"
            ),
        )
    figure.update_xaxes(title="Mean brightness: 0 is dark, 1 is bright", range=[0, 1])
    figure.update_yaxes(title="Contrast: how spread out the pixel values are")
    figure.add_annotation(
        x=0,
        y=-0.2,
        xref="paper",
        yref="paper",
        xanchor="left",
        showarrow=False,
        text="Displayed: up to 750 training images per label. Measurements use all pixels in each image.",
        font=dict(size=11, color=COLOR_MUTED),
    )
    return _layout(
        figure,
        "Simple image summaries overlap: brightness and contrast are not the label",
        height=510,
    )


def pixel_distribution(splits: dict[str, data.ImageSplit]) -> go.Figure:
    figure = go.Figure()
    bins = np.linspace(0, 255, 52)
    for name, color in (("Normal", COLOR_NORMAL), ("Pneumonia-labeled", COLOR_PNEUMONIA)):
        class_id = config.CLASS_NAMES.index(name)
        pixels = splits["train"].images[splits["train"].labels == class_id, ::4, ::4].reshape(-1)
        counts, edges = np.histogram(pixels, bins=bins, density=True)
        centers = (edges[:-1] + edges[1:]) / 2
        figure.add_trace(
            go.Scatter(
                x=centers,
                y=counts,
                mode="lines",
                name=name,
                line=dict(color=color, width=3),
                hovertemplate="Intensity %{x:.0f}<br>Density %{y:.4f}<extra></extra>",
            )
        )
    figure.update_xaxes(title="Pixel intensity: 0 black to 255 white")
    figure.update_yaxes(title="Density")
    return _layout(figure, "Pixel distributions overlap: no single brightness rule solves the task")


def training_history(history: list[dict[str, float]]) -> go.Figure:
    frame = pd.DataFrame(history)
    figure = go.Figure()
    figure.add_scatter(
        x=frame["epoch"], y=frame["train_loss"], name="Training loss",
        mode="lines+markers", line=dict(color=COLOR_NORMAL, width=3)
    )
    figure.add_scatter(
        x=frame["epoch"], y=frame["validation_loss"], name="Validation loss",
        mode="lines+markers", line=dict(color=COLOR_PNEUMONIA, width=3)
    )
    figure.update_xaxes(title="Epoch", dtick=1)
    figure.update_yaxes(title="Weighted binary cross-entropy")
    return _layout(figure, "Training stops at the best validation checkpoint")


def score_distribution(labels: np.ndarray, scores: np.ndarray, threshold: float) -> go.Figure:
    figure = go.Figure()
    bins = np.linspace(0, 1, 31)
    for class_id, class_name, color in (
        (0, "Normal", COLOR_NORMAL),
        (1, "Pneumonia-labeled", COLOR_PNEUMONIA),
    ):
        counts, edges = np.histogram(scores[np.asarray(labels) == class_id], bins=bins)
        centers = (edges[:-1] + edges[1:]) / 2
        figure.add_bar(x=centers, y=counts, width=np.diff(edges), name=class_name, marker_color=color)
    figure.add_vline(
        x=threshold, line_color=COLOR_POLICY, line_width=3, line_dash="dash",
        annotation_text="Validation-selected cutoff", annotation_position="top left"
    )
    figure.update_layout(barmode="overlay", bargap=0.02)
    figure.update_traces(opacity=0.68, hovertemplate="Score %{x:.2f}<br>%{y} images<extra></extra>")
    figure.update_xaxes(title="Model score", range=[0, 1])
    figure.update_yaxes(title="Test images")
    return _layout(figure, "The cutoff converts a continuous score into queue routing")


def threshold_policy(frame: pd.DataFrame, selected_threshold: float) -> go.Figure:
    figure = go.Figure()
    for column, label, color in (
        ("sensitivity", "Sensitivity (pneumonia labels prioritized)", COLOR_PNEUMONIA),
        ("specificity", "Specificity (normal labels kept standard)", COLOR_NORMAL),
        ("review_rate", "Priority-review percentage (all images)", COLOR_MUTED),
    ):
        figure.add_scatter(
            x=frame["threshold"], y=frame[column], name=label,
            mode="lines", line=dict(color=color, width=3)
        )
    figure.add_vline(
        x=selected_threshold, line_color=COLOR_POLICY, line_width=3, line_dash="dash",
        annotation_text=f"Selected {selected_threshold:.3f}", annotation_position="top right"
    )
    figure.update_xaxes(title="Candidate cutoff", range=[0, 1])
    figure.update_yaxes(title="Percentage of the relevant group", tickformat=".0%", range=[0, 1.02])
    return _layout(figure, "A threshold is an operating policy, not a model fact")


def confusion_matrix(result: dict[str, float | int]) -> go.Figure:
    values = np.array([[result["tn"], result["fp"]], [result["fn"], result["tp"]]])
    text = np.array(
        [
            [f"{result['tn']}<br>Normal / standard", f"{result['fp']}<br>Normal / priority"],
            [f"{result['fn']}<br>Pneumonia / standard", f"{result['tp']}<br>Pneumonia / priority"],
        ]
    )
    figure = go.Figure(
        go.Heatmap(
            z=values,
            x=["Standard review", "Priority review"],
            y=["Normal label", "Pneumonia label"],
            text=text,
            texttemplate="%{text}",
            colorscale=[[0, "#EFF3F8"], [1, "#E8913C"]],
            showscale=False,
            hovertemplate="%{y}<br>%{x}<br>%{z} images<extra></extra>",
        )
    )
    figure.update_yaxes(autorange="reversed", title="Dataset label")
    figure.update_xaxes(title="Queue action")
    return _layout(figure, "Untouched test patients at the validation-selected cutoff")