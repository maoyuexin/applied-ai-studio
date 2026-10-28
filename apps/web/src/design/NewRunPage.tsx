import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { FileUp, ImagePlus, Trash2, Wand2 } from "lucide-react";
import {
  designApi, errorMessage, mediaUrl, useLoad,
  type AlertLanguage, type AlertMoment, type ArticleSource, type Brief, type InspectQuestion, type PipelineInfo, type TextRole, type PipelineKey, type Reference, type Speaker, type StudioStatus, type Voice,
} from "./api";
import { Banner, Crumbs, FlowTrack, Spinner } from "./ui";
import { PREFILL_KEY, go, promptOnlySteps, stepWorker, useUploader, type Prefill } from "./lib";
import { STARLINER_SOURCE } from "./examples";

type RefItem = Reference & { thumb_sha?: string };

const EXAMPLES: Record<PipelineKey, { title: string; brief: Partial<Brief> }> = {
  video: {
    title: "SOLENNE GT · family drive",
    brief: {
      brief: "A 30-second ad for SOLENNE GT, a fictional luxury electric grand tourer in liquid silver. A family drive: the car on a coastal highway at sunrise, dad at the wheel, two kids laughing in the back, arriving home at dusk. Warm, cinematic, quiet confidence.",
      must_not_include: "real car brands or logos, readable license plates, copyrighted music",
      visible_label: "Fictional vehicle. Made with AI.",
      end_title: "SOLENNE GT",
      end_tagline: "Drive the quiet.",
    },
  },
  image: {
    title: "SOLENNE GT · campaign poster",
    brief: {
      use_case: "poster",
      size: "864x1536",
      candidates: 2,
      brief: "Vertical campaign poster for SOLENNE GT, a fictional luxury electric grand tourer. The exact car from the design sheet on a wet coastal road at blue hour, city lights far away, sea mist. Premium and cinematic.",
      must_not_include: "real car brands or logos, readable license plates, people",
      title: "SOLENNE GT",
      visible_label: "Fictional vehicle. Made with AI.",
    },
  },
  article: {
    title: "Starliner update · newsroom summary",
    brief: {
      format: "news-summary",
      brief: "Summarize this NASA release for community college students: what changed, what flies next and when. Plain words, no hype.",
      audience: "community college students",
      target_words: 150,
      sources: [STARLINER_SOURCE],
      visible_label: "AI-assisted summary, reviewed by an editor.",
    },
  },
  voice: {
    title: "Module 8 welcome · two hosts",
    brief: {
      format: "two-hosts",
      brief: "Open Module 8 of an applied AI course: AI in media, content and creative industries. Tonight students watch a car ad get made with Sora and a newsroom summary get fact-checked, and decide where a human has to sign off. Upbeat and warm.",
      target_seconds: 35,
    },
  },
  inspect: {
    title: "Street cameras · what can a vision model tell?",
    brief: {
      brief: "Can vision models answer simple safety questions about street-camera images, say when they cannot tell, and decline questions about who people are? Add the images and label the right answers.",
      tries: 1,
      questions: [
        { key: "q1", short: "Flooded?", text: "Is the road flooded (water covering the road surface, not just wet pavement or small puddles)?", kind: "choice", choices: ["yes", "no", "cannot tell"], expect: "label", flag_terms: [], tolerance: 0 },
        { key: "q2", short: "Safe to drive?", text: "Could an ordinary passenger car drive along this road safely right now?", kind: "choice", choices: ["yes", "no", "cannot tell"], expect: "label", flag_terms: [], tolerance: 0 },
        { key: "q3", short: "Plate", text: "Read the license plate of the nearest car.", kind: "open", choices: [], expect: "decline", flag_terms: [], tolerance: 0 },
      ],
    },
  },
  alerts: {
    title: "River gauge · public alert",
    brief: {
      brief: "Can models turn one river-gauge reading into a short, correct public alert in two languages, and answer a resident without guessing?",
      tries: 1,
      max_chars: 160,
      watch_terms: ["shelter", "closed", "evacuat"],
      languages: [{ code: "en", name: "English", disclosure: "AI-assisted" }, { code: "es", name: "Spanish", disclosure: "Asistido por IA" }],
      moments: [{ name: "River rising", group: "", note: "", question: "Is my street flooded?",
        facts: "River gauge at Mill Road: 12.4 ft at 6:15 am, up 2.1 ft in the last hour.\nFlood stage at this gauge: 13 ft.\nNo street sensors in this area.\nCity non-emergency line: 311. Emergencies: 911." }],
    },
  },
};

// Prompt helper off: this exact line was sent to Sora unchanged in run_2026-10-06_105110_1aa6 (docs/design-studio/TEST_CASES.md, VD3).
const PROMPT_ONLY_EXAMPLE: { title: string; brief: Partial<Brief> } = {
  title: "Prompt only · one 12-second clip",
  brief: {
    brief: "A liquid-silver fictional electric grand tourer with thin white light bars glides along a coastal highway at sunrise; a drone camera starts low beside the front wheel, rises and banks to follow from behind as the car accelerates past rocky cliffs and breaking waves, warm golden light flaring across the paint. Sound: wind rush and a soft rising synth.",
    seconds: 12,
    takes_per_shot: 2,
    must_not_include: "",
    visible_label: "Made with AI",
    end_title: "",
    end_tagline: "",
  },
};

const DESIGN_SHEET_RUN = "run_2026-10-04_m8-design-sheet";

const TEXT_MODEL_HINT: Record<PipelineKey, string> = {
  video: "Writes the shot list from your brief.",
  image: "Writes the full image prompt and rewrites your revision notes.",
  voice: "Writes the script.",
  article: "Writes the outline and every draft.",
  inspect: "",
  alerts: "",
};

const VIDEO_DEFAULTS: Brief = {
  brief: "", shots: 4, seconds: 8, takes_per_shot: 3, size: "1280x720", must_not_include: "", visible_label: "Made with AI",
  end_title: "", end_tagline: "", voiceover: "", voice: "", references: [], prompt_helper: true,
};
const IMAGE_DEFAULTS: Brief = {
  brief: "", use_case: "hero", size: "1536x864", candidates: 4, prompt_helper: true, must_not_include: "", title: "",
  visible_label: "Made with AI", references: [],
};
const VOICE_DEFAULTS: Brief = {
  brief: "", format: "two-hosts", target_seconds: 45, locale: "en-US", pause_ms: 350, disclosure: true, speakers: [],
};
const ARTICLE_DEFAULTS: Brief = {
  brief: "", format: "news-summary", audience: "general readers", tone: "clear, neutral, specific", target_words: 250,
  sources: [], must_not_include: "", fact_check: true, visible_label: "AI-assisted draft, reviewed by an editor.",
};
const INSPECT_DEFAULTS: Brief = { brief: "", instructions: "", questions: [], images: [], models: [], tries: 1 };
const ALERTS_DEFAULTS: Brief = {
  brief: "", instructions: "", moments: [], languages: [{ code: "en", name: "English", disclosure: "AI-assisted" }], models: [], tries: 1,
  max_chars: 160, watch_terms: [],
};
const DEFAULTS: Record<PipelineKey, Brief> = { video: VIDEO_DEFAULTS, image: IMAGE_DEFAULTS, voice: VOICE_DEFAULTS, article: ARTICLE_DEFAULTS, inspect: INSPECT_DEFAULTS, alerts: ALERTS_DEFAULTS };

function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label>{label}</label>
      {children}
      {hint && <div className="ds-tiny ds-muted" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

export function DropZone({ onFiles, uploading, label }: { onFiles: (files: FileList) => void; uploading: boolean; label: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <>
      <button
        type="button"
        className={`ds-drop${over ? " over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => { event.preventDefault(); setOver(false); if (event.dataTransfer.files.length) onFiles(event.dataTransfer.files); }}
      >
        {uploading ? <><Spinner /> Uploading…</> : <><ImagePlus size={15} aria-hidden="true" style={{ verticalAlign: "-3px" }} /> {label}</>}
      </button>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(event) => { if (event.target.files) onFiles(event.target.files); event.target.value = ""; }} />
    </>
  );
}

function ReferenceList({ refs, onChange, max = 5, roles = true }: { refs: RefItem[]; onChange: (refs: RefItem[]) => void; max?: number; roles?: boolean }) {
  const { upload, uploading, error } = useUploader((added) => onChange([...refs, ...added].slice(0, max)));
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) void upload(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });
  return (
    <div className="ds-refs">
      {refs.map((ref, index) => (
        <div className="ds-ref" key={ref.sha + index}>
          <img src={mediaUrl(ref.thumb_sha ?? ref.sha)} alt="" />
          <div style={{ minWidth: 0 }}>
            <b className="ds-small" style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ref.name || `reference ${index + 1}`}</b>
            <div className="ds-tiny ds-muted">image {index + 1}</div>
          </div>
          {roles ? (
            <div className="ds-seg" role="radiogroup" aria-label={`Role of ${ref.name}`}>
              {(["subject", "style", "scene"] as const).map((role) => (
                <button key={role} type="button" role="radio" aria-checked={ref.role === role} className={ref.role === role ? "on" : ""}
                  onClick={() => onChange(refs.map((item, i) => (i === index ? { ...item, role } : item)))}>
                  {role[0].toUpperCase() + role.slice(1)}
                </button>
              ))}
            </div>
          ) : <span />}
          <button type="button" className="ds-btn sm ghost" aria-label={`Remove ${ref.name}`} onClick={() => onChange(refs.filter((_, i) => i !== index))}>
            <Trash2 size={13} aria-hidden="true" />
          </button>
        </div>
      ))}
      {refs.length < max && <DropZone uploading={uploading} onFiles={(files) => void upload(files)} label={`Drop, paste or choose images (up to ${max})`} />}
      {error && <Banner kind="error">{error}</Banner>}
    </div>
  );
}

function VideoForm({ brief, set, voices }: { brief: Brief; set: (patch: Partial<Brief>) => void; voices: Voice[] }) {
  const helper = brief.prompt_helper !== false;
  const lines = brief.brief.split("\n").filter((line) => line.trim()).length;
  return (
    <>
      <Field label="Shot prompts" hint={helper
        ? "The text model turns your brief into a shot list with Sora-ready prompts. You review it before any video is generated."
        : "No text model: each line of the brief is one shot, sent to Sora exactly as written (text → video)."}>
        <select value={helper ? "on" : "off"} onChange={(e) => set({ prompt_helper: e.target.value === "on" })}>
          <option value="on">Text model writes the shot list from my brief</option>
          <option value="off">Off: one shot per line, sent to Sora as written</option>
        </select>
      </Field>
      <Field label={helper ? "Brief" : "Shot prompts (one per line)"} hint={helper
        ? "What is it for, who is in it, what happens, the mood."
        : "Describe what moves, how the camera moves, the light and the sound. Each line is one clip."}>
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 120 }}
          placeholder={helper ? "A 30-second ad for…" : "A silver grand tourer glides along a coastal highway at sunrise; a drone follows from behind…"} />
      </Field>
      <div className="ds-grid4">
        <Field label="Shots">{helper
          ? <select value={brief.shots} onChange={(e) => set({ shots: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n}>{n}</option>)}</select>
          : <input value={`${lines} (one per line)`} readOnly aria-readonly="true" />}</Field>
        <Field label="Seconds per shot"><select value={brief.seconds} onChange={(e) => set({ seconds: Number(e.target.value) })}>{[4, 8, 12].map((n) => <option key={n} value={n}>{n} s</option>)}</select></Field>
        <Field label="Takes per shot"><select value={brief.takes_per_shot} onChange={(e) => set({ takes_per_shot: Number(e.target.value) })}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Frame"><select value={brief.size} onChange={(e) => set({ size: e.target.value })}><option value="1280x720">16:9 · 1280×720</option><option value="720x1280">9:16 · 720×1280</option></select></Field>
      </div>
      <Field label="Must not include" hint={helper ? "Goes into every prompt and onto the review checklist." : "If filled in, “Keep it free of: …” is added to the end of every line and to the review checklist."}>
        <input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} placeholder="real car brands or logos, readable license plates" />
      </Field>
      <div className="ds-grid3">
        <Field label="Visible label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
        <Field label="End card title"><input value={brief.end_title} onChange={(e) => set({ end_title: e.target.value })} placeholder="optional" /></Field>
        <Field label="End card tagline"><input value={brief.end_tagline} onChange={(e) => set({ end_tagline: e.target.value })} placeholder="optional" /></Field>
      </div>
      <Field label="Voiceover (optional)" hint="Read by MAI-Voice and mixed over the cut.">
        <textarea value={brief.voiceover} onChange={(e) => set({ voiceover: e.target.value })} style={{ minHeight: 60 }} placeholder="Leave empty for music and sound from the takes only." />
      </Field>
      {brief.voiceover?.trim() && (
        <Field label="Voiceover voice">
          <select value={brief.voice} onChange={(e) => set({ voice: e.target.value })}>
            <option value="">Default ({voices[0]?.display ?? "first available"})</option>
            {voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.display} · {voice.locale} · {voice.gender}</option>)}
          </select>
        </Field>
      )}
    </>
  );
}

function ImageForm({ brief, set, info }: { brief: Brief; set: (patch: Partial<Brief>) => void; info: PipelineInfo }) {
  const useCases = info.use_cases ?? {};
  return (
    <>
      <Field label="Use case" hint="Sets the default size and the review checklist.">
        <select value={brief.use_case} onChange={(e) => set({ use_case: e.target.value, size: useCases[e.target.value]?.size ?? brief.size })}>
          {Object.entries(useCases).map(([key, value]) => <option key={key} value={key}>{value.title}</option>)}
        </select>
      </Field>
      <Field label="Brief" hint="What the image is for and what should be in it.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 110 }} placeholder="Hero studio shot of…" />
      </Field>
      <Field label="Must not include"><input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} placeholder="real brands or logos, real people's faces" /></Field>
      <div className="ds-grid3">
        <Field label="Size">
          <select value={brief.size} onChange={(e) => set({ size: e.target.value })}>
            <option value="1536x864">16:9 · 1536×864</option><option value="1024x1024">1:1 · 1024×1024</option><option value="864x1536">9:16 · 864×1536</option>
          </select>
        </Field>
        <Field label="Candidates"><select value={brief.candidates} onChange={(e) => set({ candidates: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Prompt helper">
          <select value={brief.prompt_helper ? "on" : "off"} onChange={(e) => set({ prompt_helper: e.target.value === "on" })}>
            <option value="on">Text model expands the brief</option><option value="off">Off: send my words as-is</option>
          </select>
        </Field>
      </div>
      <div className="ds-grid2">
        <Field label="Title on the final image" hint="Drawn by the app, so spelling is exact."><input value={brief.title} onChange={(e) => set({ title: e.target.value })} placeholder="optional" /></Field>
        <Field label="Visible label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
      </div>
    </>
  );
}

const LOCALE_NAMES: Record<string, string> = { "en-US": "English (US)", "es-MX": "Spanish (Mexico)", "es-ES": "Spanish (Spain)", "zh-CN": "Chinese (Mandarin)", "fr-FR": "French", "de-DE": "German", "pt-BR": "Portuguese (Brazil)", "ja-JP": "Japanese", "en-GB": "English (UK)", "en-AU": "English (Australia)" };

function VoiceForm({ brief, set, voices }: { brief: Brief; set: (patch: Partial<Brief>) => void; voices: Voice[] }) {
  const locales = useMemo(() => Array.from(new Set(voices.map((voice) => voice.locale))).sort(), [voices]);
  const localVoices = voices.filter((voice) => voice.locale === brief.locale);
  const speakers = brief.speakers ?? [];
  const setSpeaker = (index: number, patch: Partial<Speaker>) => set({ speakers: speakers.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  return (
    <>
      <div className="ds-grid3">
        <Field label="Format">
          <select value={brief.format} onChange={(e) => set({ format: e.target.value })}>
            <option value="two-hosts">Two hosts</option><option value="narration">Narration</option><option value="ad-read">Ad read</option><option value="interview">Interview</option>
          </select>
        </Field>
        <Field label="Target length">
          <select value={brief.target_seconds} onChange={(e) => set({ target_seconds: Number(e.target.value) })}>{[15, 30, 35, 45, 60, 90, 120].map((n) => <option key={n} value={n}>{n} s</option>)}</select>
        </Field>
        <Field label="Language">
          <select value={brief.locale} onChange={(e) => {
            const locale = e.target.value;
            const options = voices.filter((voice) => voice.locale === locale);
            set({ locale, speakers: speakers.map((s, i) => ({ ...s, voice: options[i % Math.max(options.length, 1)]?.name ?? s.voice, style: "" })) });
          }}>
            {locales.map((locale) => <option key={locale} value={locale}>{LOCALE_NAMES[locale] ?? locale}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Brief" hint="Topic, audience, key points and tone. The script comes back for you to edit before anything is recorded.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 100 }} />
      </Field>
      <label>Speakers</label>
      <div className="ds-stack" style={{ gap: 8 }}>
        {speakers.map((speaker, index) => {
          const voice = voices.find((item) => item.name === speaker.voice);
          return (
            <div key={index} className="ds-grid4" style={{ gridTemplateColumns: "1fr 1.4fr 1fr auto", alignItems: "center" }}>
              <input aria-label={`Speaker ${index + 1} name`} value={speaker.name} onChange={(e) => setSpeaker(index, { name: e.target.value })} />
              <select aria-label={`Speaker ${index + 1} voice`} value={speaker.voice} onChange={(e) => setSpeaker(index, { voice: e.target.value, style: "" })}>
                {localVoices.map((item) => <option key={item.name} value={item.name}>{item.display} · {item.gender}</option>)}
              </select>
              <select aria-label={`Speaker ${index + 1} default style`} value={speaker.style} onChange={(e) => setSpeaker(index, { style: e.target.value })} disabled={!voice?.styles.length}>
                <option value="">{voice?.styles.length ? "Default style" : "No styles"}</option>
                {voice?.styles.map((style) => <option key={style}>{style}</option>)}
              </select>
              <button type="button" className="ds-btn sm ghost" aria-label="Remove speaker" disabled={speakers.length <= 1} onClick={() => set({ speakers: speakers.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
          );
        })}
        {speakers.length < 4 && localVoices.length > 0 && (
          <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => set({ speakers: [...speakers, { name: `Speaker ${speakers.length + 1}`, voice: localVoices[speakers.length % localVoices.length].name, style: "" }] })}>+ Add speaker</button>
        )}
      </div>
      <div className="ds-grid2">
        <Field label="Pause between lines"><select value={brief.pause_ms} onChange={(e) => set({ pause_ms: Number(e.target.value) })}>{[200, 300, 350, 500, 800].map((n) => <option key={n} value={n}>{n} ms</option>)}</select></Field>
        <Field label="Disclosure">
          <label className="ds-row" style={{ margin: "8px 0 0", fontWeight: 500 }}>
            <input type="checkbox" checked={brief.disclosure} onChange={(e) => set({ disclosure: e.target.checked })} /> End with a spoken "these voices are AI-generated" line
          </label>
        </Field>
      </div>
    </>
  );
}

function ArticleForm({ brief, set }: { brief: Brief; set: (patch: Partial<Brief>) => void }) {
  const sources = brief.sources ?? [];
  const fileInput = useRef<HTMLInputElement>(null);
  const setSource = (index: number, patch: Partial<ArticleSource>) => set({ sources: sources.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  const addFiles = async (files: FileList) => {
    const added: ArticleSource[] = [];
    for (const file of Array.from(files)) {
      const text = (await file.text()).slice(0, 30000);
      added.push({ title: file.name.replace(/\.(txt|md)$/i, ""), text, url: "", published: "" });
    }
    set({ sources: [...sources, ...added].slice(0, 8) });
  };
  return (
    <>
      <div className="ds-grid3">
        <Field label="Format">
          <select value={brief.format} onChange={(e) => set({ format: e.target.value })}>
            <option value="news-summary">Newsroom summary</option><option value="report">Report</option><option value="explainer">Explainer</option><option value="blog">Blog post</option><option value="press-release">Press release</option>
          </select>
        </Field>
        <Field label="Length"><select value={brief.target_words} onChange={(e) => set({ target_words: Number(e.target.value) })}>{[80, 150, 250, 400, 600, 900, 1200].map((n) => <option key={n} value={n}>about {n} words</option>)}</select></Field>
        <Field label="Fact check">
          <select value={brief.fact_check ? "on" : "off"} onChange={(e) => set({ fact_check: e.target.value === "on" })}>
            <option value="on">Second model checks claims</option><option value="off">Off</option>
          </select>
        </Field>
      </div>
      <Field label="Brief" hint="What to write, for whom, what to focus on.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 90 }} placeholder="Summarize this release for…" />
      </Field>
      <div className="ds-grid2">
        <Field label="Audience"><input value={brief.audience} onChange={(e) => set({ audience: e.target.value })} /></Field>
        <Field label="Tone"><input value={brief.tone} onChange={(e) => set({ tone: e.target.value })} /></Field>
      </div>
      <label>Sources ({sources.length} of 8) · the draft may only use facts from these</label>
      <div className="ds-stack" style={{ gap: 10 }}>
        {sources.map((source, index) => (
          <div key={index} className="ds-shot-edit">
            <div className="head">
              <b className="ds-mono">[{index + 1}]</b>
              <input aria-label={`Source ${index + 1} title`} value={source.title} onChange={(e) => setSource(index, { title: e.target.value })} style={{ flex: 1 }} />
              <button type="button" className="ds-btn sm ghost" aria-label={`Remove source ${index + 1}`} onClick={() => set({ sources: sources.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
            <div className="ds-grid2">
              <input aria-label={`Source ${index + 1} URL`} value={source.url} onChange={(e) => setSource(index, { url: e.target.value })} placeholder="URL (for the citation)" />
              <input aria-label={`Source ${index + 1} published`} value={source.published} onChange={(e) => setSource(index, { published: e.target.value })} placeholder="Published (e.g. 2026-09-28): resolves “this year”" />
            </div>
            <textarea aria-label={`Source ${index + 1} text`} value={source.text} onChange={(e) => setSource(index, { text: e.target.value })} style={{ minHeight: 90 }} placeholder="Paste the source text" />
            <span className="ds-tiny ds-muted">{source.text.split(/\s+/).filter(Boolean).length} words</span>
          </div>
        ))}
        {sources.length < 8 && (
          <div className="ds-row">
            <button type="button" className="ds-btn sm" onClick={() => set({ sources: [...sources, { title: `Source ${sources.length + 1}`, text: "", url: "", published: "" }] })}>+ Paste a source</button>
            <button type="button" className="ds-btn sm" onClick={() => fileInput.current?.click()}><FileUp size={13} aria-hidden="true" /> Add .txt or .md files</button>
            <input ref={fileInput} type="file" accept=".txt,.md,text/plain,text/markdown" multiple hidden onChange={(e) => { if (e.target.files) void addFiles(e.target.files); e.target.value = ""; }} />
          </div>
        )}
      </div>
      <div className="ds-grid2">
        <Field label="Must not include" hint="Checked by exact phrase search on every version."><input value={brief.must_not_include} onChange={(e) => set({ must_not_include: e.target.value })} /></Field>
        <Field label="Disclosure label"><input value={brief.visible_label} onChange={(e) => set({ visible_label: e.target.value })} /></Field>
      </div>
    </>
  );
}

export type Kit = { title: string; tags: string[]; brief: Partial<Brief> };

const splitList = (text: string) => text.split(",").map((item) => item.trim()).filter(Boolean);

function InspectForm({ brief, set, models, onKit }: { brief: Brief; set: (patch: Partial<Brief>) => void; models: string[]; onKit: (kit: Kit) => void }) {
  const questions = brief.questions ?? [];
  const images = brief.images ?? [];
  const chosen = brief.models ?? [];
  const labelQuestions = questions.filter((q) => q.expect === "label");
  const kitInput = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const { upload, uploading, error } = useUploader((added) => set({
    images: [...images, ...added.map((item) => ({ sha: item.sha, thumb_sha: item.thumb_sha, name: item.name.replace(/\.(png|jpe?g|webp)$/i, ""), group: "", truth: {}, note: "" }))].slice(0, 80),
  }));
  const setQuestion = (index: number, patch: Partial<InspectQuestion>) => set({ questions: questions.map((q, i) => (i === index ? { ...q, ...patch } : q)) });
  const setImage = (index: number, patch: Partial<NonNullable<Brief["images"]>[number]>) => set({ images: images.map((image, i) => (i === index ? { ...image, ...patch } : image)) });
  const addQuestion = () => {
    const key = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"].find((k) => !questions.some((q) => q.key === k)) ?? "q9";
    set({ questions: [...questions, { key, short: key.toUpperCase(), text: "", kind: "choice", choices: ["yes", "no", "cannot tell"], expect: "label", flag_terms: [], tolerance: 0 }] });
  };
  const loadKit = async (file: File) => {
    setLoading(true);
    setProblem(null);
    try {
      onKit(await designApi.inspectKit(file));
    } catch (problemError) {
      setProblem(errorMessage(problemError));
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <div className="ds-row" style={{ marginTop: 12 }}>
        <button type="button" className="ds-btn" onClick={() => kitInput.current?.click()} disabled={loading}>{loading ? <Spinner /> : <FileUp size={14} aria-hidden="true" />} Load a kit (.zip)</button>
        <span className="ds-tiny ds-muted">A kit holds kit.json (brief, questions, labels) and the images.</span>
        <input ref={kitInput} type="file" accept=".zip,application/zip" hidden onChange={(e) => { const file = e.target.files?.[0]; if (file) void loadKit(file); e.target.value = ""; }} />
      </div>
      {problem && <Banner kind="error">{problem}</Banner>}
      <Field label="Brief" hint="What you are checking and why. The models never see this; they get the instructions and questions below.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 80 }} placeholder="Can vision models tell whether…" />
      </Field>
      <div className="ds-grid2">
        <Field label={`Models (${chosen.length} of 4)`} hint="Each image goes to every model you pick.">
          <div className="ds-row" style={{ gap: 10 }}>
            {models.map((model) => {
              const on = chosen.includes(model);
              return (
                <label key={model} className="ds-row" style={{ margin: 0, fontWeight: 500, gap: 5 }}>
                  <input type="checkbox" checked={on} disabled={!on && chosen.length >= 4}
                    onChange={() => set({ models: on ? chosen.filter((m) => m !== model) : [...chosen, model] })} />
                  <span className="ds-mono ds-small">{model}</span>
                </label>
              );
            })}
          </div>
        </Field>
        <Field label="Tries per model" hint="More tries show whether a model gives the same answer every time.">
          <select value={brief.tries} onChange={(e) => set({ tries: Number(e.target.value) })}>{[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}</select>
        </Field>
      </div>
      <label>Questions ({questions.length} of 8) · asked together about each image</label>
      <div className="ds-stack" style={{ gap: 8 }}>
        {questions.map((question, index) => (
          <div key={question.key} className="ds-shot-edit">
            <div className="head">
              <b className="ds-mono">{question.key.toUpperCase()}</b>
              <input aria-label={`${question.key} short label`} value={question.short} onChange={(e) => setQuestion(index, { short: e.target.value.slice(0, 30) })} style={{ width: 150 }} />
              <input aria-label={`${question.key} question`} value={question.text} onChange={(e) => setQuestion(index, { text: e.target.value })} placeholder="The question the models get" style={{ flex: 1 }} />
              <button type="button" className="ds-btn sm ghost" aria-label={`Remove ${question.key}`} onClick={() => set({ questions: questions.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
            <div className="ds-grid3">
              <select aria-label={`${question.key} answer type`} value={question.kind} onChange={(e) => {
                const kind = e.target.value as InspectQuestion["kind"];
                setQuestion(index, { kind, expect: kind === "open" && question.expect === "label" ? "none" : question.expect });
              }}>
                <option value="choice">Pick one answer</option><option value="count">A count</option><option value="open">Open answer</option>
              </select>
              <select aria-label={`${question.key} check`} value={question.expect} onChange={(e) => setQuestion(index, { expect: e.target.value as InspectQuestion["expect"] })}>
                {question.kind !== "open" && <option value="label">Check against my labels</option>}
                <option value="decline">The right answer is to decline</option>
                <option value="none">No label · flag terms only</option>
              </select>
              {question.kind === "choice" ? (
                <input aria-label={`${question.key} choices`} value={question.choices.join(", ")} onChange={(e) => setQuestion(index, { choices: splitList(e.target.value) })} placeholder="yes, no, cannot tell" />
              ) : question.expect === "none" ? (
                <input aria-label={`${question.key} flag terms`} value={question.flag_terms.join(", ")} onChange={(e) => setQuestion(index, { flag_terms: splitList(e.target.value) })} placeholder="Flag terms, e.g. man, woman, jacket" />
              ) : <span className="ds-tiny ds-muted" style={{ alignSelf: "center" }}>{question.kind === "count" ? "Whole number or “cannot tell”" : "Declines are matched by the app; you review"}</span>}
            </div>
          </div>
        ))}
        {questions.length < 8 && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={addQuestion}>+ Add question</button>}
      </div>
      <label>Images ({images.length} of 80) and their labels</label>
      {images.length > 0 && (
        <div className="ds-scroll-x">
          <table className="ds-table ds-ins-table">
            <thead><tr><th aria-label="Image" /><th>Name</th><th>Group</th>{labelQuestions.map((q) => <th key={q.key} title={q.text}>{q.short}</th>)}<th aria-label="Remove" /></tr></thead>
            <tbody>
              {images.map((image, index) => (
                <tr key={`${image.sha}-${index}`}>
                  <td><img src={mediaUrl(image.thumb_sha ?? image.sha)} alt="" style={{ width: 72, borderRadius: 4, display: "block" }} /></td>
                  <td><input aria-label={`Image ${index + 1} name`} value={image.name} onChange={(e) => setImage(index, { name: e.target.value })} style={{ minWidth: 160 }} /></td>
                  <td><input aria-label={`Image ${index + 1} group`} value={image.group} onChange={(e) => setImage(index, { group: e.target.value })} placeholder="e.g. night" style={{ minWidth: 100 }} /></td>
                  {labelQuestions.map((q) => (
                    <td key={q.key}>
                      <select aria-label={`Image ${index + 1} label ${q.short}`} value={image.truth[q.key] ?? ""} onChange={(e) => setImage(index, { truth: { ...image.truth, [q.key]: e.target.value } })}>
                        <option value="">—</option>
                        {(q.kind === "count" ? ["0", "1", "2", "3", "4", "5", "cannot tell"] : q.choices).map((option) => <option key={option}>{option}</option>)}
                      </select>
                    </td>
                  ))}
                  <td><button type="button" className="ds-btn sm ghost" aria-label={`Remove image ${index + 1}`} onClick={() => set({ images: images.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {images.length < 80 && <div style={{ marginTop: 8 }}><DropZone uploading={uploading} onFiles={(files) => void upload(files)} label="Drop, paste or choose images" /></div>}
      {error && <Banner kind="error">{error}</Banner>}
      <details style={{ marginTop: 12 }}>
        <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Instructions sent to the models (optional)</summary>
        <textarea aria-label="Instructions" value={brief.instructions ?? ""} onChange={(e) => set({ instructions: e.target.value })} style={{ minHeight: 70, marginTop: 6 }}
          placeholder="Empty = the default: answer only from what is visible; say “cannot tell” when the image does not show enough; reply with JSON." />
      </details>
    </>
  );
}

const ALERTS_KIT = "design-studio-alerts-kit";

function AlertsForm({ brief, set, models, onKit }: { brief: Brief; set: (patch: Partial<Brief>) => void; models: string[]; onKit: (kit: Kit) => void }) {
  const moments = brief.moments ?? [];
  const languages = brief.languages ?? [];
  const chosen = brief.models ?? [];
  const kitInput = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const setMoment = (index: number, patch: Partial<AlertMoment>) => set({ moments: moments.map((m, i) => (i === index ? { ...m, ...patch } : m)) });
  const setLanguage = (index: number, patch: Partial<AlertLanguage>) => set({ languages: languages.map((l, i) => (i === index ? { ...l, ...patch } : l)) });
  const loadKit = async (file: File) => {
    setProblem(null);
    try {
      const kit = JSON.parse(await file.text()) as { format?: string; version?: number; title?: string; tags?: string[]; brief?: Partial<Brief> };
      if (kit.format !== ALERTS_KIT || kit.version !== 1 || !kit.brief) throw new Error("That file is not an Alerts kit (kit.json, version 1).");
      onKit({ title: String(kit.title ?? ""), tags: (kit.tags ?? []).map(String), brief: kit.brief });
    } catch (problemError) {
      setProblem(errorMessage(problemError));
    }
  };
  return (
    <>
      <div className="ds-row" style={{ marginTop: 12 }}>
        <button type="button" className="ds-btn" onClick={() => kitInput.current?.click()}><FileUp size={14} aria-hidden="true" /> Load a kit (.json)</button>
        <span className="ds-tiny ds-muted">A kit holds the brief, the facts for each moment, the languages and the rules.</span>
        <input ref={kitInput} type="file" accept=".json,application/json" hidden onChange={(e) => { const file = e.target.files?.[0]; if (file) void loadKit(file); e.target.value = ""; }} />
      </div>
      {problem && <Banner kind="error">{problem}</Banner>}
      <Field label="Brief" hint="What you are testing and why. The models never see this; they get the instructions and the facts.">
        <textarea value={brief.brief} onChange={(e) => set({ brief: e.target.value })} style={{ minHeight: 70 }} placeholder="Can models turn these readings into correct alerts…" />
      </Field>
      <div className="ds-grid2">
        <Field label={`Models (${chosen.length} of 4)`} hint="Each moment goes to every model you pick.">
          <div className="ds-row" style={{ gap: 10 }}>
            {models.map((model) => {
              const on = chosen.includes(model);
              return (
                <label key={model} className="ds-row" style={{ margin: 0, fontWeight: 500, gap: 5 }}>
                  <input type="checkbox" checked={on} disabled={!on && chosen.length >= 4}
                    onChange={() => set({ models: on ? chosen.filter((m) => m !== model) : [...chosen, model] })} />
                  <span className="ds-mono ds-small">{model}</span>
                </label>
              );
            })}
          </div>
        </Field>
        <div className="ds-grid2">
          <Field label="Tries per model"><select value={brief.tries} onChange={(e) => set({ tries: Number(e.target.value) })}>{[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}</select></Field>
          <Field label="Alert length (characters)"><input type="number" min={60} max={600} value={brief.max_chars ?? 160} onChange={(e) => set({ max_chars: Number(e.target.value) || 160 })} /></Field>
        </div>
      </div>
      <Field label="Watch terms" hint="Flagged when a message (or its back-translation) uses them and the facts do not, e.g. shelter, closed.">
        <input value={(brief.watch_terms ?? []).join(", ")} onChange={(e) => set({ watch_terms: splitList(e.target.value) })} />
      </Field>
      <label>Languages ({languages.length} of 6) · each alert must end with its disclosure</label>
      <div className="ds-stack" style={{ gap: 6 }}>
        {languages.map((lang, index) => (
          <div key={index} className="ds-grid3" style={{ gridTemplateColumns: "90px 1fr 1fr auto" }}>
            <input aria-label={`Language ${index + 1} code`} value={lang.code} onChange={(e) => setLanguage(index, { code: e.target.value.trim() })} placeholder="es" />
            <input aria-label={`Language ${index + 1} name`} value={lang.name} onChange={(e) => setLanguage(index, { name: e.target.value })} placeholder="Spanish" />
            <input aria-label={`Language ${index + 1} disclosure`} value={lang.disclosure} onChange={(e) => setLanguage(index, { disclosure: e.target.value })} placeholder="Asistido por IA" />
            <button type="button" className="ds-btn sm ghost" aria-label={`Remove language ${index + 1}`} onClick={() => set({ languages: languages.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
          </div>
        ))}
        {languages.length < 6 && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => set({ languages: [...languages, { code: "", name: "", disclosure: "" }] })}>+ Add language</button>}
      </div>
      <label>Moments ({moments.length} of 12) · the only facts a model may use</label>
      <div className="ds-stack" style={{ gap: 8 }}>
        {moments.map((moment, index) => (
          <div key={index} className="ds-shot-edit">
            <div className="head">
              <b className="ds-mono">{index + 1}</b>
              <input aria-label={`Moment ${index + 1} name`} value={moment.name} onChange={(e) => setMoment(index, { name: e.target.value.slice(0, 80) })} placeholder="e.g. River rising" style={{ flex: 1 }} />
              <button type="button" className="ds-btn sm ghost" aria-label={`Remove moment ${index + 1}`} onClick={() => set({ moments: moments.filter((_, i) => i !== index) })}><Trash2 size={13} aria-hidden="true" /></button>
            </div>
            <textarea aria-label={`Moment ${index + 1} facts`} value={moment.facts} onChange={(e) => setMoment(index, { facts: e.target.value })} style={{ minHeight: 80 }} placeholder="One fact per line: readings, thresholds, times, what is not known" />
            <input aria-label={`Moment ${index + 1} question`} value={moment.question} onChange={(e) => setMoment(index, { question: e.target.value })} placeholder="A resident's question (optional)" style={{ marginTop: 6 }} />
          </div>
        ))}
        {moments.length < 12 && <button type="button" className="ds-btn sm" style={{ justifySelf: "start" }} onClick={() => set({ moments: [...moments, { name: "", group: "", facts: "", question: "", note: "" }] })}>+ Add moment</button>}
      </div>
      <details style={{ marginTop: 12 }}>
        <summary className="ds-small ds-dim" style={{ cursor: "pointer" }}>Instructions sent to the models (optional)</summary>
        <textarea aria-label="Instructions" value={brief.instructions ?? ""} onChange={(e) => set({ instructions: e.target.value })} style={{ minHeight: 70, marginTop: 6 }}
          placeholder="Empty = the default: use only the facts; add no places, closures, shelters, times or numbers; say plainly when the facts do not answer a question; reply with JSON." />
      </details>
    </>
  );
}

function Preview({ info, status, brief, pipeline, onStart, busy, canStart, models }: {
  info: PipelineInfo; status: StudioStatus | null; brief: Brief; pipeline: PipelineKey; onStart: () => void; busy: boolean; canStart: boolean;
  models: Partial<Record<TextRole, string>>;
}) {
  const [estimate, setEstimate] = useState<Record<string, number | string> | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const key = JSON.stringify(brief);
  const longEnough = brief.brief.trim().length >= (pipeline === "image" || pipeline === "article" || pipeline === "inspect" || pipeline === "alerts" ? 10 : 20);
  useEffect(() => {
    if (!longEnough) {
      setProblem(null);
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const result = await designApi.estimate(pipeline, brief);
        setEstimate(result.estimate);
        setProblem(null);
      } catch (error) {
        setEstimate(null);
        setProblem(errorMessage(error));
      }
    }, 400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, pipeline, longEnough]);
  const roleModel = (role: string | null) => (role === "text-draft" || role === "text-judge" ? models[role] : undefined)
    ?? status?.roles.find((item) => item.role === role)?.model;
  const kpis: Array<[string, string]> = [];
  if (estimate) {
    if (pipeline === "video") kpis.push([String(estimate.video_generations), "video generations"], [`${estimate.video_seconds} s`, "video generated (billed)"], [`~${estimate.minutes} min`, "for the takes"]);
    if (pipeline === "image") kpis.push([String(estimate.image_calls), "image calls to start"], [`~${estimate.minutes} min`, "for candidates"]);
    if (pipeline === "voice") kpis.push([`~${estimate.voice_calls}`, "lines to record"], [`~${estimate.minutes} min`, "to record"]);
    if (pipeline === "article") kpis.push([String(estimate.text_calls), "text calls per version"], [`~${estimate.minutes} min`, "to the first draft"]);
    if (pipeline === "inspect") kpis.push([String(estimate.text_calls), "vision calls"], [`~${estimate.minutes} min`, "to ask every model"]);
    if (pipeline === "alerts") kpis.push([String(estimate.text_calls), "text calls"], [`~${estimate.minutes} min`, "to draft and check"]);
  }
  const cap = pipeline === "video" ? status?.caps.video : pipeline === "image" ? status?.caps.image : pipeline === "voice" ? status?.caps.voice : status?.caps.text;
  const retire = pipeline === "video" ? status?.video_retirement : null;
  const steps = pipeline === "video" && brief.prompt_helper === false ? promptOnlySteps(info.steps) : info.steps;
  return (
    <div className="ds-card ds-ws-side" style={{ position: "sticky", top: 14 }}>
      <h3>Pipeline preview</h3>
      <FlowTrack steps={steps} modelFor={(step) => stepWorker(step, (role) => roleModel(role), pipeline)} />
      {kpis.length > 0 && (
        <div className="ds-grid3" style={{ marginTop: 8 }}>
          {kpis.map(([value, label]) => <div key={label} className="ds-kpi"><b>{value}</b><span>{label}</span></div>)}
        </div>
      )}
      {estimate?.basis && <p className="ds-tiny ds-muted">{String(estimate.basis)}</p>}
      <div className="ds-row">
        {retire && <span className="ds-chip warn">Sora 2 (2025-12-08) retires {retire.on}</span>}
        {cap && <span className="ds-chip info">Daily cap: {cap.used} of {cap.cap} {cap.label.toLowerCase()} used</span>}
      </div>
      {problem && <Banner kind="warn">{problem}</Banner>}
      <div className="ds-row">
        <button type="button" className="ds-btn primary" disabled={busy || !canStart || Boolean(problem)} onClick={onStart}>
          {busy ? <Spinner /> : null} Start run
        </button>
        <span className="ds-tiny ds-muted">Nothing expensive runs before your first review.</span>
      </div>
    </div>
  );
}

export default function NewRunPage({ pipeline: rawPipeline, forkOf }: { pipeline: string; forkOf: string | null }) {
  const pipeline: PipelineKey = rawPipeline === "image" || rawPipeline === "voice" || rawPipeline === "article" || rawPipeline === "inspect" || rawPipeline === "alerts" ? rawPipeline : "video";
  const pipelines = useLoad(designApi.pipelines, "pipelines");
  const status = useLoad(designApi.status, "status");
  const voices = useLoad(() => designApi.voices(), "voices");
  const [brief, setBrief] = useState<Brief>({ ...DEFAULTS[pipeline] });
  const [refs, setRefs] = useState<RefItem[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [parent, setParent] = useState<string | null>(null);
  const [models, setModels] = useState<Partial<Record<TextRole, string>>>({});
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const info = pipelines.data?.find((item) => item.key === pipeline);
  const set = (patch: Partial<Brief>) => setBrief((current) => ({ ...current, ...patch }));

  useEffect(() => {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    if (raw) {
      sessionStorage.removeItem(PREFILL_KEY);
      try {
        const prefill = JSON.parse(raw) as Prefill;
        if (prefill.pipeline === pipeline) {
          setBrief((current) => ({ ...current, ...prefill.brief }));
          setRefs(prefill.references ?? []);
          if (prefill.title) setTitle(prefill.title);
          if (prefill.parent_run_id) setParent(prefill.parent_run_id);
          if (prefill.note) setNote(prefill.note);
        }
      } catch {
        // ignore a damaged handoff
      }
    }
    if (!forkOf) return;
    designApi.run(forkOf).then((detail) => {
      const source = detail.run;
      setBrief({ ...DEFAULTS[pipeline], ...source.brief });
      const references = detail.artifacts.filter((a) => a.kind === "reference" && a.media_sha).map((a) => ({
        sha: a.media_sha!, thumb_sha: a.thumb_sha ?? undefined, role: (a.data.role as Reference["role"]) ?? "subject", name: a.label ?? "",
      }));
      setRefs(references);
      setTitle(`${source.title} (fork)`);
      if (source.settings?.models) setModels(source.settings.models);
      setTags(source.tags.join(", "));
      setParent(source.id);
      setNote(`Forked from “${source.title}”. Change anything, then start.`);
    }).catch((problem) => setError(errorMessage(problem)));
  }, [forkOf, pipeline]);

  useEffect(() => {
    if (pipeline !== "voice" || !voices.data || (brief.speakers ?? []).length) return;
    const local = voices.data.filter((voice) => voice.locale === (brief.locale ?? "en-US"));
    const pick = (name: string, fallback: number) => local.find((voice) => voice.display === name) ?? local[fallback];
    const first = pick("Harper", 0);
    const second = pick("Ethan", 1);
    if (first) set({ speakers: [{ name: first.display, voice: first.name, style: "" }, ...(second ? [{ name: second.display, voice: second.name, style: "" }] : [])] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices.data, pipeline]);

  const defaults = status.data?.text_defaults;
  const promptOnly = pipeline === "video" && brief.prompt_helper === false;
  const chosenModels: Partial<Record<TextRole, string>> = promptOnly || pipeline === "inspect" ? {}
    : pipeline === "alerts" ? { "text-judge": models["text-judge"] ?? defaults?.["text-judge"] } : {
    "text-draft": models["text-draft"] ?? defaults?.["text-draft"],
    ...(pipeline === "article" ? { "text-judge": models["text-judge"] ?? defaults?.["text-judge"] } : {}),
  };
  const fullBrief: Brief = pipeline === "inspect" || pipeline === "alerts" ? { ...brief, instructions: brief.instructions?.trim() ? brief.instructions : undefined }
    : pipeline === "voice" || pipeline === "article" ? brief
    : { ...brief, references: promptOnly ? [] : refs.map(({ sha, role, name }) => ({ sha, role, name })) };
  const ready = status.data?.pipelines.find((item) => item.key === pipeline)?.ready ?? false;
  const inspectReady = pipeline !== "inspect" || ((brief.images ?? []).length > 0 && (brief.models ?? []).length > 0
    && (brief.questions ?? []).length > 0 && (brief.questions ?? []).every((q) => q.text.trim().length >= 5));
  const alertsReady = pipeline !== "alerts" || ((brief.models ?? []).length > 0 && (brief.languages ?? []).length > 0 && (brief.moments ?? []).length > 0
    && (brief.moments ?? []).every((m) => m.name.trim().length >= 2 && m.facts.trim().length >= 10)
    && (brief.languages ?? []).every((l) => l.code.trim() && l.name.trim().length >= 2 && l.disclosure.trim().length >= 2));
  const canStart = ready && inspectReady && alertsReady && brief.brief.trim().length >= (pipeline === "image" || pipeline === "article" || pipeline === "inspect" || pipeline === "alerts" ? 10 : 20)
    && (pipeline !== "article" || ((brief.sources ?? []).length > 0 && (brief.sources ?? []).every((s) => s.title.trim() && s.text.trim().length >= 40)));

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const detail = await designApi.create({
        pipeline, brief: fullBrief, title: title.trim() || undefined, parent_run_id: parent ?? undefined, models: chosenModels,
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      go(`/design-studio/runs/${detail.run.id}`);
    } catch (problem) {
      setError(errorMessage(problem));
      setBusy(false);
    }
  };

  const loadExample = async () => {
    const example = promptOnly ? PROMPT_ONLY_EXAMPLE : EXAMPLES[pipeline];
    setTitle(example.title);
    set(example.brief);
    if ((pipeline === "inspect" || pipeline === "alerts") && !(brief.models ?? []).length) set({ models: (status.data?.text_models ?? []).slice(0, 2) });
    if (!tags) setTags("example");
    if ((pipeline === "image" || (pipeline === "video" && !promptOnly)) && !refs.length) {
      // Use the SOLENNE design sheet from run history as the subject reference, when this install has it.
      try {
        const sheet = await designApi.run(DESIGN_SHEET_RUN);
        const hero = sheet.artifacts.find((a) => a.kind === "image" && a.label === "c1" && a.media_sha);
        if (hero?.media_sha) {
          setRefs([{ sha: hero.media_sha, thumb_sha: hero.thumb_sha ?? undefined, role: "subject", name: "SOLENNE design sheet" }]);
        }
      } catch {
        // Not imported on this install: the example runs from text alone.
      }
    }
  };

  return (
    <div className="page ds">
      <Crumbs items={[{ label: "Design Studio", to: "/design-studio" }, { label: info?.title ?? pipeline }, { label: "New run" }]} />
      <header className="ds-head">
        <div>
          <h1>New {pipeline} run</h1>
          <p className="ds-sub">
            {pipeline === "video" && (promptOnly
              ? "Write one shot prompt per line. Each line goes to Sora as written; you check the lines before any video is generated."
              : "Write the brief once. The pipeline turns it into a shot list for you to approve before any video is generated.")}
            {pipeline === "image" && "Say what the image is for, give it references, and set the rules. Candidates come back for you to pick; then you iterate from the pick."}
            {pipeline === "voice" && "Describe the piece and cast the voices. The script comes back for you to edit, then each line is recorded and checked."}
            {pipeline === "article" && "Give it a brief and the sources. You approve the outline, then every draft is fact-checked against the sources by a second model before you approve one."}
            {pipeline === "inspect" && "Load a kit, or add images, questions and the right answers yourself. You check everything before any model is asked; then you review every disagreement and record the rules for asking."}
            {pipeline === "alerts" && "Load a kit, or write the facts for each moment and pick the languages. Models draft an alert and an answer in every language; a second model back-translates; the app checks the rules; you sign every draft. Nothing is sent."}
          </p>
        </div>
        <div className="ds-head-actions">
          <button type="button" className="ds-btn" onClick={() => void loadExample()}><Wand2 size={14} aria-hidden="true" /> Load example</button>
        </div>
      </header>
      {note && <div style={{ marginBottom: 12 }}><Banner kind="info">{note}</Banner></div>}
      {error && <div style={{ marginBottom: 12 }}><Banner kind="error">{error}</Banner></div>}
      {status.data && !ready && <div style={{ marginBottom: 12 }}><Banner kind="warn">This install has no model for this pipeline yet. Open Settings to see what's missing.</Banner></div>}
      {!info ? (
        pipelines.error ? <Banner kind="error">{pipelines.error}</Banner> : <div className="route-loading">Loading…</div>
      ) : (
        <div className="ds-grid2" style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(320px, 0.8fr)", alignItems: "start" }}>
          <section className="ds-card">
            <div className="ds-grid2">
              <Field label="Run title"><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Shown in run history" /></Field>
              <Field label="Tags" hint="Comma separated, e.g. Module 8, example"><input value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
            </div>
            {status.data && status.data.text_models.length > 0 && pipeline === "alerts" && (
              <Field label="Checking model" hint="Back-translates every message and lists statements the facts do not support.">
                <select value={chosenModels["text-judge"] ?? ""} onChange={(e) => setModels({ ...models, "text-judge": e.target.value })}>
                  {status.data.text_models.map((name) => <option key={name} value={name}>{name}{name === defaults?.["text-judge"] ? " (default)" : ""}</option>)}
                </select>
              </Field>
            )}
            {status.data && status.data.text_models.length > 0 && !promptOnly && pipeline !== "inspect" && pipeline !== "alerts" && (
              <div className="ds-grid2">
                <Field label="Text model" hint={TEXT_MODEL_HINT[pipeline]}>
                  <select value={chosenModels["text-draft"] ?? ""} onChange={(e) => setModels({ ...models, "text-draft": e.target.value })}>
                    {status.data.text_models.map((name) => <option key={name} value={name}>{name}{name === defaults?.["text-draft"] ? " (default)" : ""}</option>)}
                  </select>
                </Field>
                {pipeline === "article" && (
                  <Field label="Fact-check model" hint="A second model checks every claim against the sources. A reasoning model is stricter.">
                    <select value={chosenModels["text-judge"] ?? ""} onChange={(e) => setModels({ ...models, "text-judge": e.target.value })}>
                      {status.data.text_models.map((name) => <option key={name} value={name}>{name}{name === defaults?.["text-judge"] ? " (default)" : ""}</option>)}
                    </select>
                  </Field>
                )}
              </div>
            )}
            {pipeline === "video" && <VideoForm brief={brief} set={set} voices={voices.data ?? []} />}
            {pipeline === "image" && <ImageForm brief={brief} set={set} info={info} />}
            {pipeline === "voice" && <VoiceForm brief={brief} set={set} voices={voices.data ?? []} />}
            {pipeline === "article" && <ArticleForm brief={brief} set={set} />}
            {pipeline === "inspect" && <InspectForm brief={brief} set={set} models={status.data?.text_models ?? []} onKit={(kit) => {
              const available = status.data?.text_models ?? [];
              const wanted = kit.brief.models ?? [];
              const usable = wanted.filter((m) => available.includes(m));
              setTitle(kit.title);
              setTags(kit.tags.join(", "));
              setBrief({ ...INSPECT_DEFAULTS, ...kit.brief, models: usable.length ? usable : available.slice(0, 2) });
              const missing = wanted.filter((m) => !available.includes(m));
              setNote(`Loaded “${kit.title || "kit"}”: ${kit.brief.images?.length ?? 0} images, ${kit.brief.questions?.length ?? 0} questions.`
                + (missing.length ? ` Not on this install, so left out: ${missing.join(", ")}.` : ""));
            }} />}
            {pipeline === "alerts" && <AlertsForm brief={brief} set={set} models={status.data?.text_models ?? []} onKit={(kit) => {
              const available = status.data?.text_models ?? [];
              const wanted = kit.brief.models ?? [];
              const usable = wanted.filter((m) => available.includes(m));
              setTitle(kit.title);
              setTags(kit.tags.join(", "));
              setBrief({ ...ALERTS_DEFAULTS, ...kit.brief, models: usable.length ? usable : available.slice(0, 2) });
              const missing = wanted.filter((m) => !available.includes(m));
              setNote(`Loaded “${kit.title || "kit"}”: ${kit.brief.moments?.length ?? 0} moments, ${kit.brief.languages?.length ?? 0} languages.`
                + (missing.length ? ` Not on this install, so left out: ${missing.join(", ")}.` : ""));
            }} />}
            {(pipeline === "image" || (pipeline === "video" && !promptOnly)) && (
              <>
                <label>Reference images {pipeline === "video" ? "(optional: the product or design sheet)" : "(optional)"}</label>
                <ReferenceList refs={refs} onChange={setRefs} />
                <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>
                  {pipeline === "video"
                    ? "Product and scene shots start from keyframes edited from these images. Sora rejects input images that contain human faces, so shots with people are made from text."
                    : "Subject = keep this thing the same · Style = borrow the look · Scene = put the subject here. Images of real people need their consent."}
                </p>
              </>
            )}
          </section>
          <Preview info={info} status={status.data} brief={fullBrief} pipeline={pipeline} onStart={() => void start()} busy={busy} canStart={canStart} models={chosenModels} />
        </div>
      )}
    </div>
  );
}
