import type {
  AiSolutionBlueprint,
  AiSolutionBlueprintRequest,
  ChatRequest,
  CourseCase,
  FitAssessmentInput,
  FitAssessmentResult,
  UseCase,
  WorkflowDraft,
  WorkflowDraftInput,
} from "@applied-ai-studio/contracts";

interface ListResponse<T> {
  items: T[];
}

export type AgentEvent =
  | { type: "meta"; sessionId: string; model: string }
  | { type: "delta"; content: string }
  | { type: "done" }
  | { type: "error"; message: string };

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new Error(payload?.error ?? `Request failed with ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export async function getUseCases(): Promise<UseCase[]> {
  const payload = await requestJson<ListResponse<UseCase>>("/api/catalog/use-cases");
  return payload.items;
}

export function getUseCase(id: string): Promise<UseCase> {
  return requestJson<UseCase>(`/api/catalog/use-cases/${encodeURIComponent(id)}`);
}

export function getCourseCase(id: string): Promise<CourseCase> {
  return requestJson<CourseCase>(`/api/catalog/course-cases/${encodeURIComponent(id)}`);
}

export async function getIndustries(): Promise<Array<{ id: string; label: string; count: number }>> {
  const payload = await requestJson<ListResponse<{ id: string; label: string; count: number }>>(
    "/api/catalog/industries",
  );
  return payload.items;
}

export function createAssessment(input: FitAssessmentInput): Promise<FitAssessmentResult> {
  return requestJson<FitAssessmentResult>("/api/catalog/assessments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

/** Where a workflow draft came from. "starter" means Copilot was unavailable. */
export type WorkflowDraftSource = "copilot" | "starter";

export interface WorkflowDraftResult {
  draft: WorkflowDraft;
  source: WorkflowDraftSource;
}

/**
 * Ask Copilot to draft a workflow from the student's own problem statement, and fall back
 * to a fixed starter outline if it cannot.
 *
 * Copilot is free for students but only once their Student Developer Pack is approved,
 * which takes several days. Week one of the course is exactly when this feature is taught,
 * so an unavailable Copilot has to degrade into something usable rather than an error.
 *
 * The caller is told which path was taken so the UI can say so plainly. Passing a canned
 * outline off as a tailored one would contradict the assumption-labelling the course
 * grades students on.
 */
export async function createWorkflowDraft(input: WorkflowDraftInput): Promise<WorkflowDraftResult> {
  const body = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  } satisfies RequestInit;

  try {
    return { draft: await requestJson<WorkflowDraft>("/api/agent/workflow-drafts", body), source: "copilot" };
  } catch {
    // Deliberately swallowed: any Copilot failure - signed out, pending approval, quota,
    // timeout - leads to the same place. If the fallback itself fails, that error is real
    // and propagates to the caller.
    return { draft: await requestJson<WorkflowDraft>("/api/catalog/workflow-drafts", body), source: "starter" };
  }
}

export function createAiSolutionBlueprint(input: AiSolutionBlueprintRequest): Promise<AiSolutionBlueprint> {
  return requestJson<AiSolutionBlueprint>("/api/agent/solution-blueprints", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function streamAgentChat(
  request: ChatRequest,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Agent request failed with ${response.status}.`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let remoteError: string | null = null;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) {
        const event = JSON.parse(dataLine.slice(6)) as AgentEvent;
        if (event.type === "error") remoteError = event.message;
        onEvent(event);
      }
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }

  if (remoteError) throw new Error(remoteError);
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
  const response = await fetch(`/api/agent/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 404) {
    throw new Error("Could not clear the conversation.");
  }
}