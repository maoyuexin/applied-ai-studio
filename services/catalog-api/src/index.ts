import cors from "cors";
import express from "express";
import { fitAssessmentInputSchema, fitAssessmentResultSchema } from "@applied-ai-studio/contracts";
import { CatalogStore } from "./catalog.js";
import { assessFit } from "./scoring.js";

const port = Number(process.env.CATALOG_PORT ?? process.env.PORT ?? 4310);
const host = process.env.HOST ?? "127.0.0.1";
const allowedOrigins = (process.env.ALLOWED_ORIGINS ?? "http://127.0.0.1:5173,http://localhost:5173")
  .split(",")
  .map((value) => value.trim());

const catalog = await CatalogStore.load();
const assessments = new Map<string, ReturnType<typeof assessFit>>();
const app = express();

app.disable("x-powered-by");
app.use(cors({ origin: allowedOrigins }));
app.use(express.json({ limit: "32kb" }));

app.get("/health", (_request, response) => {
  response.json({ status: "ok", service: "catalog-api", useCases: catalog.list().length });
});

app.get("/api/catalog/industries", (_request, response) => {
  response.json({ items: catalog.industries() });
});

app.get("/api/catalog/use-cases", (request, response) => {
  const industry = typeof request.query.industry === "string" ? request.query.industry : undefined;
  const search = typeof request.query.search === "string" ? request.query.search : undefined;
  const items = catalog.list({ industry, search }).slice(0, 20);
  response.json({ items, total: items.length, source: "public-synthetic" });
});

app.get("/api/catalog/use-cases/:id", (request, response) => {
  const useCase = catalog.get(request.params.id);
  if (!useCase) {
    response.status(404).json({ error: "Use case not found." });
    return;
  }
  response.json(useCase);
});

app.get("/api/catalog/course-cases/:id", (request, response) => {
  const courseCase = catalog.getCourseCase(request.params.id);
  if (!courseCase) {
    response.status(404).json({ error: "Workflow scenario not found." });
    return;
  }
  response.json(courseCase);
});

app.post("/api/catalog/assessments", (request, response) => {
  const parsed = fitAssessmentInputSchema.safeParse(request.body);
  if (!parsed.success) {
    response.status(400).json({ error: "Invalid assessment input.", details: parsed.error.flatten() });
    return;
  }
  const result = fitAssessmentResultSchema.parse(assessFit(parsed.data, catalog.list()));
  assessments.set(result.id, result);
  response.status(201).json(result);
});

app.get("/api/catalog/assessments/:id", (request, response) => {
  const assessment = assessments.get(request.params.id);
  if (!assessment) {
    response.status(404).json({ error: "Assessment not found in this app session." });
    return;
  }
  response.json(assessment);
});

const server = app.listen(port, host, () => {
  console.log(`[catalog-api] http://${host}:${port}`);
});

const shutdown = (): void => {
  server.close(() => process.exit(0));
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);