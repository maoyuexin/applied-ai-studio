"""Declarative scenario description shared by the runner and the web canvas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .runner import BuildContext

STEPS = ("sense", "plan", "act", "check", "ask")
PATTERNS = ("single", "sequential", "handoff", "group_chat", "concurrent")


@dataclass
class ToolSpec:
    id: str
    label: str
    step: str
    kind: str  # lookup | model | action | check | code
    description: str
    source: str = ""
    approval: bool = False


@dataclass
class AgentSpec:
    id: str
    label: str
    role: str
    color: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    step: str = "plan"
    kind: str = "agent"  # agent | chair


@dataclass
class NodeSpec:
    id: str
    label: str
    kind: str  # input | output | human | code
    detail: str = ""


@dataclass
class EdgeSpec:
    source: str
    target: str
    kind: str = "flow"  # flow | handoff | chair | approval
    label: str = ""


@dataclass
class TaskSpec:
    id: str
    label: str
    prompt: str
    note: str = ""
    # Ground truth the agents never see; shown after the run.
    truth: str = ""


@dataclass
class Scenario:
    id: str
    title: str
    tagline: str
    industry: str
    pattern: str
    pattern_label: str
    summary: str
    watch_for: list[str]
    agents: list[AgentSpec]
    tools: list[ToolSpec]
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]
    layout: dict[str, tuple[float, float]]
    tasks: list[TaskSpec]
    requires: list[str] = field(default_factory=list)
    data_note: str = ""
    builder: Callable[["BuildContext"], Any] | None = None
    summarize: Callable[[list[dict], list[dict]], dict] | None = None

    def task(self, task_id: str) -> TaskSpec:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Unknown task {task_id!r} for scenario {self.id!r}")

    def agent(self, agent_id: str) -> AgentSpec:
        return next(a for a in self.agents if a.id == agent_id)

    def to_dict(self) -> dict:
        data = {
            key: value
            for key, value in asdict(self).items()
            if key not in {"builder", "summarize"}
        }
        data["layout"] = {key: list(value) for key, value in self.layout.items()}
        return data

    def validate(self) -> None:
        assert self.pattern in PATTERNS, self.pattern
        tool_ids = {t.id for t in self.tools}
        node_ids = {a.id for a in self.agents} | {n.id for n in self.nodes}
        for agent in self.agents:
            assert agent.step in STEPS, (self.id, agent.id)
            for tool_id in agent.tools:
                assert tool_id in tool_ids, (self.id, agent.id, tool_id)
        for spec in self.tools:
            assert spec.step in STEPS, (self.id, spec.id)
        for edge in self.edges:
            assert edge.source in node_ids and edge.target in node_ids, (self.id, edge)
        for node_id in node_ids:
            assert node_id in self.layout, (self.id, node_id)
        assert self.tasks, self.id
