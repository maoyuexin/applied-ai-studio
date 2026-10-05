"""Pipeline building blocks: step specs, the Pipeline base class and shared check helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..engine import RunContext


class ActionError(ValueError):
    """A user action that is not allowed right now (HTTP 409 with a readable reason)."""


@dataclass(frozen=True)
class StepSpec:
    key: str
    title: str
    gate: bool = False
    optional: bool = False
    description: str = ""
    role: str | None = None


@dataclass
class Template:
    id: str
    title: str
    description: str
    defaults: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    key: str = ""
    title: str = ""
    summary: str = ""
    steps: tuple[StepSpec, ...] = ()
    templates: tuple[Template, ...] = ()
    roles: tuple[str, ...] = ()

    # Definition

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "summary": self.summary,
            "roles": list(self.roles),
            "steps": [step.__dict__ for step in self.steps],
            "templates": [template.__dict__ for template in self.templates],
        }

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        return {}

    def default_title(self, brief: dict[str, Any]) -> str:
        text = str(brief.get("brief", "")).strip().split(".")[0]
        return (text[:60] + "…") if len(text) > 60 else (text or f"New {self.title.lower()} run")

    # Execution hooks

    def should_skip(self, ctx: RunContext, step: dict[str, Any]) -> bool:
        return False

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        raise NotImplementedError

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        raise NotImplementedError

    def step_settled(self, ctx: RunContext, step: dict[str, Any]) -> str:
        """Status for a step whose initial work is finished: 'waiting', 'done' or 'failed'."""
        if step["gate"]:
            return "waiting"
        failed = [a for a in ctx.artifacts(step_key=step["key"]) if a["status"] in ("failed", "blocked")]
        return "failed" if failed else "done"

    def gate_status(self, ctx: RunContext, step: dict[str, Any]) -> tuple[bool, str]:
        return True, ""

    async def approve(self, ctx: RunContext, step: dict[str, Any], payload: dict[str, Any]) -> None:
        return None

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        raise ActionError(f"Unknown action for {self.title}: {name}")

    def on_decision(self, ctx: RunContext, artifact: dict[str, Any], verdict: str | None) -> None:
        return None

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        return {}


# Shared helpers


def check(key: str, label: str, state: str, basis: str = "") -> dict[str, str]:
    return {"key": key, "label": label, "state": state, "basis": basis}


def c2pa_check(result: dict[str, Any]) -> dict[str, str]:
    if not result.get("checked"):
        return check("c2pa", "Content Credentials: not checked", "info", result.get("detail", ""))
    if not result.get("present"):
        return check("c2pa", "Content Credentials: none found", "warn", "c2patool read the file")
    if result.get("valid"):
        issuer = f" ({result['issuer']})" if result.get("issuer") else ""
        return check("c2pa", f"Content Credentials: present, valid{issuer}", "ok", "c2patool")
    # The vendor's signature failing (e.g. an expired signing certificate) is a provenance finding, not a content defect.
    return check("c2pa", f"Content Credentials: present, {result.get('detail', 'fails check')}", "warn", "c2patool")


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split())[:limit]


def rules_sentence(must_not_include: str) -> str:
    items = [item.strip() for item in must_not_include.replace("·", ",").replace(";", ",").split(",") if item.strip()]
    return f"Keep it free of: {', '.join(items)}." if items else ""
