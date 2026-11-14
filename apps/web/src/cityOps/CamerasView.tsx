import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Camera, Check, ShieldCheck, X } from "lucide-react";
import { mediaUrl, type Artifact, type InspectPolicy, type InspectQuestion, type InspectReport, type RunDetail } from "../design/api";
import { fmtRecorded } from "./data";
import { useEscape } from "./hooks";
import { conditionOf, consensus, gradeOf, normalizedOf, siteOf, stepOf, truthOf, type RecordedRun } from "./runs";
import { ActionError, Panel } from "./ui";

const GRADE_TEXT: Record<string, string> = {
  correct: "matches label", wrong: "wrong", overconfident: "firm answer where the label is cannot tell", unsure: "said cannot tell",
  invalid: "unreadable answer", declined: "declined", breach: "did not decline", ok: "no identity detail", flagged: "identity detail",
};
const GOOD = new Set(["correct", "declined", "ok"]);
const toneOfGrade = (grade: string) => (GOOD.has(grade) ? "ok" : grade === "unsure" ? "warn" : grade ? "bad" : "");

export default function CamerasView({ run, detail }: { run: RecordedRun; detail: RunDetail }) {
  const brief = detail.run.brief;
  const questions = useMemo(() => brief.questions ?? [], [brief.questions]);
  const models = useMemo(() => brief.models ?? [], [brief.models]);
  const images = useMemo(() => detail.artifacts.filter((a) => a.kind === "image")
    .sort((a, b) => Number(a.data.position ?? 0) - Number(b.data.position ?? 0)), [detail.artifacts]);
  const answers = useMemo(() => detail.artifacts.filter((a) => a.kind === "answer" && a.status !== "superseded"), [detail.artifacts]);
  const byImage = useMemo(() => {
    const map = new Map<string, Artifact[]>();
    answers.forEach((a) => map.set(a.parent_id ?? "", [...(map.get(a.parent_id ?? "") ?? []), a]));
    return map;
  }, [answers]);
  const sites = useMemo(() => [...new Set(images.map(siteOf))], [images]);
  const conditions = useMemo(() => [...new Set(images.map(conditionOf))], [images]);
  const report = stepOf(detail, "check")?.data.report as InspectReport | undefined;
  const reviewed = useMemo(() => new Set((report?.disagreements ?? []).map((d) => d.image_id)), [report]);

  const [condition, setCondition] = useState(() => (conditions.includes("Flood") ? "Flood" : conditions[0] ?? ""));
  const [override, setOverride] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const imageAt = (site: string) => {
    const wanted = override[site] ?? condition;
    return images.find((img) => siteOf(img) === site && conditionOf(img) === wanted) ?? images.find((img) => siteOf(img) === site) ?? null;
  };
  const openImage = images.find((img) => img.id === open) ?? null;

  return (
    <div className="co-cams">
      <div className="co-cams-main">
        <Panel eyebrow={`${sites.length} camera sites · ${images.length} snapshots · ${models.length} models × ${brief.tries ?? 1} tries`} title="Camera wall"
          aside={<span className="co-testscene"><Camera size={13} aria-hidden="true" /> Test scenes · AI-generated · not real cameras</span>}>
          <div className="co-cond-bar" role="radiogroup" aria-label="Condition on every camera">
            <span>Condition</span>
            {conditions.map((c) => (
              <button key={c} type="button" role="radio" aria-checked={c === condition && !Object.keys(override).length}
                className={c === condition ? "is-on" : ""} onClick={() => { setCondition(c); setOverride({}); }}>{c}</button>
            ))}
          </div>
          <div className="co-wall">
            {sites.map((site) => {
              const image = imageAt(site);
              if (!image) return null;
              return (
                <CameraTile key={site} site={site} image={image} conditions={conditions} questions={questions}
                  answers={byImage.get(image.id) ?? []} reviewed={reviewed.has(image.id)}
                  onCondition={(c) => setOverride((current) => ({ ...current, [site]: c }))} onOpen={() => setOpen(image.id)} />
              );
            })}
          </div>
          <p className="co-foot-note">Readouts are recorded answers from {models.join(", ")}; live questions are not available in replay. A person reviewed every label.</p>
        </Panel>
        {report && <ReviewList report={report} questions={questions} images={images} onOpen={setOpen} />}
      </div>
      <div className="co-cams-side">
        <AccessPolicy run={run} detail={detail} />
      </div>
      {openImage && (
        <ImageDrawer image={openImage} questions={questions} models={models} answers={byImage.get(openImage.id) ?? []}
          report={report} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}

function CameraTile({ site, image, conditions, questions, answers, reviewed, onCondition, onOpen }: {
  site: string; image: Artifact; conditions: string[]; questions: InspectQuestion[]; answers: Artifact[]; reviewed: boolean;
  onCondition: (c: string) => void; onOpen: () => void;
}) {
  const truth = truthOf(image);
  const reads = questions.map((q) => ({ q, c: consensus(q, answers, truth) }));
  const off = reads.filter((r) => r.c.offLabel);
  return (
    <article className="co-tile">
      <header>
        <strong>{site}</strong>
        <select aria-label={`Condition for ${site}`} value={conditionOf(image)} onChange={(e) => onCondition(e.target.value)}>
          {conditions.map((c) => <option key={c}>{c}</option>)}
        </select>
      </header>
      <button type="button" className="co-tile-img" onClick={onOpen} aria-label={`Open ${image.label}`}>
        {image.thumb_sha && <img src={mediaUrl(image.thumb_sha)} alt={`${image.label} (AI-generated test scene)`} loading="lazy" />}
        <span className="co-tile-tag">Test scene</span>
        <span className="co-tile-badges">
          {off.length > 0 && <span className="co-badge is-bad" title={off.map((r) => `${r.q.short}: models say ${r.c.top}, label is ${truth[r.q.key]}`).join("\n")}>Disagrees with label</span>}
          {reviewed && <span className="co-badge" title="This snapshot had a disagreement that a person reviewed">Reviewed</span>}
        </span>
      </button>
      <ul className="co-readout">
        {reads.map(({ q, c }) => (
          <li key={q.key} title={`${q.text}\n${c.counts.map(([v, n]) => `${v}: ${n}`).join(" · ")}${truth[q.key] ? `\nReviewed label: ${truth[q.key]}` : ""}`}>
            <span>{q.short.replace(/\?$/, "")}</span>
            <b className={`is-${c.tone}`}>{c.text}</b>
          </li>
        ))}
      </ul>
    </article>
  );
}

function ImageDrawer({ image, questions, models, answers, report, onClose }: {
  image: Artifact; questions: InspectQuestion[]; models: string[]; answers: Artifact[]; report: InspectReport | undefined; onClose: () => void;
}) {
  useEscape(onClose);
  const truth = truthOf(image);
  const fixes = (image.data.fixes ?? {}) as Record<string, { value: string; was: string; note?: string }>;
  const resolutions = (report?.disagreements ?? []).filter((d) => d.image_id === image.id);
  const answersOf = (model: string) => answers.filter((a) => a.params.model === model).sort((a, b) => (a.params.try ?? 0) - (b.params.try ?? 0));
  return createPortal(
    <div className="co-drawer-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="co-drawer" role="dialog" aria-modal="true" aria-label={image.label ?? "Camera snapshot"}>
        <header className="co-drawer-head">
          <div>
            <span className="co-eyebrow">{siteOf(image)} · {conditionOf(image)}</span>
            <strong>{image.label}</strong>
          </div>
          <button type="button" className="co-icon-btn" onClick={onClose} aria-label="Close"><X size={16} aria-hidden="true" /></button>
        </header>
        <div className="co-drawer-body">
          <figure className="co-drawer-img">
            {image.media_sha && <img src={mediaUrl(image.media_sha)} alt={`${image.label} (AI-generated test scene)`} />}
            <figcaption>
              <span className="co-testscene">Test scene · AI-generated · fictional place · not a real camera</span>
              {image.checks.map((c) => <span key={c.key} className={`co-chip is-${c.state}`} title={c.basis}>{c.label}</span>)}
            </figcaption>
          </figure>
          <div className="co-scroll-x">
            <table className="co-table">
              <thead><tr><th>Question</th><th>Reviewed label</th>{models.map((m) => <th key={m}>{m}</th>)}</tr></thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.key}>
                    <td><b>{q.short}</b><small>{q.text}</small></td>
                    <td>
                      {q.expect === "decline" ? <span className="co-dim">should decline</span>
                        : q.expect === "none" ? <span className="co-dim">no identity detail</span>
                        : <><b>{truth[q.key] ?? "—"}</b>{fixes[q.key] && <small>fixed in review; was {fixes[q.key].was}</small>}</>}
                    </td>
                    {models.map((m) => (
                      <td key={m}>
                        <span className="co-tries">
                          {answersOf(m).map((a) => {
                            const grade = gradeOf(a, q.key);
                            const value = normalizedOf(a)[q.key] ?? "";
                            return <span key={a.id} className={`co-try is-${toneOfGrade(grade)}`} title={`try ${a.params.try}: ${value || "no answer"} (${GRADE_TEXT[grade] ?? grade})`}>
                              {q.expect === "label" ? value || "—" : GRADE_TEXT[grade] ?? grade}
                            </span>;
                          })}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resolutions.length > 0 && (
            <section className="co-drawer-section">
              <h3>Review of this snapshot</h3>
              <ul className="co-resolutions">
                {resolutions.map((r) => (
                  <li key={r.question}>
                    <b>{questions.find((q) => q.key === r.question)?.short}</b>
                    {r.resolution
                      ? <span className={`co-chip ${r.resolution.outcome === "fixed" ? "is-warn" : "is-ok"}`}>{r.resolution.outcome === "fixed" ? `label fixed: ${r.resolution.was} → ${r.resolution.value}` : `label stands: ${r.label}`}</span>
                      : <span className="co-chip is-warn">not reviewed</span>}
                    {r.resolution?.note && <p>{r.resolution.note}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <details className="co-drawer-section">
            <summary>Exact model answers ({answers.length})</summary>
            <div className="co-raw">
              {[...answers].sort((a, b) => models.indexOf(a.params.model ?? "") - models.indexOf(b.params.model ?? "") || (a.params.try ?? 0) - (b.params.try ?? 0)).map((a) => (
                <div key={a.id}><b>{a.params.model} · try {a.params.try}</b>{a.gen_seconds ? ` · ${a.gen_seconds.toFixed(1)} s` : ""}<code>{String(a.data.raw ?? a.error ?? a.status)}</code></div>
              ))}
            </div>
          </details>
        </div>
      </aside>
    </div>,
    document.body,
  );
}

function ReviewList({ report, questions, images, onOpen }: {
  report: InspectReport; questions: InspectQuestion[]; images: Artifact[]; onOpen: (id: string) => void;
}) {
  const [all, setAll] = useState(false);
  const items = report.disagreements;
  const done = items.filter((d) => d.resolution).length;
  const fixed = items.filter((d) => d.resolution?.outcome === "fixed").length;
  const shown = all ? items : items.slice(0, 6);
  return (
    <Panel eyebrow="Recorded review" title={`Disagreements · ${done} of ${items.length} resolved · ${fixed} label${fixed === 1 ? "" : "s"} fixed`}>
      {!items.length ? <p className="co-empty">Every answer matched the labels.</p> : (
        <>
          <ul className="co-review">
            {shown.map((item) => {
              const image = images.find((img) => img.id === item.image_id);
              const q = questions.find((x) => x.key === item.question);
              const wrong = item.answers.filter((a) => a.grade !== "correct");
              return (
                <li key={`${item.image_id}:${item.question}`}>
                  <button type="button" className="co-review-thumb" onClick={() => onOpen(item.image_id)} aria-label={`Open ${item.image}`}>
                    {image?.thumb_sha && <img src={mediaUrl(image.thumb_sha)} alt="" loading="lazy" />}
                  </button>
                  <div>
                    <div className="co-review-line">
                      <b>{item.image}</b>
                      <span>{q?.short} · label <b>{item.label || "—"}</b></span>
                      {item.resolution
                        ? <span className={`co-chip ${item.resolution.outcome === "fixed" ? "is-warn" : "is-ok"}`}>{item.resolution.outcome === "fixed" ? `fixed: ${item.resolution.was} → ${item.resolution.value}` : "label stands"}</span>
                        : <span className="co-chip is-warn">open</span>}
                    </div>
                    <p className="co-review-note">
                      {wrong.length} of {item.answers.length} answers differed ({[...new Set(wrong.map((a) => a.value || "—"))].join(", ")}).
                      {item.resolution?.note ? ` Note: ${item.resolution.note}` : ""}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
          {items.length > 6 && <button type="button" className="co-link" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${items.length}`}</button>}
        </>
      )}
    </Panel>
  );
}

const DEFAULT_POLICY: InspectPolicy = { identity: "refuse", retention_days: 30, access: "", signoff: "yes", notice: "yes", note: "" };

function Seg<T extends string>({ label, value, options, onPick }: { label: string; value: T; options: Array<[T, string]>; onPick: (v: T) => void }) {
  return (
    <div className="co-seg" role="radiogroup" aria-label={label}>
      {options.map(([key, text]) => (
        <button key={key} type="button" role="radio" aria-checked={value === key} className={value === key ? "is-on" : ""} onClick={() => onPick(key)}>{text}</button>
      ))}
    </div>
  );
}

function AccessPolicy({ run, detail }: { run: RecordedRun; detail: RunDetail }) {
  const step = stepOf(detail, "policy");
  const saved = step?.data.policy;
  const [policy, setPolicy] = useState<InspectPolicy>(saved ?? DEFAULT_POLICY);
  const [confirm, setConfirm] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  // Follow the saved rules when they change on the server, not on every quiet refresh (that would undo typing).
  const savedKey = saved ? JSON.stringify(saved) : "";
  useEffect(() => { if (savedKey) setPolicy(JSON.parse(savedKey) as InspectPolicy); }, [savedKey]);
  const set = (patch: Partial<InspectPolicy>) => { setPolicy((current) => ({ ...current, ...patch })); setSavedAt(null); };
  const waiting = step?.status === "waiting";
  const reportArt = detail.artifacts.find((a) => a.kind === "report" && a.status !== "superseded");
  const reportStep = stepOf(detail, "report");
  const valid = policy.access.trim().length >= 2;
  const busy = run.busy !== null;

  const save = async () => { if (await run.act("save_policy", { policy })) setSavedAt(new Date().toISOString()); };
  const adopt = async () => { if (await run.act("approve", { step: "policy", policy })) setConfirm(false); };

  if (!step || step.status === "pending") {
    return <Panel eyebrow="Access policy" title="Rules for asking the cameras"><p className="co-empty">The camera review in this run has not reached the policy step.</p></Panel>;
  }

  if (!waiting && saved) {
    const decided = detail.decisions.filter((d) => d.step_key === "policy" && d.action === "approve").at(-1);
    return (
      <Panel eyebrow="Access policy · adopted" title="Rules for asking the cameras" aside={<span className="co-pill is-ok"><ShieldCheck size={13} aria-hidden="true" /> Adopted</span>}>
        <dl className="co-kv">
          <dt>Identity questions</dt><dd>{saved.identity === "refuse" ? "Refused: no questions about who people are, no plates or faces" : "Allowed"}</dd>
          <dt>Keep images</dt><dd>{saved.retention_days ? `${saved.retention_days} days` : "Not kept"}</dd>
          <dt>Who may search</dt><dd>{saved.access}</dd>
          <dt>Sign-off before action</dt><dd>{saved.signoff === "yes" ? "Yes, a person approves" : "No"}</dd>
          <dt>Public notice</dt><dd>{saved.notice === "yes" ? "Yes" : "No"}</dd>
          {saved.note && <><dt>Note</dt><dd>{saved.note}</dd></>}
          {decided && <><dt>Adopted</dt><dd>{fmtRecorded(decided.at)}</dd></>}
        </dl>
        <div className="co-report-checks">
          <h3>Camera desk report</h3>
          {reportArt?.status === "ready"
            ? <ul>{reportArt.checks.map((c) => <li key={c.key} className={`is-${c.state}`} title={c.basis}>{c.label}</li>)}</ul>
            : <p className="co-dim">{reportStep?.status === "failed" ? "The report step failed in the Design Studio." : "Writing the report…"}</p>}
        </div>
      </Panel>
    );
  }

  return (
    <Panel eyebrow="Access policy · awaiting adoption" title="Rules for asking the cameras" aside={<span className="co-pill is-watch">Waiting</span>}>
      <div className="co-form">
        <label>May staff ask these cameras about identity (who a person is, faces, license plates)?</label>
        <Seg label="Identity questions" value={policy.identity} options={[["refuse", "No, refuse"], ["allow", "Yes, allow"]]} onPick={(v) => set({ identity: v })} />
        <label htmlFor="co-retention">Keep images for (days, 0 = not kept)</label>
        <input id="co-retention" type="number" min={0} max={3650} value={policy.retention_days}
          onChange={(e) => set({ retention_days: Math.max(0, Math.min(3650, Number(e.target.value) || 0)) })} />
        <label htmlFor="co-access">Who may search the images?</label>
        <input id="co-access" value={policy.access} onChange={(e) => set({ access: e.target.value })} placeholder="e.g. traffic operations staff on duty" />
        <div className="co-form-pair">
          <div><label>A person signs off before any action?</label><Seg label="Sign-off" value={policy.signoff} options={[["yes", "Yes"], ["no", "No"]]} onPick={(v) => set({ signoff: v })} /></div>
          <div><label>Publish a public notice about the cameras?</label><Seg label="Public notice" value={policy.notice} options={[["yes", "Yes"], ["no", "No"]]} onPick={(v) => set({ notice: v })} /></div>
        </div>
        <label htmlFor="co-note">Note (for example, the vote)</label>
        <textarea id="co-note" value={policy.note} onChange={(e) => set({ note: e.target.value })} rows={3} />
        <ActionError run={run} />
        {confirm ? (
          <div className="co-confirm" role="group" aria-label="Confirm adoption">
            <p>Adopt these rules for the camera desk? The run records your decision and writes its report.</p>
            <div className="co-row">
              <button type="button" className="co-btn primary" disabled={busy || !valid} onClick={() => void adopt()}><Check size={14} aria-hidden="true" /> Adopt policy</button>
              <button type="button" className="co-btn" disabled={busy} onClick={() => setConfirm(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="co-row">
            <button type="button" className="co-btn" disabled={busy || !valid} onClick={() => void save()}>{run.busy === "save_policy" ? "Saving…" : "Save draft"}</button>
            <button type="button" className="co-btn primary" disabled={busy || !valid} onClick={() => setConfirm(true)}>Adopt policy…</button>
            {savedAt && <span className="co-dim">Saved</span>}
            {!valid && <span className="co-dim">Say who may search the images.</span>}
          </div>
        )}
      </div>
    </Panel>
  );
}
