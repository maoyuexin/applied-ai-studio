import { useRef, useState } from "react";
import { Download, GitCompare, GitFork, Lock, Trash2, Upload } from "lucide-react";
import { designApi, mediaUrl, useLoad, type RunSummary } from "./api";
import { PipelineGlyph } from "./HomePage";
import { Banner, Crumbs, Dialog, Link, Spinner, StatusPill } from "./ui";
import { bytes, go, useAction, when } from "./lib";

export default function HistoryPage() {
  const [query, setQuery] = useState("");
  const [pipeline, setPipeline] = useState("");
  const [status, setStatus] = useState("");
  const [days, setDays] = useState("");
  const [tag, setTag] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<RunSummary | null>(null);
  const [imported, setImported] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const filters = { q: query.trim() || undefined, pipeline: pipeline || undefined, status: status || undefined, days: days || undefined, tag: tag || undefined };
  const list = useLoad(() => designApi.runs(filters), JSON.stringify(filters));
  const { busy, run, toast } = useAction();

  const importBundle = async (file: File) => {
    const detail = await run("import", () => designApi.importBundle(file));
    if (detail) {
      setImported(detail.run.title);
      void list.reload();
    }
  };
  const remove = async (target: RunSummary) => {
    setConfirm(null);
    const done = await run("delete", async () => { await designApi.remove(target.id); return true; });
    if (done) void list.reload();
  };
  const togglePick = (id: string) => setPicked((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current.slice(-1), id]);
  const runs = list.data?.runs ?? [];

  return (
    <div className="page ds">
      <Crumbs items={[{ label: "Design Studio", to: "/design-studio" }, { label: "Run history" }]} />
      <header className="ds-head">
        <div>
          <h1>Run history</h1>
          <p className="ds-sub">Every run on this machine, with its prompts, models, outputs and decisions. Open one to replay it, fork it to try a change, or export it to another machine.</p>
        </div>
        <div className="ds-head-actions">
          {picked.length === 2 && <button type="button" className="ds-btn" onClick={() => go(`/design-studio/compare?a=${picked[0]}&b=${picked[1]}`)}><GitCompare size={14} aria-hidden="true" /> Compare 2 runs</button>}
          <button type="button" className="ds-btn" disabled={busy === "import"} onClick={() => fileInput.current?.click()}>
            {busy === "import" ? <Spinner /> : <Upload size={14} aria-hidden="true" />} Import bundle…
          </button>
          <input ref={fileInput} type="file" accept=".zip,application/zip" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void importBundle(file); event.target.value = ""; }} />
          <Link to="/design-studio" className="ds-btn primary">New run</Link>
        </div>
      </header>
      {imported && <div style={{ marginBottom: 12 }}><Banner kind="ok">Imported “{imported}”.</Banner></div>}
      <section className="ds-card tight" style={{ marginBottom: 14 }}>
        <div className="ds-filters">
          <input aria-label="Search runs" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search titles, briefs, run ids…" />
          <select aria-label="Pipeline" value={pipeline} onChange={(e) => setPipeline(e.target.value)}>
            <option value="">All pipelines</option><option value="video">Video</option><option value="image">Image</option><option value="voice">Voice</option><option value="article">Article</option><option value="inspect">Inspect</option>
          </select>
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option><option value="waiting">Waiting for review</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Needs attention</option><option value="canceled">Canceled</option>
          </select>
          <select aria-label="Created" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="">Any time</option><option value="1">Last 24 hours</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option>
          </select>
          <div className="ds-row">
            {(list.data?.tags ?? []).slice(0, 6).map((item) => (
              <button key={item} type="button" className={`ds-btn sm${tag === item ? " on" : ""}`} onClick={() => setTag(tag === item ? "" : item)}>#{item}</button>
            ))}
          </div>
        </div>
        {list.data && <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>Storage: {bytes(list.data.storage_bytes)} · <span className="ds-mono">{list.data.data_dir}</span> · tick two runs to compare them.</p>}
      </section>
      {list.error && <Banner kind="error">{list.error}</Banner>}
      <section className="ds-card tight">
        {runs.length ? (
          <div className="ds-scroll-x">
            <table className="ds-table">
              <thead>
                <tr>
                  <th aria-label="Compare" />
                  <th aria-label="Preview" />
                  <th>Run</th>
                  <th>Pipeline</th>
                  <th>Status</th>
                  <th className="ds-hide-sm">Outputs</th>
                  <th className="ds-hide-sm">Models</th>
                  <th>Created</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {runs.map((item) => (
                  <tr key={item.id}>
                    <td><input type="checkbox" aria-label={`Compare ${item.title}`} checked={picked.includes(item.id)} onChange={() => togglePick(item.id)} /></td>
                    <td>
                      <Link to={`/design-studio/runs/${item.id}`} className="ds-thumb">
                        {item.counters.thumb_sha ? <img src={mediaUrl(item.counters.thumb_sha)} alt="" loading="lazy" /> : <PipelineGlyph pipeline={item.pipeline} />}
                      </Link>
                    </td>
                    <td className="title">
                      <Link to={`/design-studio/runs/${item.id}`}><b>{item.title}</b></Link>
                      <small>
                        {item.source === "imported" ? "imported · " : ""}
                        {item.parent_run_id ? "fork · " : ""}
                        {item.tags.map((t) => `#${t}`).join(" ")}
                      </small>
                    </td>
                    <td>{item.pipeline_title}</td>
                    <td>
                      <StatusPill status={item.status} restricted={item.restricted} />
                      {item.status === "waiting" && item.step && <div className="ds-tiny ds-muted" style={{ marginTop: 3 }}>at {item.step.title}</div>}
                    </td>
                    <td className="ds-hide-sm ds-small ds-dim">{item.counters.outputs ?? "—"}</td>
                    <td className="ds-hide-sm ds-mono ds-tiny ds-muted">{(item.counters.models ?? []).join(" · ")}</td>
                    <td className="ds-small" style={{ whiteSpace: "nowrap" }}>{when(item.created_at)}</td>
                    <td>
                      <div className="ds-row" style={{ flexWrap: "nowrap", gap: 4 }}>
                        <Link to={`/design-studio/new/${item.pipeline}?fork=${item.id}`} className="ds-btn sm" ><GitFork size={12} aria-hidden="true" /> Fork</Link>
                        {item.restricted ? <span className="ds-btn sm ghost" title="Restricted runs are never exported"><Lock size={12} aria-hidden="true" /></span>
                          : <a className="ds-btn sm" href={designApi.exportUrl(item.id)} download title="Export bundle"><Download size={12} aria-hidden="true" /></a>}
                        <button type="button" className="ds-btn sm ghost" aria-label={`Delete ${item.title}`} onClick={() => setConfirm(item)}><Trash2 size={12} aria-hidden="true" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : list.loading ? <div className="ds-empty"><Spinner /> Loading…</div> : (
          <div className="ds-empty">
            <b>No runs match</b>
            <span>Clear the filters, start a new run, or import a bundle exported from another machine.</span>
          </div>
        )}
      </section>
      {confirm && (
        <Dialog title="Delete this run?" onClose={() => setConfirm(null)} actions={<>
          <button type="button" className="ds-btn ghost" onClick={() => setConfirm(null)}>Keep it</button>
          <button type="button" className="ds-btn danger" onClick={() => void remove(confirm)}>Delete run and its media</button>
        </>}>
          “{confirm.title}” and its outputs will be removed from this machine. Export a bundle first if you may want it back.
        </Dialog>
      )}
      {toast}
    </div>
  );
}
