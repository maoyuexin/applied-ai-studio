import type { RunEvent, ScenarioSpec, Step } from "./types";

export const STEPS: { id: Step; label: string; hint: string }[] = [
  { id: "sense", label: "Sense", hint: "Look things up" },
  { id: "plan", label: "Plan", hint: "Reason and decide" },
  { id: "act", label: "Act", hint: "Do or draft something" },
  { id: "check", label: "Check", hint: "Test the work" },
  { id: "ask", label: "Ask", hint: "A person decides" },
];

export const TIMELINE_TYPES = new Set([
  "run_start",
  "agent_start",
  "message",
  "tool_call",
  "handoff",
  "speaker",
  "approval_request",
  "code_step",
  "run_end",
]);

const MIN_GAP: Record<string, number> = {
  run_start: 0.2,
  agent_start: 0.6,
  message: 1.1,
  tool_call: 0.8,
  tool_result: 0.5,
  handoff: 0.9,
  speaker: 0.8,
  approval_request: 1.1,
  approval_response: 0.9,
  code_step: 1.3,
  run_end: 0.6,
  model_call: 0.25,
};
const MAX_GAP = 2.4;

/** Replay clock (seconds) at which each event appears: real gaps, squeezed into a watchable range. */
export function schedule(events: RunEvent[]): number[] {
  let clock = 0;
  let previous = events[0]?.t ?? 0;
  return events.map((event) => {
    const real = Math.max(0, event.t - previous);
    previous = event.t;
    const floor = MIN_GAP[event.type] ?? 0.3;
    clock += Math.min(Math.max(real, floor), Math.max(floor, MAX_GAP));
    return clock;
  });
}

export interface Transition {
  seq: number;
  from: string;
  to: string;
  kind: "flow" | "handoff" | "chair" | "approval" | "return";
}

export interface ViewState {
  activeNode: string | null;
  activeTool: { agent: string; tool: string; seq: number } | null;
  transition: Transition | null;
  modelPulse: { agent: string; seq: number } | null;
  visited: Set<string>;
  usedTools: Set<string>;
  stepCounts: Record<Step, number>;
  currentStep: Step | null;
  modelCalls: number;
  toolCalls: number;
  approvals: number;
  handoffs: number;
  elapsed: number;
  pendingApproval: RunEvent | null;
  finished: boolean;
  status: string | null;
}

export function deriveState(scenario: ScenarioSpec, events: RunEvent[], cursor: number): ViewState {
  const agentIds = new Set(scenario.agents.map((agent) => agent.id));
  const human = scenario.nodes.find((node) => node.kind === "human")?.id ?? null;
  const output = scenario.nodes.find((node) => node.kind === "output")?.id ?? null;
  const input = scenario.nodes.find((node) => node.kind === "input")?.id ?? null;
  const state: ViewState = {
    activeNode: null,
    activeTool: null,
    transition: null,
    modelPulse: null,
    visited: new Set(),
    usedTools: new Set(),
    stepCounts: { sense: 0, plan: 0, act: 0, check: 0, ask: 0 },
    currentStep: null,
    modelCalls: 0,
    toolCalls: 0,
    approvals: 0,
    handoffs: 0,
    elapsed: 0,
    pendingApproval: null,
    finished: false,
    status: null,
  };
  let lastNode = input;
  const answered = new Set<string>();

  const move = (seq: number, to: string | null, kind: Transition["kind"]) => {
    if (!to) return;
    if (lastNode && lastNode !== to) state.transition = { seq, from: lastNode, to, kind };
    lastNode = to;
    state.activeNode = to;
    state.visited.add(to);
  };

  for (const event of events.slice(0, cursor)) {
    state.elapsed = event.t;
    switch (event.type) {
      case "run_start":
        if (input) state.visited.add(input);
        break;
      case "agent_start":
        if (event.agent && agentIds.has(event.agent) && lastNode !== event.agent) move(event.seq, event.agent, "flow");
        state.activeTool = null;
        break;
      case "speaker":
        if (event.agent) {
          const chair = scenario.agents.find((agent) => agent.kind === "chair")?.id ?? null;
          if (chair) lastNode = chair;
          move(event.seq, event.agent, "chair");
        }
        break;
      case "handoff":
        state.handoffs += 1;
        if (event.source) lastNode = event.source;
        move(event.seq, event.target ?? null, "handoff");
        break;
      case "model_call":
        state.modelCalls += 1;
        if (event.agent) state.modelPulse = { agent: event.agent, seq: event.seq };
        break;
      case "message":
        if (event.step) {
          state.stepCounts[event.step] += 1;
          state.currentStep = event.step;
        }
        state.activeTool = null;
        break;
      case "tool_call":
        state.toolCalls += 1;
        if (event.step) {
          state.stepCounts[event.step] += 1;
          state.currentStep = event.step;
        }
        if (event.agent && event.tool) {
          state.activeTool = { agent: event.agent, tool: event.tool, seq: event.seq };
          state.usedTools.add(event.tool);
        }
        break;
      case "code_step":
        state.stepCounts.check += 1;
        state.currentStep = "check";
        move(event.seq, event.node ?? null, "flow");
        break;
      case "approval_request":
        state.stepCounts.ask += 1;
        state.currentStep = "ask";
        state.pendingApproval = event;
        if (event.agent) lastNode = event.agent;
        move(event.seq, human, "approval");
        break;
      case "approval_response":
        state.approvals += 1;
        if (event.request_id) answered.add(event.request_id);
        if (state.pendingApproval && answered.has(state.pendingApproval.request_id ?? "")) {
          const owner = state.pendingApproval.agent ?? null;
          state.pendingApproval = null;
          move(event.seq, owner, "return");
        }
        break;
      case "run_end":
        state.finished = true;
        state.status = event.status ?? null;
        state.activeTool = null;
        move(event.seq, output, "flow");
        break;
    }
  }
  return state;
}

export function stepColor(step: Step | undefined | null): string {
  switch (step) {
    case "sense":
      return "#7eaeb8";
    case "plan":
      return "#b48ead";
    case "act":
      return "#e8913c";
    case "check":
      return "#a3be8c";
    case "ask":
      return "#f0b429";
    default:
      return "#9396a6";
  }
}

export function formatSeconds(value: number): string {
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)} s`;
  const minutes = Math.floor(value / 60);
  return `${minutes} min ${Math.round(value - minutes * 60)} s`;
}
