import { randomUUID } from "node:crypto";
import type {
  FitAssessmentInput,
  FitAssessmentResult,
  FitDimension,
  UseCase,
  WorkflowGraph,
} from "@applied-ai-studio/contracts";

const rationale = (value: number, strength: string, gap: string): string =>
  value >= 4 ? strength : value === 3 ? `Usable with targeted validation. ${gap}` : gap;

function dimensions(input: FitAssessmentInput): FitDimension[] {
  return [
    {
      id: "value",
      label: "Business value",
      score: input.businessValue * 4,
      maxScore: 20,
      rationale: rationale(input.businessValue, "The outcome is valuable enough to justify an AI workflow.", "Clarify the measurable decision or operating outcome."),
    },
    {
      id: "data",
      label: "Data readiness",
      score: input.dataReadiness * 4,
      maxScore: 20,
      rationale: rationale(input.dataReadiness, "Representative, accessible data is available for grounding and evaluation.", "Inventory sources, permissions, quality, and a representative evaluation set."),
    },
    {
      id: "repeatability",
      label: "Process repeatability",
      score: input.processRepeatability * 3,
      maxScore: 15,
      rationale: rationale(input.processRepeatability, "The workflow repeats often enough to benefit from reusable tools and prompts.", "Document the current workflow and identify the stable decision points."),
    },
    {
      id: "integration",
      label: "Integration readiness",
      score: input.integrationReadiness * 3,
      maxScore: 15,
      rationale: rationale(input.integrationReadiness, "The required systems expose usable APIs or controlled data interfaces.", "Define a narrow adapter or manual handoff before pursuing end-to-end automation."),
    },
    {
      id: "oversight",
      label: "Human oversight",
      score: input.humanOversight * 3,
      maxScore: 15,
      rationale: rationale(input.humanOversight, "A qualified reviewer can inspect evidence and approve consequential actions.", "Name the accountable reviewer and design an explicit approval step."),
    },
    {
      id: "risk",
      label: "Error tolerance",
      score: input.riskTolerance * 3,
      maxScore: 15,
      rationale: rationale(input.riskTolerance, "Errors are recoverable within the proposed human-review boundary.", "Reduce scope, strengthen deterministic checks, and prevent autonomous consequential action."),
    },
  ];
}

function patternFor(input: FitAssessmentInput): FitAssessmentResult["recommendedPattern"] {
  if (input.workloadType === "document-processing") return "document-intelligence";
  if (input.workloadType === "vision-analysis") return "vision-analysis";
  if (input.workloadType === "content-generation") return "content-studio";
  if (input.workloadType === "workflow-automation" && input.integrationReadiness >= 3) return "workflow-agent";
  if (input.workloadType === "decision-support") return "decision-support";
  return "retrieval-copilot";
}

const graphByPattern: Record<FitAssessmentResult["recommendedPattern"], WorkflowGraph> = {
  "retrieval-copilot": {
    nodes: [
      { id: "question", label: "User question", kind: "input" },
      { id: "retrieve", label: "Retrieve approved knowledge", kind: "process" },
      { id: "copilot", label: "Grounded Copilot", kind: "ai" },
      { id: "review", label: "User verifies sources", kind: "human" },
      { id: "answer", label: "Supported answer", kind: "output" },
    ],
    edges: [
      { from: "question", to: "retrieve", label: "search" },
      { from: "retrieve", to: "copilot", label: "evidence" },
      { from: "copilot", to: "review", label: "draft" },
      { from: "review", to: "answer", label: "accept" },
    ],
  },
  "document-intelligence": {
    nodes: [
      { id: "documents", label: "Documents", kind: "input" },
      { id: "extract", label: "Deterministic extraction", kind: "process" },
      { id: "interpret", label: "AI interpretation", kind: "ai" },
      { id: "review", label: "Domain review", kind: "human" },
      { id: "record", label: "Validated record", kind: "system" },
    ],
    edges: [
      { from: "documents", to: "extract", label: "parse" },
      { from: "extract", to: "interpret", label: "structured evidence" },
      { from: "interpret", to: "review", label: "exceptions" },
      { from: "review", to: "record", label: "approve" },
    ],
  },
  "decision-support": {
    nodes: [
      { id: "signals", label: "Governed signals", kind: "input" },
      { id: "analysis", label: "Deterministic analysis", kind: "process" },
      { id: "explain", label: "Copilot explanation", kind: "ai" },
      { id: "decision", label: "Human decision", kind: "human" },
      { id: "outcome", label: "Recorded outcome", kind: "system" },
    ],
    edges: [
      { from: "signals", to: "analysis", label: "calculate" },
      { from: "analysis", to: "explain", label: "ground" },
      { from: "explain", to: "decision", label: "recommend" },
      { from: "decision", to: "outcome", label: "record" },
    ],
  },
  "workflow-agent": {
    nodes: [
      { id: "request", label: "Workflow request", kind: "input" },
      { id: "agent", label: "Tool-using agent", kind: "ai" },
      { id: "tools", label: "Allowlisted tools", kind: "system" },
      { id: "approval", label: "Human approval", kind: "human" },
      { id: "action", label: "Audited action", kind: "output" },
    ],
    edges: [
      { from: "request", to: "agent", label: "plan" },
      { from: "agent", to: "tools", label: "read" },
      { from: "tools", to: "approval", label: "proposal" },
      { from: "approval", to: "action", label: "authorize" },
    ],
  },
  "content-studio": {
    nodes: [
      { id: "brief", label: "Approved brief", kind: "input" },
      { id: "guidance", label: "Brand and policy retrieval", kind: "process" },
      { id: "generate", label: "Content generation", kind: "ai" },
      { id: "editor", label: "Editor review", kind: "human" },
      { id: "publish", label: "Approved content", kind: "output" },
    ],
    edges: [
      { from: "brief", to: "guidance", label: "scope" },
      { from: "guidance", to: "generate", label: "constraints" },
      { from: "generate", to: "editor", label: "draft" },
      { from: "editor", to: "publish", label: "approve" },
    ],
  },
  "vision-analysis": {
    nodes: [
      { id: "media", label: "Image or video", kind: "input" },
      { id: "prepare", label: "Preprocess and segment", kind: "process" },
      { id: "vision", label: "Vision analysis", kind: "ai" },
      { id: "expert", label: "Expert validation", kind: "human" },
      { id: "finding", label: "Evidence-linked finding", kind: "output" },
    ],
    edges: [
      { from: "media", to: "prepare", label: "normalize" },
      { from: "prepare", to: "vision", label: "regions" },
      { from: "vision", to: "expert", label: "candidate findings" },
      { from: "expert", to: "finding", label: "validate" },
    ],
  },
};

function matchedUseCases(input: FitAssessmentInput, useCases: UseCase[]): string[] {
  return useCases
    .map((useCase) => ({
      id: useCase.id,
      score:
        (useCase.industry === input.industry ? 3 : 0) +
        (useCase.workloadType === input.workloadType ? 4 : 0) +
        (useCase.riskLevel === "high" && input.riskTolerance <= 2 ? 1 : 0),
    }))
    .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id))
    .filter((match) => match.score > 0)
    .slice(0, 4)
    .map((match) => match.id);
}

export function assessFit(input: FitAssessmentInput, useCases: UseCase[]): FitAssessmentResult {
  const scoredDimensions = dimensions(input);
  const totalScore = scoredDimensions.reduce((total, dimension) => total + dimension.score, 0);
  const readiness = totalScore >= 75 ? "strong-fit" : totalScore >= 55 ? "conditional-fit" : "foundation-first";
  const recommendedPattern = patternFor(input);
  const risks: string[] = [];
  const nextSteps: string[] = [];

  if (input.dataReadiness <= 2) risks.push("Evidence quality and access are not ready for reliable grounding.");
  if (input.integrationReadiness <= 2) risks.push("The workflow lacks a controlled interface to required systems.");
  if (input.humanOversight <= 2) risks.push("No sufficiently strong review and accountability boundary is defined.");
  if (input.riskTolerance <= 2) risks.push("The proposed decision has low tolerance for model error or ambiguity.");

  if (input.businessValue <= 3) nextSteps.push("Define one measurable outcome and a baseline before building the AI experience.");
  if (input.dataReadiness <= 3) nextSteps.push("Assemble a representative, permission-cleared evaluation dataset.");
  if (input.processRepeatability <= 3) nextSteps.push("Map the current workflow and separate stable rules from judgment-heavy steps.");
  if (input.integrationReadiness <= 3) nextSteps.push("Prototype one read-only adapter before enabling any write action.");
  if (input.humanOversight <= 3 || input.riskTolerance <= 3) nextSteps.push("Design explicit review, refusal, audit, and escalation behavior.");
  nextSteps.push("Run a bounded PoC and evaluate grounded quality, latency, safety, and user value.");

  return {
    id: randomUUID(),
    createdAt: new Date().toISOString(),
    input,
    totalScore,
    readiness,
    recommendedPattern,
    dimensions: scoredDimensions,
    matchedUseCaseIds: matchedUseCases(input, useCases),
    risks,
    nextSteps,
    workflow: graphByPattern[recommendedPattern],
  };
}