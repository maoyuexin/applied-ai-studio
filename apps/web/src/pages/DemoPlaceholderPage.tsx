import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Gauge,
  Play,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";
import type { UseCase } from "@applied-ai-studio/contracts";
import { getUseCase } from "../api";
import { navigate } from "../router";

export default function DemoPlaceholderPage() {
  const useCaseId = new URLSearchParams(window.location.search).get("case");
  const [useCase, setUseCase] = useState<UseCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!useCaseId) return;
    void getUseCase(useCaseId).then(setUseCase).catch((reason: Error) => setError(reason.message));
  }, [useCaseId]);

  if (!useCaseId) return <div className="page"><div className="error-banner">Select a use case from Industry Cases.</div></div>;
  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;
  if (!useCase) return <div className="route-loading">Loading demo plan...</div>;

  const workflowTarget = useCase.courseCaseId
    ? `/workflow?courseCase=${encodeURIComponent(useCase.courseCaseId)}`
    : `/workflow?case=${encodeURIComponent(useCase.id)}`;

  return (
    <div className="page demo-placeholder-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Back to Industry Cases
      </button>
      <header className="page-header">
        <div>
          <span className="eyebrow">{useCase.industryLabel} · Simulation slot</span>
          <h1>{useCase.title} Demo</h1>
          <p>A future hands-on simulation for this specific workflow.</p>
        </div>
        <div className="source-badge"><Play size={16} aria-hidden="true" /> Planned module</div>
      </header>

      <section className="demo-reservation">
        <div className="demo-reservation-mark"><Play size={32} aria-hidden="true" /></div>
        <span>Simulation placeholder</span>
        <h2>Turn the workflow into an observable decision experiment</h2>
        <p>The production demo will let students change assumptions, compare interventions, and see how technical metrics connect to business outcomes and human review.</p>
      </section>

      <section className="demo-plan-grid">
        <div><SlidersHorizontal size={20} aria-hidden="true" /><strong>Scenario controls</strong><p>Change input volume, risk thresholds, exception rates, and review capacity.</p></div>
        <div><Workflow size={20} aria-hidden="true" /><strong>Decision behavior</strong><p>Compare a rule, automation, AI recommendation, and human decision boundary.</p></div>
        <div><Gauge size={20} aria-hidden="true" /><strong>Outcome metrics</strong><p>Observe quality, cost, delay, false positives, false negatives, and workload.</p></div>
      </section>

      <div className="demo-placeholder-actions">
        <button className="secondary-button" type="button" onClick={() => navigate(workflowTarget)}><Workflow size={16} aria-hidden="true" /> Open workflow</button>
        <button className="primary-button compact" type="button" disabled>Build in a later sprint <ArrowRight size={16} aria-hidden="true" /></button>
      </div>
    </div>
  );
}