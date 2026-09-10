import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Database,
  Image as ImageIcon,
  Layers3,
  ListFilter,
  Play,
  RefreshCcw,
  ScanLine,
  ShieldAlert,
  SlidersHorizontal,
  Stethoscope,
  UserCheck,
  XCircle,
} from "lucide-react";
import {
  getPneumoniaModel,
  getPneumoniaReviewQueue,
  getPneumoniaSamples,
  scorePneumoniaSample,
  type PneumoniaComparison,
  type PneumoniaModelInfo,
  type PneumoniaReviewQueue,
  type PneumoniaSample,
  type PneumoniaScore,
} from "../pneumoniaApi";
import { navigate } from "../router";

type Workspace = "workbench" | "queue" | "model";
type ImageView = "original" | "influence";

const workspaces = [
  { id: "workbench" as const, label: "Scoring workbench", detail: "Trace one packaged study", icon: SlidersHorizontal },
  { id: "queue" as const, label: "Review queue", detail: "Inspect policy and errors", icon: ListFilter },
  { id: "model" as const, label: "Model card", detail: "Review evidence and limits", icon: Layers3 },
];

const comparisonLabels: Record<PneumoniaComparison, string> = {
  true_positive: "Pneumonia label / priority review",
  false_positive: "Normal label / priority review",
  false_negative: "Pneumonia label / standard review",
  true_negative: "Normal label / standard review",
};

const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const rankingScore = (value: number, digits = 3): string => value.toFixed(digits);
const number = (value: number): string => new Intl.NumberFormat("en-US").format(value);
const routeTitle = (route: PneumoniaScore["route"]): string => {
  if (route === "priority_review") return "Priority review";
  if (route === "standard_review") return "Standard review";
  return "Quality hold";
};

export default function PneumoniaPage() {
  const [workspace, setWorkspace] = useState<Workspace>("workbench");
  const [model, setModel] = useState<PneumoniaModelInfo | null>(null);
  const [samples, setSamples] = useState<PneumoniaSample[]>([]);
  const [queue, setQueue] = useState<PneumoniaReviewQueue | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [blurRadius, setBlurRadius] = useState(0);
  const [exposureShift, setExposureShift] = useState(0);
  const [imageView, setImageView] = useState<ImageView>("original");
  const [score, setScore] = useState<PneumoniaScore | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getPneumoniaModel(), getPneumoniaSamples(), getPneumoniaReviewQueue()])
      .then(async ([modelInfo, preparedSamples, reviewQueue]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setSamples(preparedSamples);
        setQueue(reviewQueue);
        const first = preparedSamples[0];
        if (first) {
          setSelectedId(first.sample_id);
          const initial = await scorePneumoniaSample({
            sample_id: first.sample_id,
            blur_radius: 0,
            exposure_shift: 0,
          });
          if (!cancelled) setScore(initial);
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      });
    return () => { cancelled = true; };
  }, []);

  const selectedSample = samples.find((sample) => sample.sample_id === selectedId);
  const hasTransformation = blurRadius !== 0 || exposureShift !== 0;
  const shownImage = imageView === "influence" && score?.overlay_data_uri
    ? score.overlay_data_uri
    : score?.image_data_uri ?? selectedSample?.image_data_uri;
  const shownImageAlt = score?.transformed
    ? `Controlled what-if version of packaged test image ${score.sample_id}; no historical outcome applies.`
    : `Packaged pediatric chest X-ray ${selectedSample?.sample_id ?? ""}, source dataset label ${selectedSample?.dataset_label ?? "not loaded"}.`;

  const chooseSample = (sample: PneumoniaSample) => {
    setSelectedId(sample.sample_id);
    setBlurRadius(0);
    setExposureShift(0);
    setImageView("original");
    setScore(null);
    setError(null);
  };

  const runScore = async () => {
    if (!selectedId) return;
    setRunning(true);
    setError(null);
    setImageView("original");
    try {
      const result = await scorePneumoniaSample({
        sample_id: selectedId,
        blur_radius: blurRadius,
        exposure_shift: exposureShift,
      });
      setScore(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The model could not score this study.");
    } finally {
      setRunning(false);
    }
  };

  const resetTransformation = () => {
    setBlurRadius(0);
    setExposureShift(0);
    setImageView("original");
    setScore(null);
  };

  return (
    <div className="page pneumonia-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=healthcare")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="pneumonia-header">
        <div>
          <span className="eyebrow">Image classification - bounded human review</span>
          <h1>Pediatric Chest X-ray Prioritization</h1>
          <p>Follow one packaged benchmark image from technical quality through model score, policy cutoff, queue position, and qualified interpretation.</p>
        </div>
        <div className="pneumonia-runtime-status">
          <span className={model ? "ready" : ""} />
          <div>
            <strong>{model ? "Teaching model ready" : "Connecting"}</strong>
            <small>FastAPI - PyTorch - packaged samples only</small>
          </div>
        </div>
      </header>

      <div className="pneumonia-safety-line" role="note">
        <ShieldAlert size={17} aria-hidden="true" />
        <strong>Educational demonstration</strong>
        <span>No uploads, diagnosis, clearance, or treatment recommendations. Every study still requires qualified interpretation.</span>
      </div>

      {model ? (
        <section className="pneumonia-metric-strip" aria-label="Untouched test results">
          <div><strong>{percent(model.metrics.sensitivity)}</strong><span>pneumonia labels prioritized</span><small>Sensitivity on 624 test images</small></div>
          <div><strong>{percent(model.metrics.specificity)}</strong><span>normal labels kept standard</span><small>Specificity on untouched test data</small></div>
          <div><strong>{percent(model.metrics.priority_review_rate)}</strong><span>priority queue share</span><small>{model.metrics.true_positives + model.metrics.false_positives} of 624 studies</small></div>
          <div><strong>{model.threshold.toFixed(3)}</strong><span>policy cutoff</span><small>Selected on validation, not test</small></div>
        </section>
      ) : null}

      <nav className="pneumonia-workspace-switcher" aria-label="Chest X-ray prioritization views">
        {workspaces.map(({ id, label, detail, icon: Icon }) => (
          <button
            type="button"
            className={workspace === id ? "active" : ""}
            aria-label={`${label}: ${detail}`}
            aria-pressed={workspace === id}
            key={id}
            onClick={() => setWorkspace(id)}
          >
            <Icon size={18} aria-hidden="true" />
            <div><strong>{label}</strong><small>{detail}</small></div>
          </button>
        ))}
      </nav>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {!model && !error ? <div className="loading-state">Loading model and packaged test studies...</div> : null}

      {workspace === "workbench" && model ? (
        <section className="pneumonia-workbench">
          <aside className="pneumonia-sample-browser">
            <header><span>Packaged examples</span><strong>Choose a held-out study</strong><small>Retrospective test data</small></header>
            <div className="pneumonia-sample-list">
              {samples.map((sample) => (
                <button
                  type="button"
                  className={selectedId === sample.sample_id ? "active" : ""}
                  aria-pressed={selectedId === sample.sample_id}
                  key={sample.sample_id}
                  onClick={() => chooseSample(sample)}
                >
                  <img src={sample.image_data_uri} alt="" />
                  <div>
                    <span>{sample.sample_id}</span>
                    <strong>{sample.scenario_label}</strong>
                    <small>Score {sample.model_score.toFixed(3)}</small>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className="pneumonia-image-panel">
            <header>
              <div><span>Image and quality</span><strong>Inspect a bounded scenario</strong><small>128 x 128 grayscale benchmark input</small></div>
              <div className="pneumonia-image-toggle" aria-label="Image view">
                <button type="button" className={imageView === "original" ? "active" : ""} aria-pressed={imageView === "original"} onClick={() => setImageView("original")}>
                  <ImageIcon size={15} aria-hidden="true" /> Original
                </button>
                <button type="button" className={imageView === "influence" ? "active" : ""} aria-pressed={imageView === "influence"} disabled={!score?.overlay_data_uri} onClick={() => setImageView("influence")}>
                  <ScanLine size={15} aria-hidden="true" /> Influence
                </button>
              </div>
            </header>

            <figure className="pneumonia-image-stage">
              {shownImage ? <img src={shownImage} alt={shownImageAlt} /> : <div className="pneumonia-image-loading">Select and score a packaged study.</div>}
              <figcaption>
                <span>{imageView === "influence" ? "Model-influence overlay" : score?.transformed ? "Controlled what-if image" : "Source benchmark image"}</span>
                <strong>{selectedId}</strong>
              </figcaption>
            </figure>

            <div className="pneumonia-provenance-row">
              <div><span>Dataset</span><strong>PneumoniaMNIST 128</strong><small>CC BY 4.0</small></div>
              <div><span>Historical label</span><strong>{hasTransformation ? "Not applicable" : selectedSample?.dataset_label}</strong><small>{hasTransformation ? "Pixels changed" : "Visible only in retrospective data"}</small></div>
              <div><span>Population</span><strong>Pediatric</strong><small>Limited source setting</small></div>
            </div>

            <div className="pneumonia-transform-controls">
              <label>
                <span><b>Blur radius</b><output>{blurRadius.toFixed(0)}</output></span>
                <input type="range" min="0" max="12" step="1" value={blurRadius} onChange={(event) => { setBlurRadius(Number(event.target.value)); setScore(null); }} />
                <small>0 original - 12 severe</small>
              </label>
              <label>
                <span><b>Exposure shift</b><output>{exposureShift > 0 ? `+${exposureShift}` : exposureShift}</output></span>
                <input type="range" min="-100" max="100" step="10" value={exposureShift} onChange={(event) => { setExposureShift(Number(event.target.value)); setScore(null); }} />
                <small>-100 dark - 0 original - +100 bright</small>
              </label>
            </div>

            <footer className="pneumonia-image-actions">
              <div>
                <button className="secondary-button" type="button" onClick={resetTransformation} disabled={!hasTransformation}>
                  <RefreshCcw size={15} aria-hidden="true" /> Reset
                </button>
                <button className="primary-button compact" type="button" onClick={runScore} disabled={running || !selectedId}>
                  <Play size={15} fill="currentColor" aria-hidden="true" /> {running ? "Running..." : "Run workflow"}
                </button>
              </div>
              <p>Changing pixels creates a what-if image with no known outcome.</p>
            </footer>
          </section>

          <section className="pneumonia-result-panel" aria-live="polite">
            <header><div><span>Workflow result</span><strong>Score, policy, and authority</strong><small>Do not collapse these into diagnosis</small></div><BrainCircuit size={20} aria-hidden="true" /></header>
            {score ? (
              <>
                <div className={`pneumonia-route-summary ${score.route}`}>
                  {score.route === "quality_hold" ? <AlertTriangle size={28} aria-hidden="true" /> : score.route === "priority_review" ? <ShieldAlert size={28} aria-hidden="true" /> : <CheckCircle2 size={28} aria-hidden="true" />}
                  <div><span>Workflow route</span><strong>{routeTitle(score.route)}</strong><small>{score.route_label}</small></div>
                  <div><span>Model ranking score</span><strong>{score.model_score === null ? "Held" : rankingScore(score.model_score, 7)}</strong><small>Cutoff {rankingScore(score.threshold)}</small></div>
                </div>

                <div className={`pneumonia-quality-band ${score.quality.status}`}>
                  <Activity size={18} aria-hidden="true" />
                  <div><span>Technical quality</span><strong>{score.quality.status === "sufficient" ? "Within classroom bounds" : "Outside classroom bounds"}</strong><small>Mean {score.quality.mean_intensity.toFixed(3)} - focus {score.quality.focus_score.toFixed(3)}</small></div>
                </div>

                {score.model_score !== null ? (
                  <div className="pneumonia-score-axis" aria-label={`Model ranking score ${rankingScore(score.model_score, 7)}; policy cutoff ${rankingScore(score.threshold)}`}>
                    <div className="pneumonia-score-track">
                      <span className="pneumonia-cutoff-marker" style={{ left: `${score.threshold * 100}%` }}><b>Cutoff</b></span>
                      <span className="pneumonia-score-marker" style={{ left: `${Math.min(score.model_score, 0.995) * 100}%` }}><b>Score</b></span>
                    </div>
                    <div><span>Lower model score</span><span>Higher model score</span></div>
                  </div>
                ) : (
                  <div className="pneumonia-quality-reasons">
                    {score.quality.reasons.map((reason) => <p key={reason}>{reason}</p>)}
                    <strong>Ordinary model routing stopped before a score was used.</strong>
                  </div>
                )}

                <div className="pneumonia-decision-chain">
                  <div><Activity size={16} aria-hidden="true" /><span>Quality gate</span><strong>{score.quality.status}</strong></div>
                  <ArrowRight size={16} aria-hidden="true" />
                  <div><BrainCircuit size={16} aria-hidden="true" /><span>Ranking score</span><strong>{score.model_score === null ? "Not used" : rankingScore(score.model_score, 7)}</strong></div>
                  <ArrowRight size={16} aria-hidden="true" />
                  <div><ClipboardList size={16} aria-hidden="true" /><span>Queue action</span><strong>{routeTitle(score.route)}</strong></div>
                </div>

                <div className="pneumonia-label-band">
                  {score.dataset_label ? <CheckCircle2 size={18} aria-hidden="true" /> : <XCircle size={18} aria-hidden="true" />}
                  <div><span>{score.dataset_label ? "Retrospective comparison" : "What-if scenario"}</span><strong>{score.dataset_label ?? "No known outcome"}</strong><small>{score.label_note}</small></div>
                </div>

                {score.influence_note ? (
                  <div className="pneumonia-influence-note"><ScanLine size={18} aria-hidden="true" /><p>{score.influence_note}</p></div>
                ) : null}

                <div className="pneumonia-human-boundary">
                  <UserCheck size={19} aria-hidden="true" />
                  <div><span>Human authority</span><p>The model may change queue position. A radiologist interprets the image; a clinician diagnoses and decides treatment using the whole patient context.</p></div>
                </div>
              </>
            ) : (
              <div className="pneumonia-result-empty">
                <BrainCircuit size={30} aria-hidden="true" />
                <strong>{hasTransformation ? "Pixels changed" : "Study selected"}</strong>
                <p>Run the workflow to apply the technical gate, model, and queue policy.</p>
              </div>
            )}
          </section>
        </section>
      ) : null}

      {workspace === "queue" && model && queue ? (
        <section className="pneumonia-queue-workspace">
          <header className="pneumonia-section-heading">
            <div><span>Retrospective operating view</span><h2>One score becomes two review queues</h2><p>The cutoff was selected on validation data. These are ranking scores, not probabilities. Seven decimals keep the highest-scoring studies in their true order instead of rounding them all to 100%.</p></div>
            <strong><ClipboardList size={15} aria-hidden="true" /> {queue.summary.heldout_studies} test studies</strong>
          </header>
          <div className="pneumonia-queue-summary">
            <div><span>Priority review</span><strong>{number(queue.summary.priority_review)}</strong><small>{percent(queue.summary.priority_review_rate)} of the test queue</small></div>
            <div><span>Standard review</span><strong>{number(queue.summary.standard_review)}</strong><small>Still receives qualified interpretation</small></div>
            <div><span>Pneumonia labels prioritized</span><strong>{number(queue.summary.pneumonia_labeled_in_priority)}</strong><small>True positives</small></div>
            <div><span>Normal labels prioritized</span><strong>{number(queue.summary.normal_labeled_in_priority)}</strong><small>False positives and added workload</small></div>
          </div>
          <div className="pneumonia-retrospective-note"><Database size={17} aria-hidden="true" /><p>{queue.retrospective_note}</p></div>
          <div className="pneumonia-queue-table-wrap">
            <table className="pneumonia-queue-table">
              <caption className="sr-only">Highest-scoring studies routed to priority review</caption>
              <thead><tr><th>Study</th><th>Ranking score</th><th>Policy cutoff</th><th>Queue route</th><th>Dataset label</th><th>Retrospective comparison</th></tr></thead>
              <tbody>{queue.items.map((item, index) => (
                <tr key={item.sample_id}>
                  <td><strong>{item.sample_id}</strong><span>Packaged test image</span></td>
                  <td><div className="pneumonia-table-score"><strong>{rankingScore(item.model_score, 7)}</strong><small>Rank {index + 1}</small></div></td>
                  <td>{item.model_score >= queue.summary.threshold ? ">= " : "< "}{queue.summary.threshold.toFixed(3)}</td>
                  <td><span className={`pneumonia-route-pill ${item.route}`}>{item.route_label}</span></td>
                  <td>{item.dataset_label}</td>
                  <td>{comparisonLabels[item.comparison]}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <section className="pneumonia-error-review">
            <header><div><span>Error review</span><h3>The cases a headline metric hides</h3></div><p>Examples nearest the cutoff. Standard review never means cleared.</p></header>
            <div>{queue.teaching_cases.map((item) => (
              <article key={item.sample_id} className={item.comparison}>
                {item.comparison === "false_negative" ? <AlertTriangle size={19} aria-hidden="true" /> : <ClipboardList size={19} aria-hidden="true" />}
                <div><span>{item.sample_id}</span><strong>{comparisonLabels[item.comparison]}</strong><small>Score {item.model_score.toFixed(3)} - cutoff {queue.summary.threshold.toFixed(3)}</small></div>
              </article>
            ))}</div>
          </section>
        </section>
      ) : null}

      {workspace === "model" && model ? (
        <section className="pneumonia-model-workspace">
          <header className="pneumonia-section-heading">
            <div><span>Deployment record</span><h2>{model.model_name}</h2><p>{model.score_note}</p></div>
            <strong><Database size={15} aria-hidden="true" /> Notebook artifacts loaded</strong>
          </header>
          <div className="pneumonia-model-facts">
            <div><BrainCircuit size={19} aria-hidden="true" /><span>Architecture</span><strong>{model.architecture}</strong><small>{number(model.trainable_parameters)} trainable parameters</small></div>
            <div><ImageIcon size={19} aria-hidden="true" /><span>Model input</span><strong>{model.input_shape.join(" x ")} grayscale</strong><small>Pixels only, not the patient record</small></div>
            <div><BarChart3 size={19} aria-hidden="true" /><span>Operating policy</span><strong>score &gt;= {model.threshold.toFixed(3)}</strong><small>Targeted {percent(model.target_validation_sensitivity, 0)} validation sensitivity</small></div>
            <div><Database size={19} aria-hidden="true" /><span>Source data</span><strong>{model.dataset.name}</strong><small>{model.dataset.license} - checksum verified</small></div>
          </div>
          <section className="pneumonia-confusion-section">
            <header><span>Untouched test evaluation</span><h3>Every metric comes from the same 2 x 2 table</h3></header>
            <div className="pneumonia-confusion-layout">
              <table className="pneumonia-confusion-table">
                <thead><tr><th>Dataset label</th><th>Standard review</th><th>Priority review</th></tr></thead>
                <tbody>
                  <tr><th>Normal</th><td><strong>{model.metrics.true_negatives}</strong><span>True negatives</span></td><td><strong>{model.metrics.false_positives}</strong><span>False positives</span></td></tr>
                  <tr><th>Pneumonia</th><td><strong>{model.metrics.false_negatives}</strong><span>False negatives</span></td><td><strong>{model.metrics.true_positives}</strong><span>True positives</span></td></tr>
                </tbody>
              </table>
              <div className="pneumonia-evaluation-metrics">
                <div><span>Sensitivity</span><strong>{percent(model.metrics.sensitivity)}</strong></div>
                <div><span>Specificity</span><strong>{percent(model.metrics.specificity)}</strong></div>
                <div><span>Precision</span><strong>{percent(model.metrics.precision)}</strong></div>
                <div><span>ROC AUC</span><strong>{model.metrics.roc_auc.toFixed(3)}</strong></div>
              </div>
            </div>
          </section>
          <section className="pneumonia-robustness-section">
            <header><span>Controlled robustness checks</span><h3>Quality routing sits in front of ordinary score routing</h3></header>
            <div className="pneumonia-robustness-grid">
              {model.robustness.map((row) => (
                <div key={String(row.scenario)}>
                  <strong>{row.scenario}</strong>
                  <span>Quality pass <b>{percent(Number(row.quality_pass_rate))}</b></span>
                  <i><b style={{ width: percent(Number(row.quality_pass_rate)) }} /></i>
                  <small>Sensitivity {percent(Number(row.sensitivity))} - specificity {percent(Number(row.specificity))}</small>
                </div>
              ))}
            </div>
          </section>
          <section className="pneumonia-model-boundaries">
            <div>
              <span>Intended use</span>
              <h3>{model.intended_use}</h3>
              <p>{model.dataset.population}. The source study reports patient separation between training and test data.</p>
              <code>Archive MD5 {model.dataset.archive_md5}</code>
            </div>
            <div>
              <span>Known limitations</span>
              <ul>{model.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
            <div>
              <span>Excluded uses</span>
              <ul>{model.excluded_uses.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </section>
          <div className="pneumonia-authority-chain">
            <div><BrainCircuit size={17} aria-hidden="true" /><span>Model</span><strong>Estimate</strong></div><ArrowRight size={16} aria-hidden="true" />
            <div><ClipboardList size={17} aria-hidden="true" /><span>Policy</span><strong>Queue position</strong></div><ArrowRight size={16} aria-hidden="true" />
            <div><Stethoscope size={17} aria-hidden="true" /><span>Radiologist</span><strong>Interpret image</strong></div><ArrowRight size={16} aria-hidden="true" />
            <div><UserCheck size={17} aria-hidden="true" /><span>Clinician</span><strong>Diagnose and treat</strong></div>
          </div>
        </section>
      ) : null}
    </div>
  );
}