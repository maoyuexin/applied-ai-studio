import { describe, expect, it } from "vitest";
import {
  AI_SOLUTION_SCORE_THRESHOLD,
  isAiSolutionEligible,
  type FitAssessmentInput,
  type UseCase,
} from "@applied-ai-studio/contracts";
import { assessFit } from "./scoring.js";

const input: FitAssessmentInput = {
  name: "Maintenance triage",
  industry: "manufacturing",
  problem: "Technicians need a consistent way to prioritize fragmented machine alerts and notes.",
  desiredOutcome: "Reduce first-pass triage time while preserving technician approval.",
  workloadType: "decision-support",
  businessValue: 5,
  dataReadiness: 4,
  processRepeatability: 4,
  integrationReadiness: 3,
  humanOversight: 5,
  riskTolerance: 3,
};

const useCases = [
  {
    id: "manufacturing-maintenance-triage",
    industry: "manufacturing",
    workloadType: "decision-support",
    riskLevel: "medium",
  },
  {
    id: "retail-assortment-copilot",
    industry: "retail",
    workloadType: "decision-support",
    riskLevel: "medium",
  },
] as UseCase[];

describe("assessFit", () => {
  it("scores a ready decision-support scenario and produces a deterministic graph", () => {
    const result = assessFit(input, useCases);

    expect(result.totalScore).toBe(81);
    expect(result.readiness).toBe("strong-fit");
    expect(result.recommendedPattern).toBe("decision-support");
    expect(result.matchedUseCaseIds[0]).toBe("manufacturing-maintenance-triage");
    expect(result.workflow.nodes.map((node) => node.id)).toEqual([
      "signals",
      "analysis",
      "explain",
      "decision",
      "outcome",
    ]);
  });

  it("fails toward foundations when data, integration, and oversight are weak", () => {
    const result = assessFit(
      {
        ...input,
        dataReadiness: 1,
        integrationReadiness: 1,
        humanOversight: 1,
        riskTolerance: 1,
      },
      useCases,
    );

    expect(result.readiness).toBe("foundation-first");
    expect(result.risks).toHaveLength(4);
    expect(result.nextSteps).toContain("Prototype one read-only adapter before enabling any write action.");
  });

  it("opens detailed AI solution design at exactly 75 and not below", () => {
    const result = assessFit(
      {
        ...input,
        businessValue: 5,
        dataReadiness: 4,
        processRepeatability: 4,
        integrationReadiness: 3,
        humanOversight: 3,
        riskTolerance: 3,
      },
      useCases,
    );

    expect(result.totalScore).toBe(AI_SOLUTION_SCORE_THRESHOLD);
    expect(result.readiness).toBe("strong-fit");
    expect(isAiSolutionEligible(result.totalScore)).toBe(true);
    expect(isAiSolutionEligible(AI_SOLUTION_SCORE_THRESHOLD - 1)).toBe(false);
  });
});