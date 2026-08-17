import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowLeft,
  Bot,
  Boxes,
  BriefcaseBusiness,
  Check,
  CircleUserRound,
  Database,
  Flag,
  GitBranch,
  Goal,
  Route,
  Scale,
  UsersRound,
  Workflow,
} from "lucide-react";
import type { CourseCase, CourseDecision } from "@applied-ai-studio/contracts";
import { getCourseCase } from "../api";
import BusinessWorkflowCanvas from "../components/BusinessWorkflowCanvas";
import { navigate } from "../router";

type LessonPhase = "map" | "judge" | "design";
type FlowView = "documented" | "actual";

const lessonSteps: Array<{
  id: LessonPhase;
  number: string;
  title: string;
  subtitle: string;
  icon: typeof Workflow;
}> = [
  { id: "map", number: "01", title: "Map the process", subtitle: "Find the decisions", icon: Workflow },
  { id: "judge", number: "02", title: "Judge AI fit", subtitle: "Most are not AI", icon: Scale },
  { id: "design", number: "03", title: "Design what survives", subtitle: "Data · Method · Metric · Human", icon: Goal },
];

const verdictClass = (decision: CourseDecision): string => `verdict-${decision.verdict}`;

function MapInspector({ decision }: { decision: CourseDecision }) {
  return (
    <>
      <div className="inspector-kicker">Step 1 · Business decision</div>
      <h2>{decision.label}</h2>
      <p className="inspector-lead">A decision is a choice with more than one path. Quantify it before proposing a solution.</p>
      <dl className="decision-facts">
        <div><dt>Who decides today</dt><dd>{decision.owner}</dd></div>
        <div><dt>How often</dt><dd>{decision.frequency}</dd></div>
        <div><dt>Cost of getting it wrong</dt><dd>{decision.wrongCost}</dd></div>
      </dl>
      <div className="teaching-callout">
        <GitBranch size={17} aria-hidden="true" />
        <p><strong>Hunt for the diamond.</strong> Stay at the full process level before decomposing the technical steps beneath it.</p>
      </div>
    </>
  );
}

function JudgeInspector({ decision }: { decision: CourseDecision }) {
  return (
    <>
      <div className="inspector-kicker">Step 2 · AI fit test</div>
      <h2>{decision.label}</h2>
      <span className={`decision-verdict ${verdictClass(decision)}`}>{decision.verdictLabel}</span>
      <div className="fit-test-question">
        <span>The test</span>
        <strong>Would it behave differently with another year of data?</strong>
        <p>{decision.testAnswer}</p>
      </div>
      <div className="inspector-section">
        <h3>Why</h3>
        <p>{decision.why}</p>
      </div>
      <div className="recommendation-block">
        <Check size={17} aria-hidden="true" />
        <div><span>Least expensive intervention</span><p>{decision.recommendation}</p></div>
      </div>
      {!decision.aiRelevant ? <p className="elimination-note">Ruling AI out is the finding, not a failure.</p> : null}
      {decision.placement === "process" ? <p className="placement-note">Generation is the exception: it produces an artifact inside a process box rather than resolving a diamond.</p> : null}
    </>
  );
}

function DesignInspector({ decision, courseCaseId }: { decision: CourseDecision; courseCaseId: string }) {
  if (!decision.design) {
    return (
      <>
        <div className="inspector-kicker">Step 3 · Design only what survives</div>
        <h2>{decision.label}</h2>
        <div className="no-build-panel">
          <Scale size={28} aria-hidden="true" />
          <strong>Do not build an AI model here</strong>
          <p>{decision.recommendation}</p>
        </div>
        <p className="inspector-lead">Move to another diamond and choose the least expensive intervention that resolves the problem.</p>
      </>
    );
  }

  const { data, method, metric, human, architecture } = decision.design;
  return (
    <>
      <div className="inspector-kicker">Step 3 · Data → Method → Metric → Human</div>
      <h2>{decision.label}</h2>
      <div className="design-stack">
        <section className="design-card design-data">
          <div><span>01</span><Database size={16} aria-hidden="true" /><h3>Data</h3></div>
          <p>{data.summary}</p>
          <dl><div><dt>Owner</dt><dd>{data.owner}</dd></div><div><dt>Readiness</dt><dd>{data.readiness}</dd></div></dl>
          <div className="compact-tags">{data.fields.map((field) => <span key={field}>{field}</span>)}</div>
          <small>{data.risk}</small>
        </section>
        <section className="design-card design-method">
          <div><span>02</span><Boxes size={16} aria-hidden="true" /><h3>Method</h3></div>
          <strong>{method.pattern}</strong>
          <p>{method.output}</p>
          <small>{method.technique}</small>
        </section>
        <section className="design-card design-metric">
          <div><span>03</span><Goal size={16} aria-hidden="true" /><h3>Metric</h3></div>
          <dl><div><dt>Technical</dt><dd>{metric.technical}</dd></div><div><dt>Business</dt><dd>{metric.business}</dd></div></dl>
          <small>{metric.baseline}</small>
        </section>
        <section className="design-card design-human">
          <div><span>04</span><CircleUserRound size={16} aria-hidden="true" /><h3>Human</h3></div>
          <strong>{human.role}</strong>
          <p>{human.checkpoint}</p>
          <dl><div><dt>False positive</dt><dd>{human.falsePositiveCost}</dd></div><div><dt>False negative</dt><dd>{human.falseNegativeCost}</dd></div></dl>
        </section>
      </div>
      <div className="architecture-chain" aria-label="Recommended solution components">
        {architecture.map((component, index) => (
          <div key={component}><span>{component}</span>{index < architecture.length - 1 ? <ArrowRight size={13} aria-hidden="true" /> : null}</div>
        ))}
      </div>
      <button className="secondary-button course-ask-button" type="button" onClick={() => navigate(`/ask?courseCase=${encodeURIComponent(courseCaseId)}`)}>
        <Bot size={16} aria-hidden="true" /> Ask Studio about this design
      </button>
    </>
  );
}

export default function CourseFlowPage({ courseCaseId }: { courseCaseId: string }) {
  const [courseCase, setCourseCase] = useState<CourseCase | null>(null);
  const [phase, setPhase] = useState<LessonPhase>("map");
  const [view, setView] = useState<FlowView>("actual");
  const [selectedDecisionId, setSelectedDecisionId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getCourseCase(courseCaseId)
      .then((result) => {
        setCourseCase(result);
        setSelectedDecisionId(result.featuredDecisionId);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [courseCaseId]);

  if (error) return <div className="page"><div className="error-banner">{error}</div></div>;
  if (!courseCase) return <div className="route-loading">Loading detailed workflow...</div>;

  const selectedDecision = courseCase.decisions.find((decision) => decision.id === selectedDecisionId)
    ?? courseCase.decisions[0];
  const isRetailWorkflow = courseCase.id === "retail-online-order";

  return (
    <div className="page course-flow-page">
      <button className="page-back-button" type="button" onClick={() => navigate(isRetailWorkflow ? "/showcase?industry=retail" : "/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Back to Industry Workflows
      </button>
      <header className="page-header course-header">
        <div>
          <span className="eyebrow">{courseCase.industry} · Decision workflow</span>
          <h1>{courseCase.title}</h1>
          <p>{courseCase.subtitle}</p>
        </div>
        <div className="source-badge"><Workflow size={16} aria-hidden="true" /> Detailed workflow</div>
      </header>

      <section className="workflow-introduction" aria-labelledby="workflow-context-title">
        <div className="workflow-introduction-summary">
          <div className="workflow-introduction-heading">
            <span><BriefcaseBusiness size={15} aria-hidden="true" /> Business context</span>
            <h2 id="workflow-context-title">{courseCase.introduction.title}</h2>
          </div>
          <p>{courseCase.introduction.context}</p>
        </div>
        <div className="workflow-introduction-grid">
          <div className="workflow-introduction-detail">
            <Route size={17} aria-hidden="true" />
            <div><span>Workflow in plain language</span><p>{courseCase.introduction.workflow}</p></div>
          </div>
          <div className="workflow-introduction-detail">
            <Flag size={17} aria-hidden="true" />
            <div>
              <span>Process boundary</span>
              <p><strong>Starts:</strong> {courseCase.introduction.startsWhen}</p>
              <p><strong>Ends:</strong> {courseCase.introduction.endsWhen}</p>
            </div>
          </div>
          <div className="workflow-introduction-detail">
            <UsersRound size={17} aria-hidden="true" />
            <div><span>Who is involved</span><p>{courseCase.lanes.map((lane) => lane.label).join(" · ")}</p></div>
          </div>
        </div>
      </section>

      <nav className="lesson-stepper" aria-label="Decision design method">
        {lessonSteps.map(({ id, number, title, subtitle, icon: Icon }, index) => (
          <button type="button" key={id} className={phase === id ? "active" : ""} onClick={() => setPhase(id)}>
            <span>{number}</span>
            <Icon size={19} aria-hidden="true" />
            <div><strong>{title}</strong><small>{subtitle}</small></div>
            {index < lessonSteps.length - 1 ? <ArrowRight className="step-arrow" size={16} aria-hidden="true" /> : null}
          </button>
        ))}
      </nav>

      <section className="five-stage-strip" aria-label="Five stages of a business process">
        {courseCase.stages.map((stage, index) => (
          <div key={stage.id} className={stage.id === "decision" ? "decision-stage" : ""}>
            <span>{index + 1}</span><strong>{stage.label}</strong><small>{stage.description}</small>
            {index < courseCase.stages.length - 1 ? <ArrowRight size={15} aria-hidden="true" /> : null}
          </div>
        ))}
      </section>

      <section className="retail-workbench">
        <div className="workflow-panel">
          <div className="workflow-panel-header">
            <div><span>{courseCase.industry} workflow</span><strong>{view === "documented" ? "The documented path" : "What actually happens"}</strong></div>
            <div className="segmented-control" aria-label="Workflow view">
              <button type="button" className={view === "documented" ? "active" : ""} onClick={() => setView("documented")}>Documented</button>
              <button type="button" className={view === "actual" ? "active" : ""} onClick={() => setView("actual")}>Actual + exceptions</button>
            </div>
          </div>
          <BusinessWorkflowCanvas
            courseCase={courseCase}
            view={view}
            phase={phase}
            selectedDecisionId={selectedDecision.id}
            onSelectDecision={setSelectedDecisionId}
          />
          <div className="workflow-legend">
            <span><i className="legend-process" /> Process</span>
            <span><i className="legend-decision" /> Decision diamond</span>
            <span><i className="legend-exception" /> Exception path</span>
            <strong>{courseCase.throughline}</strong>
          </div>
        </div>

        <aside className="decision-inspector" aria-live="polite">
          {phase === "map" ? <MapInspector decision={selectedDecision} /> : null}
          {phase === "judge" ? <JudgeInspector decision={selectedDecision} /> : null}
          {phase === "design" ? <DesignInspector decision={selectedDecision} courseCaseId={courseCase.id} /> : null}
        </aside>
      </section>

      <section className="decision-inventory">
        <div className="section-title-row">
          <div><span>{courseCase.decisions.length} decisions inside this workflow</span><h2>Select a diamond to inspect</h2></div>
          <small>Volumes and operating figures are synthetic assumptions.</small>
        </div>
        <div className="decision-grid">
          {courseCase.decisions.map((decision, index) => (
            <button
              type="button"
              key={decision.id}
              className={`${selectedDecision.id === decision.id ? "active" : ""} ${verdictClass(decision)}`}
              onClick={() => setSelectedDecisionId(decision.id)}
            >
              <span>{index + 1}</span>
              <div><strong>{decision.label}</strong><small>{phase === "map" ? decision.owner : decision.verdictLabel}</small></div>
            </button>
          ))}
        </div>
      </section>

      <section className="baseline-strip" aria-label={`${courseCase.title} workflow baseline`}>
        {courseCase.baseline.map((metric) => (
          <div key={metric.label}><strong>{metric.value}</strong><span>{metric.label}</span><small>{metric.note}</small></div>
        ))}
      </section>
    </div>
  );
}