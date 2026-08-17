import cors from "cors";
import express from "express";
import {
  AI_SOLUTION_SCORE_THRESHOLD,
  aiSolutionBlueprintRequestSchema,
  chatRequestSchema,
  workflowDraftInputSchema,
} from "@applied-ai-studio/contracts";
import { CatalogClient } from "./catalogClient.js";
import {
  CopilotGateway,
  SolutionBlueprintThresholdError,
  type AgentStreamEvent,
} from "./copilotGateway.js";

const port = Number(process.env.AGENT_PORT ?? process.env.PORT ?? 4320);
const host = process.env.HOST ?? "127.0.0.1";
const catalogUrl =
  process.env.CATALOG_API_URL ??
  process.env["services__catalog__http__0"] ??
  "http://127.0.0.1:4310";
const allowedOrigins = (process.env.ALLOWED_ORIGINS ?? "http://127.0.0.1:5173,http://localhost:5173")
  .split(",")
  .map((value) => value.trim());

const gateway = new CopilotGateway(new CatalogClient(catalogUrl));
const app = express();

app.disable("x-powered-by");
app.use(cors({ origin: allowedOrigins }));
app.use(express.json({ limit: "16kb" }));

app.get("/health", async (_request, response) => {
  const health = await gateway.health();
  response.status(health.runtime === "ok" && health.catalog === "ok" ? 200 : 503).json({
    status: health.runtime === "ok" && health.catalog === "ok" ? "ok" : "degraded",
    service: "agent-api",
    model: gateway.model,
    ...health,
  });
});

app.post("/api/agent/chat", async (request, response) => {
  const parsed = chatRequestSchema.safeParse(request.body);
  if (!parsed.success) {
    response.status(400).json({ error: "Invalid chat request.", details: parsed.error.flatten() });
    return;
  }

  response.status(200);
  response.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  response.setHeader("Cache-Control", "no-cache, no-transform");
  response.setHeader("Connection", "keep-alive");
  response.setHeader("X-Accel-Buffering", "no");
  response.flushHeaders();

  let activeSessionId = parsed.data.sessionId;
  const emit = (event: AgentStreamEvent): void => {
    if (event.type === "meta") activeSessionId = event.sessionId;
    response.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
  };

  response.on("close", () => {
    if (!response.writableEnded && activeSessionId) {
      void gateway.abort(activeSessionId);
    }
  });

  try {
    await gateway.stream(parsed.data.sessionId, parsed.data.message, emit);
  } catch (error) {
    emit({
      type: "error",
      message: error instanceof Error
        ? error.message
        : "Ask Studio could not reach GitHub Copilot. Everything else in the app still works without it.",
    });
  } finally {
    response.end();
  }
});

app.post("/api/agent/workflow-drafts", async (request, response) => {
  const parsed = workflowDraftInputSchema.safeParse(request.body);
  if (!parsed.success) {
    response.status(400).json({ error: "Invalid workflow problem.", details: parsed.error.flatten() });
    return;
  }
  try {
    response.json(await gateway.draftWorkflow(parsed.data));
  } catch (error) {
    // The browser treats any failure here as its cue to serve the starter outline from the
    // catalog service, so this message is a last resort rather than the normal path.
    response.status(502).json({
      error: error instanceof Error
        ? error.message
        : "Copilot could not draft a workflow. A standard starter outline will be used instead.",
    });
  }
});

app.post("/api/agent/solution-blueprints", async (request, response) => {
  const parsed = aiSolutionBlueprintRequestSchema.safeParse(request.body);
  if (!parsed.success) {
    response.status(400).json({ error: "Invalid solution blueprint request.", details: parsed.error.flatten() });
    return;
  }
  try {
    response.json(await gateway.draftSolutionBlueprint(parsed.data));
  } catch (error) {
    if (error instanceof SolutionBlueprintThresholdError) {
      response.status(409).json({ error: error.message, score: error.score, threshold: AI_SOLUTION_SCORE_THRESHOLD });
      return;
    }
    response.status(502).json({
      error: error instanceof Error ? error.message : "Copilot solution design failed.",
    });
  }
});

app.delete("/api/agent/sessions/:id", async (request, response) => {
  await gateway.removeSession(request.params.id);
  response.status(204).end();
});

const server = app.listen(port, host, () => {
  console.log(`[agent-api] http://${host}:${port}`);
});

let shuttingDown = false;
const shutdown = (): void => {
  if (shuttingDown) return;
  shuttingDown = true;
  server.close(() => {
    void gateway.stop().finally(() => process.exit(0));
  });
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);