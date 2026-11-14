import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Download, Send, X } from "lucide-react";
import { mediaUrl, type Artifact, type InspectPolicy, type InspectQuestion, type InspectReport } from "./api";
import type { RunViewProps } from "./RunPage";
import { Banner, Checks, Progress, ReviewTag, Spinner } from "./ui";

type Tone = "ok" | "bad" | "warn" | "info" | "";

const MARKS: Record<string, { text: string; tone: Tone }> = {
  correct: { text: "right", tone: "ok" },
  wrong: { text: "wrong", tone: "bad" },
  overconfident: { text: "overconfident", tone: "bad" },
  unsure: { text: "said cannot tell", tone: "warn" },
  invalid: { text: "unreadable answer", tone: "bad" },
  unlabeled: { text: "no label", tone: "" },
  declined: { text: "declined", tone: "ok" },
  breach: { text: "did not decline", tone: "bad" },
  ok: { text: "no flag terms", tone: "ok" },
  flagged: { text: "flag term used", tone: "bad" },
};

const markOf = (grade: string | undefined) => MARKS[grade ?? ""] ?? { text: grade ?? "—", tone: "" as Tone };
const record = <T,>(value: unknown) => (value ?? {}) as Record<string, T>;
const pct = (part: number, whole: number) => (whole ? `${Math.round((100 * part) / whole)}%` : "—");

function truthOf(image: Artifact): Record<string, string> {
  const fixes = record<{ value: string }>(image.data.fixes);
  return { ...record<string>(image.data.truth), ...Object.fromEntries(Object.entries(fixes).map(([key, fix]) => [key, fix.value])) };
}

function labelOptions(question: InspectQuestion): string[] {
  return question.kind === "count" ? ["0", "1", "2", "3", "4", "5", "cannot tell"] : question.choices;
}

/** The answers of one model for one image and question, one per try. */
function triesOf(answers: Artifact[], key: string) {
  return answers.map((a) => ({
    tryNo: a.params.try ?? 0,
    status: a.status,
    value: record<string>(a.data.normalized)[key] ?? "",
    raw: record<string | null>(a.data.answers)[key] ?? null,
    grade: a.status === "ready" ? record<string>(a.data.grades)[key] : a.status,
  })).sort((x, y) => x.tryNo - y.tryNo);
}

function AnswerChip({ items }: { items: ReturnType<typeof triesOf> }) {
  if (!items.length) return <span className="ds-chip">…</span>;
  if (items.every((item) => item.status === "queued" || item.status === "running")) return <span className="ds-chip"><Spinner size={11} /></span>;
  const first = items[0];
  const mark = markOf(first.grade);
  const varies = new Set(items.map((item) => `${item.value}|${item.grade}`)).size > 1;
  const title = items.map((item) => `try ${item.tryNo}: ${item.raw ?? item.status} (${markOf(item.grade).text})`).join("\n");
  return (
    <span className={`ds-chip ds-ins-chip ${mark.tone}`} title={title}>
      {first.status === "blocked" ? "blocked" : first.value || "—"}
      {items.length > 1 && <span className="ds-ins-dots" aria-hidden="true">{items.map((item) => <i key={item.tryNo} className={markOf(item.grade).tone} />)}</span>}
      {varies && <b className="ds-ins-varies">varies</b>}
    </span>
  );
}

function ImageDialog({ image, detail, act, busy, questions, models, answers, lives, onClose, editable }: {
  image: Artifact; detail: RunViewProps["detail"]; act: RunViewProps["act"]; busy: string | null; questions: InspectQuestion[];
  models: string[]; answers: Artifact[]; lives: Artifact[]; onClose: () => void; editable: boolean;
}) {
  const truth = truthOf(image);
  const fixes = record<{ value: string; was: string }>(image.data.fixes);
  const askDone = detail.steps.find((s) => s.key === "ask")?.status === "done";
  const [model, setModel] = useState(models[0] ?? "");
  const [text, setText] = useState("");
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const ask = async () => {
    const result = await act<{ created: string }>("ask_live", { image_id: image.id, model, question: text });
    if (result?.created) setText("");
  };
  const mine = answers.filter((a) => a.parent_id === image.id);
  return createPortal(
    <div className="ds">
    <div className="ds-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="ds-dialog ds-ins-dialog" role="dialog" aria-modal="true" aria-label={image.label ?? "Image"}>
        <div className="ds-row between">
          <h2 style={{ margin: 0 }}>{image.label}</h2>
          <button type="button" className="ds-btn sm ghost" onClick={onClose} aria-label="Close"><X size={15} aria-hidden="true" /></button>
        </div>
        <div className="ds-ins-dialog-body">
          <div className="ds-stack" style={{ gap: 8 }}>
            <div className="ds-player"><img src={mediaUrl(image.media_sha!)} alt={image.label ?? ""} /></div>
            <div className="ds-row ds-small">
              {String(image.data.group ?? "") && <span className="ds-chip info">{String(image.data.group)}</span>}
              {String(image.data.note ?? "") && <span className="ds-muted">{String(image.data.note)}</span>}
            </div>
            <Checks checks={image.checks} />
          </div>
          <div className="ds-stack" style={{ gap: 10, minWidth: 0 }}>
            <div className="ds-scroll-x">
              <table className="ds-table ds-ins-table">
                <thead><tr><th>Question</th><th>Label</th>{models.map((m) => <th key={m}>{m}</th>)}</tr></thead>
                <tbody>
                  {questions.map((question) => (
                    <tr key={question.key}>
                      <td className="wrap" title={question.text}><b>{question.short}</b><small className="ds-tiny ds-muted" style={{ display: "block" }}>{question.text}</small></td>
                      <td>
                        {question.expect !== "label" ? <span className="ds-muted ds-small">{question.expect === "decline" ? "should decline" : "flag terms"}</span>
                          : editable ? (
                            <select aria-label={`Label for ${question.short}`} value={truth[question.key] ?? ""} disabled={busy !== null}
                              onChange={(e) => void act("set_label", { image_id: image.id, question: question.key, value: e.target.value })}>
                              {!truth[question.key] && <option value="">—</option>}
                              {labelOptions(question).map((option) => <option key={option}>{option}</option>)}
                            </select>
                          ) : <span><b>{truth[question.key] ?? "—"}</b>{fixes[question.key] && <small className="ds-tiny ds-muted" style={{ display: "block" }}>was {fixes[question.key].was}</small>}</span>}
                      </td>
                      {models.map((m) => <td key={m}><AnswerChip items={triesOf(mine.filter((a) => a.params.model === m), question.key)} /></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {mine.some((a) => a.status === "ready") && (
              <details>
                <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Exact answers ({mine.length})</summary>
                <div className="ds-stack" style={{ gap: 6, marginTop: 6 }}>
                  {mine.map((a) => <div key={a.id} className="ds-promptbox ds-tiny"><b>{a.label}</b>{a.gen_seconds ? ` · ${a.gen_seconds.toFixed(1)} s` : ""}<br />{String(a.data.raw ?? a.error ?? a.status)}</div>)}
                </div>
              </details>
            )}
            {askDone && (
              <div className="ds-card tight">
                <h3>Ask live</h3>
                <div className="ds-ins-live">
                  <select aria-label="Model" value={model} onChange={(e) => setModel(e.target.value)}>{models.map((m) => <option key={m}>{m}</option>)}</select>
                  <input aria-label="Live question" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask anything about this image…"
                    onKeyDown={(e) => { if (e.key === "Enter" && text.trim().length >= 5) void ask(); }} />
                  <button type="button" className="ds-btn primary" disabled={busy !== null || text.trim().length < 5} onClick={() => void ask()}>
                    {busy === "ask_live" ? <Spinner /> : <Send size={14} aria-hidden="true" />} Ask
                  </button>
                </div>
                <div className="ds-stack" style={{ gap: 6, marginTop: 8 }}>
                  {lives.filter((a) => a.parent_id === image.id).slice().reverse().map((a) => (
                    <div key={a.id} className="ds-promptbox ds-small">
                      <b>{a.prompt}</b> <span className="ds-chip model">{a.deployment}</span>
                      <div style={{ marginTop: 4 }}>{a.status === "ready" ? String(a.data.answer ?? "") : a.status === "failed" || a.status === "blocked" ? <span style={{ color: "var(--red)" }}>{a.error}</span> : <><Spinner /> asking…</>}</div>
                      {a.gen_seconds ? <small className="ds-tiny ds-muted">{a.gen_seconds.toFixed(1)} s</small> : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
    </div>,
    document.body,
  );
}

function Summary({ report, questions, models, tries }: { report: InspectReport; questions: InspectQuestion[]; models: string[]; tries: number }) {
  const labelQs = questions.filter((q) => q.expect === "label");
  const otherQs = questions.filter((q) => q.expect !== "label");
  return (
    <div className="ds-stack">
      <div className="ds-scroll-x">
        <table className="ds-table ds-ins-table">
          <thead>
            <tr>
              <th>Model</th>
              {labelQs.map((q) => <th key={q.key} title={q.text}>{q.short} right</th>)}
              <th title="A firm answer where the label is “cannot tell”">Overconfident</th>
              <th>Said cannot tell</th>
              {otherQs.map((q) => <th key={q.key} title={q.text}>{q.short}</th>)}
              {tries > 1 && <th>Same answer every try</th>}
              <th>Median s</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => {
              const row = report.models[model];
              if (!row) return null;
              return (
                <tr key={model}>
                  <td className="ds-mono ds-small">{model}</td>
                  {labelQs.map((q) => {
                    const cell = row.questions[q.key] ?? {};
                    const graded = ["correct", "wrong", "overconfident", "unsure", "invalid"].reduce((t, k) => t + (cell[k] ?? 0), 0);
                    return <td key={q.key}><b>{pct(cell.correct ?? 0, graded)}</b> <small className="ds-muted">{cell.correct ?? 0}/{graded}</small></td>;
                  })}
                  <td className={row.overconfident ? "ds-ins-bad" : ""}>{row.overconfident}</td>
                  <td>{row.unsure}</td>
                  {otherQs.map((q) => {
                    const cell = row.questions[q.key] ?? {};
                    const total = Object.values(cell).reduce((t, v) => t + v, 0);
                    const good = q.expect === "decline" ? cell.declined ?? 0 : cell.ok ?? 0;
                    return <td key={q.key} className={good < total ? "ds-ins-bad" : ""}>{q.expect === "decline" ? "declined" : "clean"} {good}/{total}</td>;
                  })}
                  {tries > 1 && <td>{row.consistent ? pct(row.consistent[0], row.consistent[1]) : "—"}</td>}
                  <td>{row.median_seconds ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {report.groups.length > 1 && (
        <div className="ds-scroll-x">
          <table className="ds-table ds-ins-table">
            <thead><tr><th>Group: labeled questions right</th>{models.map((m) => <th key={m}>{m}</th>)}</tr></thead>
            <tbody>
              {report.groups.map((row) => (
                <tr key={row.group}>
                  <td>{row.group}</td>
                  {models.map((model) => {
                    const [right, total] = row.models[model] ?? [0, 0];
                    const share = total ? right / total : 0;
                    return (
                      <td key={model}>
                        <div className="ds-ins-bar" title={`${right} of ${total}`}><i style={{ width: `${Math.round(share * 100)}%` }} className={share >= 0.9 ? "ok" : share >= 0.6 ? "warn" : "bad"} /></div>
                        <small>{pct(right, total)}</small>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReviewList({ report, questions, images, act, busy, open, onOpen }: {
  report: InspectReport; questions: InspectQuestion[]; images: Artifact[]; act: RunViewProps["act"]; busy: string | null;
  open: boolean; onOpen: (id: string) => void;
}) {
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [fixes, setFixes] = useState<Record<string, string>>({});
  const done = report.disagreements.filter((d) => d.resolution).length;
  if (!report.disagreements.length) return <Banner kind="ok">Every answer matched your labels. Nothing to review.</Banner>;
  return (
    <div className="ds-stack" style={{ gap: 8 }}>
      <div className="ds-row between">
        <span className="ds-small">{done} of {report.disagreements.length} reviewed</span>
        <div style={{ width: 180 }}><Progress value={(100 * done) / report.disagreements.length} /></div>
      </div>
      {report.disagreements.map((item) => {
        const key = `${item.image_id}:${item.question}`;
        const question = questions.find((q) => q.key === item.question);
        const image = images.find((a) => a.id === item.image_id);
        const options = question ? labelOptions(question).filter((o) => o !== item.label) : [];
        const fixTo = fixes[key] ?? options[0] ?? "";
        return (
          <div key={key} className={`ds-ins-item${item.resolution ? " done" : ""}`}>
            <button type="button" className="ds-media-btn" onClick={() => onOpen(item.image_id)} aria-label={`Open ${item.image}`}>
              {image?.thumb_sha && <img src={mediaUrl(image.thumb_sha)} alt="" />}
            </button>
            <div className="ds-stack" style={{ gap: 6, minWidth: 0 }}>
              <div className="ds-row ds-small">
                <b>{item.image}</b>{item.group && <span className="ds-chip info">{item.group}</span>}
                <span title={question?.text}>{question?.short}: label <b>{item.label || "—"}</b></span>
                {item.resolution && <span className={`ds-chip ${item.resolution.outcome === "fixed" ? "or" : "ok"}`}>{item.resolution.outcome === "fixed" ? `fixed: ${item.resolution.was} → ${item.resolution.value}` : "label stands"}</span>}
              </div>
              <div className="ds-row" style={{ gap: 4 }}>
                {item.answers.map((answer) => (
                  <span key={`${answer.model}-${answer.try}`} className={`ds-chip ${markOf(answer.grade).tone}`} title={markOf(answer.grade).text}>
                    <span className="ds-mono">{answer.model}</span>{answer.try ? ` t${answer.try}` : ""}: {answer.value || "—"}
                  </span>
                ))}
              </div>
              {item.resolution?.note && <span className="ds-tiny ds-muted">Note: {item.resolution.note}</span>}
              {open && (
                <div className="ds-row">
                  <input aria-label="Review note" value={notes[key] ?? ""} onChange={(e) => setNotes({ ...notes, [key]: e.target.value })} placeholder="Note (optional)" style={{ flex: "1 1 180px" }} />
                  <button type="button" className="ds-btn sm good" disabled={busy !== null} onClick={() => void act("resolve", { image_id: item.image_id, question: item.question, outcome: "keep", note: notes[key] ?? "" })}>Label stands</button>
                  {options.length > 0 && (
                    <>
                      <select aria-label="Fix the label to" value={fixTo} onChange={(e) => setFixes({ ...fixes, [key]: e.target.value })} style={{ width: "auto" }}>
                        {options.map((option) => <option key={option}>{option}</option>)}
                      </select>
                      <button type="button" className="ds-btn sm warn" disabled={busy !== null || !fixTo} onClick={() => void act("resolve", { image_id: item.image_id, question: item.question, outcome: "fix", value: fixTo, note: notes[key] ?? "" })}>Fix label</button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const DEFAULT_POLICY: InspectPolicy = { identity: "refuse", retention_days: 30, access: "", signoff: "yes", notice: "yes", note: "" };

function PolicyForm({ step, act, busy, setApproveExtra }: { step: RunViewProps["detail"]["steps"][number] } & Pick<RunViewProps, "act" | "busy" | "setApproveExtra">) {
  const saved = step.data.policy;
  const [policy, setPolicy] = useState<InspectPolicy>(saved ?? DEFAULT_POLICY);
  const set = (patch: Partial<InspectPolicy>) => setPolicy((current) => ({ ...current, ...patch }));
  const waiting = step.status === "waiting";
  useEffect(() => {
    if (!waiting) return;
    setApproveExtra(() => ({ policy }));
    return () => setApproveExtra(null);
  }, [policy, waiting, setApproveExtra]);
  if (!waiting && saved) {
    return (
      <dl className="ds-kv">
        <dt>Identity questions</dt><dd>{saved.identity === "refuse" ? "Refused: no questions about who people are, no plates or faces" : "Allowed"}</dd>
        <dt>Keep images</dt><dd>{saved.retention_days ? `${saved.retention_days} days` : "Not kept"}</dd>
        <dt>Who may search</dt><dd>{saved.access}</dd>
        <dt>Sign-off before action</dt><dd>{saved.signoff === "yes" ? "Yes, a person approves" : "No"}</dd>
        <dt>Public notice</dt><dd>{saved.notice === "yes" ? "Yes" : "No"}</dd>
        {saved.note && <><dt>Note</dt><dd>{saved.note}</dd></>}
      </dl>
    );
  }
  const seg = (name: string, value: string, options: Array<[string, string]>, onPick: (v: string) => void) => (
    <div className="ds-seg" role="radiogroup" aria-label={name}>
      {options.map(([key, text]) => <button key={key} type="button" role="radio" aria-checked={value === key} className={value === key ? "on" : ""} onClick={() => onPick(key)}>{text}</button>)}
    </div>
  );
  return (
    <div className="ds-stack" style={{ gap: 4 }}>
      <label>May staff ask these images about identity (who a person is, faces, license plates)?</label>
      {seg("Identity questions", policy.identity, [["refuse", "No, refuse"], ["allow", "Yes, allow"]], (v) => set({ identity: v as InspectPolicy["identity"] }))}
      <div className="ds-grid2">
        <div>
          <label htmlFor="ins-retention">Keep images for (days, 0 = not kept)</label>
          <input id="ins-retention" type="number" min={0} max={3650} value={policy.retention_days} onChange={(e) => set({ retention_days: Math.max(0, Math.min(3650, Number(e.target.value) || 0)) })} />
        </div>
        <div>
          <label htmlFor="ins-access">Who may search the images?</label>
          <input id="ins-access" value={policy.access} onChange={(e) => set({ access: e.target.value })} placeholder="e.g. operations staff on duty" />
        </div>
      </div>
      <div className="ds-grid2">
        <div><label>A person signs off before any action?</label>{seg("Sign-off", policy.signoff, [["yes", "Yes"], ["no", "No"]], (v) => set({ signoff: v as "yes" | "no" }))}</div>
        <div><label>Publish a public notice about the cameras?</label>{seg("Public notice", policy.notice, [["yes", "Yes"], ["no", "No"]], (v) => set({ notice: v as "yes" | "no" }))}</div>
      </div>
      <label htmlFor="ins-note">Note (e.g. the vote)</label>
      <textarea id="ins-note" value={policy.note} onChange={(e) => set({ note: e.target.value })} style={{ minHeight: 60 }} />
      <div className="ds-row" style={{ marginTop: 8 }}>
        <button type="button" className="ds-btn sm" disabled={busy !== null || policy.access.trim().length < 2} onClick={() => void act("save_policy", { policy })}>Save rules</button>
        <span className="ds-tiny ds-muted">“Approve & continue” above saves them and writes the report.</span>
      </div>
    </div>
  );
}

export default function InspectRun(props: RunViewProps) {
  const { detail, act, busy, setApproveExtra } = props;
  const brief = detail.run.brief;
  const questions = useMemo(() => brief.questions ?? [], [brief.questions]);
  const models = useMemo(() => brief.models ?? [], [brief.models]);
  const tries = brief.tries ?? 1;
  const steps = Object.fromEntries(detail.steps.map((step) => [step.key, step]));
  const images = detail.artifacts.filter((a) => a.kind === "image");
  const answers = detail.artifacts.filter((a) => a.kind === "answer" && a.status !== "superseded");
  const lives = detail.artifacts.filter((a) => a.kind === "live");
  const report = steps.check?.data.report as InspectReport | undefined;
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState(questions.find((q) => q.expect === "label")?.key ?? questions[0]?.key ?? "q1");
  const [group, setGroup] = useState("all");
  const groups = Array.from(new Set(images.map((image) => String(image.data.group ?? "")).filter(Boolean)));
  const byImage = useMemo(() => {
    const map = new Map<string, Artifact[]>();
    answers.forEach((a) => map.set(a.parent_id ?? "", [...(map.get(a.parent_id ?? "") ?? []), a]));
    return map;
  }, [answers]);
  const finished = answers.filter((a) => a.status !== "queued" && a.status !== "running").length;
  const failed = answers.filter((a) => a.status === "failed").length;
  const question = questions.find((q) => q.key === focus) ?? questions[0];
  const shown = images.filter((image) => group === "all" || image.data.group === group);
  const selectedImage = images.find((image) => image.id === selected) ?? null;
  const reportArt = detail.artifacts.find((a) => a.kind === "report" && a.status !== "superseded");
  const table = detail.artifacts.find((a) => a.kind === "table" && a.status !== "superseded");
  const setupWaiting = steps.setup?.status === "waiting";
  const answersOf = (imageId: string, model: string) => (byImage.get(imageId) ?? []).filter((a) => a.params.model === model);

  return (
    <div className="ds-stack">
      <section id="step-setup" className="ds-card">
        <h3>Images, questions, labels {setupWaiting && <ReviewTag waiting />}</h3>
        <p className="ds-small" style={{ marginBottom: 8 }}><b>Brief:</b> {brief.brief}</p>
        <div className="ds-row ds-small" style={{ marginBottom: 8 }}>
          <span className="ds-chip info">{images.length} images</span>
          {models.map((m) => <span key={m} className="ds-chip model">{m}</span>)}
          <span className="ds-chip">{tries} {tries === 1 ? "try" : "tries"} each</span>
          {steps.setup?.data.calls ? <span className="ds-chip">{steps.setup.data.calls} calls</span> : null}
          <span className="ds-chip">{images.filter((a) => (a.metrics.c2pa as { present?: boolean } | undefined)?.present).length} with Content Credentials</span>
        </div>
        {steps.setup?.data.prompt && (
          <details open={setupWaiting}>
            <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Sent with every image</summary>
            <div className="ds-promptbox scroll" style={{ marginTop: 6, whiteSpace: "pre-wrap" }}><b>Instructions:</b> {steps.setup.data.system}{"\n\n"}{steps.setup.data.prompt}</div>
          </details>
        )}
        {setupWaiting && <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>Open any image to check or change its labels. Approve to send every image to every model.</p>}
      </section>

      {steps.ask && steps.ask.status !== "pending" && (
        <section id="step-ask" className="ds-card">
          <div className="ds-row between">
            <h3 style={{ margin: 0 }}>Answers {steps.ask.status === "running" && <Spinner />}</h3>
            <span className="ds-small ds-muted">{finished} of {answers.length} answered{failed ? ` · ${failed} failed` : ""}</span>
          </div>
          {steps.ask.status === "running" && <div style={{ marginTop: 8 }}><Progress value={answers.length ? (100 * finished) / answers.length : 0} /></div>}
        </section>
      )}

      <section id="step-check" className="ds-card">
        <div className="ds-ins-bar-top">
          <div className="ds-seg" role="radiogroup" aria-label="Question">
            {questions.map((q) => <button key={q.key} type="button" role="radio" aria-checked={q.key === focus} className={q.key === focus ? "on" : ""} title={q.text} onClick={() => setFocus(q.key)}>{q.short}</button>)}
          </div>
          {groups.length > 1 && (
            <div className="ds-seg" role="radiogroup" aria-label="Group">
              {["all", ...groups].map((g) => <button key={g} type="button" role="radio" aria-checked={g === group} className={g === group ? "on" : ""} onClick={() => setGroup(g)}>{g === "all" ? "All" : g}</button>)}
            </div>
          )}
        </div>
        {question && <p className="ds-small" style={{ margin: "8px 0" }}><b>{question.short}:</b> {question.text}{question.expect === "decline" ? " · the right behaviour is to decline" : question.expect === "none" ? ` · flag terms: ${question.flag_terms.slice(0, 8).join(", ")}${question.flag_terms.length > 8 ? "…" : ""}` : ""}</p>}
        <div className="ds-ins-legend ds-tiny">
          {(question?.expect === "label" ? ["correct", "wrong", "overconfident", "unsure"] : question?.expect === "decline" ? ["declined", "breach"] : ["ok", "flagged"]).map((g) => <span key={g} className={`ds-chip ${markOf(g).tone}`}>{markOf(g).text}</span>)}
          {tries > 1 && <span className="ds-muted">dots = tries · “varies” = not the same every try</span>}
        </div>
        <div className="ds-ins-grid">
          {shown.map((image) => {
            const truth = truthOf(image);
            return (
              <button key={image.id} type="button" className="ds-ins-tile" onClick={() => setSelected(image.id)} aria-label={`Open ${image.label}`}>
                <span className="ds-ins-img">
                  {image.thumb_sha && <img src={mediaUrl(image.thumb_sha)} alt="" loading="lazy" />}
                  {String(image.data.group ?? "") && <span className="ds-ins-group">{String(image.data.group)}</span>}
                </span>
                <span className="ds-ins-meta">
                  <span className="ds-ins-name">{image.label}</span>
                  {question?.expect === "label" && <span className="ds-ins-label">Label <b>{truth[question.key] ?? "—"}</b>{record(image.data.fixes)[question.key] ? " (fixed)" : ""}</span>}
                  {answers.length > 0 && models.map((model) => (
                    <span key={model} className="ds-ins-row"><span className="m">{model}</span><AnswerChip items={triesOf(answersOf(image.id, model), question?.key ?? "")} /></span>
                  ))}
                </span>
              </button>
            );
          })}
        </div>
        {report && steps.check?.status === "done" && (
          <div style={{ marginTop: 14 }}>
            <h3>By model</h3>
            <Summary report={report} questions={questions} models={models} tries={tries} />
          </div>
        )}
      </section>

      {steps.review && steps.review.status !== "pending" && report && (
        <section id="step-review" className="ds-card">
          <h3>Review disagreements {steps.review.status === "waiting" && <ReviewTag waiting />}</h3>
          <p className="ds-tiny ds-muted" style={{ marginBottom: 8 }}>Every image and question where a model disagreed with your label. If the model was right, fix the label: all answers are marked again.</p>
          <ReviewList report={report} questions={questions} images={images} act={act} busy={busy} open={steps.review.status === "waiting"} onOpen={setSelected} />
        </section>
      )}

      {steps.policy && steps.policy.status !== "pending" && (
        <section id="step-policy" className="ds-card">
          <h3>Rules for asking {steps.policy.status === "waiting" && <ReviewTag waiting />}</h3>
          <PolicyForm step={steps.policy} act={act} busy={busy} setApproveExtra={setApproveExtra} />
        </section>
      )}

      {reportArt && (
        <section id="step-report" className="ds-card hl">
          <div className="ds-row between" style={{ marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Report</h3>
            <div className="ds-row">
              {reportArt.media_sha && <a className="ds-btn sm" href={mediaUrl(reportArt.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.json`)}><Download size={13} aria-hidden="true" /> Report (JSON)</a>}
              {table?.media_sha && <a className="ds-btn sm" href={mediaUrl(table.media_sha, `${detail.run.title.replace(/[^\w .-]+/g, "")}.csv`)}><Download size={13} aria-hidden="true" /> Every answer (CSV)</a>}
            </div>
          </div>
          {reportArt.status === "ready" ? <Checks checks={reportArt.checks} /> : <p className="ds-muted"><Spinner /> Writing the report…</p>}
          {steps.policy?.status === "done" && <button type="button" className="ds-btn sm" style={{ marginTop: 10 }} onClick={() => void act("reopen", { step: "policy" })}>Change the rules</button>}
        </section>
      )}

      {selectedImage && (
        <ImageDialog image={selectedImage} detail={detail} act={act} busy={busy} questions={questions} models={models}
          answers={answers} lives={lives} onClose={() => setSelected(null)} editable={setupWaiting} />
      )}
    </div>
  );
}
