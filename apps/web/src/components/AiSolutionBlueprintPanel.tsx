import {
  ArrowRight,
  Boxes,
  CircleUserRound,
  Database,
  FlaskConical,
  Goal,
  ShieldAlert,
  Workflow,
} from "lucide-react";
import type { AiSolutionBlueprint } from "@applied-ai-studio/contracts";
import MermaidDiagram from "./MermaidDiagram";

function MetricList({ title, metrics }: { title: string; metrics: AiSolutionBlueprint["metrics"]["technical"] }) {
  return (
    <section className="blueprint-metric-group">
      <h4>{title}</h4>
      {metrics.map((metric) => (
        <div key={metric.name} className="blueprint-metric">
          <strong>{metric.name}</strong>
          <span>{metric.successCriterion}</span>
          <small>{metric.rationale}</small>
        </div>
      ))}
    </section>
  );
}

export default function AiSolutionBlueprintPanel({ blueprint }: { blueprint: AiSolutionBlueprint }) {
  return (
    <section className="solution-blueprint" aria-label="Proposed AI solution blueprint">
      <header className="blueprint-header">
        <div>
          <span><FlaskConical size={14} aria-hidden="true" /> Strong-fit design</span>
          <h2>{blueprint.title}</h2>
          <p>{blueprint.summary}</p>
        </div>
        <div className="blueprint-patterns">
          <div><small>AI method</small><strong>{blueprint.coursePattern}</strong></div>
          <ArrowRight size={15} aria-hidden="true" />
          <div><small>Solution pattern</small><strong>{blueprint.solutionPattern.replaceAll("-", " ")}</strong></div>
        </div>
      </header>

      <div className="blueprint-lens-grid">
        <section className="blueprint-lens data-lens">
          <h3><Database size={16} aria-hidden="true" /> Data</h3>
          <p><strong>Ground truth:</strong> {blueprint.data.targetOrGroundTruth}</p>
          <p><strong>Owner:</strong> {blueprint.data.owner}</p>
          <div className="compact-tags">{blueprint.data.sources.map((source) => <span key={source}>{source}</span>)}</div>
          <ul>{blueprint.data.preparation.map((step) => <li key={step}>{step}</li>)}</ul>
        </section>

        <section className="blueprint-lens method-lens">
          <h3><Boxes size={16} aria-hidden="true" /> Method</h3>
          <p><strong>Approach:</strong> {blueprint.method.approach}</p>
          <p><strong>Output:</strong> {blueprint.method.output}</p>
          <p><strong>Guardrail:</strong> {blueprint.method.guardrail}</p>
        </section>

        <section className="blueprint-lens human-lens">
          <h3><CircleUserRound size={16} aria-hidden="true" /> Human</h3>
          <p><strong>{blueprint.human.role}</strong></p>
          <p>{blueprint.human.checkpoint}</p>
          <p><strong>Authority:</strong> {blueprint.human.authority}</p>
          <p><strong>Escalation:</strong> {blueprint.human.escalation}</p>
        </section>
      </div>

      <section className="blueprint-metrics">
        <div className="blueprint-section-title"><Goal size={16} aria-hidden="true" /><h3>Success metrics</h3><span>Proposed PoC criteria</span></div>
        <div className="blueprint-metric-columns">
          <MetricList title="Technical" metrics={blueprint.metrics.technical} />
          <MetricList title="Business" metrics={blueprint.metrics.business} />
        </div>
      </section>

      <section className="blueprint-workflow">
        <div className="blueprint-section-title"><Workflow size={16} aria-hidden="true" /><h3>Second workflow · AI solution</h3><span>Data to monitored outcome</span></div>
        <MermaidDiagram graph={blueprint.workflow} label={`${blueprint.title} AI solution workflow`} />
      </section>

      <section className="blueprint-components">
        <div className="blueprint-section-title"><Boxes size={16} aria-hidden="true" /><h3>Proposed components</h3></div>
        <div className="blueprint-component-chain">
          {blueprint.components.map((component, index) => (
            <div key={component.id} className={`component-kind-${component.kind}`}>
              <span>{component.kind}</span>
              <strong>{component.name}</strong>
              <small>{component.responsibility}</small>
              {index < blueprint.components.length - 1 ? <ArrowRight size={14} aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
      </section>

      <div className="blueprint-bottom-grid">
        <section>
          <h3><ShieldAlert size={16} aria-hidden="true" /> Design risks</h3>
          <ul>{blueprint.risks.map((risk) => <li key={risk}>{risk}</li>)}</ul>
        </section>
        <section>
          <h3><FlaskConical size={16} aria-hidden="true" /> PoC plan</h3>
          <ol>{blueprint.pocPlan.map((step) => <li key={step}>{step}</li>)}</ol>
        </section>
      </div>
    </section>
  );
}