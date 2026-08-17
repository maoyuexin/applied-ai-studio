import { useEffect, useState } from "react";
import { Database, Play, Search, Workflow } from "lucide-react";
import type { UseCase } from "@applied-ai-studio/contracts";
import { getUseCases } from "../api";
import IndustryIcon from "../components/IndustryIcon";
import { navigate } from "../router";

export default function ShowcasePage() {
  const initialIndustry = new URLSearchParams(window.location.search).get("industry") ?? "all";
  const [items, setItems] = useState<UseCase[]>([]);
  const [industry, setIndustry] = useState(initialIndustry);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getUseCases()
      .then(setItems)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const courseLabs = items.filter((item) => item.courseCaseId);
  const industries = [...new Map(courseLabs.map((item) => [item.industry, item.industryLabel])).entries()];
  const normalized = query.trim().toLocaleLowerCase();
  const filtered = courseLabs.filter((item) => {
    if (industry !== "all" && item.industry !== industry) return false;
    if (!normalized) return true;
    return [item.title, item.summary, item.industryLabel, ...item.capabilities, ...item.patterns]
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized);
  });
  return (
    <div className="page showcase-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">End-to-end decision workflows</span>
          <h1>Industry Workflows</h1>
          <p>Complete business workflows with decisions, exceptions, baselines, and accountable AI boundaries.</p>
        </div>
        <div className="source-badge">
          <Database size={16} aria-hidden="true" />
          Synthetic scenarios
        </div>
      </header>

      <section className="metric-strip" aria-label="Catalog summary">
        <div><strong>{courseLabs.length}</strong><span>workflows</span></div>
        <div><strong>{industries.length}</strong><span>industries</span></div>
        <div><strong>{new Set(courseLabs.flatMap((item) => item.capabilities)).size}</strong><span>AI capabilities</span></div>
        <div><strong>{courseLabs.filter((item) => item.riskLevel === "high").length}</strong><span>high-review cases</span></div>
      </section>

      <div className="catalog-toolbar">
        <label className="search-field">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search use cases</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search capability, pattern, or problem" />
        </label>
        <div className="filter-tabs" aria-label="Industry filter">
          <button type="button" className={industry === "all" ? "selected" : ""} onClick={() => setIndustry("all")}>All</button>
          {industries.map(([id, label]) => (
            <button type="button" className={industry === id ? "selected" : ""} key={id} onClick={() => setIndustry(id)}>{label}</button>
          ))}
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {!items.length && !error ? <div className="loading-state">Loading catalog...</div> : null}

      {items.length ? (
        <section className="use-case-grid card-only-grid" aria-label="Use cases">
          {filtered.map((item) => {
            const workflowTarget = item.courseCaseId
              ? `/workflow?courseCase=${encodeURIComponent(item.courseCaseId)}`
              : `/workflow?case=${encodeURIComponent(item.id)}`;
            const demoTarget = item.id === "retail-online-order-decision-lab"
              ? "/online-order?view=customer"
              : `/demo?case=${encodeURIComponent(item.id)}`;
            return (
              <article key={item.id} className={`use-case-card accent-${item.accent}`}>
                <div className="use-case-card-main">
                  <span className="card-icon"><IndustryIcon name={item.icon} /></span>
                  <span className="card-industry">{item.industryLabel}</span>
                  <strong>{item.title}</strong>
                  <span className="card-summary">{item.summary}</span>
                  <div className="card-capabilities">
                    {item.capabilities.slice(0, 3).map((capability) => <span key={capability}>{capability}</span>)}
                  </div>
                  <div className="card-trust-row">
                    <span>{item.workloadType.replaceAll("-", " ")}</span>
                    <span>Risk: {item.riskLevel}</span>
                    <span>Data: {item.dataReadiness}</span>
                  </div>
                </div>
                <div className="case-card-actions">
                  <button type="button" onClick={() => navigate(workflowTarget)}>
                    <Workflow size={14} aria-hidden="true" /> Workflow
                  </button>
                  {/* Only Online Order has a runnable demo today. Showing a "Demo" button on
                      the other five sent students to a roadmap placeholder, which reads as a
                      broken link rather than a plan. Hide it until the demo actually exists. */}
                  {item.demoStatus === "available" ? (
                    <button type="button" onClick={() => navigate(demoTarget)}>
                      <Play size={14} aria-hidden="true" /> Demo
                      <small>live</small>
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}