import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Boxes,
  CircleUserRound,
  Database,
  Goal,
  Scale,
  Workflow,
} from "lucide-react";
import type { UseCase } from "@applied-ai-studio/contracts";
import { getUseCase } from "../api";
import MermaidDiagram from "../components/MermaidDiagram";
import { navigate } from "../router";
import CourseFlowPage from "./CourseFlowPage";

type WorkflowPhase = "map" | "judge" | "design";

export default function WorkflowPage() {
  const params = new URLSearchParams(window.location.search);
  const courseCaseId = params.get("courseCase");
  const useCaseId = params.get("case");
  const [useCase, setUseCase] = useState<UseCase | null>(null);
  const [phase, setPhase] = useState<WorkflowPhase>("map");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!useCaseId || courseCaseId) return;
    void getUseCase(useCaseId).then(setUseCase).catch((reason: Error) => setError(reason.message));
  }, [courseCaseId, useCaseId]);

  if (courseCaseId) return <CourseFlowPage courseCaseId={courseCaseId} />;
  if (!useCaseId) return <div className="page"><div className="error-banner">Select a workflow from Industry Workflows.</div></div>;
  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;
  if (!useCase) return <div className="route-loading">Loading workflow...</div>;

  const humanNodes = useCase.workflow.nodes.filter((node) => node.kind === "human");
  return (
    <div className="page generic-workflow-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Back to Industry Workflows
      </button>
      <header className="page-header">
        <div>
          <span className="eyebrow">{useCase.industryLabel} · Workflow</span>
          <h1>{useCase.title}</h1>
          <p>{useCase.summary}</p>
        </div>
        <div className="source-badge"><Workflow size={16} aria-hidden="true" /> Synthetic workflow</div>
      </header>

      <nav className="lesson-stepper compact-stepper" aria-label="Use case workflow lenses">
        <button type="button" className={phase === "map" ? "active" : ""} onClick={() => setPhase("map")}>
          <span>01</span><Workflow size={18} aria-hidden="true" /><div><strong>Business workflow</strong><small>Problem → outcome</small></div>
        </button>
        <button type="button" className={phase === "judge" ? "active" : ""} onClick={() => setPhase("judge")}>
          <span>02</span><Scale size={18} aria-hidden="true" /><div><strong>Potential AI fit</strong><small>Data · risk · workload</small></div>
        </button>
        <button type="button" className={phase === "design" ? "active" : ""} onClick={() => setPhase("design")}>
          <span>03</span><Goal size={18} aria-hidden="true" /><div><strong>Solution pattern</strong><small>Components · controls</small></div>
        </button>
      </nav>

      <div className="generic-workflow-layout">
        <section className="generic-workflow-diagram">
          <div className="workflow-panel-header"><div><span>Current view</span><strong>{phase === "map" ? "Business workflow" : phase === "judge" ? "AI fit lens" : "Solution pattern"}</strong></div></div>
          <MermaidDiagram graph={useCase.workflow} label={`${useCase.title} workflow`} />
        </section>
        <aside className="generic-workflow-inspector">
          {phase === "map" ? (
            <>
              <div className="inspector-kicker">Step 1 · Map the work</div>
              <h2>Problem and outcome</h2>
              <p>{useCase.problem}</p>
              <h3>Expected outcomes</h3>
              <ul>{useCase.outcomes.map((outcome) => <li key={outcome}>{outcome}</li>)}</ul>
            </>
          ) : null}
          {phase === "judge" ? (
            <>
              <div className="inspector-kicker">Step 2 · Potential fit</div>
              <h2>{useCase.workloadType.replaceAll("-", " ")}</h2>
              <div className="generic-fit-facts">
                <div><Database size={16} aria-hidden="true" /><span>Data readiness</span><strong>{useCase.dataReadiness}</strong></div>
                <div><Scale size={16} aria-hidden="true" /><span>Risk level</span><strong>{useCase.riskLevel}</strong></div>
                <div><Boxes size={16} aria-hidden="true" /><span>Maturity</span><strong>{useCase.maturity}</strong></div>
              </div>
              <p className="workflow-caveat">This is a catalog hypothesis. Students should still identify the actual decisions and test cheaper alternatives before approving an AI project.</p>
            </>
          ) : null}
          {phase === "design" ? (
            <>
              <div className="inspector-kicker">Step 3 · Design lens</div>
              <h2>Solution components</h2>
              <ol>{useCase.architecture.map((component) => <li key={component}>{component}</li>)}</ol>
              <h3>AI capabilities</h3>
              <div className="compact-tags">{useCase.capabilities.map((capability) => <span key={capability}>{capability}</span>)}</div>
              <h3><CircleUserRound size={15} aria-hidden="true" /> Human boundary</h3>
              <p>{humanNodes.length ? humanNodes.map((node) => node.label).join(", ") : "Define an accountable reviewer before implementation."}</p>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}