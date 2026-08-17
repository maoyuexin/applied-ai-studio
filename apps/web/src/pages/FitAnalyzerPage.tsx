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
  type WorkflowDraftSource,
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
  const [draftSource, setDraftSource] = useState<WorkflowDraftSource | null>(null);
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
    } catch {
      setBlueprintError(
        "The detailed design needs GitHub Copilot, and it is not connected to your account yet. Your score and the readiness notes above are already saved — nothing was lost. If you have applied for the Student Developer Pack, try again once it is approved.",
      );
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
    } catch {
      setError(
        "We could not score that just now. Check that every box above is filled in, then try again. If it keeps happening, make sure the app is still running in your terminal.",
      );
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
      const { draft, source } = await createWorkflowDraft({
        industry: industries.find((item) => item.id === input.industry)?.label ?? input.industry,
        problem: input.problem,
        desiredOutcome: input.desiredOutcome,
      });
      setWorkflowDraft(draft);
      setDraftSource(source);
      const firstCandidate = draft.decisions.find((decision) => decision.aiCandidate) ?? draft.decisions[0];
      if (firstCandidate) selectDraftDecision(firstCandidate);
    } catch {
      // Both the Copilot path and the starter-outline fallback failed, which almost always
      // means the app itself is not running properly rather than anything the student did.
      setError(
        "We could not build an outline just now. Check that the app is still running in your terminal, then try again. If it keeps happening, close this codespace and open a new one.",
      );
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
              {draftSource === "starter" ? (
                <div className="starter-draft-notice">
                  <strong>Starter outline — written without AI</strong>
                  <p>
                    GitHub Copilot is not connected to your account yet, so we filled in a standard
                    five-stage outline instead of writing one about your own problem.
                  </p>
                  <p>
                    Everything below still works. Edit any stage, pick a decision, and score it.
                  </p>
                  <p>
                    If you have applied for the Student Developer Pack, Copilot usually switches on
                    within a few days. Come back then and this button will write an outline based on
                    what you typed.
                  </p>
                </div>
              ) : null}
              <div className="draft-review-heading"><div><span>{draftSource === "starter" ? "Starter outline" : "Copilot draft"}</span><strong>{workflowDraft.title}</strong></div><small>Review assumptions before scoring</small></div>
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
            <div className="draft-empty-state"><Workflow size={22} aria-hidden="true" /><p>Use the button above to lay your problem out as the five stages, with the decisions marked. You can also skip this and score a decision you name yourself.</p></div>
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
                    <span><strong>Ready for a detailed design</strong><small>You scored {result.totalScore} out of 100. Anything from {AI_SOLUTION_SCORE_THRESHOLD} is enough to design this in detail.</small></span>
                  </div>
                  {blueprintLoading ? <div className="blueprint-loading"><Sparkles size={18} aria-hidden="true" /><span>Working out the data, the method, the numbers that prove it worked, and where the person sits. This takes a few seconds.</span></div> : null}
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
                    <strong>Not ready for a detailed design yet</strong>
                    <small>
                      You scored {result.totalScore} out of 100, and a detailed design needs {AI_SOLUTION_SCORE_THRESHOLD}.
                      This is a normal, useful result — not a failure and not something you broke. Look at the
                      lowest rows above: they name what is missing. Deciding a problem is not ready for AI is a
                      real finding, and you can write it up as one.
                    </small>
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