import { describe, expect, it } from "vitest";
import { workflowDraftSchema } from "@applied-ai-studio/contracts";
import { starterWorkflowDraft } from "./starterDraft.js";

const input = {
  industry: "Healthcare",
  problem: "Referrals arrive by fax and email and take too long to triage into the right clinic.",
  desiredOutcome: "Cut first-pass triage time in half.",
};

describe("starterWorkflowDraft", () => {
  it("satisfies the shared workflow draft contract", () => {
    expect(() => workflowDraftSchema.parse(starterWorkflowDraft(input))).not.toThrow();
  });

  it("produces the five business stages exactly once, in order", () => {
    const draft = starterWorkflowDraft(input);
    expect(draft.stages.map((stage) => stage.id)).toEqual([
      "input",
      "process",
      "decision",
      "action",
      "outcome",
    ]);
  });

  it("covers every intervention the course teaches, so the elimination lesson survives", () => {
    const interventions = starterWorkflowDraft(input).decisions.map((d) => d.intervention);
    for (const expected of ["rule", "automation", "optimization", "ai", "human"] as const) {
      expect(interventions).toContain(expected);
    }
  });

  it("marks exactly one decision as an AI candidate, and gives it a method", () => {
    const candidates = starterWorkflowDraft(input).decisions.filter((d) => d.aiCandidate);
    expect(candidates).toHaveLength(1);
    expect(candidates[0]?.suggestedCoursePattern).toBe("classification");
    expect(candidates[0]?.suggestedWorkloadType).toBeDefined();
  });

  it("keeps non-AI decisions free of AI method hints", () => {
    for (const decision of starterWorkflowDraft(input).decisions) {
      if (decision.aiCandidate) continue;
      expect(decision.suggestedCoursePattern).toBeUndefined();
      expect(decision.suggestedWorkloadType).toBeUndefined();
    }
  });

  it("states plainly that it was not generated from the student's problem", () => {
    const assumptions = starterWorkflowDraft(input).assumptions.join(" ").toLowerCase();
    expect(assumptions).toContain("not generated from your problem statement");
  });

  it("keeps the title within contract limits even for a very long industry name", () => {
    const draft = starterWorkflowDraft({ ...input, industry: "X".repeat(80) });
    expect(draft.title.length).toBeLessThanOrEqual(100);
    expect(() => workflowDraftSchema.parse(draft)).not.toThrow();
  });

  it("is deterministic - the same input always yields the same draft", () => {
    expect(starterWorkflowDraft(input)).toEqual(starterWorkflowDraft(input));
  });
});
