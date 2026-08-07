import { z } from "zod";

export const workloadTypeSchema = z.enum([
  "knowledge-qna",
  "document-processing",
  "decision-support",
  "workflow-automation",
  "content-generation",
  "vision-analysis",
]);

export const graphNodeSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  kind: z.enum(["input", "process", "ai", "human", "system", "output"]),
});

export const graphEdgeSchema = z.object({
  from: z.string().min(1),
  to: z.string().min(1),
  label: z.string().default(""),
});

export const workflowGraphSchema = z.object({
  nodes: z.array(graphNodeSchema).min(2).max(12),
  edges: z.array(graphEdgeSchema).min(1).max(16),
});

export const courseStageSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  description: z.string().min(1),
});

export const workflowLaneSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  order: z.number().int().min(0),
});

export const courseWorkflowNodeSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  lane: z.string().min(1),
  kind: z.enum(["start", "process", "decision", "action", "outcome"]),
  x: z.number().min(0).max(1200),
  documented: z.boolean(),
  decisionId: z.string().optional(),
});

export const courseWorkflowEdgeSchema = z.object({
  id: z.string().min(1),
  from: z.string().min(1),
  to: z.string().min(1),
  label: z.string().default(""),
  labelDx: z.number().min(-120).max(120).optional(),
  labelDy: z.number().min(-80).max(80).optional(),
  kind: z.enum(["normal", "exception", "loop"]),
  documented: z.boolean(),
});

export const decisionVerdictSchema = z.enum([
  "rule",
  "automation",
  "ai-classification",
  "ai-prediction",
  "optimization",
  "ai-generation",
  "human",
]);

export const aiDecisionDesignSchema = z.object({
  data: z.object({
    summary: z.string(),
    owner: z.string(),
    readiness: z.string(),
    fields: z.array(z.string()).min(1),
    risk: z.string(),
  }),
  method: z.object({
    pattern: z.enum(["classification", "prediction", "optimization", "generation"]),
    output: z.string(),
    technique: z.string(),
  }),
  metric: z.object({
    technical: z.string(),
    business: z.string(),
    baseline: z.string(),
  }),
  human: z.object({
    role: z.string(),
    checkpoint: z.string(),
    falsePositiveCost: z.string(),
    falseNegativeCost: z.string(),
  }),
  architecture: z.array(z.string()).min(3),
});

export const courseDecisionSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  owner: z.string().min(1),
  frequency: z.string().min(1),
  wrongCost: z.string().min(1),
  verdict: decisionVerdictSchema,
  verdictLabel: z.string().min(1),
  testAnswer: z.string().min(1),
  why: z.string().min(1),
  recommendation: z.string().min(1),
  aiRelevant: z.boolean(),
  placement: z.enum(["decision", "process"]),
  design: aiDecisionDesignSchema.optional(),
});

export const courseCaseSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  subtitle: z.string().min(1),
  industry: z.string().min(1),
  learningObjective: z.string().min(1),
  throughline: z.string().min(1),
  introduction: z.object({
    title: z.string().min(1).max(100),
    context: z.string().min(40).max(700),
    workflow: z.string().min(40).max(700),
    startsWhen: z.string().min(10).max(240),
    endsWhen: z.string().min(10).max(240),
  }),
  stages: z.array(courseStageSchema).length(5),
  baseline: z.array(z.object({ value: z.string(), label: z.string(), note: z.string() })).min(1),
  lanes: z.array(workflowLaneSchema).min(2),
  nodes: z.array(courseWorkflowNodeSchema).min(5),
  edges: z.array(courseWorkflowEdgeSchema).min(4),
  decisions: z.array(courseDecisionSchema).min(5),
  featuredDecisionId: z.string().min(1),
  source: z.literal("synthetic-workflow-assumption"),
});

export const useCaseSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  industry: z.string().min(1),
  industryLabel: z.string().min(1),
  icon: z.string().min(1),
  accent: z.enum(["orange", "teal", "amber", "red", "pink"]),
  summary: z.string().min(1),
  problem: z.string().min(1),
  outcomes: z.array(z.string()).min(1),
  capabilities: z.array(z.string()).min(1),
  patterns: z.array(z.string()).min(1),
  workloadType: workloadTypeSchema,
  dataReadiness: z.enum(["low", "medium", "high"]),
  riskLevel: z.enum(["low", "medium", "high"]),
  maturity: z.enum(["showcase", "prototype", "production-pattern"]),
  architecture: z.array(z.string()).min(2),
  workflow: workflowGraphSchema,
  demoPrompts: z.array(z.string()).min(1),
  courseCaseId: z.string().optional(),
  demoStatus: z.enum(["planned", "available"]).optional(),
  source: z.literal("public-synthetic"),
});

export const fitAssessmentInputSchema = z.object({
  name: z.string().trim().min(2).max(80),
  industry: z.string().trim().min(1).max(60),
  problem: z.string().trim().min(20).max(1200),
  desiredOutcome: z.string().trim().min(10).max(600),
  workloadType: workloadTypeSchema,
  businessValue: z.number().int().min(1).max(5),
  dataReadiness: z.number().int().min(1).max(5),
  processRepeatability: z.number().int().min(1).max(5),
  integrationReadiness: z.number().int().min(1).max(5),
  humanOversight: z.number().int().min(1).max(5),
  riskTolerance: z.number().int().min(1).max(5),
});

export const workflowDraftInputSchema = z.object({
  industry: z.string().trim().min(1).max(80),
  problem: z.string().trim().min(20).max(1200),
  desiredOutcome: z.string().trim().min(10).max(600),
});

export const workflowDraftStageSchema = z.object({
  id: z.enum(["input", "process", "decision", "action", "outcome"]),
  label: z.string().min(1).max(40),
  description: z.string().min(5).max(240),
});

export const workflowDraftDecisionSchema = z.object({
  id: z.string().regex(/^[a-z0-9-]+$/).max(60),
  label: z.string().min(5).max(160),
  owner: z.string().min(2).max(100),
  alternatives: z.array(z.string().min(1).max(100)).min(2).max(4),
  intervention: z.enum(["rule", "automation", "ai", "optimization", "human", "investigate"]),
  rationale: z.string().min(10).max(400),
  aiCandidate: z.boolean(),
  suggestedWorkloadType: workloadTypeSchema.optional(),
  suggestedCoursePattern: z.enum(["classification", "prediction", "optimization", "generation"]).optional(),
});

export const workflowDraftSchema = z.object({
  title: z.string().min(2).max(100),
  stages: z.array(workflowDraftStageSchema).length(5).refine(
    (stages) => new Set(stages.map((stage) => stage.id)).size === 5,
    "Workflow draft must contain each of the five business stages exactly once.",
  ),
  decisions: z.array(workflowDraftDecisionSchema).min(1).max(6),
  assumptions: z.array(z.string().min(3).max(240)).max(8),
});

export const solutionPatternSchema = z.enum([
  "retrieval-copilot",
  "document-intelligence",
  "decision-support",
  "workflow-agent",
  "content-studio",
  "vision-analysis",
]);

export const aiSolutionBlueprintRequestSchema = z.object({
  assessmentId: z.string().uuid(),
  selectedDecision: workflowDraftDecisionSchema.optional(),
});

export const successMetricSchema = z.object({
  name: z.string().min(2).max(100),
  successCriterion: z.string().min(5).max(400),
  rationale: z.string().min(5).max(400),
});

export const aiSolutionBlueprintSchema = z.object({
  assessmentId: z.string().uuid(),
  title: z.string().min(2).max(120),
  summary: z.string().min(20).max(700),
  coursePattern: z.enum(["classification", "prediction", "optimization", "generation"]),
  solutionPattern: solutionPatternSchema,
  data: z.object({
    sources: z.array(z.string().min(2).max(140)).min(2).max(8),
    targetOrGroundTruth: z.string().min(5).max(500),
    owner: z.string().min(2).max(140),
    preparation: z.array(z.string().min(5).max(400)).min(1).max(6),
  }),
  method: z.object({
    approach: z.string().min(5).max(600),
    output: z.string().min(5).max(400),
    guardrail: z.string().min(5).max(600),
  }),
  metrics: z.object({
    technical: z.array(successMetricSchema).min(1).max(4),
    business: z.array(successMetricSchema).min(1).max(4),
  }),
  human: z.object({
    role: z.string().min(2).max(120),
    checkpoint: z.string().min(5).max(500),
    authority: z.string().min(5).max(500),
    escalation: z.string().min(5).max(500),
  }),
  components: z.array(z.object({
    id: z.string().regex(/^[a-z0-9-]+$/).max(60),
    name: z.string().min(2).max(100),
    responsibility: z.string().min(5).max(500),
    kind: z.enum(["data", "process", "ai", "human", "system", "output"]),
  })).min(4).max(10),
  workflow: workflowGraphSchema,
  risks: z.array(z.string().min(5).max(500)).min(1).max(6),
  pocPlan: z.array(z.string().min(5).max(500)).min(3).max(6),
});

export const AI_SOLUTION_SCORE_THRESHOLD = 75;

export function isAiSolutionEligible(score: number): boolean {
  return score >= AI_SOLUTION_SCORE_THRESHOLD;
}

export const fitDimensionSchema = z.object({
  id: z.string(),
  label: z.string(),
  score: z.number().int().min(0),
  maxScore: z.number().int().positive(),
  rationale: z.string(),
});

export const fitAssessmentResultSchema = z.object({
  id: z.string(),
  createdAt: z.string().datetime(),
  input: fitAssessmentInputSchema,
  totalScore: z.number().int().min(0).max(100),
  readiness: z.enum(["strong-fit", "conditional-fit", "foundation-first"]),
  recommendedPattern: solutionPatternSchema,
  dimensions: z.array(fitDimensionSchema).length(6),
  matchedUseCaseIds: z.array(z.string()).max(4),
  risks: z.array(z.string()),
  nextSteps: z.array(z.string()),
  workflow: workflowGraphSchema,
});

export const chatRequestSchema = z.object({
  sessionId: z.string().uuid().optional(),
  message: z.string().trim().min(1).max(4000),
});

export type WorkloadType = z.infer<typeof workloadTypeSchema>;
export type WorkflowGraph = z.infer<typeof workflowGraphSchema>;
export type UseCase = z.infer<typeof useCaseSchema>;
export type CourseCase = z.infer<typeof courseCaseSchema>;
export type CourseDecision = z.infer<typeof courseDecisionSchema>;
export type CourseWorkflowNode = z.infer<typeof courseWorkflowNodeSchema>;
export type CourseWorkflowEdge = z.infer<typeof courseWorkflowEdgeSchema>;
export type FitAssessmentInput = z.infer<typeof fitAssessmentInputSchema>;
export type WorkflowDraftInput = z.infer<typeof workflowDraftInputSchema>;
export type WorkflowDraft = z.infer<typeof workflowDraftSchema>;
export type AiSolutionBlueprintRequest = z.infer<typeof aiSolutionBlueprintRequestSchema>;
export type AiSolutionBlueprint = z.infer<typeof aiSolutionBlueprintSchema>;
export type FitDimension = z.infer<typeof fitDimensionSchema>;
export type FitAssessmentResult = z.infer<typeof fitAssessmentResultSchema>;
export type ChatRequest = z.infer<typeof chatRequestSchema>;