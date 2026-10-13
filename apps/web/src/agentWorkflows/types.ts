export type Step = "sense" | "plan" | "act" | "check" | "ask";
export type Pattern = "single" | "sequential" | "handoff" | "group_chat" | "concurrent";

export interface ToolSpec {
  id: string;
  label: string;
  step: Step;
  kind: "lookup" | "model" | "action" | "check" | "code";
  description: string;
  source: string;
  approval: boolean;
}

export interface AgentSpec {
  id: string;
  label: string;
  role: string;
  color: string;
  instructions: string;
  tools: string[];
  step: Step;
  kind: "agent" | "chair";
}

export interface NodeSpec {
  id: string;
  label: string;
  kind: "input" | "output" | "human" | "code";
  detail: string;
}

export interface EdgeSpec {
  source: string;
  target: string;
  kind: "flow" | "handoff" | "chair" | "approval";
  label: string;
}

export interface TaskSpec {
  id: string;
  label: string;
  prompt: string;
  note: string;
  truth: string;
}

export interface ScenarioSpec {
  id: string;
  title: string;
  tagline: string;
  industry: string;
  pattern: Pattern;
  pattern_label: string;
  summary: string;
  watch_for: string[];
  agents: AgentSpec[];
  tools: ToolSpec[];
  nodes: NodeSpec[];
  edges: EdgeSpec[];
  layout: Record<string, [number, number]>;
  tasks: TaskSpec[];
  requires: string[];
  data_note: string;
  has_live: boolean;
}

export interface CheckItem {
  check: string;
  ok: boolean;
  detail?: string;
}

export interface RunEvent {
  seq: number;
  t: number;
  type: string;
  agent?: string;
  tool?: string;
  text?: string;
  step?: Step;
  args?: unknown;
  result?: unknown;
  ok?: boolean;
  call_id?: string;
  approval?: boolean;
  request_id?: string;
  approved?: boolean;
  by?: string;
  source?: string;
  target?: string;
  round?: number;
  node?: string;
  title?: string;
  passed?: boolean;
  checks?: CheckItem[];
  status?: string;
  error?: string | null;
  prompt?: string;
  task?: string;
}

export interface RunStats {
  model_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  approvals: number;
  handoffs: number;
  messages: number;
  per_agent?: Record<string, { model_calls: number; tool_calls: number; tokens: number }>;
}

export interface RunResult {
  headline?: string;
  fields?: { label: string; value: string }[];
  document?: unknown;
  code?: string | null;
  copy?: string;
  final?: string;
  outbox?: Record<string, unknown>[];
}

export interface Run {
  schema?: string;
  id: string;
  scenario: string;
  pattern?: Pattern;
  task: { id: string; label: string; prompt: string; truth?: string };
  mode: string;
  model?: string | null;
  framework?: string;
  started_at?: string;
  seconds?: number;
  status: string;
  error?: string | null;
  stats?: RunStats;
  result?: RunResult;
  events: RunEvent[];
}

export interface RecordingSummary {
  file: string;
  scenario: string;
  task_id: string;
  task_label: string;
  status: string;
  seconds: number;
  model?: string | null;
  started_at?: string;
  headline?: string | null;
  model_calls?: number;
  tool_calls?: number;
  tokens?: number;
}

export interface RunChoice {
  key: string;
  label: string;
  detail: string;
  source: "recorded" | "live";
  load: () => Promise<Run>;
}

export interface Health {
  status: string;
  live_ready: boolean;
  model: string | null;
  framework: string;
  services: Record<string, boolean>;
  busy: boolean;
}

export interface LiveAvailability {
  available: boolean;
  reason: string;
}
