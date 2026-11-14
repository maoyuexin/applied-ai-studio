import { designApi, mediaUrl, useLoad, type AlertsReport, type Artifact, type InspectReport, type RunDetail } from "./api";
import { Banner, Crumbs, Link, StatusPill } from "./ui";
import { when } from "./lib";

interface Row {
  label: string;
  value: (detail: RunDetail) => string;
  setting?: boolean;
}

const median = (values: number[]) => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

const takes = (detail: RunDetail) => detail.artifacts.filter((a) => a.kind === "take" && a.status !== "superseded");
const passed = (items: Artifact[]) => items.filter((a) => a.verdict === "keep" || a.verdict === "usable").length;

const textModel = (d: RunDetail) => d.run.settings?.models?.["text-draft"] ?? "install default";
const judgeModel = (d: RunDetail) => d.run.settings?.models?.["text-judge"] ?? "install default";
const TEXT_MODEL_ROW: Row = { label: "Text model", setting: true, value: textModel };

const alertsReport = (d: RunDetail) => d.steps.find((s) => s.key === "check")?.data.report as AlertsReport | undefined;
const inspectReport = (d: RunDetail) => d.steps.find((s) => s.key === "check")?.data.report as InspectReport | undefined;
const inspectTotal = (d: RunDetail, key: "correct" | "overconfident" | "unsure" | "graded") =>
  Object.values(inspectReport(d)?.models ?? {}).reduce((total, row) => total + row[key], 0);

const ROWS: Record<string, Row[]> = {
  video: [
    { label: "Text model", setting: true, value: (d) => (d.run.brief.prompt_helper === false ? "none · prompt helper off" : textModel(d)) },
    { label: "Shots", setting: true, value: (d) => `${d.run.brief.shots} × ${d.run.brief.seconds} s` },
    { label: "Takes per shot", setting: true, value: (d) => String(d.run.brief.takes_per_shot) },
    { label: "Frame", setting: true, value: (d) => d.run.brief.size ?? "" },
    { label: "References", setting: true, value: (d) => String(d.artifacts.filter((a) => a.kind === "reference").length) },
    { label: "Shot sources", setting: true, value: (d) => (d.steps.find((s) => s.key === "shotlist")?.data.shots ?? []).map((s) => (s.mode === "i2v" ? "keyframe" : "text")).join(" · ") },
    { label: "Takes made", value: (d) => String(takes(d).length) },
    { label: "Passed (keep or usable)", value: (d) => { const t = takes(d).filter((a) => a.status === "ready"); return t.length ? `${passed(t)} of ${t.length} (${Math.round((passed(t) / t.length) * 100)}%)` : "—"; } },
    { label: "Median motion", value: (d) => { const m = median(takes(d).map((a) => a.metrics.motion).filter((v): v is number => typeof v === "number")); return m == null ? "—" : m.toFixed(2); } },
    { label: "Mean generation time", value: (d) => { const s = takes(d).map((a) => a.gen_seconds).filter((v): v is number => typeof v === "number"); return s.length ? `${Math.round(s.reduce((x, y) => x + y, 0) / s.length)} s` : "—"; } },
    { label: "Blocked or failed", value: (d) => String(takes(d).filter((a) => a.status === "blocked" || a.status === "failed").length) },
    { label: "Final cut", value: (d) => { const f = d.artifacts.find((a) => a.kind === "final" && a.status === "ready"); return f ? `${f.metrics.duration?.toFixed(1)} s` : "—"; } },
  ],
  image: [
    TEXT_MODEL_ROW,
    { label: "Use case", setting: true, value: (d) => d.run.brief.use_case ?? "" },
    { label: "Size", setting: true, value: (d) => d.run.brief.size ?? "" },
    { label: "Prompt helper", setting: true, value: (d) => (d.run.brief.prompt_helper ? "on" : "off") },
    { label: "References", setting: true, value: (d) => String(d.artifacts.filter((a) => a.kind === "reference").length) },
    { label: "Images made", value: (d) => String(d.artifacts.filter((a) => a.kind === "image" && a.status === "ready").length) },
    { label: "Kept", value: (d) => String(d.artifacts.filter((a) => a.kind === "image" && a.verdict === "keep").length) },
    { label: "Edit passes", value: (d) => String(d.artifacts.filter((a) => a.grp === "versions" && a.status === "ready").length) },
    { label: "Blocked by filter", value: (d) => String(d.artifacts.filter((a) => a.status === "blocked").length) },
  ],
  article: [
    TEXT_MODEL_ROW,
    { label: "Fact-check model", setting: true, value: judgeModel },
    { label: "Must not include", setting: true, value: (d) => d.run.brief.must_not_include || "—" },
    { label: "Format", setting: true, value: (d) => d.run.brief.format ?? "" },
    { label: "Target length", setting: true, value: (d) => `${d.run.brief.target_words} words` },
    { label: "Sources", setting: true, value: (d) => String(d.run.brief.sources?.length ?? 0) },
    { label: "Fact check", setting: true, value: (d) => (d.run.brief.fact_check ? "on" : "off") },
    { label: "Versions", value: (d) => String(d.artifacts.filter((a) => a.kind === "version" && a.status === "ready").length) },
    { label: "Unsupported claims (v1 → approved)", value: (d) => { const v = d.artifacts.filter((a) => a.kind === "version" && a.status === "ready"); const f = d.artifacts.find((a) => a.kind === "final" && a.status === "ready"); return v.length ? `${v[0].metrics.unsupported ?? 0} → ${(f ?? v[v.length - 1]).metrics.unsupported ?? 0}` : "—"; } },
    { label: "Words", value: (d) => { const f = d.artifacts.find((a) => a.kind === "final" && a.status === "ready"); return f ? String(f.metrics.words ?? "") : "—"; } },
  ],
  voice: [
    TEXT_MODEL_ROW,
    { label: "Format", setting: true, value: (d) => d.run.brief.format ?? "" },
    { label: "Language", setting: true, value: (d) => d.run.brief.locale ?? "" },
    { label: "Voices", setting: true, value: (d) => (d.run.brief.speakers ?? []).map((s) => s.voice.split(":")[0].split("-").pop()).join(" · ") },
    { label: "Target", setting: true, value: (d) => `${d.run.brief.target_seconds} s` },
    { label: "Lines", value: (d) => String(d.steps.find((s) => s.key === "script")?.data.lines?.length ?? 0) },
    { label: "Re-recorded lines", value: (d) => String(d.artifacts.filter((a) => a.kind === "line" && a.parent_id).length) },
    { label: "Word differences (kept)", value: (d) => String(d.artifacts.filter((a) => a.kind === "line" && a.verdict === "keep").reduce((t, a) => t + (a.metrics.word_errors ?? 0), 0)) },
    { label: "Final length", value: (d) => { const f = d.artifacts.find((a) => a.kind === "final" && a.status === "ready"); return f ? `${f.metrics.duration?.toFixed(1)} s` : "—"; } },
  ],
  alerts: [
    { label: "Models", setting: true, value: (d) => (d.run.brief.models ?? []).join(" · ") },
    { label: "Tries", setting: true, value: (d) => String(d.run.brief.tries ?? 1) },
    { label: "Moments", setting: true, value: (d) => String(d.run.brief.moments?.length ?? 0) },
    { label: "Languages", setting: true, value: (d) => (d.run.brief.languages ?? []).map((l) => l.name).join(" · ") },
    { label: "Drafts", value: (d) => String(d.run.counters.drafts ?? 0) },
    { label: "Messages flagged", value: (d) => { const r = alertsReport(d); if (!r) return "—"; const rows = Object.values(r.models); const f = rows.reduce((t, x) => t + x.flagged, 0); const m = rows.reduce((t, x) => t + x.messages, 0); return m ? `${f} of ${m} (${Math.round((100 * f) / m)}%)` : "—"; } },
    { label: "Signed", value: (d) => { const s = alertsReport(d)?.signed; return s ? `${s.approve} approved · ${s.edit} edited · ${s.reject} rejected` : "—"; } },
  ],
  inspect: [
    { label: "Models", setting: true, value: (d) => (d.run.brief.models ?? []).join(" · ") },
    { label: "Tries", setting: true, value: (d) => String(d.run.brief.tries ?? 1) },
    { label: "Images", setting: true, value: (d) => String(d.run.brief.images?.length ?? 0) },
    { label: "Questions", setting: true, value: (d) => (d.run.brief.questions ?? []).map((q) => q.short).join(" · ") },
    { label: "Answers", value: (d) => String(d.run.counters.answers ?? 0) },
    { label: "Labeled answers right", value: (d) => { const g = inspectTotal(d, "graded"); return g ? `${inspectTotal(d, "correct")} of ${g} (${Math.round((100 * inspectTotal(d, "correct")) / g)}%)` : "—"; } },
    { label: "Overconfident", value: (d) => String(inspectTotal(d, "overconfident")) },
    { label: "Said cannot tell", value: (d) => String(inspectTotal(d, "unsure")) },
    { label: "Labels fixed in review", value: (d) => String(inspectReport(d)?.fixes ?? 0) },
    { label: "Identity questions", value: (d) => { const p = d.steps.find((s) => s.key === "policy")?.data.policy; return p ? (p.identity === "refuse" ? "refused" : "allowed") : "—"; } },
  ],
};

function Hero({ detail }: { detail: RunDetail }) {
  const final = detail.artifacts.find((a) => a.kind === "final" && a.status === "ready");
  if (final?.media_type === "video/mp4" && final.media_sha) {
    return <div className="ds-player"><video src={mediaUrl(final.media_sha)} poster={final.thumb_sha ? mediaUrl(final.thumb_sha) : undefined} controls preload="metadata" playsInline /></div>;
  }
  if (final?.media_type?.startsWith("audio/") && final.media_sha) return <audio controls src={mediaUrl(final.media_sha)} preload="metadata" />;
  if (final?.media_type === "text/markdown") return <div className="ds-article ds-promptbox"><h2>{final.data.headline}</h2><p>{final.data.body}</p></div>;
  const image = final ?? detail.artifacts.find((a) => a.thumb_sha && a.verdict === "keep") ?? detail.artifacts.find((a) => a.thumb_sha);
  return image?.media_sha ? <div className="ds-player"><img src={mediaUrl(image.media_sha)} alt="" /></div> : <div className="ds-empty">No output yet</div>;
}

export default function ComparePage({ a, b }: { a: string | null; b: string | null }) {
  const left = useLoad(() => (a ? designApi.run(a) : Promise.reject(new Error("Pick two runs in Run history to compare."))), a ?? "");
  const right = useLoad(() => (b ? designApi.run(b) : Promise.reject(new Error("Pick two runs in Run history to compare."))), b ?? "");
  const error = left.error ?? right.error;
  const pair = left.data && right.data ? [left.data, right.data] : null;
  const rows = pair ? ROWS[pair[0].run.pipeline] ?? [] : [];
  const sameKind = pair ? pair[0].run.pipeline === pair[1].run.pipeline : true;

  return (
    <div className="page ds">
      <Crumbs items={[{ label: "Design Studio", to: "/design-studio" }, { label: "History", to: "/design-studio/history" }, { label: "Compare" }]} />
      <header className="ds-head">
        <div>
          <h1>{pair ? `${pair[0].run.title} vs ${pair[1].run.title}` : "Compare runs"}</h1>
          <p className="ds-sub">What changed in the settings (orange) next to what changed in the results: a classroom A/B test built from run history.</p>
        </div>
      </header>
      {error && <Banner kind="error">{error}</Banner>}
      {pair && !sameKind && <Banner kind="warn">These runs use different pipelines, so only the outputs are compared.</Banner>}
      {pair && (
        <div className="ds-grid2" style={{ marginTop: 12, alignItems: "start" }}>
          {pair.map((detail, index) => (
            <section key={detail.run.id} className={`ds-card${index === 1 ? " hl" : ""}`}>
              <div className="ds-row between" style={{ marginBottom: 10 }}>
                <Link to={`/design-studio/runs/${detail.run.id}`}><b>{detail.run.title}</b></Link>
                <StatusPill status={detail.run.status} />
              </div>
              <Hero detail={detail} />
              <dl className="ds-kv" style={{ marginTop: 12 }}>
                {sameKind && rows.map((row) => {
                  const value = row.value(detail);
                  const other = row.value(pair[1 - index]);
                  return (
                    <div key={row.label} style={{ display: "contents" }}>
                      <dt>{row.label}</dt>
                      <dd>{value || "—"} {row.setting && index === 1 && value !== other && <span className="ds-chip or ds-compare-tag">changed</span>}</dd>
                    </div>
                  );
                })}
                <dt>Created</dt><dd>{when(detail.run.created_at)}</dd>
              </dl>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
