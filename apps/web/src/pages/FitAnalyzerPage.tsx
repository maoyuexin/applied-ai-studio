import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, GitBranch, Sparkles, TriangleAlert, Workflow } from "lucide-react";
import type {
  AiSolutionBlueprint,
  FitAssessmentInput,
  FitAssessmentResult,
  WorkflowDraft,
  WorkloadType,
} from "@applied-ai-studio/contracts";
import {
  AI_SOLUTION_SCORE_THRESHOLD,
  isAiSolutionEligible,
} from "@applied-ai-studio/contracts";
import {
  createAiSolutionBlueprint,
  createAssessment,
  createWorkflowDraft,
  getIndustries,
} from "../api";
import AiSolutionBlueprintPanel from "../components/AiSolutionBlueprintPanel";
import { navigate } from "../router";

const defaultInput: FitAssessmentInput = {
  name: "",
  industry: "energy",
  problem: "",
  desiredOutcome: "",
  workloadType: "knowledge-qna",
  businessValue: 3,
  dataReadiness: 3,
  processRepeatability: 3,
  integrationReadiness: 3,
  humanOversight: 3,
  riskTolerance: 3,
};

const sliderFields: Array<{ key: keyof Pick<FitAssessmentInput, "businessValue" | "dataReadiness" | "processRepeatability" | "integrationReadiness" | "humanOversight" | "riskTolerance">; label: string; low: string; high: string }> = [
  { key: "businessValue", label: "Business value", low: "Marginal", high: "Material" },
  { key: "dataReadiness", label: "Data readiness", low: "Unknown", high: "Governed" },
  { key: "processRepeatability", label: "Process repeatability", low: "Ad hoc", high: "Repeatable" },
  { key: "integrationReadiness", label: "Integration readiness", low: "Manual", high: "API ready" },
  { key: "humanOversight", label: "Human oversight", low: "Undefined", high: "Accountable" },
  { key: "riskTolerance", label: "Error tolerance", low: "Very low", high: "Recoverable" },
];

const workloadOptions: Array<{ value: WorkloadType; label: string }> = [
  { value: "knowledge-qna", label: "Knowledge Q&A" },
  { value: "document-processing", label: "Document processing" },
  { value: "decision-support", label: "Decision support" },
  { value: "workflow-automation", label: "Workflow automation" },
  { value: "content-generation", label: "Content generation" },
  { value: "vision-analysis", label: "Vision analysis" },
];

export default function FitAnalyzerPage() {
  const [input, setInput] = useState(defaultInput);
  const [industries, setIndustries] = useState<Array<{ id: string; label: string }>>([]);
  const [result, setResult] = useState<FitAssessmentResult | null>(null);
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft | null>(null);
  const [selectedDraftDecisionId, setSelectedDraftDecisionId] = useState<string | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [solutionBlueprint, setSolutionBlueprint] = useState<AiSolutionBlueprint | null>(null);
  const [blueprintLoading, setBlueprintLoading] = useState(false);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getIndustries().then(setIndustries).catch(() => undefined);
  }, []);

  const generateSolutionBlueprint = async (assessment: FitAssessmentResult) => {
    const selectedDecision = workflowDraft?.decisions.find((decision) => decision.id === selectedDraftDecisionId);
    setBlueprintLoading(true);
    setBlueprintError(null);
    setSolutionBlueprint(null);
    try {
      setSolutionBlueprint(await createAiSolutionBlueprint({
        assessmentId: assessment.id,
        selectedDecision,
      }));
    } catch (reason) {
      setBlueprintError(reason instanceof Error ? reason.message : "AI solution design failed.");
    } finally {
      setBlueprintLoading(false);
    }
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const assessment = await createAssessment(input);
      setResult(assessment);
      setSolutionBlueprint(null);
      setBlueprintError(null);
      if (isAiSolutionEligible(assessment.totalScore)) {
        void generateSolutionBlueprint(assessment);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Assessment failed.");
    } finally {
      setLoading(false);
    }
  };

  const selectDraftDecision = (decision: WorkflowDraft["decisions"][number]) => {
    setSelectedDraftDecisionId(decision.id);
    setInput((current) => ({
      ...current,
      name: decision.label,
      workloadType: decision.suggestedWorkloadType ?? current.workloadType,
    }));
    setResult(null);
    setSolutionBlueprint(null);
    setBlueprintError(null);
  };

  const draftBusinessWorkflow = async () => {
    setDraftLoading(true);
    setError(null);
    try {
      const draft = await createWorkflowDraft({
        industry: industries.find((item) => item.id === input.industry)?.label ?? input.industry,
        problem: input.problem,
        desiredOutcome: input.desiredOutcome,
      });
      setWorkflowDraft(draft);
      const firstCandidate = draft.decisions.find((decision) => decision.aiCandidate) ?? draft.decisions[0];
      if (firstCandidate) selectDraftDecision(firstCandidate);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Workflow drafting failed.");
    } finally {
      setDraftLoading(false);
    }
  };

  return (
    <div className="page fit-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Structured discovery</span>
          <h1>AI Fit Analyzer</h1>
          <p>Describe the problem, review a five-stage workflow draft, then score one decision.</p>
        </div>
        <div className="source-badge"><Sparkles size={16} aria-hidden="true" /> Copilot draft + deterministic score</div>
      </header>

      <section className="fit-course-sequence" aria-label="AI Fit Analyzer sequence">
        <div><span>01</span><Workflow size={17} aria-hidden="true" /><strong>Map five stages</strong></div>
        <ArrowRight size={15} aria-hidden="true" />
        <div><span>02</span><GitBranch size={17} aria-hidden="true" /><strong>Review decisions</strong></div>
        <ArrowRight size={15} aria-hidden="true" />
        <div><span>03</span><CheckCircle2 size={17} aria-hidden="true" /><strong>Score selected fit</strong></div>
      </section>

      <div className="fit-layout">
        <form className="assessment-form" onSubmit={submit}>
          <div className="form-section-heading"><span>01</span><h2>Problem and process context</h2></div>
          <div className="form-grid">
            <label>
              <span>Use case name</span>
              <input required minLength={2} maxLength={80} value={input.name} onChange={(event) => setInput({ ...input, name: event.target.value })} placeholder="e.g. Maintenance triage" />
            </label>
            <label>
              <span>Industry</span>
              <select value={input.industry} onChange={(event) => setInput({ ...input, industry: event.target.value })}>
                {industries.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="full-width">
              <span>Current problem</span>
              <textarea required minLength={20} maxLength={1200} rows={4} value={input.problem} onChange={(event) => setInput({ ...input, problem: event.target.value })} placeholder="Describe the decision, delay, rework, or operating friction." />
            </label>
            <label className="full-width">
              <span>Desired outcome</span>
              <textarea required minLength={10} maxLength={600} rows={2} value={input.desiredOutcome} onChange={(event) => setInput({ ...input, desiredOutcome: event.target.value })} placeholder="State the measurable change you want." />
            </label>
            <label className="full-width">
              <span>Primary workload</span>
              <select value={input.workloadType} onChange={(event) => setInput({ ...input, workloadType: event.target.value as WorkloadType })}>
                {workloadOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>

          <button
            className="secondary-button workflow-draft-button"
            type="button"
            disabled={draftLoading || input.problem.trim().length < 20 || input.desiredOutcome.trim().length < 10}
            onClick={() => void draftBusinessWorkflow()}
          >
            <Sparkles size={16} aria-hidden="true" />
            {draftLoading ? "Drafting workflow..." : "Generate five-stage workflow"}
          </button>

          <div className="form-section-heading"><span>02</span><h2>Review candidate decisions</h2></div>
          {workflowDraft ? (
            <section className="workflow-draft-review" aria-label="Generated workflow draft">
              <div className="draft-review-heading"><div><span>Copilot draft</span><strong>{workflowDraft.title}</strong></div><small>Review assumptions before scoring</small></div>
              <div className="draft-stage-strip">
                {workflowDraft.stages.map((stage, index) => (
                  <div key={stage.id} className={stage.id === "decision" ? "decision-stage" : ""}>
                    <span>{index + 1}</span><strong>{stage.label}</strong><p>{stage.description}</p>
                  </div>
                ))}
              </div>
              <div className="draft-decision-list">
                {workflowDraft.decisions.map((decision) => (
                  <button
                    type="button"
                    key={decision.id}
                    className={`${selectedDraftDecisionId === decision.id ? "active" : ""} intervention-${decision.intervention}`}
                    onClick={() => selectDraftDecision(decision)}
                  >
                    <div><strong>{decision.label}</strong><span>{decision.owner}</span></div>
                    <small>
                      {decision.intervention}
                      {decision.suggestedCoursePattern ? ` · ${decision.suggestedCoursePattern}` : ""}
                    </small>
                    <p>{decision.rationale}</p>
                  </button>
                ))}
              </div>
              {workflowDraft.assumptions.length ? <div className="draft-assumptions"><strong>Assumptions</strong><ul>{workflowDraft.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}</ul></div> : null}
            </section>
          ) : (
            <div className="draft-empty-state"><Workflow size={22} aria-hidden="true" /><p>Generate a draft to expose the five business stages and candidate decisions. You can still score a manually defined decision if Copilot is unavailable.</p></div>
          )}

          <div className="form-section-heading"><span>03</span><h2>Readiness signals for the selected decision</h2></div>
          <div className="slider-list">
            {sliderFields.map((field) => (
              <label className="slider-row" key={field.key}>
                <span className="slider-label"><strong>{field.label}</strong><b>{input[field.key]}/5</b></span>
                <input type="range" min="1" max="5" step="1" value={input[field.key]} onChange={(event) => setInput({ ...input, [field.key]: Number(event.target.value) })} />
                <span className="slider-scale"><small>{field.low}</small><small>{field.high}</small></span>
              </label>
            ))}
          </div>

          {error ? <div className="error-banner">{error}</div> : null}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Scoring..." : "Run fit analysis"}
            <ArrowRight size={17} aria-hidden="true" />
          </button>
        </form>

        <section className="assessment-result" aria-live="polite">
          {!result ? (
            <div className="result-empty">
              <GitBranch size={42} aria-hidden="true" />
              <h2>Assessment workspace</h2>
              <p>The scored architecture and review boundary will appear here.</p>
            </div>
          ) : (
            <>
              <div className="result-summary">
                <div className="score-dial" style={{ "--score": `${result.totalScore}%` } as React.CSSProperties}>
                  <strong>{result.totalScore}</strong><span>/100</span>
                </div>
                <div>
                  <span className={`readiness-label ${result.readiness}`}>{result.readiness.replaceAll("-", " ")}</span>
                  <h2>{result.recommendedPattern.replaceAll("-", " ")}</h2>
                  <p>{result.input.name}</p>
                </div>
              </div>

              <div className="dimension-list">
                {result.dimensions.map((dimension) => (
                  <div className="dimension-row" key={dimension.id}>
                    <div><strong>{dimension.label}</strong><span>{dimension.rationale}</span></div>
                    <div className="dimension-score"><span style={{ width: `${(dimension.score / dimension.maxScore) * 100}%` }} /><b>{dimension.score}/{dimension.maxScore}</b></div>
                  </div>
                ))}
              </div>

              <div className="result-columns">
                <div className="result-section">
                  <h3><TriangleAlert size={16} aria-hidden="true" /> Risks</h3>
                  {result.risks.length ? <ul>{result.risks.map((risk) => <li key={risk}>{risk}</li>)}</ul> : <p>No foundational risk triggered by the current scores.</p>}
                </div>
                <div className="result-section">
                  <h3><CheckCircle2 size={16} aria-hidden="true" /> Next validation</h3>
                  <ol>{result.nextSteps.map((step) => <li key={step}>{step}</li>)}</ol>
                </div>
              </div>

              {isAiSolutionEligible(result.totalScore) ? (
                <div className="solution-gate solution-gate-open">
                  <div>
                    <CheckCircle2 size={19} aria-hidden="true" />
                    <span><strong>AI solution design unlocked</strong><small>Score {result.totalScore} meets the {AI_SOLUTION_SCORE_THRESHOLD}-point gate.</small></span>
                  </div>
                  {blueprintLoading ? <div className="blueprint-loading"><Sparkles size={18} aria-hidden="true" /><span>Copilot is designing the second workflow, metrics, and human controls...</span></div> : null}
                  {blueprintError ? (
                    <div className="blueprint-error">
                      <p>{blueprintError}</p>
                      <button className="secondary-button" type="button" onClick={() => void generateSolutionBlueprint(result)}>Retry AI solution design</button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="solution-gate solution-gate-closed">
                  <TriangleAlert size={19} aria-hidden="true" />
                  <span>
                    <strong>Strengthen readiness before solution design</strong>
                    <small>Score {result.totalScore} is below the {AI_SOLUTION_SCORE_THRESHOLD}-point gate. No detailed AI solution or second workflow was generated.</small>
                  </span>
                </div>
              )}

              {solutionBlueprint ? <AiSolutionBlueprintPanel blueprint={solutionBlueprint} /> : null}

              <button className="secondary-button" type="button" onClick={() => navigate(`/ask?assessment=${result.id}`)}>
                Ask Copilot about this assessment
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            </>
          )}
        </section>
      </div>
    </div>
  );
}