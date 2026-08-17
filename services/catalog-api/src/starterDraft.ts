import {
  workflowDraftSchema,
  type WorkflowDraft,
  type WorkflowDraftInput,
} from "@applied-ai-studio/contracts";

/**
 * A five-stage workflow draft produced entirely in code, with no AI involved.
 *
 * WHY THIS EXISTS
 * ---------------
 * The normal "Generate five-stage workflow" button asks GitHub Copilot to read the
 * student's problem statement and draft something specific to it. Copilot is free for
 * students, but only after the Student Developer Pack is approved, and approval takes
 * several days. Without this fallback the AI Fit Analyzer is simply dead for the first
 * week of the course - which is the week it is actually taught.
 *
 * So when Copilot is not available, the app serves this instead: a generic outline the
 * student edits, rather than an error message.
 *
 * WHY THE DECISIONS ARE THE ONES BELOW
 * ------------------------------------
 * The five decisions deliberately cover all five verdicts the course teaches - rule,
 * automation, optimization, AI, and keep-the-human - because the central lesson is that
 * most decisions are NOT AI problems. A starter outline where everything looked like an
 * AI candidate would teach the opposite of the course.
 *
 * WHY IT LIVES IN THE CATALOG SERVICE
 * -----------------------------------
 * docs/architecture.md separates deterministic scoring (catalog-api) from Copilot
 * reasoning (agent-api). Generating this in the agent service would blur that boundary,
 * and it would also mean the fallback depended on the very service that is unavailable.
 */
export function starterWorkflowDraft(input: WorkflowDraftInput): WorkflowDraft {
  const industry = input.industry.trim().slice(0, 60) || "This industry";

  const draft: WorkflowDraft = {
    title: `${industry}: starter workflow outline`.slice(0, 100),

    stages: [
      {
        id: "input",
        label: "Inputs",
        description:
          "What arrives, and from whom. Replace this with the real trigger: a form, an order, a referral, an alert.",
      },
      {
        id: "process",
        label: "Process",
        description:
          "The work performed on it before any choice is made - checking, preparing, assembling, recording.",
      },
      {
        id: "decision",
        label: "Decision",
        description:
          "The point where somebody picks between paths. Most workflows hide several of these; list them all.",
      },
      {
        id: "action",
        label: "Action",
        description:
          "What is carried out once the choice is made, including the path taken when the answer is no.",
      },
      {
        id: "outcome",
        label: "Outcome",
        description:
          "What the customer, patient, resident, or requester actually ends up with, and how you would measure it.",
      },
    ],

    decisions: [
      {
        id: "input-valid",
        label: "Is the incoming request complete and valid?",
        owner: "The system, or whoever does first-pass checking today",
        alternatives: ["Accept and continue", "Send back for missing information"],
        intervention: "rule",
        rationale:
          "Completeness checks are usually written down somewhere already. If the logic is stable and someone will sign it, write the rule instead of training a model.",
        aiCandidate: false,
      },
      {
        id: "categorise",
        label: "Which category, queue, or team does this belong to?",
        owner: "The person who currently sorts incoming work",
        alternatives: ["Route to category A", "Route to category B", "Hold for a human to read"],
        intervention: "ai",
        rationale:
          "Sorting free-text or mixed-quality input is judgement nobody has fully written down, and it improves with more labelled examples. That is the test for AI.",
        aiCandidate: true,
        suggestedWorkloadType: "decision-support",
        suggestedCoursePattern: "classification",
      },
      {
        id: "auto-release",
        label: "Can this proceed automatically, or should it be held?",
        owner: "Operations lead",
        alternatives: ["Release automatically", "Hold for review"],
        intervention: "automation",
        rationale:
          "A threshold somebody decides in advance - value, risk band, customer type. More history does not change it, so it is automation rather than AI.",
        aiCandidate: false,
      },
      {
        id: "assign",
        label: "Which resource, slot, or route should handle it?",
        owner: "Scheduler or dispatcher",
        alternatives: ["Assign to the cheapest option", "Assign to the fastest option", "Split across several"],
        intervention: "optimization",
        rationale:
          "Assignment, routing, and scheduling have a stateable objective and stateable constraints. A solver is cheaper than a model, needs no training data, and can be explained.",
        aiCandidate: false,
      },
      {
        id: "exception",
        label: "Should this exception be approved, refused, or escalated?",
        owner: "Named accountable person",
        alternatives: ["Approve", "Refuse", "Escalate"],
        intervention: "human",
        rationale:
          "The cost of a wrong answer is lopsided, so the decision stays with a person. AI can prepare the evidence, but it should not own the outcome.",
        aiCandidate: false,
      },
    ],

    assumptions: [
      "This outline was written in advance, not generated from your problem statement.",
      "Every stage, decision, owner, and alternative here is a placeholder - replace them with what really happens.",
      "The five decisions show the five possible verdicts on purpose. Your workflow will not split the same way.",
      "Name a real role as the owner of each decision, not a department.",
      "State what a wrong answer actually costs before proposing any solution.",
    ],
  };

  // Parse rather than cast: if the shape above ever drifts from the shared contract, this
  // throws here in one obvious place instead of failing validation in the browser.
  return workflowDraftSchema.parse(draft);
}
