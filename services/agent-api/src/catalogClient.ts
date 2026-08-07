import {
  courseCaseSchema,
  fitAssessmentResultSchema,
    type CourseCase,
  useCaseSchema,
  type FitAssessmentResult,
  type UseCase,
} from "@applied-ai-studio/contracts";
import { z } from "zod";

const useCaseListSchema = z.object({
  items: z.array(useCaseSchema),
  total: z.number(),
  source: z.literal("public-synthetic"),
});

export class CatalogClient {
  readonly #baseUrl: string;

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl.replace(/\/$/, "");
  }

  async search(query: string, industry?: string): Promise<UseCase[]> {
    const url = new URL("/api/catalog/use-cases", this.#baseUrl);
    if (query.trim()) url.searchParams.set("search", query.trim());
    if (industry?.trim()) url.searchParams.set("industry", industry.trim());
    const payload = useCaseListSchema.parse(await this.#get(url));
    return payload.items.slice(0, 8);
  }

  async getUseCase(id: string): Promise<UseCase> {
    const url = new URL(`/api/catalog/use-cases/${encodeURIComponent(id)}`, this.#baseUrl);
    return useCaseSchema.parse(await this.#get(url));
  }

  async compareUseCases(ids: string[]): Promise<UseCase[]> {
    return Promise.all([...new Set(ids)].slice(0, 4).map((id) => this.getUseCase(id)));
  }

  async getAssessment(id: string): Promise<FitAssessmentResult> {
    const url = new URL(`/api/catalog/assessments/${encodeURIComponent(id)}`, this.#baseUrl);
    return fitAssessmentResultSchema.parse(await this.#get(url));
  }

  async getCourseCase(id: string): Promise<CourseCase> {
    const url = new URL(`/api/catalog/course-cases/${encodeURIComponent(id)}`, this.#baseUrl);
    return courseCaseSchema.parse(await this.#get(url));
  }

  async health(): Promise<boolean> {
    try {
      const response = await fetch(new URL("/health", this.#baseUrl), {
        signal: AbortSignal.timeout(3_000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  async #get(url: URL): Promise<unknown> {
    const response = await fetch(url, { signal: AbortSignal.timeout(8_000) });
    if (!response.ok) {
      throw new Error(`Catalog request failed with ${response.status}.`);
    }
    return response.json();
  }
}