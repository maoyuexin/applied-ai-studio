import { ArrowLeft, ExternalLink, Workflow } from "lucide-react";
import { navigate } from "../router";
import forecastUrl from "../../../../notebooks/demand-forecasting/backup/02_forecast_simulator.html?url";
import recommendationsUrl from "../../../../notebooks/product-recommendations/backup/02_recommendation_simulator.html?url";

const cases = {
  forecast: {
    title: "Demand Forecasting with Regression",
    courseCase: "retail-demand-forecasting",
    route: "/forecast",
    simulator: forecastUrl,
    model: "Pooled gradient-boosted regression",
    scope: "469 modeled products; 10 products in this historical replay.",
    evidence: "Final test: 12,194 product-weeks. MAE 52.31 → 47.97 units; RMSE 129.75 → 133.78 units.",
    boundary: "One-week predictions use recorded history, not earlier predictions. What-if edits do not retrain the model or change historical outcomes. An inventory planner still owns the order decision.",
    reference: "Earlier interval and inventory-policy lab",
  },
  recommendations: {
    title: "Next Best Product",
    courseCase: "retail-product-recommendations",
    route: "/recommendations",
    simulator: recommendationsUrl,
    model: "Item-item cosine similarity / top 15 neighbors",
    scope: "4,443 training products; five distinct purchases required for personalized ranking.",
    evidence: "Later-period discovery comparison: Hit Rate at 10 29.5% → 41.6%; catalog coverage 1.8% → 25.8%. This comparison informed model choice, not an independent final confirmation.",
    boundary: "Scores sum learned links from distinct purchases. The model stays fixed as simulated history changes. Already-bought products are excluded; cold-start slots use a labeled generic fallback. No purchase or sales lift is caused or measured here.",
    reference: "Advanced recommendation comparison lab",
  },
} as const;

const styles = `
.retail-demo { width: 100%; min-width: 0; }
.retail-demo .page-back-button { min-height: 44px; font-size: 12px; }
.retail-demo-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin: 18px 0; }
.retail-demo-header h1 { margin: 4px 0 8px; font-size: 27px; line-height: 1.25; }
.retail-demo-header p { margin: 0; color: var(--text-secondary); font-size: 14px; }
.retail-demo-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.retail-demo-actions a, .retail-simulator-bar a { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 5px; color: var(--teal); background: var(--surface); text-decoration: none; font-size: 13px; }
.retail-demo-actions a:hover, .retail-simulator-bar a:hover { background: var(--surface-raised); }
.retail-demo-evidence { border-block: 1px solid var(--border); margin: 0 0 18px; padding: 0 2px; }
.retail-demo-evidence summary { min-height: 44px; padding: 12px 0; cursor: pointer; color: var(--text-secondary); font-size: 13px; }
.retail-demo-evidence p { max-width: 95ch; margin: 10px 0; font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
.retail-demo-evidence a { color: var(--teal); display: inline-flex; align-items: center; gap: 7px; min-height: 44px; font-size: 13px; }
.retail-demo-frame { display: block; width: 100%; height: max(760px, calc(100dvh - 260px)); border: 1px solid var(--border); border-radius: 5px; background: #111318; }
.retail-simulator { display: flex; flex-direction: column; height: 100dvh; background: #111318; }
.retail-simulator-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 16px; border-bottom: 1px solid var(--border); }
.retail-simulator-bar strong { font-size: 14px; font-weight: 600; }
.retail-simulator .retail-demo-frame { flex: 1; min-height: 0; height: auto; border: 0; border-radius: 0; }
@media (max-width: 760px) {
  .retail-demo-header { flex-direction: column; gap: 14px; }
  .retail-demo-header h1 { font-size: 23px; }
  .retail-demo-actions { width: 100%; }
  .retail-demo-actions a { flex: 1; }
  .retail-demo-frame { height: 100dvh; min-height: 660px; }
  .retail-simulator-bar { align-items: flex-start; flex-wrap: wrap; padding: 8px; gap: 8px; }
  .retail-simulator-bar strong { flex-basis: 100%; order: -1; padding: 3px 4px; font-size: 12px; }
  .retail-simulator-bar a { white-space: nowrap; }
}
`;

export default function RetailDemoPage({ kind, standalone = false }: {
  kind: keyof typeof cases;
  standalone?: boolean;
}) {
  const item = cases[kind];
  const frame = (
    <iframe
      className="retail-demo-frame"
      title={`${item.title} simulator`}
      src={item.simulator}
      allow="fullscreen"
    />
  );

  if (standalone) {
    return (
      <main className="retail-simulator">
        <style>{styles}</style>
        <header className="retail-simulator-bar">
          <a href={item.route}><ArrowLeft size={16} aria-hidden="true" /> Back to demo</a>
          <strong>{item.title}</strong>
          <a href={`/workflow?courseCase=${item.courseCase}`}><Workflow size={16} aria-hidden="true" /> Workflow</a>
        </header>
        {frame}
      </main>
    );
  }

  return (
    <div className="page retail-demo">
      <style>{styles}</style>
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=retail")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>
      <header className="retail-demo-header">
        <div>
          <span className="eyebrow">Retail decisions / classroom model</span>
          <h1>{item.title}</h1>
          <p>{item.model}</p>
        </div>
        <nav className="retail-demo-actions" aria-label="Retail case navigation">
          <a href={`/workflow?courseCase=${item.courseCase}`}><Workflow size={16} aria-hidden="true" /> Workflow</a>
        </nav>
      </header>
      <details className="retail-demo-evidence">
        <summary>Model evidence and authority</summary>
        <p>{item.scope}</p>
        <p>{item.evidence}</p>
        <p>{item.boundary}</p>
        <p>Embedded model / browser inference / no API dependency. UCI Online Retail II, CC BY 4.0. Product photographs have separate merchant rights.</p>
        <a href={`${item.route}-reference`}>{item.reference} <ExternalLink size={14} aria-hidden="true" /></a>
      </details>
      {frame}
    </div>
  );
}