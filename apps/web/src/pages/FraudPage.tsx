import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Database,
  GitBranch,
  Info,
  Layers3,
  ListFilter,
  Play,
  Scale,
  ShieldAlert,
  SlidersHorizontal,
  UserCheck,
  XCircle,
} from "lucide-react";
import {
  getFraudModel,
  getFraudReviewQueue,
  getFraudSamples,
  scoreFraudTransaction,
  type FraudModelInfo,
  type FraudReviewQueue,
  type FraudSample,
  type FraudScore,
  type FraudTransactionInput,
} from "../fraudApi";
import { navigate } from "../router";

type Workspace = "simulator" | "queue" | "model";
type NumericField = Exclude<{
  [Key in keyof FraudTransactionInput]: FraudTransactionInput[Key] extends number ? Key : never;
}[keyof FraudTransactionInput], undefined>;

const workspaces = [
  { id: "simulator" as const, label: "Scoring workbench", detail: "Score one transaction", icon: SlidersHorizontal },
  { id: "queue" as const, label: "Review queue", detail: "See the operating policy", icon: ListFilter },
  { id: "model" as const, label: "Model card", detail: "Inspect lineage and metrics", icon: Layers3 },
];

const numericFields: Array<{
  key: NumericField;
  label: string;
  step: string;
  hint: string;
}> = [
  { key: "amount", label: "Amount", step: "0.01", hint: "USD" },
  { key: "card_transactions_1h", label: "Earlier transactions in 1 hour", step: "1", hint: "count" },
  { key: "card_transactions_24h", label: "Earlier transactions in 24 hours", step: "1", hint: "count" },
  { key: "minutes_since_previous", label: "Minutes since previous", step: "0.1", hint: "minutes" },
  { key: "distance_from_home_km", label: "Distance from home", step: "0.1", hint: "km" },
  { key: "customer_age", label: "Customer age", step: "0.1", hint: "years" },
  { key: "city_population", label: "Home-city population", step: "1", hint: "people" },
];

const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const displayedModelScore = (value: number): number => Math.min(value, 0.999);
const modelScorePercent = (value: number): string => percent(displayedModelScore(value));
const scorePoints = (value: number): string =>
  `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} pts`;
const multiple = (value: number): string =>
  `${value < 0.1 ? value.toFixed(2) : value.toFixed(1)}x`;
const contributionEffect = (value: number): string =>
  `${Math.abs(value * 100).toFixed(1)} points ${value >= 0 ? "toward" : "away from"} review`;
const inferredCardAverage = (transaction: FraudTransactionInput): number => {
  const average = transaction.amount_ratio_to_card_mean > 0
    ? transaction.amount / transaction.amount_ratio_to_card_mean
    : Math.max(transaction.amount, 1);
  return Math.round(average * 100) / 100;
};
const money = (value: number): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
const integer = (value: number): string => new Intl.NumberFormat("en-US").format(value);
const shortDate = (value: string): string =>
  new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));

function outcomeComparison(score: FraudScore, sample: FraudSample | undefined, edited: boolean) {
  if (!sample || edited) return null;
  const fraud = sample.known_outcome === "Fraud";
  if (score.decision === "review" && fraud) return { label: "Fraud caught", className: "correct", icon: CheckCircle2 };
  if (score.decision === "review") return { label: "False positive", className: "incorrect", icon: XCircle };
  if (fraud) return { label: "Fraud missed", className: "incorrect", icon: XCircle };
  return { label: "Correct normal decision", className: "correct", icon: CheckCircle2 };
}

export default function FraudPage() {
  const [workspace, setWorkspace] = useState<Workspace>("simulator");
  const [model, setModel] = useState<FraudModelInfo | null>(null);
  const [samples, setSamples] = useState<FraudSample[]>([]);
  const [queue, setQueue] = useState<FraudReviewQueue | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<FraudTransactionInput | null>(null);
  const [cardAverage, setCardAverage] = useState(1);
  const [score, setScore] = useState<FraudScore | null>(null);
  const [referenceScore, setReferenceScore] = useState<FraudScore | null>(null);
  const [edited, setEdited] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getFraudModel(), getFraudSamples(), getFraudReviewQueue()])
      .then(async ([modelInfo, preparedSamples, reviewQueue]) => {
        if (cancelled) return;
        const first = preparedSamples[0];
        setModel(modelInfo);
        setSamples(preparedSamples);
        setQueue(reviewQueue);
        if (first) {
          setSelectedId(first.scenario_id);
          setDraft(first.transaction);
          setCardAverage(inferredCardAverage(first.transaction));
          const initialScore = await scoreFraudTransaction(first.transaction);
          if (!cancelled) {
            setScore(initialScore);
            setReferenceScore(initialScore);
          }
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      });
    return () => { cancelled = true; };
  }, []);

  const selectedSample = samples.find((sample) => sample.scenario_id === selectedId);
  const comparison = score ? outcomeComparison(score, selectedSample, edited) : null;
  const topContribution = score?.explanation.contributions[0];
  const VerdictIcon = score?.decision === "review" ? ShieldAlert : CheckCircle2;
  const canScore = Number.isFinite(cardAverage) && cardAverage > 0;
  const whatIfComparison = score && referenceScore && selectedSample && draft && edited
    ? {
      sample: selectedSample,
      referenceScore,
        decisionChanged: score.decision !== referenceScore.decision,
        largestShift: score.explanation.contributions
          .map((current) => {
            const reference = referenceScore.explanation.contributions.find(
              (item) => item.feature === current.feature,
            );
            return {
              label: current.label,
              current: current.contribution,
              reference: reference?.contribution ?? 0,
              shift: current.contribution - (reference?.contribution ?? 0),
            };
          })
          .sort((left, right) => Math.abs(right.shift) - Math.abs(left.shift))[0],
      }
    : null;

  const chooseSample = (sample: FraudSample) => {
    setSelectedId(sample.scenario_id);
    setDraft({ ...sample.transaction });
    setCardAverage(inferredCardAverage(sample.transaction));
    setScore(null);
    setReferenceScore(null);
    setEdited(false);
    setError(null);
  };

  const updateNumber = (key: NumericField, value: string) => {
    if (!draft) return;
    const numericValue = key === "card_transactions_1h" || key === "card_transactions_24h"
      ? Math.max(0, Math.round(Number(value)))
      : Number(value);
    const nextDraft: FraudTransactionInput = { ...draft, [key]: numericValue };
    if (key === "amount") {
      nextDraft.amount_ratio_to_card_mean = cardAverage > 0 ? numericValue / cardAverage : 0;
    }
    if (key === "card_transactions_1h" && numericValue > nextDraft.card_transactions_24h) {
      nextDraft.card_transactions_24h = numericValue;
    }
    if (key === "card_transactions_24h" && numericValue < nextDraft.card_transactions_1h) {
      nextDraft.card_transactions_1h = numericValue;
    }
    setDraft(nextDraft);
    setScore(null);
    setEdited(true);
  };

  const updateCardAverage = (value: string) => {
    if (!draft) return;
    const average = Number(value);
    setCardAverage(average);
    setDraft({
      ...draft,
      amount_ratio_to_card_mean: average > 0 ? draft.amount / average : 0,
    });
    setScore(null);
    setEdited(true);
  };

  const runScore = async () => {
    if (!draft) return;
    setRunning(true);
    setError(null);
    try {
      const [nextScore, fetchedReference] = await Promise.all([
        scoreFraudTransaction(draft),
        selectedSample && edited && !referenceScore
          ? scoreFraudTransaction(selectedSample.transaction)
          : Promise.resolve(referenceScore),
      ]);
      setScore(nextScore);
      setReferenceScore(edited ? fetchedReference : nextScore);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The model could not score this transaction.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page fraud-page">
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="fraud-header">
        <div>
          <span className="eyebrow">Classification · Human review</span>
          <h1>Card Transaction Fraud Detection</h1>
          <p>Change a held-out transaction, run the deployed model, and trace how a score becomes a review decision.</p>
        </div>
        <div className="fraud-runtime-status">
          <span className={model ? "ready" : ""} />
          <div><strong>{model ? "Live model ready" : "Connecting"}</strong><small>FastAPI · MLflow pyfunc · skops</small></div>
        </div>
      </header>

      {model ? (
        <section className="fraud-metric-strip" aria-label="Held-out model results">
          <div><strong>{percent(model.metrics.recall)}</strong><span>fraud caught</span><small>Recall on held-out data</small></div>
          <div><strong>{percent(model.metrics.precision)}</strong><span>alerts that were fraud</span><small>Precision in the review queue</small></div>
          <div><strong>{percent(model.review_budget, 0)}</strong><span>review budget</span><small>Share sent to analysts</small></div>
          <div><strong>{percent(model.threshold)}</strong><span>policy cutoff</span><small>Score required for review</small></div>
        </section>
      ) : null}

      <nav className="fraud-workspace-switcher" aria-label="Fraud detection views">
        {workspaces.map(({ id, label, detail, icon: Icon }) => (
          <button type="button" className={workspace === id ? "active" : ""} aria-label={`${label}: ${detail}`} aria-pressed={workspace === id} key={id} onClick={() => setWorkspace(id)}>
            <Icon size={18} aria-hidden="true" />
            <div><strong>{label}</strong><small>{detail}</small></div>
          </button>
        ))}
      </nav>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {!model && !error ? <div className="loading-state">Loading model and held-out transactions...</div> : null}

      {workspace === "simulator" && model && draft ? (
        <section className="fraud-simulator">
          <aside className="fraud-sample-browser">
            <header><span>Step 1</span><strong>Choose a known example</strong><small>Held-out test data</small></header>
            <div className="fraud-sample-list">
              {samples.map((sample) => (
                <button
                  type="button"
                  className={selectedId === sample.scenario_id ? "active" : ""}
                  aria-pressed={selectedId === sample.scenario_id}
                  key={sample.scenario_id}
                  onClick={() => chooseSample(sample)}
                >
                  <span>{sample.scenario_label}</span>
                  <strong>{sample.merchant}</strong>
                  <small>{money(sample.transaction.amount)} · {sample.transaction.category.replaceAll("_", " ")}</small>
                </button>
              ))}
            </div>
          </aside>

          <section className="fraud-input-panel">
            <header>
              <div><span>Step 2</span><strong>Inspect or change the inputs</strong><small>Only information available when the purchase happened</small></div>
              <Database size={19} aria-hidden="true" />
            </header>
            {selectedSample ? (
              <div className="fraud-transaction-identity">
                <div><span>Merchant</span><strong>{selectedSample.merchant}</strong></div>
                <div><span>Location</span><strong>{selectedSample.location}</strong></div>
                <div><span>Card</span><strong>•••• {selectedSample.card_last4}</strong></div>
              </div>
            ) : null}
            <div className="fraud-input-grid">
              <label className="wide"><span>Purchase date and time</span><input type="datetime-local" value={draft.occurred_at.slice(0, 16)} onChange={(event) => { setDraft({ ...draft, occurred_at: `${event.target.value}:00` }); setScore(null); setEdited(true); }} /></label>
              <label className="wide"><span>Merchant category</span><select value={draft.category} onChange={(event) => { setDraft({ ...draft, category: event.target.value }); setScore(null); setEdited(true); }}>{model.categories.map((category) => <option value={category} key={category}>{category.replaceAll("_", " ")}</option>)}</select></label>
              <label className="fraud-derived-input">
                <span>Card's earlier average purchase</span>
                <div><input type="number" min="0.01" step="0.01" value={cardAverage} aria-invalid={!canScore} aria-describedby="fraud-card-average-help" onChange={(event) => updateCardAverage(event.target.value)} /><small>USD</small></div>
                <em id="fraud-card-average-help">{canScore ? `Model input: ${multiple(draft.amount_ratio_to_card_mean)} usual` : "Enter an average above $0 to score."}</em>
              </label>
              {numericFields.map((field) => (
                <label key={field.key}>
                  <span>{field.label}</span>
                  <div><input type="number" min="0" step={field.step} value={draft[field.key]} onChange={(event) => updateNumber(field.key, event.target.value)} /><small>{field.hint}</small></div>
                </label>
              ))}
            </div>
            <footer>
              <div><Info size={15} aria-hidden="true" /><span>Changing an input creates a what-if scenario; the historical outcome no longer applies.</span></div>
              <button className="primary-button" type="button" onClick={runScore} disabled={running || !canScore}>
                <Play size={15} fill="currentColor" aria-hidden="true" /> {running ? "Scoring..." : "Run model"}
              </button>
            </footer>
          </section>

          <section className="fraud-result-panel" aria-live="polite">
            <header><div><span>Step 3</span><strong>Interpret the result</strong><small>Estimate, policy, then human judgment</small></div><BrainCircuit size={19} aria-hidden="true" /></header>
            {score ? (
              <>
                <div className={`fraud-score-summary ${score.decision}`}>
                  <div className="fraud-score-verdict"><span>Model verdict</span><strong>{score.decision === "review" ? "Fraud suspected" : "Not flagged"}</strong><small>{score.decision_label} · not a confirmed outcome</small></div>
                  <div className="fraud-score-value"><span>Ranking score</span><strong>{modelScorePercent(score.fraud_score)}</strong><small>{score.model_name} · uncalibrated</small></div>
                  <VerdictIcon size={28} aria-hidden="true" />
                </div>
                <div className="fraud-risk-axis" aria-label={`Model score ${modelScorePercent(score.fraud_score)}; review cutoff ${percent(score.threshold)}`}>
                  <div className="fraud-risk-track">
                    <span className="fraud-threshold-marker" style={{ left: `${score.threshold * 100}%` }}><b>Cutoff</b></span>
                    <span className="fraud-score-marker" style={{ left: `${displayedModelScore(score.fraud_score) * 100}%` }}><b>Score</b></span>
                  </div>
                  <div><span>Lower score</span><span>Higher score</span></div>
                </div>
                <div className="fraud-decision-chain">
                  <div><BrainCircuit size={16} aria-hidden="true" /><span>Model estimate</span><strong>{modelScorePercent(score.fraud_score)}</strong></div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div><Scale size={16} aria-hidden="true" /><span>Policy test</span><strong>{score.fraud_score >= score.threshold ? "At or above cutoff" : "Below cutoff"}</strong></div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div className={score.decision}><GitBranch size={16} aria-hidden="true" /><span>Workflow action</span><strong>{score.decision_label}</strong></div>
                </div>
                {comparison ? (
                  <div className={`fraud-known-outcome ${comparison.className}`}>
                    <comparison.icon size={18} aria-hidden="true" />
                    <div><span>Compared with the known outcome</span><strong>{comparison.label}</strong><small>Historical label: {selectedSample?.known_outcome}</small></div>
                  </div>
                ) : edited ? <div className="fraud-known-outcome neutral"><Info size={18} aria-hidden="true" /><div><span>What-if scenario</span><strong>No known outcome</strong><small>You changed the historical transaction.</small></div></div> : null}
                {whatIfComparison ? (
                  <section className="fraud-what-if-explanation" aria-label="Historical and what-if comparison">
                    <header>
                      <GitBranch size={17} aria-hidden="true" />
                      <div><span>Business explanation</span><strong>{whatIfComparison.decisionChanged ? "Why the routing decision changed" : "Why the score moved"}</strong></div>
                    </header>
                    <div className="fraud-score-comparison">
                      <div><span>Historical transaction</span><strong>{money(whatIfComparison.sample.transaction.amount)} · {modelScorePercent(whatIfComparison.referenceScore.fraud_score)}</strong><small>Known label: {whatIfComparison.sample.known_outcome} · {whatIfComparison.referenceScore.decision_label}</small></div>
                      <ArrowRight size={16} aria-hidden="true" />
                      <div><span>What-if transaction</span><strong>{money(draft.amount)} · {modelScorePercent(score.fraud_score)}</strong><small>No outcome label · {score.decision_label}</small></div>
                    </div>
                    {draft.amount !== whatIfComparison.sample.transaction.amount ? (
                      <p>The original purchase was <strong>{multiple(whatIfComparison.sample.transaction.amount_ratio_to_card_mean)} the card's earlier average of {money(inferredCardAverage(whatIfComparison.sample.transaction))}</strong>. The what-if is <strong>{multiple(draft.amount_ratio_to_card_mean)} the entered average of {money(cardAverage)}</strong>.</p>
                    ) : null}
                    {whatIfComparison.largestShift ? (
                      <p><strong>{whatIfComparison.largestShift.label}</strong> changed most in this model: from {contributionEffect(whatIfComparison.largestShift.reference)} to {contributionEffect(whatIfComparison.largestShift.current)}.</p>
                    ) : null}
                    <footer>{score.decision === "normal" ? `Below the ${percent(score.threshold)} cutoff means "not flagged at this review budget," not "not fraud."` : "Above the cutoff means route to an analyst, not confirmed fraud."}</footer>
                  </section>
                ) : null}
                {topContribution ? (
                  <section className="fraud-local-explanation" aria-label="Local model explanation">
                    <header>
                      <div><span>Local explanation · {score.explanation.method}</span><strong>Strongest driver: {topContribution.label}</strong><small>{topContribution.value} moved the score {Math.abs(topContribution.contribution * 100).toFixed(1)} points {topContribution.direction === "toward_review" ? "toward review" : "away from review"}.</small></div>
                      <BrainCircuit size={18} aria-hidden="true" />
                    </header>
                    <div className="fraud-contribution-legend"><span className="away">Away from review</span><span className="toward">Toward review</span></div>
                    <div className="fraud-contribution-list">
                      {score.explanation.contributions.slice(0, 5).map((item) => {
                        const strongestMagnitude = Math.max(Math.abs(topContribution.contribution), Number.EPSILON);
                        const width = Math.max(2, Math.abs(item.contribution) / strongestMagnitude * 50);
                        return (
                          <div className="fraud-contribution-row" key={item.feature}>
                            <div><strong>{item.label}</strong><small>{item.value}</small><b>{scorePoints(item.contribution)}</b></div>
                            <div className="fraud-contribution-track" aria-hidden="true"><i className={item.direction} style={{ width: `${width}%` }} /></div>
                          </div>
                        );
                      })}
                    </div>
                    <footer>Contributions add to the raw score from a {percent(score.explanation.baseline_score)} internal baseline. Tree models are nonlinear, so a larger input does not always raise the score. These values explain this prediction, not what caused fraud.</footer>
                  </section>
                ) : null}
                <div className="fraud-human-boundary"><UserCheck size={18} aria-hidden="true" /><div><span>Human authority</span><p>The model prioritizes review. An analyst investigates evidence and decides whether fraud occurred.</p></div></div>
              </>
            ) : (
              <div className="fraud-result-empty"><BrainCircuit size={30} aria-hidden="true" /><strong>Inputs changed</strong><p>Run the model to calculate a fresh score and decision.</p></div>
            )}
          </section>
        </section>
      ) : null}

      {workspace === "queue" && model && queue ? (
        <section className="fraud-queue-workspace">
          <header className="fraud-section-heading">
            <div><span>Operating view</span><h2>Transactions routed to human review</h2><p>The cutoff spends a fixed 3% review budget. Highest scores appear first.</p></div>
            <strong>{integer(queue.summary.transactions_routed_to_review)} reviewed</strong>
          </header>
          <div className="fraud-policy-bars">
            <div><div><span>Held-out traffic sent to review</span><strong>{percent(queue.summary.transactions_routed_to_review / queue.summary.heldout_transactions)}</strong></div><div className="policy-bar"><i style={{ width: percent(queue.summary.transactions_routed_to_review / queue.summary.heldout_transactions) }} /></div><small>{integer(queue.summary.transactions_routed_to_review)} of {integer(queue.summary.heldout_transactions)} transactions</small></div>
            <div><div><span>Reviewed transactions known to be fraud</span><strong>{percent(queue.summary.known_fraud_in_review / queue.summary.transactions_routed_to_review)}</strong></div><div className="policy-bar precision"><i style={{ width: percent(queue.summary.known_fraud_in_review / queue.summary.transactions_routed_to_review) }} /></div><small>The remaining reviewed transactions are false positives.</small></div>
          </div>
          <div className="fraud-label-warning"><Info size={16} aria-hidden="true" /><p><strong>Why outcomes are visible here:</strong> this is historical held-out data. A live queue would not know whether a transaction was fraud before investigation.</p></div>
          <div className="fraud-queue-table-wrap">
            <table className="fraud-queue-table">
              <thead><tr><th>Transaction</th><th>Merchant</th><th>Amount</th><th>Category</th><th>Model score</th><th>Known outcome</th></tr></thead>
              <tbody>{queue.items.map((item) => (
                <tr key={item.transaction_id}>
                  <td><strong>{item.transaction_id.slice(0, 8)}</strong><span>{shortDate(item.occurred_at)} · {item.location}</span></td>
                  <td>{item.merchant}</td>
                  <td>{money(item.amount)}</td>
                  <td>{item.category.replaceAll("_", " ")}</td>
                  <td><div className="queue-score-cell"><strong>{modelScorePercent(item.fraud_score)}</strong><i><b style={{ width: modelScorePercent(item.fraud_score) }} /></i></div></td>
                  <td><span className={item.known_outcome === "Fraud" ? "outcome-fraud" : "outcome-normal"}>{item.known_outcome}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      ) : null}

      {workspace === "model" && model ? (
        <section className="fraud-model-workspace">
          <header className="fraud-section-heading">
            <div><span>Deployment record</span><h2>{model.model_name}</h2><p>{model.score_note}</p></div>
            <strong><Database size={14} aria-hidden="true" /> MLflow packaged</strong>
          </header>
          <div className="fraud-model-facts">
            <div><BrainCircuit size={18} aria-hidden="true" /><span>Training method</span><strong>Random forest</strong><small>{model.balancing_treatment}</small></div>
            <div><Database size={18} aria-hidden="true" /><span>Training window</span><strong>{model.training_window.join(" to ")}</strong><small>Earlier records only</small></div>
            <div><BarChart3 size={18} aria-hidden="true" /><span>Test window</span><strong>{model.test_window.join(" to ")}</strong><small>Held-out future period</small></div>
            <div><ShieldAlert size={18} aria-hidden="true" /><span>Deployment format</span><strong>MLflow pyfunc</strong><small>Safe skops serialization</small></div>
          </div>
          <div className="fraud-evaluation-band">
            <div><span>Fraud caught</span><strong>{integer(model.metrics.fraud_caught)}</strong><small>True positives</small></div>
            <div><span>Normal transactions reviewed</span><strong>{integer(model.metrics.false_positives)}</strong><small>False positives</small></div>
            <div><span>Fraud missed</span><strong>{integer(model.metrics.false_negatives)}</strong><small>False negatives</small></div>
            <div><span>Decision rule</span><strong>score ≥ {percent(model.threshold)}</strong><small>Send to review</small></div>
          </div>
          <div className="fraud-feature-heading"><div><span>Model lineage</span><h3>13 concepts become {model.features.length === 13 ? "26" : model.features.length} numeric columns</h3></div><p>Merchant category expands into one yes/no column per category. Every engineered input traces back to source data.</p></div>
          <div className="fraud-feature-table">
            <div className="fraud-feature-table-head"><span>Model input</span><span>Kind</span><span>Plain meaning</span><span>Built from source column(s)</span></div>
            {model.features.map((feature) => <div key={feature.name}><strong>{feature.name}</strong><span>{feature.kind}</span><p>{feature.meaning}</p><code>{feature.source_columns}</code></div>)}
          </div>
        </section>
      ) : null}
    </div>
  );
}