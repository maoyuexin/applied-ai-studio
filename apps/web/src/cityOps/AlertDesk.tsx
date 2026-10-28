import { useMemo, useState } from "react";
import { Check, Info, Pencil, Play, X } from "lucide-react";
import type { AlertLanguage, AlertsReport, Artifact, Check as CheckItem, RunDetail } from "../design/api";
import { STORMS, dayTimeAt, fmtRecorded, type Storm } from "./data";
import {
  PREFERRED_MODEL,
  STATUS_TEXT,
  alertRequests,
  backOf,
  draftsFor,
  flagCount,
  flagsOf,
  gradesOf,
  messagesOf,
  rankDrafts,
  requestStatus,
  signoffOf,
  stepOf,
  type AlertRequest,
  type Messages,
  type RecordedRun,
  type RequestStatus,
  type Verdict,
} from "./runs";
import { ActionError, NotSent, Panel } from "./ui";

const PARTS: Array<{ key: string; label: string }> = [
  { key: "alert", label: "Public alert" },
  { key: "answer", label: "Answer to the resident" },
];
const VERDICT_TEXT: Record<Verdict, string> = { approve: "Approved", edit: "Approved with edits", reject: "Rejected" };
const RECOMMEND_WHY = "Recommended: the draft with the fewest flags across every language and check; ties go to "
  + `${PREFERRED_MODEL}, then to the earliest try. It is a starting point, not a decision.`;

interface Props {
  run: RecordedRun;
  detail: RunDetail;
  storm: Storm;
  step: number;
  showAll: boolean;
  setShowAll: (value: boolean) => void;
  selected: number | null;
  setSelected: (moment: number) => void;
  onJump: (stormId: string, step: number) => void;
}

export default function AlertDesk({ run, detail, storm, step, showAll, setShowAll, selected, setSelected, onJump }: Props) {
  const requests = useMemo(() => alertRequests(detail), [detail]);
  const languages = useMemo(() => detail.run.brief.languages ?? [], [detail.run.brief.languages]);
  const maxChars = detail.run.brief.max_chars ?? 160;
  const desk = stepOf(detail, "desk");
  const deskOpen = desk?.status === "waiting";
  const reached = (r: AlertRequest) => showAll || (r.storm.id === storm.id && step >= r.step);
  const visible = requests.filter((r) => showAll || r.storm.id === storm.id);
  const current = visible.find((r) => r.index === selected) ?? visible.find((r) => reached(r) && requestStatus(draftsFor(detail, r.index), true) === "awaiting") ?? visible[0];
  const [lang, setLang] = useState(languages[0]?.code ?? "en");
  const [focus, setFocus] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);

  const groups = STORMS.map((s) => ({ storm: s, items: visible.filter((r) => r.storm.id === s.id) })).filter((g) => g.items.length);
  const report = stepOf(detail, "check")?.data.report as AlertsReport | undefined;

  return (
    <div className="co-desk">
      <aside className="co-queue" aria-label="Alert requests">
        <header className="co-queue-head">
          <div>
            <span className="co-eyebrow">Public alert requests</span>
            <strong>{deskOpen ? "Sign-off desk open" : desk?.status === "done" ? "Sign-off desk closed" : "Sign-off desk"}</strong>
          </div>
          <label className="co-check"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show all</label>
        </header>
        {groups.map((group) => (
          <div key={group.storm.id} className="co-queue-group">
            {(showAll || group.storm.id !== storm.id) && <span className="co-queue-storm">{group.storm.name} {group.storm.year}</span>}
            {group.items.map((r) => {
              const status = requestStatus(draftsFor(detail, r.index), reached(r));
              return (
                <button key={r.index} type="button" className={`co-queue-item${current?.index === r.index ? " is-active" : ""}`}
                  onClick={() => { setSelected(r.index); setFocus(null); }} aria-current={current?.index === r.index}>
                  <span className="co-queue-time">{dayTimeAt(r.storm, r.step)}</span>
                  <strong>{r.question}</strong>
                  <span className={`co-status is-${status}`}>{STATUS_TEXT[status]}</span>
                </button>
              );
            })}
          </div>
        ))}
        {!visible.length && <p className="co-empty">No alert requests for this storm.</p>}
        <footer className="co-queue-foot">
          {report && <p className="co-dim">{report.counts.drafts} drafts recorded · {Object.values(report.models).reduce((t, m) => t + m.flagged, 0)} messages flagged by the checks</p>}
          {deskOpen ? (
            closing ? (
              <div className="co-confirm">
                <p>Close the sign-off desk? Drafts can no longer be signed here; unsigned drafts stay unsigned and the run writes its report.</p>
                <div className="co-row">
                  <button type="button" className="co-btn danger" disabled={run.busy !== null} onClick={() => void run.act("approve", { step: "desk" }).then((ok) => ok && setClosing(false))}>Close desk</button>
                  <button type="button" className="co-btn" onClick={() => setClosing(false)}>Cancel</button>
                </div>
              </div>
            ) : <button type="button" className="co-btn" onClick={() => setClosing(true)}>Close desk…</button>
          ) : desk?.status === "done" ? <p className="co-dim">Desk closed{desk.finished_at ? ` · ${fmtRecorded(desk.finished_at)}` : ""}. Reopen it in Design Studio if needed.</p> : null}
        </footer>
      </aside>
      <div className="co-desk-main">
        <ActionError run={run} />
        {current ? (
          reached(current)
            ? <RequestDetail key={current.index} run={run} detail={detail} request={current} languages={languages} lang={lang} setLang={setLang}
                maxChars={maxChars} deskOpen={deskOpen} focus={focus} setFocus={setFocus} />
            : (
              <Panel eyebrow={`${current.storm.name} · ${dayTimeAt(current.storm, current.step)}`} title="Upcoming request">
                <div className="co-upcoming">
                  <p>This request reaches the desk at <b>{dayTimeAt(current.storm, current.step)}</b> in the replay. Its facts and drafts stay hidden until then.</p>
                  <div className="co-row">
                    <button type="button" className="co-btn primary" onClick={() => onJump(current.storm.id, current.step)}><Play size={14} aria-hidden="true" /> Jump to {dayTimeAt(current.storm, current.step)}</button>
                    <button type="button" className="co-btn" onClick={() => setShowAll(true)}>Show all requests now</button>
                  </div>
                </div>
              </Panel>
            )
        ) : <p className="co-empty">No request selected.</p>}
      </div>
    </div>
  );
}

function RequestDetail({ run, detail, request, languages, lang, setLang, maxChars, deskOpen, focus, setFocus }: {
  run: RecordedRun; detail: RunDetail; request: AlertRequest; languages: AlertLanguage[]; lang: string; setLang: (code: string) => void;
  maxChars: number; deskOpen: boolean; focus: string | null; setFocus: (id: string | null) => void;
}) {
  const drafts = draftsFor(detail, request.index);
  const ranked = rankDrafts(drafts);
  const recommended = ranked[0] ?? null;
  const decided = ranked.find((d) => ["approve", "edit"].includes(signoffOf(d)?.verdict ?? ""));
  const lead = drafts.find((d) => d.id === focus) ?? decided ?? recommended;
  const others = ranked.filter((d) => d.id !== lead?.id);
  const status: RequestStatus = requestStatus(drafts, true);
  return (
    <div className="co-request">
      <Panel eyebrow={`${request.storm.name} · ${dayTimeAt(request.storm, request.step)}`} title={`Resident asks: “${request.question}”`}
        aside={<span className={`co-status is-${status}`}>{STATUS_TEXT[status]}</span>}>
        <div className="co-facts-grid">
          <div className="co-facts-box">
            <span className="co-eyebrow">Facts given to the models</span>
            <p>{request.moment.facts}</p>
          </div>
          {request.moment.note && (
            <details className="co-guidance">
              <summary>Reviewer guidance</summary>
              <p>{request.moment.note}</p>
            </details>
          )}
        </div>
      </Panel>
      {lead ? (
        <DraftCard key={lead.id} run={run} draft={lead} languages={languages} lang={lang} setLang={setLang} maxChars={maxChars} deskOpen={deskOpen}
          badge={lead.id === decided?.id ? "Decision" : lead.id === recommended?.id ? "Recommended" : "Selected"} />
      ) : <p className="co-empty">No drafts were recorded for this request.</p>}
      {others.length > 0 && (
        <details className="co-others" open={Boolean(focus)}>
          <summary>Other drafts ({others.length})</summary>
          <ul>
            {others.map((d) => {
              const signoff = signoffOf(d);
              const flags = flagCount(d);
              return (
                <li key={d.id}>
                  <button type="button" onClick={() => setFocus(d.id)}>
                    <span className="co-mono">{d.params.model} · try {d.params.try}</span>
                    <span className={`co-chip ${flags ? "is-warn" : "is-ok"}`}>{flags ? `${flags} flag${flags === 1 ? "" : "s"}` : "no flags"}</span>
                    {d.id === recommended?.id && <span className="co-chip">recommended</span>}
                    {signoff && <span className={`co-chip is-${signoff.verdict}`}>{VERDICT_TEXT[signoff.verdict]}</span>}
                    <span className="co-others-text" lang={lang}>{messagesOf(d).alert?.[lang] ?? ""}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </div>
  );
}

function CheckChips({ checks }: { checks: CheckItem[] | undefined }) {
  if (!checks) return null;
  const flagged = flagsOf(checks);
  const passed = checks.length - flagged.length;
  return (
    <span className="co-checks">
      {flagged.map((c) => <span key={c.key} className={`co-chip is-${c.state}`} title={c.basis}>{c.label}</span>)}
      {passed > 0 && <span className="co-chip is-ok" title={checks.filter((c) => !flagged.includes(c)).map((c) => c.label).join("\n")}>{flagged.length ? `${passed} other checks pass` : `All ${passed} checks pass`}</span>}
    </span>
  );
}

function DraftCard({ run, draft, languages, lang, setLang, maxChars, deskOpen, badge }: {
  run: RecordedRun; draft: Artifact; languages: AlertLanguage[]; lang: string; setLang: (code: string) => void;
  maxChars: number; deskOpen: boolean; badge: string;
}) {
  const messages = messagesOf(draft);
  const grades = gradesOf(draft);
  const back = backOf(draft);
  const signoff = signoffOf(draft);
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Messages>({});
  const [note, setNote] = useState("");
  const [needNote, setNeedNote] = useState(false);
  const busy = run.busy !== null;
  const original = (code: string, part: string) => messages[part]?.[code] ?? "";
  const current = (code: string, part: string) => edits[code]?.[part] ?? signoff?.edits?.[code]?.[part] ?? original(code, part);
  const edited = (code: string) => PARTS.some((p) => (edits[code]?.[p.key] ?? null) !== null && edits[code][p.key] !== original(code, p.key));
  const flags = flagCount(draft);
  const language = languages.find((l) => l.code === lang) ?? languages[0];

  const sign = async (verdict: Verdict) => {
    if (verdict === "reject" && !note.trim()) { setNeedNote(true); return; }
    const payload: Record<string, unknown> = { draft_id: draft.id, verdict, note: note.trim() };
    if (verdict === "edit") {
      payload.edits = Object.fromEntries(languages.map((l) => [l.code, Object.fromEntries(PARTS.map((p) => [p.key, current(l.code, p.key)]))]));
    }
    if (await run.act("sign", payload)) { setEditing(false); setEdits({}); setNote(""); setNeedNote(false); }
  };

  return (
    <section className="co-draft">
      <header className="co-draft-head">
        <div>
          <span className="co-eyebrow">
            {badge === "Recommended" ? <span className="co-recommend" title={RECOMMEND_WHY}>Recommended <Info size={12} aria-hidden="true" /></span> : badge}
          </span>
          <strong className="co-mono">{draft.params.model} · try {draft.params.try}</strong>
          <span className={`co-chip ${flags ? "is-warn" : "is-ok"}`}>{flags ? `${flags} flag${flags === 1 ? "" : "s"} across languages` : "No flags in any language"}</span>
        </div>
      </header>
      <div className="co-lang-tabs" role="tablist" aria-label="Language">
        {languages.map((l) => {
          const lf = PARTS.reduce((t, p) => t + flagsOf(grades[l.code]?.[p.key]).length, 0);
          return (
            <button key={l.code} type="button" role="tab" aria-selected={l.code === lang} className={l.code === lang ? "is-on" : ""} onClick={() => setLang(l.code)}>
              {l.name}{lf > 0 && <i className="co-dot is-warn" title={`${lf} flag(s)`} />}{editing && edited(l.code) && <i className="co-dot is-edit" title="Edited" />}
            </button>
          );
        })}
      </div>
      {language && PARTS.map((part) => {
        const text = current(language.code, part.key);
        const wasEdited = !editing && signoff?.edits?.[language.code]?.[part.key];
        const chars = Array.from(text).length;
        const english = back[language.code]?.[part.key];
        if (!messages[part.key]) return null;
        return (
          <div key={part.key} className="co-message">
            <div className="co-message-head">
              <span>{part.label}</span>
              {part.key === "alert" && <span className={chars > maxChars ? "co-over" : "co-dim"}>{chars} / {maxChars} characters</span>}
              <NotSent />
            </div>
            {editing ? (
              <textarea lang={language.code} aria-label={`${language.name} ${part.label}`} value={text} rows={part.key === "alert" ? 3 : 4}
                onChange={(e) => setEdits((cur) => ({ ...cur, [language.code]: { ...cur[language.code], [part.key]: e.target.value } }))} />
            ) : (
              <p className="co-message-text" lang={language.code}>
                {wasEdited ? <><s>{original(language.code, part.key)}</s><br /><b>{text}</b></> : text || <i className="co-dim">missing</i>}
              </p>
            )}
            {!editing && <CheckChips checks={grades[language.code]?.[part.key]} />}
            {english && language.code !== "en" && !editing && <p className="co-back"><span>Back-translation (English)</span> {english}</p>}
          </div>
        );
      })}
      {signoff && (
        <div className={`co-signoff is-${signoff.verdict}`}>
          <b>{VERDICT_TEXT[signoff.verdict]}</b> · signed at this desk {fmtRecorded(signoff.at)}
          {signoff.note && <p>Note: {signoff.note}</p>}
        </div>
      )}
      {deskOpen ? (
        <div className="co-sign">
          <label htmlFor={`note-${draft.id}`}>{signoff ? "Change the decision · note" : "Decision note"}{needNote && <span className="co-over"> · a note is required to reject</span>}</label>
          <input id={`note-${draft.id}`} value={note} onChange={(e) => { setNote(e.target.value); setNeedNote(false); }} placeholder="Why (required to reject)" />
          <div className="co-row">
            {editing ? (
              <>
                <button type="button" className="co-btn primary" disabled={busy} onClick={() => void sign("edit")}><Check size={14} aria-hidden="true" /> Approve with edits</button>
                <button type="button" className="co-btn" disabled={busy} onClick={() => { setEditing(false); setEdits({}); }}>Cancel edits</button>
              </>
            ) : (
              <>
                <button type="button" className="co-btn good" disabled={busy} onClick={() => void sign("approve")}><Check size={14} aria-hidden="true" /> Approve as written</button>
                <button type="button" className="co-btn" disabled={busy} onClick={() => setEditing(true)}><Pencil size={14} aria-hidden="true" /> Edit</button>
                <button type="button" className="co-btn danger" disabled={busy} onClick={() => void sign("reject")}><X size={14} aria-hidden="true" /> Reject</button>
              </>
            )}
          </div>
          <p className="co-dim">Nothing is sent. Your decision and any edits are the record.</p>
        </div>
      ) : <p className="co-dim co-sign">The sign-off desk is closed; decisions are read-only.</p>}
      <details className="co-raw-wrap">
        <summary>Exact model output</summary>
        <code className="co-raw-text">{String(draft.data.raw ?? draft.error ?? draft.status)}</code>
      </details>
    </section>
  );
}
