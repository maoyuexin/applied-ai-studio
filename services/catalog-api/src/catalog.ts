import { readFile } from "node:fs/promises";
import {
  courseCaseSchema,
  useCaseSchema,
  type CourseCase,
  type UseCase,
} from "@applied-ai-studio/contracts";
import { z } from "zod";

const catalogPath = new URL("../../../data/seed/use-cases.json", import.meta.url);
const courseCasesPath = new URL("../../../data/seed/course-cases.json", import.meta.url);

export class CatalogStore {
  readonly #useCases: UseCase[];
  readonly #courseCases: CourseCase[];

  private constructor(useCases: UseCase[], courseCases: CourseCase[]) {
    this.#useCases = useCases;
    this.#courseCases = courseCases;
  }

  static async load(): Promise<CatalogStore> {
    const raw = await readFile(catalogPath, "utf-8");
    const courseCasesRaw = await readFile(courseCasesPath, "utf-8");
    const useCases = z.array(useCaseSchema).parse(JSON.parse(raw));
    const courseCases = z.array(courseCaseSchema).parse(JSON.parse(courseCasesRaw));
    return new CatalogStore(useCases, courseCases);
  }

  list(options: { industry?: string; search?: string } = {}): UseCase[] {
    const industry = options.industry?.trim().toLocaleLowerCase();
    const terms = options.search
      ?.trim()
      .toLocaleLowerCase()
      .split(/\s+/)
      .filter(Boolean);

    return this.#useCases.filter((useCase) => {
      if (industry && useCase.industry !== industry) return false;
      if (!terms?.length) return true;
      const haystack = [
        useCase.title,
        useCase.industryLabel,
        useCase.summary,
        useCase.problem,
        useCase.workloadType,
        ...useCase.capabilities,
        ...useCase.patterns,
        ...useCase.architecture,
        ...useCase.outcomes,
      ]
        .join(" ")
        .toLocaleLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }

  get(id: string): UseCase | undefined {
    return this.#useCases.find((useCase) => useCase.id === id);
  }

  getCourseCase(id: string): CourseCase | undefined {
    return this.#courseCases.find((courseCase) => courseCase.id === id);
  }

  industries(): Array<{ id: string; label: string; count: number }> {
    const values = new Map<string, { id: string; label: string; count: number }>();
    for (const useCase of this.#useCases) {
      const current = values.get(useCase.industry);
      values.set(useCase.industry, {
        id: useCase.industry,
        label: useCase.industryLabel,
        count: (current?.count ?? 0) + 1,
      });
    }
    return [...values.values()].sort((left, right) => left.label.localeCompare(right.label));
  }
}