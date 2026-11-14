import { useCallback, useEffect, useRef, useState } from "react";

export type PipelineKey = "video" | "image" | "voice" | "article" | "inspect" | "alerts";
export type RunStatus = "running" | "waiting" | "completed" | "failed" | "canceled";
export type StepStatus = "pending" | "running" | "waiting" | "done" | "skipped" | "failed";
export type ArtifactStatus = "queued" | "running" | "ready" | "failed" | "blocked" | "canceled" | "superseded";
export type Verdict = "keep" | "usable" | "regenerate" | "reject";
export type CheckState = "ok" | "warn" | "bad" | "info";
export type TextRole = "text-draft" | "text-judge";

export interface Check {
  key: string;
  label: string;
  state: CheckState;
  basis: string;
}

export interface Reference {
  sha: string;
  role: "subject" | "style" | "scene";
  name: string;
}

export interface Shot {
  id: string;
  title: string;
  subject: "product" | "people" | "scene";
  mode: "i2v" | "t2v";
  keyframe_prompt: string;
  prompt: string;
  sound: string;
  on_screen_text: string;
}

export interface ScriptLine {
  id: string;
  speaker: string;
  text: string;
  style: string;
}

export interface Speaker {
  name: string;
  voice: string;
  style: string;
}

export interface ArticleSource {
  title: string;
  text: string;
  url: string;
  published: string;
}

export interface Claim {
  claim: string;
  verdict: "supported" | "partly" | "unsupported";
  evidence: string;
  note: string;
  source: number | null;
}

export interface InspectQuestion {
  key: string;
  text: string;
  short: string;
  kind: "choice" | "count" | "open";
  choices: string[];
  expect: "label" | "decline" | "none";
  flag_terms: string[];
  tolerance: number;
}

export interface InspectImage {
  sha: string;
  thumb_sha?: string;
  name: string;
  group: string;
  truth: Record<string, string>;
  note: string;
}

export interface InspectPolicy {
  identity: "refuse" | "allow";
  retention_days: number;
  access: string;
  signoff: "yes" | "no";
  notice: "yes" | "no";
  note: string;
}

/** One model answer in a disagreement: which try, what it said (read as) and how it was marked. */
export interface InspectMark {
  model: string;
  try: number;
  value: string;
  grade: string;
}

export interface InspectResolution {
  outcome: "label stands" | "fixed";
  value: string;
  was?: string;
  note: string;
  at: string;
}

export interface InspectModelReport {
  questions: Record<string, Record<string, number>>;
  correct: number;
  wrong: number;
  overconfident: number;
  unsure: number;
  invalid: number;
  graded: number;
  right_share: number | null;
  consistent: [number, number] | null;
  median_seconds: number | null;
}

export interface InspectReport {
  counts: { answers: number; blocked: number; failed: number; expected: number };
  models: Record<string, InspectModelReport>;
  groups: Array<{ group: string; models: Record<string, [number, number]> }>;
  disagreements: Array<{
    image_id: string; image: string; group: string; question: string; label: string;
    answers: InspectMark[]; resolution: InspectResolution | null;
  }>;
  fixes: number;
}

export interface Brief {
  brief: string;
  references?: Reference[];
  must_not_include?: string;
  visible_label?: string;
  shots?: number;
  seconds?: number;
  takes_per_shot?: number;
  size?: string;
  end_title?: string;
  end_tagline?: string;
  voiceover?: string;
  voice?: string;
  use_case?: string;
  candidates?: number;
  prompt_helper?: boolean;
  title?: string;
  format?: string;
  target_seconds?: number;
  locale?: string;
  speakers?: Speaker[];
  pause_ms?: number;
  disclosure?: boolean;
  audience?: string;
  tone?: string;
  target_words?: number;
  sources?: ArticleSource[];
  fact_check?: boolean;
  instructions?: string;
  questions?: InspectQuestion[];
  images?: InspectImage[];
  models?: string[];
  tries?: number;
  moments?: AlertMoment[];
  languages?: AlertLanguage[];
  max_chars?: number;
  watch_terms?: string[];
}

export interface AlertMoment {
  name: string;
  group: string;
  facts: string;
  question: string;
  note: string;
}

export interface AlertLanguage {
  code: string;
  name: string;
  disclosure: string;
}

export interface AlertsReport {
  counts: { drafts: number; blocked: number; failed: number; expected: number };
  models: Record<string, { drafts: number; messages: number; flagged: number; checks: Record<string, number>; median_seconds: number | null }>;
  languages: Record<string, { messages: number; flagged: number }>;
  signed: { approve: number; edit: number; reject: number; open: number; approved_flagged: number };
}

export interface C2pa {
  checked: boolean;
  present: boolean | null;
  valid: boolean | null;
  issuer?: string;
  detail?: string;
}

export interface Metrics {
  motion?: number | null;
  mean_db?: number | null;
  peak_db?: number | null;
  silent_gaps?: number | null;
  duration?: number | null;
  width?: number | null;
  height?: number | null;
  has_audio?: boolean;
  word_errors?: number;
  words?: number;
  transcript?: string | null;
  confidence?: number | null;
  diffs?: Array<{ script: string; heard: string }>;
  clips?: number;
  end_card?: boolean;
  lines?: number;
  c2pa?: C2pa;
  unsupported?: number;
  partly?: number;
  claims?: number;
}

export interface ArtifactParams {
  seconds?: number;
  size?: string;
  mode?: string;
  remix_of_label?: string;
  keyframe_id?: string;
  width?: number;
  height?: number;
  operation?: string;
  roles?: string[];
  note?: string;
  core?: string;
  voice?: string;
  style?: string;
  speaker?: string;
  locale?: string;
  edit_list?: string[];
  edit_labels?: string[];
  title?: string;
  label?: string;
  model?: string;
  try?: number;
  moment?: number;
}

export interface ProvenanceReport {
  final: { label: string; c2pa: C2pa };
  takes: Array<{ label: string; c2pa: C2pa | null; deployment: string; model_version: string | null }>;
  visible_label: string;
  models: string[];
  note: string;
}

export interface ArtifactData {
  role?: string;
  position?: number;
  transcript?: Array<{ speaker: string; text: string }>;
  voices?: string[];
  source_label?: string;
  imported_from?: string;
  headline?: string;
  body?: string;
  claims?: Claim[];
  author?: string;
  judge?: string;
  markdown?: string;
  label?: string;
  [key: string]: unknown;
}

export interface Artifact {
  id: string;
  run_id: string;
  step_key: string;
  kind: string;
  grp: string | null;
  label: string | null;
  parent_id: string | null;
  status: ArtifactStatus;
  role: string | null;
  provider: string | null;
  deployment: string | null;
  model_version: string | null;
  prompt: string | null;
  inputs: string[];
  params: ArtifactParams;
  vendor_job_id: string | null;
  progress: number | null;
  media_sha: string | null;
  media_type: string | null;
  thumb_sha: string | null;
  gen_seconds: number | null;
  metrics: Metrics;
  checks: Check[];
  verdict: Verdict | null;
  note: string | null;
  checklist: Record<string, boolean | null>;
  error: string | null;
  error_code: string | null;
  data: ArtifactData;
  seq: number;
  created_at: string;
  updated_at: string;
}

export interface StepData {
  shots?: Shot[];
  notes?: string;
  drafts?: number;
  model?: string | null;
  seconds?: number;
  feedback?: string | null;
  edited?: boolean;
  prompt?: string;
  lines?: ScriptLine[];
  final_id?: string;
  title?: string;
  label?: string;
  report?: ProvenanceReport | InspectReport | AlertsReport;
  headline?: string;
  points?: Array<{ text: string; sources: number[] }>;
  version_id?: string;
  system?: string;
  calls?: number;
  prompts?: string[];
  policy?: InspectPolicy;
}

export interface Step {
  run_id: string;
  idx: number;
  key: string;
  title: string;
  gate: boolean;
  status: StepStatus;
  data: StepData;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunEvent {
  id: number;
  at: string;
  level: "info" | "warn" | "error" | "success";
  code: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface Counters {
  drafts?: number;
  languages?: string[];
  outputs?: string;
  thumb_sha?: string | null;
  takes?: number;
  kept?: number;
  passed?: number;
  ready?: number;
  video_seconds?: number;
  images?: number;
  versions?: number;
  blocked?: number;
  lines?: number;
  audio_seconds?: number;
  median_motion?: number | null;
  final_duration?: number | null;
  models?: string[];
  answers?: number;
}

export interface Run {
  id: string;
  pipeline: PipelineKey;
  title: string;
  template: string | null;
  status: RunStatus;
  brief: Brief;
  settings: { models?: Partial<Record<TextRole, string>> };
  parent_run_id: string | null;
  tags: string[];
  restricted: boolean;
  source: string;
  current_step: string | null;
  counters: Counters;
  error: string | null;
  rev: number;
  created_at: string;
  updated_at: string;
}

export interface StepSpec {
  key: string;
  title: string;
  gate: boolean;
  optional: boolean;
  description: string;
  role: string | null;
}

export interface Template {
  id: string;
  title: string;
  description: string;
  defaults: Partial<Brief>;
}

export interface PipelineInfo {
  key: PipelineKey;
  title: string;
  summary: string;
  roles: string[];
  steps: StepSpec[];
  templates: Template[];
  use_cases?: Record<string, { title: string; size: string; checklist: string[] }>;
}

export interface Decision {
  id: number;
  artifact_id: string | null;
  step_key: string | null;
  action: string;
  verdict: string | null;
  note: string | null;
  at: string;
}

export interface Gate {
  step: string;
  ready: boolean;
  reason: string;
}

export interface RunDetail {
  run: Run;
  pipeline: PipelineInfo | null;
  steps: Step[];
  artifacts: Artifact[];
  events: RunEvent[];
  decisions: Decision[];
  gate: Gate | null;
}

export interface RunSummary {
  id: string;
  pipeline: PipelineKey;
  pipeline_title: string;
  title: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  restricted: boolean;
  source: string;
  parent_run_id: string | null;
  tags: string[];
  counters: Counters;
  error: string | null;
  brief_excerpt: string;
  step: { key: string; title: string; index: number; total: number; status: StepStatus } | null;
  steps_done: number;
  steps_total: number;
}

export interface RunList {
  runs: RunSummary[];
  tags: string[];
  storage_bytes: number;
  data_dir: string;
}

export interface RoleTest {
  ok: boolean;
  seconds: number;
  detail: string;
  code?: string;
  at: string;
}

export interface RoleStatus {
  role: string;
  label: string;
  configured: boolean;
  resource: string;
  deployment: string;
  model: string;
  note: string;
  last_test: RoleTest | null;
}

export interface StudioStatus {
  install: string;
  auth: string;
  provider_mode: "live" | "fake";
  data_dir: string;
  storage_bytes: number;
  tools: Record<string, boolean>;
  roles: RoleStatus[];
  caps: Record<string, { label: string; used: number; cap: number; detail: string }>;
  pipelines: Array<{ key: PipelineKey; title: string; ready: boolean; missing: string[] }>;
  video_retirement: { on: string; days_left: number } | null;
  hide_restricted: boolean;
  text_models: string[];
  text_defaults: Record<TextRole, string>;
}

export interface Voice {
  name: string;
  display: string;
  locale: string;
  gender: string | null;
  styles: string[];
}

export interface Upload {
  sha: string;
  thumb_sha: string;
  media_type: string;
  name: string;
  width: number;
  height: number;
}

export interface Estimate {
  estimate: Record<string, number | string>;
  usage: Record<string, number>;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const BASE = "/api/design";
const UNREACHABLE = "The Design Studio service is not reachable. Start it with `npm run dev:design` (or `npm run dev`).";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((item: { msg?: string; loc?: unknown[] }) => `${(item.loc ?? []).slice(1).join(".")}: ${item.msg}`).join("; ");
      }
    } catch {
      // Not JSON: usually the dev proxy reporting that the service is down.
    }
    if (!detail) detail = [502, 503, 504].includes(response.status) ? UNREACHABLE : `HTTP ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface CreateRunBody {
  pipeline: PipelineKey;
  brief: Brief;
  title?: string;
  template?: string;
  parent_run_id?: string;
  tags?: string[];
  models?: Partial<Record<TextRole, string>>;
}

export const designApi = {
  status: () => request<StudioStatus>("/status"),
  testRole: (role: string) => request<RoleTest>(`/status/test/${role}`, { method: "POST" }),
  pipelines: () => request<PipelineInfo[]>("/pipelines"),
  estimate: (pipeline: PipelineKey, brief: Brief) => request<Estimate>("/estimate", post({ pipeline, brief })),
  voices: (locale?: string) => request<Voice[]>(`/voices${locale ? `?locale=${encodeURIComponent(locale)}` : ""}`),
  runs: (filters: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const suffix = query.toString();
    return request<RunList>(`/runs${suffix ? `?${suffix}` : ""}`);
  },
  run: (id: string) => request<RunDetail>(`/runs/${id}`),
  create: (body: CreateRunBody) => request<RunDetail>("/runs", post(body)),
  act: <T = unknown>(id: string, action: string, payload: Record<string, unknown> = {}) =>
    request<{ result: T; detail: RunDetail }>(`/runs/${id}/actions/${action}`, post(payload)),
  update: (id: string, body: { title?: string; tags?: string[]; restricted?: boolean }) =>
    request<RunDetail>(`/runs/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  remove: (id: string) => request<void>(`/runs/${id}`, { method: "DELETE" }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Upload>("/uploads", { method: "POST", body: form });
  },
  importBundle: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<RunDetail>("/runs/import", { method: "POST", body: form });
  },
  inspectKit: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ title: string; tags: string[]; brief: Partial<Brief> }>("/inspect/kit", { method: "POST", body: form });
  },
  exportUrl: (id: string) => `${BASE}/runs/${id}/export`,
};

export const mediaUrl = (sha: string, download?: string) =>
  `${BASE}/media/${sha}${download ? `?download=${encodeURIComponent(download)}` : ""}`;

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Load a run and keep it live: server-sent events trigger a refetch; polling covers proxies that buffer. */
export function useRun(runId: string) {
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const inFlight = useRef(false);
  const again = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) {
      again.current = true;
      return;
    }
    inFlight.current = true;
    try {
      do {
        again.current = false;
        setDetail(await designApi.run(runId));
        setError(null);
      } while (again.current);
    } catch (problem) {
      setError(errorMessage(problem));
    } finally {
      inFlight.current = false;
    }
  }, [runId]);

  useEffect(() => {
    setDetail(null);
    void refresh();
    let timer: number | undefined;
    const schedule = () => {
      if (timer !== undefined) return;
      timer = window.setTimeout(() => {
        timer = undefined;
        void refresh();
      }, 250);
    };
    const source = new EventSource(`${BASE}/runs/${runId}/stream`);
    source.addEventListener("hello", () => setLive(true));
    source.addEventListener("changed", schedule);
    source.addEventListener("event", schedule);
    source.onerror = () => setLive(false);
    const poll = window.setInterval(() => {
      if (source.readyState !== EventSource.OPEN) void refresh();
    }, 4000);
    return () => {
      source.close();
      window.clearInterval(poll);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [runId, refresh]);

  return { detail, setDetail, error, refresh, live };
}

/** Run a loader on mount (and when `key` changes); exposes data, error, loading and reload. */
export function useLoad<T>(load: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loader = useRef(load);
  loader.current = load;

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await loader.current());
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, key]);

  return { data, error, loading, reload, setData };
}
