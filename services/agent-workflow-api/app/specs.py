"""Declarative scenario description shared by the runner and the web canvas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .runner import BuildContext

STEPS = ("sense", "plan", "act", "check", "ask")
PATTERNS = ("single", "sequential", "handoff", "group_chat", "concurrent")
ACTOR_KINDS = ("trigger", "agent", "system", "model", "code", "person")
MATCH_KEYS = {"type", "agent", "tool", "node", "target", "nth", "last"}
# Each name has a renderer in apps/web/src/agentWorkflows/visuals.tsx.
VISUALS = {
    "alert", "receipt", "risk", "request", "approval", "note", "patient", "search", "checks", "trials",
    "shortlist", "machine", "manual", "workorder", "fieldcheck", "ticket", "code", "tests", "review",
    "meeting", "products", "banner", "claims",
}


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
class ActorSpec:
    """A swimlane in the business view: who does the work, in plain words."""

    id: str
    label: str
    kind: str  # trigger | agent | system | model | code | person
    plain: str
    ref: str = ""  # canvas agent, tool or node this actor stands for


@dataclass
class StageSpec:
    """One business step; events matching any matcher start it (nth/last pick one occurrence)."""

    id: str
    title: str
    actor: str
    plain: str
    match: list[dict]
    visual: str
    tech: str
    optional: bool = False
    skipped: str = ""


@dataclass
class BusinessSpec:
    question: str
    situation: str
    stakes: list[str]
    decides: str
    good: list[str]
    today: list[str]
    with_agent: list[str]
    actors: list[ActorSpec]
    stages: list[StageSpec]


def _matches(matcher: dict, event: dict) -> bool:
    return all(event.get(key) == value for key, value in matcher.items() if key not in {"nth", "last"})


def stage_of_events(business: BusinessSpec, events: list[dict]) -> list[int]:
    """Stage index per event (-1 before the first stage). Mirrors mapStages in business.ts."""
    hits: list[list[set[int]]] = []
    for stage in business.stages:
        sets = []
        for matcher in stage.match:
            found = [i for i, event in enumerate(events) if _matches(matcher, event)]
            if matcher.get("nth"):
                found = found[matcher["nth"] - 1 : matcher["nth"]]
            elif matcher.get("last"):
                found = found[-1:]
            sets.append(set(found))
        hits.append(sets)
    matched = [next((s for s, sets in enumerate(hits) if any(i in hit for hit in sets)), -1) for i in range(len(events))]
    assigned = list(matched)
    for i, event in enumerate(events):
        if matched[i] >= 0 or not event.get("agent") or event.get("type") != "agent_start":
            continue
        later = next((j for j in range(i + 1, len(events)) if matched[j] >= 0), None)
        if later is not None and events[later].get("agent") == event["agent"]:
            assigned[i] = matched[later]
    current = -1
    stages = []
    for stage in assigned:
        if stage >= 0:
            current = stage
        stages.append(current)
    return stages


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
    business: BusinessSpec | None = None
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
        if self.business:
            self._validate_business(node_ids, tool_ids)

    def _validate_business(self, node_ids: set[str], tool_ids: set[str]) -> None:
        business = self.business
        assert business is not None
        actor_ids = {actor.id for actor in business.actors}
        for actor in business.actors:
            assert actor.kind in ACTOR_KINDS, (self.id, actor.id)
            assert not actor.ref or actor.ref in node_ids | tool_ids, (self.id, actor.id, actor.ref)
        for stage in business.stages:
            assert stage.actor in actor_ids, (self.id, stage.id, stage.actor)
            assert stage.visual in VISUALS, (self.id, stage.id, stage.visual)
            assert stage.match, (self.id, stage.id)
            assert not stage.optional or stage.skipped, (self.id, stage.id, "optional stages explain a skip")
            for matcher in stage.match:
                assert set(matcher) <= MATCH_KEYS, (self.id, stage.id, matcher)
                assert matcher.get("agent") in {None} | node_ids, (self.id, stage.id, matcher)
                assert matcher.get("target") in {None} | node_ids, (self.id, stage.id, matcher)
                assert matcher.get("tool") in {None} | tool_ids, (self.id, stage.id, matcher)
                assert matcher.get("node") in {None} | node_ids, (self.id, stage.id, matcher)
