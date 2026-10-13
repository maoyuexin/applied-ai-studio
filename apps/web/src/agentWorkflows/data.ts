import scenariosJson from "../../../../data/agent-workflows/scenarios.json";
import recordingsJson from "../../../../data/agent-workflows/recordings.json";
import type {
  Health,
  LiveAvailability,
  RecordingSummary,
  Run,
  RunChoice,
  RunEvent,
  ScenarioSpec,
} from "./types";

export const SCENARIOS = scenariosJson as unknown as ScenarioSpec[];
const RECORDINGS = recordingsJson as unknown as RecordingSummary[];

const recordingLoaders = import.meta.glob<Run>("../../../../data/agent-workflows/recordings/*/*.json", {
  import: "default",
});

const API = "/api/agent-workflows";

function loaderFor(file: string): () => Promise<Run> {
  const key = Object.keys(recordingLoaders).find((path) => path.endsWith(`/recordings/${file}`));
  if (!key) return () => Promise.reject(new Error(`Missing recording ${file}`));
  return recordingLoaders[key];
}

export function recordedChoices(scenarioId: string): RunChoice[] {
  const order = SCENARIOS.find((s) => s.id === scenarioId)?.tasks.map((t) => t.id) ?? [];
  const rank = (taskId: string) => (order.includes(taskId) ? order.indexOf(taskId) : order.length);
  const items = RECORDINGS.filter((item) => item.scenario === scenarioId).sort((a, b) => rank(a.task_id) - rank(b.task_id));
  const takes: Record<string, number> = {};
  return items.map((item) => {
    takes[item.task_id] = (takes[item.task_id] ?? 0) + 1;
    const sameTask = items.filter((other) => other.task_id === item.task_id).length;
    return {
      key: `recorded:${item.file}`,
      label: sameTask > 1 ? `${item.task_label} · take ${takes[item.task_id]}` : item.task_label,
      detail: `${item.headline ?? item.status} · ${Math.round(item.seconds)} s · ${item.model_calls ?? 0} model calls`,
      source: "recorded",
      load: loaderFor(item.file),
    };
  });
}

async function getJson<T>(url: string, timeoutMs = 4000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchHealth(): Promise<Health | null> {
  try {
    return await getJson<Health>(`${API}/health`, 3000);
  } catch {
    return null;
  }
}

export async function fetchLiveAvailability(): Promise<Record<string, LiveAvailability>> {
  try {
    const items = await getJson<(ScenarioSpec & { live: LiveAvailability })[]>(`${API}/scenarios`);
    return Object.fromEntries(items.map((item) => [item.id, item.live]));
  } catch {
    return {};
  }
}

interface SavedRunSummary {
  scenario: string;
  name: string;
  folder: string;
  task: string;
  status: string;
  seconds: number;
  started_at: string;
  stats: { model_calls?: number };
}

export async function savedLiveChoices(scenarioId: string): Promise<RunChoice[]> {
  try {
    const items = await getJson<SavedRunSummary[]>(`${API}/recordings`);
    return items
      .filter((item) => item.folder === "live-runs" && item.scenario === scenarioId)
      .reverse()
      .map((item) => ({
        key: `live:${item.name}`,
        label: `Live · ${new Date(item.started_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} · ${item.task}`,
        detail: `${item.status} · ${Math.round(item.seconds ?? 0)} s · ${item.stats?.model_calls ?? 0} model calls`,
        source: "live" as const,
        load: () => getJson<Run>(`${API}/recordings/live-runs/${scenarioId}/${encodeURIComponent(item.name)}`, 10000),
      }));
  } catch {
    return [];
  }
}

export async function startLiveRun(scenario: string, task: string): Promise<string> {
  const response = await fetch(`${API}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ scenario, task }),
  });
  const body = (await response.json().catch(() => ({}))) as { id?: string; detail?: string };
  if (!response.ok || !body.id) throw new Error(body.detail ?? `Could not start the run (${response.status})`);
  return body.id;
}

export function streamLiveRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onDone: (run: Partial<Run>) => void,
  onError: (message: string) => void,
): () => void {
  const source = new EventSource(`${API}/runs/${runId}/events`);
  source.addEventListener("event", (message) => onEvent(JSON.parse((message as MessageEvent).data) as RunEvent));
  source.addEventListener("done", (message) => {
    onDone(JSON.parse((message as MessageEvent).data) as Partial<Run>);
    source.close();
  });
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) return;
    onError("Lost the connection to the live run.");
    source.close();
  };
  return () => source.close();
}

export async function sendApproval(runId: string, requestId: string, approved: boolean): Promise<void> {
  const response = await fetch(`${API}/runs/${runId}/approvals/${encodeURIComponent(requestId)}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  if (!response.ok) throw new Error("The approval was not accepted (it may have timed out).");
}

export async function stopLiveRun(runId: string): Promise<void> {
  await fetch(`${API}/runs/${runId}/stop`, { method: "POST" });
}
