"""Optional multimodal interpretation attempt for the Module 3 notebook."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

from . import config


CAPTURE_PATH = config.ARTIFACT_DIR / "multimodal_demo_response.json"
DEFAULT_MODEL = os.getenv("M3_MULTIMODAL_MODEL", "gpt-5.4")
PROMPT_VERSION = "m3-multimodal-v1"
REQUIRED_FIELDS = (
    "visible_features",
    "preliminary_findings",
    "possible_hypotheses",
    "uncertainties",
    "radiologist_checks",
)
MULTIMODAL_PROMPT = """You are examining a de-identified educational pediatric chest X-ray thumbnail.

1. Describe visible image features conservatively.
2. Draft possible preliminary radiology findings.
3. List possible diagnostic hypotheses only when supported by a visible feature.
4. State uncertainty and the limitations caused by this low-resolution image.
5. State what a radiologist would need to verify.

Do not provide treatment advice. Do not claim a confirmed diagnosis.
Return one JSON object with exactly these array fields: visible_features,
preliminary_findings, possible_hypotheses, uncertainties, and radiologist_checks.
Do not wrap the JSON in Markdown."""


def select_priority_example(scores: np.ndarray, threshold: float) -> int:
    """Return the priority-routed example nearest the frozen cutoff."""

    values = np.asarray(scores, dtype=float).reshape(-1)
    priority_indices = np.flatnonzero(values >= float(threshold))
    if priority_indices.size == 0:
        raise ValueError("No priority-routed example is available.")
    distances = values[priority_indices] - float(threshold)
    return int(priority_indices[int(np.argmin(distances))])


def prepare_display_image(image: np.ndarray, display_size: int = 512) -> Image.Image:
    """Convert a 128 x 128 grayscale array to a larger display-only PNG image."""

    pixels = np.asarray(image)
    if pixels.shape != (config.IMAGE_SIZE, config.IMAGE_SIZE):
        raise ValueError(
            f"Expected {(config.IMAGE_SIZE, config.IMAGE_SIZE)}, got {pixels.shape}."
        )
    if not np.issubdtype(pixels.dtype, np.number):
        raise TypeError("Image pixels must be numeric.")
    clipped = np.clip(pixels, 0, 255).astype(np.uint8)
    source = Image.fromarray(clipped, mode="L")
    return source.resize((display_size, display_size), Image.Resampling.NEAREST)


def result_rows(result: dict[str, Any]) -> list[dict[str, str]]:
    """Return display rows without changing the generated content."""

    labels = {
        "visible_features": "Visible features",
        "preliminary_findings": "Preliminary findings",
        "possible_hypotheses": "Possible hypotheses",
        "uncertainties": "Uncertainty and limitations",
        "radiologist_checks": "What a radiologist should verify",
    }
    rows = []
    for field in REQUIRED_FIELDS:
        values = result.get(field, [])
        rows.append(
            {
                "Section": labels[field],
                "Unverified generated content": "\n".join(f"- {value}" for value in values)
                or "- No statement returned",
            }
        )
    return rows


def image_html(image: Image.Image, alt_text: str) -> str:
    """Return a self-contained image element with meaningful alternative text."""

    encoded = _image_as_base64_png(image)
    return (
        f'<img src="data:image/png;base64,{encoded}" alt="{escape(alt_text, quote=True)}" '
        f'width="{image.width}" height="{image.height}" '
        'style="max-width:100%;height:auto;image-rendering:pixelated">'
    )


async def analyze_with_fallback(
    image: Image.Image,
    *,
    sample_id: str,
    live: bool = False,
    model: str = DEFAULT_MODEL,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """Run one vision request or return the packaged response for the same sample."""

    captured = load_captured_result(sample_id)
    if not live:
        return captured

    try:
        return await _analyze_live(
            image,
            sample_id=sample_id,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        fallback = deepcopy(captured)
        fallback["mode"] = "captured fallback after live error"
        fallback["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        return fallback


def load_captured_result(sample_id: str) -> dict[str, Any]:
    """Load and validate the packaged classroom fallback."""

    payload = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    if payload.get("sample_id") != sample_id:
        raise ValueError(
            f"Captured response is for {payload.get('sample_id')!r}, not {sample_id!r}."
        )
    return _normalize_result(payload)


async def _analyze_live(
    image: Image.Image,
    *,
    sample_id: str,
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        from copilot import CopilotClient
        from copilot.rpc import PermissionDecisionReject
        from copilot.session_events import AssistantMessageData, SessionIdleData
    except ImportError as exc:
        raise RuntimeError(
            "Live mode requires github-copilot-sdk==1.0.8 in the notebook environment."
        ) from exc

    def reject_permission(request: Any, invocation: dict[str, Any]) -> Any:
        del request, invocation
        return PermissionDecisionReject(
            feedback="This notebook session does not permit tools or external actions."
        )

    with tempfile.TemporaryDirectory(prefix="m3-copilot-") as base_directory:
        async with CopilotClient(mode="empty", base_directory=base_directory) as client:
            model_info = await _find_model(client, model)
            if not _supports_vision(model_info):
                raise RuntimeError(
                    f"The selected Copilot model {model!r} does not support vision."
                )

            messages: list[str] = []
            done = asyncio.Event()
            session = await client.create_session(
                model=model,
                tools=[],
                available_tools=[],
                on_permission_request=reject_permission,
                infinite_sessions={"enabled": False},
                memory={"enabled": False},
                enable_session_store=False,
                system_message={
                    "mode": "customize",
                    "sections": {
                        "code_change_rules": {"action": "remove"},
                        "environment_context": {"action": "remove"},
                    },
                    "content": (
                        "Analyze only the attached image. Follow the requested JSON schema "
                        "and medical uncertainty boundary exactly."
                    ),
                },
            )
            try:
                def on_event(event: Any) -> None:
                    match event.data:
                        case AssistantMessageData() as data:
                            if data.content:
                                messages.append(data.content)
                        case SessionIdleData():
                            done.set()

                session.on(on_event)
                await session.send(
                    MULTIMODAL_PROMPT,
                    attachments=[
                        {
                            "type": "blob",
                            "data": _image_as_base64_png(image),
                            "mimeType": "image/png",
                            "displayName": f"{sample_id}.png",
                        }
                    ],
                )
                await asyncio.wait_for(done.wait(), timeout=timeout_seconds)
            finally:
                await session.disconnect()

    if not messages:
        raise RuntimeError("Copilot returned no assistant message.")
    parsed = _parse_json_object(messages[-1])
    parsed.update(
        {
            "mode": "live",
            "model": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_id": sample_id,
            "prompt_version": PROMPT_VERSION,
            "boundary": "Unverified educational output; not a diagnosis.",
        }
    )
    return _normalize_result(parsed)


async def _find_model(client: Any, model_name: str) -> Any:
    models = await client.list_models()
    for model in models:
        identifier = _get_value(model, "id") or _get_value(model, "name")
        if identifier == model_name:
            return model
    available = sorted(
        str(_get_value(model, "id") or _get_value(model, "name")) for model in models
    )
    raise RuntimeError(
        f"Copilot model {model_name!r} is unavailable. Available models: {available}"
    )


def _supports_vision(model: Any) -> bool:
    capabilities = _get_value(model, "capabilities")
    supports = _get_value(capabilities, "supports")
    vision = _get_value(supports, "vision")
    if vision is not None:
        return bool(vision)
    return bool(_get_value(capabilities, "supports_vision"))


def _get_value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _image_as_base64_png(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Copilot response did not contain a JSON object.")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Copilot response JSON must be an object.")
    return parsed


def _normalize_result(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for field in REQUIRED_FIELDS:
        value = normalized.get(field, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{field} must be a list of strings.")
        normalized[field] = value
    normalized.setdefault("prompt_version", PROMPT_VERSION)
    normalized.setdefault("boundary", "Unverified educational output; not a diagnosis.")
    return normalized