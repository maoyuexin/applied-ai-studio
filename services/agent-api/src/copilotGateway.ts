import { randomUUID } from "node:crypto";
import { homedir } from "node:os";
import path from "node:path";
import {
  CopilotClient,
  defineTool,
  type PermissionRequest,
  type PermissionRequestResult,
} from "@github/copilot-sdk";
import {
  AI_SOLUTION_SCORE_THRESHOLD,
  aiSolutionBlueprintSchema,
  isAiSolutionEligible,
  workflowDraftSchema,
  type AiSolutionBlueprint,
  type AiSolutionBlueprintRequest,
  type WorkflowDraft,
  type WorkflowDraftInput,
} from "@applied-ai-studio/contracts";
import { z } from "zod";
import { CatalogClient } from "./catalogClient.js";

type CopilotSession = Awaited<ReturnType<CopilotClient["createSession"]>>;

interface SessionEntry {
  session: CopilotSession;
  busy: boolean;
  lastUsedAt: number;
}

export type AgentStreamEvent =
  | { type: "meta"; sessionId: string; model: string }
  | { type: "delta"; content: string }
  | { type: "done" }
  | { type: "error"; message: string };

export class SolutionBlueprintThresholdError extends Error {
  constructor(readonly score: number) {
    super(`AI solution design requires a score of ${AI_SOLUTION_SCORE_THRESHOLD} or higher. This assessment scored ${score}.`);
  }
}

const allowedTools = [
  "custom:search_use_cases",
  "custom:get_use_case",
  "custom:compare_use_cases",
  "custom:get_fit_assessment",
  "custom:get_workflow_scenario",
];

const assistantInstructions = `
You are the Applied AI Studio workflow-design assistant for applied AI analysis.

Rules:
- Use the registered catalog tools before making any factual claim about a showcased use case or fit assessment.
- Do not narrate tool selection, retries, or lookup steps; answer after gathering the required evidence.
- Treat tool output as the only source of truth for the Studio catalog and assessment results.
- Distinguish catalog evidence from general design guidance.
- Cite relevant showcase titles in the answer and state when the catalog does not support a claim.
- Never claim access to customer data, local files, source code, shell commands, web pages, or external systems.
- Do not generate Mermaid syntax. The application renders workflow graphs deterministically from validated nodes and edges.
- Explain tradeoffs, human-review boundaries, evaluation needs, and failure modes in clear implementation-ready language.
- Keep answers concise unless the user asks for a detailed explanation.
`;

function rejectUnknownPermission(
  request: PermissionRequest,
): PermissionRequestResult {
  return {
    kind: "reject",
    feedback: `Applied AI Studio does not permit ${request.kind} operations. Use only its registered read-only catalog tools.`,
  };
}

export class CopilotGateway {
  readonly #catalog: CatalogClient;
  readonly #model: string;
  readonly #timeoutMs: number;
  readonly #sessions = new Map<string, SessionEntry>();
  readonly #idleTimer: NodeJS.Timeout;
  #client: CopilotClient | null = null;
  #starting: Promise<CopilotClient> | null = null;

  constructor(catalog: CatalogClient) {
    this.#catalog = catalog;
    this.#model = process.env.COPILOT_MODEL ?? "auto";
    this.#timeoutMs = Number(process.env.CHAT_TIMEOUT_MS ?? 60_000);
    this.#idleTimer = setInterval(() => void this.#removeIdleSessions(), 60_000);
    this.#idleTimer.unref();
  }

  get model(): string {
    return this.#model;
  }

  async health(): Promise<{ runtime: "ok" | "error"; catalog: "ok" | "error"; message?: string }> {
    const catalog = (await this.#catalog.health()) ? "ok" : "error";
    try {
      const client = await this.#ensureClient();
      await client.ping("applied-ai-studio-health");
      return { runtime: "ok", catalog };
    } catch (error) {
      return {
        runtime: "error",
        catalog,
        message: error instanceof Error ? error.message : "Copilot runtime failed to start.",
      };
    }
  }

  async stream(
    requestedSessionId: string | undefined,
    message: string,
    emit: (event: AgentStreamEvent) => void,
  ): Promise<string> {
    const { id, entry } = await this.#getSession(requestedSessionId);
    if (entry.busy) throw new Error("This conversation is already processing a message.");

    entry.busy = true;
    entry.lastUsedAt = Date.now();
    emit({ type: "meta", sessionId: id, model: this.#model });

    let streamed = false;
    const unsubscribe = entry.session.on("assistant.message_delta", (event) => {
      if (!event.data.deltaContent) return;
      streamed = true;
      emit({ type: "delta", content: event.data.deltaContent });
    });

    try {
      const response = await entry.session.sendAndWait({ prompt: message }, this.#timeoutMs);
      if (!streamed && response?.data.content) {
        emit({ type: "delta", content: response.data.content });
      }
      emit({ type: "done" });
      return id;
    } finally {
      unsubscribe();
      entry.busy = false;
      entry.lastUsedAt = Date.now();
    }
  }

  async draftWorkflow(input: WorkflowDraftInput): Promise<WorkflowDraft> {
    const client = await this.#ensureClient();
    let captured: WorkflowDraft | undefined;
    const submitWorkflowDraft = defineTool("submit_workflow_draft", {
      description: "Submit exactly one five-stage business workflow and its candidate decision points for Applied AI Studio.",
      parameters: workflowDraftSchema,
      skipPermission: true,
      defer: "never",
      handler: (draft) => {
        const parsed = workflowDraftSchema.parse(draft);
        captured = {
          ...parsed,
          decisions: parsed.decisions.map((decision) => ({
            ...decision,
            aiCandidate: decision.intervention === "ai",
            suggestedWorkloadType: decision.intervention === "ai"
              ? decision.suggestedWorkloadType
              : undefined,
            suggestedCoursePattern: decision.intervention === "ai"
              ? decision.suggestedCoursePattern
              : undefined,
          })),
        };
        return { accepted: true };
      },
    });
    const session = await client.createSession({
      sessionId: randomUUID(),
      model: this.#model,
      tools: [submitWorkflowDraft],
      availableTools: ["custom:submit_workflow_draft"],
      onPermissionRequest: rejectUnknownPermission,
      memory: { enabled: false },
      infiniteSessions: { enabled: false },
      enableSessionStore: false,
      systemMessage: {
        mode: "customize",
        sections: {
          tone: { action: "replace", content: "Use concise language suitable for professional business analysts." },
          code_change_rules: { action: "remove" },
          environment_context: { action: "remove" },
        },
        content: `
You map business work for applied AI solution design.

Call submit_workflow_draft exactly once. Do not answer in prose.

Requirements:
- Stay at business-process level, not software implementation level.
- Produce exactly Inputs, Process, Decision, Action, and Outcome stages.
- A decision must have at least two real business paths and an accountable role.
- Judge each decision against the least expensive intervention: rule, automation, AI, optimization, human, or investigate.
- Use AI only when another year of data could change inferred logic, or generation creates a grounded artifact.
- For every AI candidate, provide the suggested AI method: classification, prediction, optimization, or generation.
- Distinguish deterministic payment-policy checks from fraud inference. If the problem involves detecting fraudulent transactions from historical outcomes, classify that decision as AI rather than a rule.
- Use prediction when the output is the probability, timing, or amount of a future event, including whether equipment will fail within a time horizon. Use classification when the output is one of a fixed set of present-state buckets.
- Use optimization for assignment, routing, scheduling, or allocation when an objective and constraints can be stated.
- Keep consequential or highly asymmetric judgment with a human.
- State assumptions instead of inventing facts about the organization.
`,
      },
    });

    try {
      await session.sendAndWait({
        prompt: `Draft the business workflow and candidate decisions for this proposed use case:\n${JSON.stringify(input, null, 2)}`,
      }, this.#timeoutMs);
    } finally {
      await session.disconnect();
    }

    if (!captured) {
      // Surfaced to a student in the browser, so it says what to do rather than what failed
      // internally. The browser also falls back to a starter outline when this throws.
      throw new Error(
        "Copilot could not turn that into a workflow. Try describing the problem in a few more sentences: what arrives, who handles it, and what decision gets made.",
      );
    }
    return workflowDraftSchema.parse(captured);
  }

  async draftSolutionBlueprint(input: AiSolutionBlueprintRequest): Promise<AiSolutionBlueprint> {
    const assessment = await this.#catalog.getAssessment(input.assessmentId);
    if (!isAiSolutionEligible(assessment.totalScore)) {
      throw new SolutionBlueprintThresholdError(assessment.totalScore);
    }

    const client = await this.#ensureClient();
    let captured: AiSolutionBlueprint | undefined;
    let validationFailure: string | undefined;
    const submitBlueprint = defineTool("submit_ai_solution_blueprint", {
      description: "Submit one structured AI solution blueprint for a strong-fit Applied AI Studio assessment.",
      parameters: aiSolutionBlueprintSchema,
      skipPermission: true,
      defer: "never",
      handler: (blueprint) => {
        const parsedResult = aiSolutionBlueprintSchema.safeParse(blueprint);
        if (!parsedResult.success) {
          validationFailure = parsedResult.error.issues
            .map((issue) => `${issue.path.join(".") || "root"}: ${issue.message}`)
            .join("; ");
          throw new Error("The submitted blueprint did not match the required schema.");
        }
        const parsed = parsedResult.data;
        captured = {
          ...parsed,
          assessmentId: assessment.id,
          solutionPattern: assessment.recommendedPattern,
          coursePattern: input.selectedDecision?.suggestedCoursePattern ?? parsed.coursePattern,
        };
        return { accepted: true };
      },
    });

    const session = await client.createSession({
      sessionId: randomUUID(),
      model: this.#model,
      tools: [submitBlueprint],
      availableTools: ["custom:submit_ai_solution_blueprint"],
      onPermissionRequest: rejectUnknownPermission,
      memory: { enabled: false },
      infiniteSessions: { enabled: false },
      enableSessionStore: false,
      systemMessage: {
        mode: "customize",
        sections: {
          tone: { action: "replace", content: "Use concise architecture language suitable for professional business and technical audiences." },
          code_change_rules: { action: "remove" },
          environment_context: { action: "remove" },
        },
        content: `
You design a bounded AI application only after deterministic readiness scoring has approved it.

Call submit_ai_solution_blueprint exactly once. Do not answer in prose.

Requirements:
- Keep each individual narrative field concise; prefer one or two sentences per field.
- Preserve the supplied recommended solution pattern. Do not change the readiness score or gate decision.
- Select the AI method by output shape: classification, prediction, optimization, or generation.
- If the selected decision provides a suggested AI method, preserve it. A future event or value over a time horizon is prediction; a present-state fixed bucket is classification.
- Treat all data sources, ownership, thresholds, and targets as proposed requirements unless the assessment explicitly provides them.
- Define required data, ground truth or target, preparation, and accountable ownership.
- Pair technical metrics with business metrics. Classification uses precision/recall; numeric prediction uses MAE/RMSE; optimization compares cost or service against baseline; generation uses groundedness and human acceptance.
- State measurable success criteria as PoC hypotheses, not achieved results.
- Keep consequential authority with a named human role. Include escalation and refusal behavior.
- Build a detailed second workflow from data intake through validation, AI inference, human review, action, outcome capture, and monitoring.
- Use only the supplied assessment and optional selected decision. Do not invent organization-specific systems or facts.
`,
      },
    });

    try {
      await session.sendAndWait({
        prompt: `Design the proposed AI solution for this approved assessment:\n${JSON.stringify({ assessment, selectedDecision: input.selectedDecision }, null, 2)}`,
      }, this.#timeoutMs);
    } finally {
      await session.disconnect();
    }

    if (!captured) {
      // The schema detail is useful to the instructor but meaningless to a student, so it is
      // logged rather than shown. The student gets an action instead.
      if (validationFailure) {
        console.warn(`[agent-api] blueprint rejected by schema: ${validationFailure}`);
      }
      throw new Error(
        "Copilot could not finish the detailed design this time. Your score is saved. Select the decision again and retry — it usually works on a second attempt.",
      );
    }
    return aiSolutionBlueprintSchema.parse(captured);
  }

  async abort(sessionId: string): Promise<void> {
    const entry = this.#sessions.get(sessionId);
    if (entry?.busy) await entry.session.abort();
  }

  async removeSession(sessionId: string): Promise<void> {
    const entry = this.#sessions.get(sessionId);
    if (!entry) return;
    this.#sessions.delete(sessionId);
    await entry.session.disconnect();
  }

  async stop(): Promise<void> {
    clearInterval(this.#idleTimer);
    await Promise.all([...this.#sessions.keys()].map((id) => this.removeSession(id)));
    if (this.#client) await this.#client.stop();
    this.#client = null;
  }

  async #ensureClient(): Promise<CopilotClient> {
    if (this.#client) return this.#client;
    if (this.#starting) return this.#starting;

    this.#starting = (async () => {
      const client = new CopilotClient({
        mode: "empty",
        baseDirectory: path.join(homedir(), ".copilot", "applied-ai-studio"),
        logLevel: (process.env.COPILOT_LOG_LEVEL as "none" | "error" | "warning" | "info" | "debug" | "all") ?? "warning",
        sessionIdleTimeoutSeconds: 15 * 60,
        useLoggedInUser: true,
        telemetry: process.env.COPILOT_TRACE_FILE
          ? {
              filePath: process.env.COPILOT_TRACE_FILE,
              exporterType: "file",
              captureContent: false,
            }
          : undefined,
      });
      await client.start();
      this.#client = client;
      return client;
    })();

    try {
      return await this.#starting;
    } finally {
      this.#starting = null;
    }
  }

  async #getSession(requestedSessionId: string | undefined): Promise<{ id: string; entry: SessionEntry }> {
    if (requestedSessionId) {
      const existing = this.#sessions.get(requestedSessionId);
      if (existing) return { id: requestedSessionId, entry: existing };
    }

    const client = await this.#ensureClient();
    const id = randomUUID();
    const tools = [
      defineTool("search_use_cases", {
        description: "Search the public synthetic Applied AI Studio showcase catalog.",
        parameters: z.object({
          query: z.string().max(200).describe("Search words describing an industry, problem, capability, or pattern."),
          industry: z.string().max(60).optional().describe("Optional industry identifier."),
        }),
        skipPermission: true,
        defer: "never",
        handler: ({ query, industry }) => this.#catalog.search(query, industry),
      }),
      defineTool("get_use_case", {
        description: "Get one public synthetic showcase use case by its catalog ID.",
        parameters: z.object({ id: z.string().max(100) }),
        skipPermission: true,
        defer: "never",
        handler: ({ id }) => this.#catalog.getUseCase(id),
      }),
      defineTool("compare_use_cases", {
        description: "Compare two to four public synthetic showcase use cases by exact catalog IDs.",
        parameters: z.object({ ids: z.array(z.string().max(100)).min(2).max(4) }),
        skipPermission: true,
        defer: "never",
        handler: ({ ids }) => this.#catalog.compareUseCases(ids),
      }),
      defineTool("get_fit_assessment", {
        description: "Get one deterministic AI fit assessment from the current local app session.",
        parameters: z.object({ id: z.string().uuid() }),
        skipPermission: true,
        defer: "never",
        handler: ({ id: assessmentId }) => this.#catalog.getAssessment(assessmentId),
      }),
      defineTool("get_workflow_scenario", {
        description: "Get one detailed workflow scenario with decision verdicts, baseline, and AI design drill-down.",
        parameters: z.object({ id: z.string().max(100) }),
        skipPermission: true,
        defer: "never",
        handler: ({ id: courseCaseId }) => this.#catalog.getCourseCase(courseCaseId),
      }),
    ];

    const session = await client.createSession({
      sessionId: id,
      model: this.#model,
      streaming: true,
      tools,
      availableTools: allowedTools,
      onPermissionRequest: rejectUnknownPermission,
      memory: { enabled: false },
      infiniteSessions: { enabled: false },
      enableSessionStore: false,
      systemMessage: {
        mode: "customize",
        sections: {
          tone: {
            action: "replace",
            content: "Use direct, instructional language suitable for adult technical learners.",
          },
          code_change_rules: { action: "remove" },
          environment_context: { action: "remove" },
        },
        content: assistantInstructions,
      },
    });

    const entry = { session, busy: false, lastUsedAt: Date.now() };
    this.#sessions.set(id, entry);
    return { id, entry };
  }

  async #removeIdleSessions(): Promise<void> {
    const cutoff = Date.now() - 15 * 60_000;
    const idleIds = [...this.#sessions.entries()]
      .filter(([, entry]) => !entry.busy && entry.lastUsedAt < cutoff)
      .map(([id]) => id);
    await Promise.all(idleIds.map((id) => this.removeSession(id)));
  }
}