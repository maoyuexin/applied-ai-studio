import { describe, expect, it } from "vitest";
import { CatalogStore } from "./catalog.js";

describe("CatalogStore seed contracts", () => {
  it("loads the syllabus-aligned showcase catalog", async () => {
    const catalog = await CatalogStore.load();

    expect(catalog.list()).toHaveLength(14);
    expect(catalog.industries()).toHaveLength(12);
    expect(catalog.list({ industry: "retail" }).map((item) => item.id)).toEqual([
      "retail-online-order-decision-lab",
      "retail-assortment-copilot",
    ]);
    const fraudLab = catalog.list().find((item) => item.id === "financial-fraud-detection-lab");
    expect(fraudLab?.title).toBe("Card Transaction Fraud Detection");
    expect(fraudLab?.demoStatus).toBe("available");
    expect(fraudLab?.courseCaseId).toBe("financial-fraud-detection");
  });

  it("loads the detailed retail workflow", async () => {
    const catalog = await CatalogStore.load();
    const courseCase = catalog.getCourseCase("retail-online-order");

    expect(courseCase?.stages.map((stage) => stage.id)).toEqual([
      "input",
      "process",
      "decision",
      "action",
      "outcome",
    ]);
    expect(courseCase?.decisions).toHaveLength(6);
    expect(courseCase?.edges).toHaveLength(15);
    expect(courseCase?.featuredDecisionId).toBe("payment");
  });

  it("loads the detailed fraud workflow", async () => {
    const catalog = await CatalogStore.load();
    const courseCase = catalog.getCourseCase("financial-fraud-detection");

    expect(courseCase?.stages.map((stage) => stage.id)).toEqual([
      "input",
      "process",
      "decision",
      "action",
      "outcome",
    ]);
    expect(courseCase?.decisions).toHaveLength(6);
    expect(courseCase?.featuredDecisionId).toBe("classification");
  });

  it("links every retained workflow to a comprehensive scenario", async () => {
    const catalog = await CatalogStore.load();
    const labs = catalog.list().filter((item) => item.courseCaseId);

    expect(labs.map((item) => item.id)).toEqual([
      "manufacturing-maintenance-triage",
      "financial-kyc-review",
      "financial-fraud-detection-lab",
      "healthcare-operations-handoff",
      "retail-online-order-decision-lab",
      "public-service-intake",
      "transportation-fleet-routing",
    ]);

    for (const lab of labs) {
      const courseCase = catalog.getCourseCase(lab.courseCaseId!);
      expect(courseCase, lab.id).toBeDefined();
      expect(courseCase!.lanes.length, lab.id).toBeGreaterThanOrEqual(6);
      expect(courseCase!.nodes.length, lab.id).toBeGreaterThanOrEqual(12);
      expect(courseCase!.edges.length, lab.id).toBeGreaterThanOrEqual(15);
      expect(courseCase!.decisions.length, lab.id).toBeGreaterThanOrEqual(6);
      expect(courseCase!.baseline.length, lab.id).toBeGreaterThanOrEqual(5);
      expect(courseCase!.introduction.context.length, lab.id).toBeGreaterThanOrEqual(40);
      expect(courseCase!.introduction.workflow.length, lab.id).toBeGreaterThanOrEqual(40);
      expect(courseCase!.introduction.startsWhen, lab.id).toBeTruthy();
      expect(courseCase!.introduction.endsWhen, lab.id).toBeTruthy();
    }
  });
});