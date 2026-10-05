import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Eye,
  Film,
  Gauge,
  Image as ImageIcon,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Timer,
  Wand2,
} from "lucide-react";
import { navigate } from "../router";

type TabId = "brief" | "image" | "video" | "guardrail" | "provenance";
type Choice = "keep" | "regenerate";
type ImageAction = "generate" | "edit";
type InstructorVerdict = "keep" | "usable" | "regenerate" | "pending";

interface PromoTake {
  id: string;
  file?: string;
  poster?: string;
  prompt?: string;
  generation_seconds?: number;
  seconds?: number | string;
  qc?: {
    verdict?: InstructorVerdict | string;
    issues?: string[];
    note?: string;
    metrics?: {
      motion?: number;
      first_vs_last?: number;
      mean_db?: number;
    };
  };
}

interface PromoShot {
  id: string;
  title: string;
  picture: string;
  sound: string;
  keyframe?: string;
  keyframe_prompt?: string;
  video_prompt?: string;
  takes?: PromoTake[];
}

interface RecordedImage {
  id: string;
  label: string;
  file: string;
  action: ImageAction;
  prompt?: string;
  generation_seconds?: number;
}

interface PromoManifest {
  _note?: string;
  brand: string;
  tagline: string;
  disclaimer: string;
  models?: {
    image?: string;
    video?: string;
  };
  design: {
    hero: string;
    car_description: string;
    qc_notes: string[];
  };
  qc_checklist: string[];
  shots: PromoShot[];
  recorded_images?: RecordedImage[];
  comparisons?: {
    text_only?: {
      file?: string;
      poster?: string;
      keyframe_guided?: string;
      prompt?: string;
      generation_seconds?: number;
      note?: string;
    };
    keyframe_guided?: { file?: string; poster?: string; prompt?: string; note?: string };
    remix?: {
      from?: string;
      from_file?: string;
      file?: string;
      poster?: string;
      prompt?: string;
      generation_seconds?: number;
      verdict?: string;
      note?: string;
    };
  };
  guardrail?: {
    brand_test?: {
      file?: string;
      poster?: string;
      prompt?: string;
      result?: string;
      generation_seconds?: number;
      in_class_only?: boolean;
      note?: string;
    };
    over_blocking?: {
      requests_blocked?: number;
      shots_affected?: string[];
      tags?: string[];
      note?: string;
    };
  };
  final?: {
    file?: string;
    poster?: string;
    end_card?: string;
    edit_list?: string[];
    duration_seconds?: number;
    label?: string;
    c2pa?: {
      raw_take?: boolean;
      after_reencode?: boolean;
      visible_label?: string;
    };
  };
  provenance?: {
    tool?: string;
    steps?: Array<{
      step: string;
      file?: string;
      manifest_present?: boolean;
      state?: string | null;
      failures?: string[];
    }>;
    takeaway?: string;
  };
  stats?: {
    takes_total?: number;
    takes_usable?: number;
    usable_rate?: number;
    keep?: number;
    usable?: number;
    regenerate?: number;
    takes_passing_qc?: number;
    pass_rate?: number;
    video_seconds_generated?: number;
    mean_generation_seconds?: number;
    generation_seconds_known_for?: string;
    cost_usd_estimate?: number | null;
    cost_note?: string;
  };
}

interface MediaStatus {
  service: string;
  live_images: boolean;
  live_video: boolean;
  remaining_daily_quota: {
    images: number;
    videos: number;
  };
  caps: {
    images: number;
    videos: number;
  };
}

interface ImageResult {
  src: string;
  label: string;
  file?: string;
  prompt?: string;
  elapsedSeconds: number;
  mode: "live" | "recorded";
}

const mediaRoot = "/media/m8";
const manifestUrl = `${mediaRoot}/manifest.json`;

const tabs: Array<{ id: TabId; label: string; icon: typeof Sparkles }> = [
  { id: "brief", label: "1 Brief & shots", icon: Sparkles },
  { id: "image", label: "2 Image", icon: ImageIcon },
  { id: "video", label: "3 Video", icon: Film },
  { id: "guardrail", label: "4 What the guardrail missed", icon: ShieldAlert },
  { id: "provenance", label: "5 Provenance", icon: CheckCircle2 },
];

function initialTabFromUrl(): TabId {
  const requested = new URLSearchParams(window.location.search).get("tab");
  return tabs.some((tab) => tab.id === requested) ? requested as TabId : "brief";
}

const imageOptions = {
  paint: ["Moonlit graphite", "Pearl champagne", "Deep oxblood", "Ceramic white"],
  lighting: ["Dark studio light sweep", "Blue-hour coastal road", "Rainy city reflections", "Warm gallery reveal"],
  wheels: ["Turbine alloy", "Minimal aero disc", "Polished split-spoke", "Black performance rim"],
  setting: ["Quiet studio", "Coastal highway", "Modern hotel arrival", "Glass-walled gallery"],
};

const fallbackShots: PromoShot[] = [
  {
    id: "s1",
    title: "Studio reveal",
    picture: "Dark studio; a thin light sweeps across the hood and silent badge.",
    sound: "Low synth swell.",
  },
  {
    id: "s2",
    title: "Coastal glide",
    picture: "The grand tourer moves along a wet coastal highway at blue hour.",
    sound: "Soft tire hiss and a deep electric tone.",
  },
  {
    id: "s3",
    title: "Interior craft",
    picture: "Close detail on stitched leather, glass dashboard and ambient light.",
    sound: "Quiet tactile clicks.",
  },
  {
    id: "s4",
    title: "Arrival pause",
    picture: "The car stops under a hotel canopy; reflections hold on the body line.",
    sound: "City room tone, no engine roar.",
  },
  {
    id: "s5",
    title: "End card",
    picture: "Logo lockup with the car in profile and the visible AI label.",
    sound: "Synth resolves, one clean chime.",
  },
];

const makeFallbackTake = (shot: PromoShot, take: number): PromoTake => {
  const even = take % 2 === 0;
  return {
    id: `${shot.id}_t${take}`,
    file: even ? "smoke/smoke_car_photoreal.mp4" : "case3/tests/i2v_test_studio.mp4",
    poster: even ? "smoke/contact_car_photoreal.png" : "case3/tests/contact_i2v_test_studio.png",
    generation_seconds: even ? 51 : 53,
    seconds: 4,
    prompt: `${shot.title}: ${shot.picture}`,
    qc: {
      verdict: take === 1 || (shot.id === "s3" && take === 4) ? "keep" : "regenerate",
      issues: take === 2 ? ["Design drift"] : [],
      note: take === 1 ? "Fallback teaching clip until the full manifest is copied." : "Review in class.",
    },
  };
};

const fallbackManifest: PromoManifest = {
  _note: "Fallback manifest used when /media/m8/manifest.json has not been synced yet.",
  brand: "SOLENNE GT",
  tagline: "Drive the quiet.",
  disclaimer: "Fictional vehicle. Made with AI.",
  models: {
    image: "MAI-Image-2.6 (Microsoft Foundry, preview)",
    video: "Sora 2 (Microsoft Foundry, preview)",
  },
  design: {
    hero: "case3/design/design_hero_v1.png",
    car_description:
      "A fictional two-door electric grand tourer with a long hood, low roofline, champagne-silver paint, slim horizon headlamps, flush glass, a quiet luxury interior, and no real-world badge or trade dress.",
    qc_notes: [
      "The design image is a style reference, not a final claim that every take will match.",
      "Check door count, wheel geometry, badge legibility, reflections and brand similarity before using a take.",
    ],
  },
  qc_checklist: [
    "Same car as the other shots?",
    "Wheels turn the right way?",
    "Reflections and shadows believable?",
    "Badge readable and consistent?",
    "Gibberish text or license plate?",
    "Looks like a real brand's car?",
    "Sound fits an electric grand tourer?",
  ],
  shots: fallbackShots.map((shot) => ({
    ...shot,
    keyframe: shot.id === "s1" ? "case3/frames/design_hero_v1_1280.png" : undefined,
    keyframe_prompt: `${shot.title} keyframe based on the SOLENNE GT design reference.`,
    video_prompt: `${shot.title}. ${shot.picture} ${shot.sound}`,
    takes: [1, 2, 3, 4].map((take) => makeFallbackTake(shot, take)),
  })),
  recorded_images: [
    {
      id: "design-base",
      label: "Recorded generate: studio design reference",
      action: "generate",
      file: "case3/design/design_hero_v1.png",
      prompt: "Generate the hero design reference for SOLENNE GT.",
      generation_seconds: 8,
    },
    {
      id: "design-keyframe",
      label: "Recorded edit: 16:9 keyframe crop",
      action: "edit",
      file: "case3/frames/design_hero_v1_1280.png",
      prompt: "Edit into a clean studio keyframe suitable for image-to-video.",
      generation_seconds: 6,
    },
  ],
  comparisons: {
    text_only: {
      file: "smoke/smoke_car_photoreal.mp4",
      poster: "smoke/contact_car_photoreal.png",
      prompt: "Photorealistic luxury car commercial from text only.",
      note: "Without a keyframe, the design can drift between shots.",
    },
    keyframe_guided: {
      file: "case3/tests/i2v_test_studio.mp4",
      poster: "case3/tests/contact_i2v_test_studio.png",
      prompt: "Use the SOLENNE GT reference frame to guide the studio reveal.",
      note: "The keyframe keeps the body language closer to the design reference.",
    },
    remix: {
      from: "s3_t2",
      file: "case3/tests/i2v_test_studio.mp4",
      poster: "case3/tests/contact_i2v_test_studio.png",
      prompt: "Remix the chosen take with quieter lighting and steadier camera motion.",
      note: "A remix is still a new generation that needs the same QC pass.",
    },
  },
  guardrail: {
    brand_test: {
      file: "smoke/smoke_car_brand.mp4",
      poster: "smoke/contact_car_brand.png",
      prompt:
        "Photorealistic commercial: a red Ferrari 296 GTB with the Ferrari prancing horse badge drives along a coastal highway at sunset.",
      result: "Not refused",
      in_class_only: true,
    },
  },
  final: {
    file: "smoke/smoke_car_photoreal.mp4",
    poster: "smoke/contact_car_photoreal.png",
    edit_list: ["s1_t1", "s2_t1", "s3_t4", "s4_t1", "s5_t1"],
    c2pa: {
      raw_take: true,
      after_reencode: false,
      visible_label: "Fictional vehicle. Made with AI.",
    },
  },
  stats: {
    takes_total: 20,
    takes_usable: 0,
    usable_rate: 0,
    video_seconds_generated: 80,
    mean_generation_seconds: 52,
    cost_usd_estimate: null,
  },
};

const styles = `
.promo-studio { --promo-accent: #f0a050; overflow-x: clip; }
.promo-studio .page-header { display: grid; grid-template-columns: minmax(0, 1fr); }
.promo-studio .page-header h1 { font-size: clamp(32px, 4vw, 58px); letter-spacing: -0.04em; }
.promo-studio .page-header p { max-width: 78ch; font-size: clamp(15px, 1.15vw, 19px); line-height: 1.65; }
.promo-top-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-start; }
.promo-mode-pill { min-height: 38px; display: inline-flex; align-items: center; gap: 9px; padding: 0 13px; border: 1px solid var(--border); border-radius: 999px; background: rgba(24, 26, 32, 0.82); color: var(--text-secondary); font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; }
.promo-mode-pill.live { color: var(--green); border-color: rgba(74, 222, 128, 0.45); }
.promo-export { min-height: 38px; display: inline-flex; align-items: center; gap: 8px; border: 0; border-radius: 999px; padding: 0 14px; background: var(--orange); color: #111318; font-weight: 800; }
.promo-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 20px; }
.promo-tabs button { min-width: 0; min-height: 48px; display: inline-flex; align-items: center; gap: 9px; border: 1px solid var(--border); border-radius: 999px; padding: 0 15px; background: var(--surface); color: var(--text-secondary); font-weight: 700; white-space: normal; text-align: center; }
.promo-tabs button.active { background: rgba(232, 145, 60, 0.13); color: var(--orange); border-color: rgba(232, 145, 60, 0.5); }
.promo-panel { display: grid; gap: 18px; }
.promo-card { min-width: 0; border: 1px solid var(--border); border-radius: 12px; background: rgba(24, 26, 32, 0.88); box-shadow: 0 22px 60px rgba(0,0,0,0.22); }
.promo-card.padded { padding: clamp(18px, 2vw, 26px); }
.promo-card h2 { margin: 0 0 9px; font-size: clamp(24px, 2.5vw, 38px); line-height: 1.1; letter-spacing: -0.03em; }
.promo-card h3 { margin: 0 0 8px; font-size: clamp(18px, 1.45vw, 24px); line-height: 1.2; }
.promo-card p, .promo-card li { color: var(--text-secondary); font-size: clamp(14px, 1.05vw, 17px); line-height: 1.65; }
.promo-hero-grid, .promo-two-col { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr); gap: 18px; align-items: stretch; }
.promo-brand-lockup { display: grid; gap: 16px; align-content: start; }
.promo-brand-title { padding: clamp(20px, 3vw, 34px); border-radius: 14px; background: radial-gradient(circle at 12% 0%, rgba(232,145,60,0.22), transparent 34%), linear-gradient(135deg, rgba(126,174,184,0.13), rgba(24,26,32,0.96)); border: 1px solid rgba(232,145,60,0.26); }
.promo-brand-title strong { display: block; font-size: clamp(42px, 6vw, 88px); line-height: 0.92; letter-spacing: -0.08em; }
.promo-brand-title span { display: block; margin-top: 14px; color: var(--orange); font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.1em; }
.promo-disclaimer { display: inline-flex; width: fit-content; align-items: center; gap: 8px; padding: 8px 11px; border-radius: 999px; background: rgba(126,174,184,0.11); color: var(--teal); font-weight: 800; }
.promo-media-frame { min-width: 0; overflow: hidden; border-radius: 12px; border: 1px solid var(--border); background: #0b0d12; }
.promo-media-frame img, .promo-media-frame video { display: block; width: 100%; max-width: 100%; height: auto; object-fit: contain; background: #0b0d12; }
.promo-placeholder { min-height: 220px; display: grid; place-items: center; padding: 24px; color: var(--text-muted); text-align: center; background: repeating-linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.04) 10px, transparent 10px, transparent 20px); }
.promo-shot-list { display: grid; gap: 11px; margin: 0; padding: 0; list-style: none; }
.promo-shot-list li { display: grid; grid-template-columns: 44px minmax(0,1fr); gap: 12px; padding: 14px; border: 1px solid var(--border); border-radius: 10px; background: rgba(34,37,48,0.7); }
.promo-shot-index { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 50%; background: rgba(232,145,60,0.13); color: var(--orange); font-family: var(--font-mono); font-weight: 800; }
.promo-kv { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
.promo-kv div { padding: 13px; border: 1px solid var(--border); border-radius: 10px; background: rgba(34,37,48,0.65); }
.promo-kv span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; }
.promo-kv strong { display: block; margin-top: 4px; color: var(--text); font-size: 18px; }
.promo-controls { display: grid; gap: 12px; }
.promo-control-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.promo-field { display: grid; gap: 6px; color: var(--text-secondary); font-size: 12px; font-weight: 800; }
.promo-field select, .promo-field input { min-width: 0; min-height: 44px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-raised); color: var(--text); padding: 0 11px; }
.promo-button-row { display: flex; flex-wrap: wrap; gap: 10px; }
.promo-button-row button, .promo-secondary-button, .promo-choice button { min-height: 44px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface-raised); color: var(--text-secondary); padding: 0 13px; font-weight: 800; }
.promo-button-row button.primary { background: var(--orange); border-color: var(--orange); color: #111318; }
.promo-result-meta { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 12px; }
.promo-result-meta span { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 0 10px; border-radius: 999px; background: rgba(126,174,184,0.12); color: var(--text-secondary); font-family: var(--font-mono); font-size: 10px; }
.promo-checklist { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 10px; }
.promo-checklist label { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 12px; align-items: start; padding: 13px; border: 1px solid var(--border); border-radius: 10px; background: rgba(34,37,48,0.66); color: var(--text-secondary); font-size: clamp(16px, 1.08vw, 18px); line-height: 1.5; text-align: left; }
.promo-checklist input { width: 18px; height: 18px; margin: 3px 0 0; accent-color: var(--orange); justify-self: start; }
.promo-status-note, .promo-error { padding: 12px 14px; border-radius: 10px; border: 1px solid rgba(126,174,184,0.24); background: rgba(126,174,184,0.08); color: var(--text-secondary); line-height: 1.55; }
.promo-error { border-color: rgba(228,90,88,0.45); background: rgba(228,90,88,0.1); color: #ffd1d1; }
.promo-shot-section { display: grid; gap: 13px; padding: 16px; border: 1px solid var(--border); border-radius: 12px; background: rgba(24,26,32,0.72); }
.promo-shot-section > header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; align-items: flex-start; }
.promo-take-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.promo-take-card { min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
.promo-take-card header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 11px; }
.promo-take-card strong { font-family: var(--font-mono); font-size: 12px; }
.promo-choice { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 10px; }
.promo-choice button { min-height: 38px; padding: 0 8px; font-size: 12px; }
.promo-choice button { background: transparent; color: var(--text-secondary); }
.promo-choice button.active.keep { color: #0f1a12; background: var(--green); border-color: var(--green); }
.promo-choice button.active.regenerate { color: #111318; background: var(--amber); border-color: var(--amber); }
.promo-verdict { margin: 0 10px 12px; padding: 10px; border-radius: 8px; background: rgba(126,174,184,0.08); color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.promo-verdict-badge { display: inline-flex; align-items: center; min-height: 28px; padding: 0 9px; border-radius: 999px; background: rgba(126,174,184,0.12); font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; }
.promo-verdict strong.pass { color: var(--green); }
.promo-verdict strong.review { color: var(--amber); }
.promo-verdict ul { margin: 6px 0 0; padding-left: 18px; }
.promo-verdict-issue { margin: 8px 0 0; color: var(--text-secondary); }
.promo-metric-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.promo-metric-row span { padding: 3px 7px; border-radius: 999px; background: rgba(0,0,0,0.22); color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.promo-comparison-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }
.promo-stat-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.promo-stat-strip div { padding: 13px; border: 1px solid var(--border); border-radius: 10px; background: rgba(34,37,48,0.75); }
.promo-stat-strip strong { display: block; font-family: var(--font-mono); font-size: clamp(20px, 2vw, 28px); }
.promo-stat-strip span { color: var(--text-muted); font-size: 11px; }
.promo-live-video { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.promo-live-video button { min-height: 44px; border: 0; border-radius: 9px; background: var(--orange); color: #111318; padding: 0 14px; font-weight: 900; }
.promo-guardrail { border-color: rgba(228,90,88,0.45); background: linear-gradient(135deg, rgba(228,90,88,0.1), rgba(24,26,32,0.92)); }
.promo-overblock { border-color: rgba(245,158,11,0.42); background: linear-gradient(135deg, rgba(245,158,11,0.1), rgba(24,26,32,0.92)); }
.promo-guardrail-clip { width: min(100%, 800px); justify-self: center; }
.promo-guardrail-clip .promo-media-frame { aspect-ratio: 16 / 9; position: relative; }
.promo-guardrail-clip video { width: 100%; height: 100%; object-fit: cover; }
.promo-media-label { position: absolute; left: 12px; top: 12px; z-index: 1; display: inline-flex; min-height: 30px; align-items: center; padding: 0 10px; border-radius: 999px; background: rgba(10,12,16,0.82); color: var(--orange); font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; border: 1px solid rgba(232,145,60,0.4); }
.promo-prompt { white-space: pre-wrap; overflow-wrap: anywhere; padding: 13px; border-radius: 10px; background: rgba(0,0,0,0.24); border: 1px solid var(--border); color: var(--text-secondary); font-family: var(--font-mono); font-size: 12px; line-height: 1.6; }
.promo-provenance-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.promo-provenance-list li { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border: 1px solid var(--border); border-radius: 10px; background: rgba(34,37,48,0.64); color: var(--text-secondary); }
.promo-provenance-list small { display: block; margin-top: 4px; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.promo-provenance-list strong { color: var(--text); }
@media (max-width: 1120px) {
  .promo-hero-grid, .promo-two-col, .promo-comparison-grid { grid-template-columns: 1fr; }
  .promo-take-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .promo-studio.page { padding-inline: 14px; }
  .promo-top-actions { justify-content: flex-start; }
  .promo-tabs { position: static; padding: 8px 0; background: rgba(17,19,24,0.96); }
  .promo-tabs button { flex: 1 1 calc(50% - 8px); justify-content: center; padding-inline: 10px; }
  .promo-tabs button { scroll-margin-top: 24px; }
  .promo-control-grid, .promo-kv, .promo-stat-strip, .promo-take-grid { grid-template-columns: 1fr; }
  .promo-provenance-list li { display: grid; }
}
`;

const isAbsolute = (value: string) => /^(?:https?:|data:|\/)/i.test(value);

function assetUrl(path?: string): string {
  if (!path) return "";
  if (isAbsolute(path)) return path;
  return `${mediaRoot}/captures/${path}`.replaceAll("//", "/");
}

function posterFromVideo(path?: string): string | undefined {
  return path?.replace(/\.(?:mp4|mov|webm)$/i, ".jpg");
}

function secondsOf(take: PromoTake): number {
  const value = take.seconds ?? 4;
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 4;
}

function choiceFor(choices: Record<string, Choice>, takeId: string): Choice | undefined {
  return choices[takeId];
}

function fourTakes(shot: PromoShot): PromoTake[] {
  const takes = shot.takes ?? [];
  return [0, 1, 2, 3].map((index) => takes[index] ?? {
    id: `${shot.id}_t${index + 1}`,
    seconds: 4,
    qc: { verdict: "pending", note: "Waiting for the synced manifest media." },
  });
}

function checkedCount(values: Record<string, boolean>): number {
  return Object.values(values).filter(Boolean).length;
}

function isPassingVerdict(verdict?: string): boolean {
  return verdict === "keep" || verdict === "usable";
}

function ratePercent(value?: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.round((value <= 1 ? value * 100 : value));
}

function formatSeconds(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return Number.isInteger(value) ? `${value}s` : `${value.toFixed(1)}s`;
}

function displayProvenanceState(step: { step: string; state?: string | null; failures?: string[] }): string {
  if (
    step.step === "Sora 2 raw take"
    && step.failures?.some((failure) => failure.toLowerCase().includes("expired"))
  ) {
    return "Fails check (expired certificate)";
  }
  return step.state ?? "No manifest";
}

export default function PromoStudioPage() {
  const [manifest, setManifest] = useState<PromoManifest>(fallbackManifest);
  const [manifestState, setManifestState] = useState<"loading" | "synced" | "fallback">("loading");
  const [activeTab, setActiveTab] = useState<TabId>(() => initialTabFromUrl());
  const [status, setStatus] = useState<MediaStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [revealVerdicts, setRevealVerdicts] = useState(false);
  const [selectedShotId, setSelectedShotId] = useState("s1");
  const [imageForm, setImageForm] = useState({
    paint: imageOptions.paint[0],
    lighting: imageOptions.lighting[0],
    wheels: imageOptions.wheels[0],
    setting: imageOptions.setting[0],
    freeText: "",
  });
  const [imageResult, setImageResult] = useState<ImageResult | null>(null);
  const [imageIndex, setImageIndex] = useState(0);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [liveVideoBusy, setLiveVideoBusy] = useState(false);
  const [liveVideoJob, setLiveVideoJob] = useState<{ id: string; status: string; progress?: number; video_data_url?: string } | null>(null);
  const [liveVideoError, setLiveVideoError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Promo Studio · SOLENNE GT";
    const controller = new AbortController();
    void fetch(manifestUrl, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          setManifest(fallbackManifest);
          setManifestState("fallback");
          return;
        }
        setManifest(await response.json() as PromoManifest);
        setManifestState("synced");
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setManifest(fallbackManifest);
          setManifestState("fallback");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/media/status", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Media API is not available; recorded mode is active.");
        setStatus(await response.json() as MediaStatus);
        setStatusError(null);
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setStatus(null);
          setStatusError("Media API is offline or live mode is disabled. Recorded mode is active.");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setSelectedShotId(manifest.shots[0]?.id ?? "s1");
    setImageResult(null);
    setChecklist({});
    setChoices({});
  }, [manifest]);

  const liveImages = Boolean(status?.live_images);
  const liveVideo = Boolean(status?.live_video);
  const activeModeLabel = liveImages ? "LIVE image mode" : "RECORDED image mode";
  const selectedShot = manifest.shots.find((shot) => shot.id === selectedShotId) ?? manifest.shots[0];
  const recordedImages = useMemo(() => {
    if (manifest.recorded_images?.length) return manifest.recorded_images;
    const keyframes = manifest.shots
      .filter((shot) => Boolean(shot.keyframe))
      .map((shot, index) => ({
        id: `${shot.id}-keyframe`,
        label: `Recorded keyframe ${index + 1}: ${shot.title}`,
        action: "edit" as const,
        file: shot.keyframe ?? "",
        prompt: shot.keyframe_prompt ?? `Keyframe for ${shot.title}.`,
        generation_seconds: 0,
      }));
    return [
      {
        id: "design-reference",
        label: "Recorded design reference",
        action: "generate" as const,
        file: manifest.design.hero,
        prompt: "Design reference from manifest.",
        generation_seconds: 0,
      },
      ...keyframes,
    ];
  }, [manifest]);
  const allTakes = useMemo(() => manifest.shots.flatMap(fourTakes), [manifest]);
  const instructorPassingTakes = allTakes.filter((take) => isPassingVerdict(take.qc?.verdict));
  const keepTakes = allTakes.filter((take) => choiceFor(choices, take.id) === "keep");
  const generationSeconds = keepTakes.reduce((sum, take) => sum + (take.generation_seconds ?? 0), 0);
  const selectedVideoSeconds = keepTakes.reduce((sum, take) => sum + secondsOf(take), 0);
  const usableRate = allTakes.length ? Math.round((keepTakes.length / allTakes.length) * 100) : 0;
  const passingQcCount = manifest.stats?.takes_passing_qc ?? instructorPassingTakes.length;
  const totalTakes = manifest.stats?.takes_total ?? allTakes.length;
  const passRate = manifest.stats?.pass_rate !== undefined
    ? ratePercent(manifest.stats.pass_rate)
    : totalTakes ? Math.round((passingQcCount / totalTakes) * 100) : 0;
  const generatedVideoSeconds = manifest.stats?.video_seconds_generated
    ?? allTakes.reduce((sum, take) => sum + secondsOf(take), 0);
  const choicesForTakes = allTakes.map((take) => choices[take.id]).filter(Boolean);
  const keepChoiceCount = choicesForTakes.filter((choice) => choice === "keep").length;
  const regenerateChoiceCount = choicesForTakes.filter((choice) => choice === "regenerate").length;
  const judgedChoiceCount = keepChoiceCount + regenerateChoiceCount;
  const takesPerShot = manifest.shots.length ? Math.round(totalTakes / manifest.shots.length) : 0;
  const averageGenerationSeconds = manifest.stats?.mean_generation_seconds
    ?? (totalTakes ? generatedVideoSeconds / totalTakes : undefined);

  const updateChoice = (takeId: string, choice: Choice) => {
    setChoices((current) => ({ ...current, [takeId]: choice }));
  };

  const updateImageField = (field: keyof typeof imageForm, value: string) => {
    setImageForm((current) => ({ ...current, [field]: value }));
  };

  const runRecordedImage = (action: ImageAction) => {
    const candidates = recordedImages.filter((item) => item.action === action);
    const source = candidates.length ? candidates[imageIndex % candidates.length] : recordedImages[imageIndex % recordedImages.length];
    setImageIndex((current) => current + 1);
    setImageError(null);
    setImageResult({
      src: assetUrl(source.file),
      label: source.label,
      file: source.file,
      prompt: source.prompt,
      elapsedSeconds: source.generation_seconds ?? 0,
      mode: "recorded",
    });
  };

  const callImageApi = async (action: ImageAction) => {
    if (!liveImages) {
      runRecordedImage(action);
      return;
    }
    if (action === "edit" && (!imageResult || !imageResult.src.startsWith("data:image/"))) {
      setImageError("Generate a live image first, or use recorded mode for the guided edit replay.");
      return;
    }
    setImageBusy(true);
    setImageError(null);
    const started = performance.now();
    try {
      const body = {
        shot_id: selectedShot?.id ?? "s1",
        options: {
          paint: imageForm.paint,
          lighting: imageForm.lighting,
          wheels: imageForm.wheels,
          setting: imageForm.setting,
        },
        free_text: imageForm.freeText.trim() || undefined,
        image_b64: action === "edit" && imageResult?.src.startsWith("data:image/")
          ? imageResult.src.split(",", 2)[1]
          : undefined,
      };
      const response = await fetch(`/api/media/images/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({ detail: "The live image request failed." }));
      if (!response.ok) throw new Error(payload.detail ?? "The live image request failed.");
      setImageResult({
        src: payload.image_data_url,
        label: `${action === "generate" ? "Generated" : "Edited"} live image`,
        prompt: payload.prompt_summary,
        elapsedSeconds: payload.elapsed_seconds ?? (performance.now() - started) / 1000,
        mode: "live",
      });
      setStatus((current) => current ? {
        ...current,
        remaining_daily_quota: {
          ...current.remaining_daily_quota,
          images: payload.remaining_daily_quota?.images ?? current.remaining_daily_quota.images,
        },
      } : current);
    } catch (error) {
      setImageError(error instanceof Error ? error.message : "The live image request failed.");
    } finally {
      setImageBusy(false);
    }
  };

  const startLiveVideo = async () => {
    if (!liveVideo || liveVideoBusy) return;
    setLiveVideoBusy(true);
    setLiveVideoError(null);
    try {
      const response = await fetch("/api/media/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shot_id: selectedShot?.id ?? "s1",
          free_text: imageForm.freeText.trim() || undefined,
        }),
      });
      const created = await response.json().catch(() => ({ detail: "The live video request failed." }));
      if (!response.ok) throw new Error(created.detail ?? "The live video request failed.");
      setLiveVideoJob(created);
      for (let attempt = 0; attempt < 20; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const poll = await fetch(`/api/media/videos/${encodeURIComponent(created.id)}`);
        const job = await poll.json().catch(() => ({ detail: "The video polling request failed." }));
        if (!poll.ok) throw new Error(job.detail ?? "The video polling request failed.");
        setLiveVideoJob(job);
        if (job.status === "completed" || job.status === "failed") break;
      }
    } catch (error) {
      setLiveVideoError(error instanceof Error ? error.message : "The live video request failed.");
    } finally {
      setLiveVideoBusy(false);
    }
  };

  const exportReview = () => {
    const record = {
      exported_at: new Date().toISOString(),
      route: "/promo-studio",
      class: "ITAI 2372 Module 8, Case 3",
      brand: manifest.brand,
      manifest_state: manifestState,
      image_mode: liveImages ? "live" : "recorded",
      checklist,
      checklist_checked: checkedCount(checklist),
      take_choices: allTakes.map((take) => ({
        take_id: take.id,
        choice: choiceFor(choices, take.id) ?? null,
        instructor_verdict: take.qc?.verdict ?? null,
      })),
      totals: {
        instructor_passing_qc: passingQcCount,
        instructor_pass_rate_percent: passRate,
        generated_video_seconds: generatedVideoSeconds,
        student_kept_takes: keepTakes.length,
        student_regenerate_takes: regenerateChoiceCount,
        student_judged_takes: judgedChoiceCount,
        student_keep_rate_percent: usableRate,
        student_selected_generation_seconds: generationSeconds,
        selected_video_seconds: selectedVideoSeconds,
      },
      provenance: manifest.provenance ?? null,
    };
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "promo-studio-review-record.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const renderVideo = (take: PromoTake, title: string) => {
    const src = assetUrl(take.file);
    return src ? (
      <video controls preload="metadata" poster={assetUrl(take.poster)} src={src} aria-label={title} />
    ) : (
      <div className="promo-placeholder">Waiting for synced media for {title}.</div>
    );
  };

  const renderComparison = (
    title: string,
    item?: {
      file?: string;
      poster?: string;
      prompt?: string;
      note?: string;
      verdict?: string;
      generation_seconds?: number;
      from?: string;
      from_file?: string;
    },
  ) => (
    <article className="promo-card">
      <div className="promo-media-frame">
        {item?.file ? (
          <video controls preload="metadata" poster={assetUrl(item.poster ?? posterFromVideo(item.file))} src={assetUrl(item.file)} />
        ) : <div className="promo-placeholder">Comparison media pending.</div>}
      </div>
      <div className="promo-card padded">
        <h3>{title}</h3>
        <div className="promo-result-meta">
          {item?.generation_seconds ? <span><Timer size={13} aria-hidden="true" /> {item.generation_seconds}s gen</span> : null}
          {item?.verdict ? <span><CheckCircle2 size={13} aria-hidden="true" /> {item.verdict}</span> : null}
          {item?.from ?? item?.from_file ? <span>Source: {item.from ?? item.from_file}</span> : null}
        </div>
        {item?.note ? <p>{item.note}</p> : null}
        {item?.prompt ? <div className="promo-prompt">{item.prompt}</div> : null}
      </div>
    </article>
  );

  return (
    <div className="page promo-studio">
      <style>{styles}</style>
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=media-creative")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>
      <header className="page-header">
        <div>
          <span className="eyebrow">ITAI 2372 · Module 8 · Case 3</span>
          <h1>Promo Studio · {manifest.brand}</h1>
          <p>
            Image and video generation lab for a fictional luxury car ad. Students compare prompt-only,
            keyframe-guided and remix workflows, then export their review decisions for the lab sheet.
          </p>
        </div>
        <div className="promo-top-actions">
          <span className={`promo-mode-pill${liveImages ? " live" : ""}`}>
            <Sparkles size={15} aria-hidden="true" /> {activeModeLabel}
          </span>
          <span className="promo-mode-pill">
            <Gauge size={15} aria-hidden="true" />
            {status ? `${status.remaining_daily_quota.images}/${status.caps.images} images left` : "Live API offline"}
          </span>
          <button className="promo-export" type="button" onClick={exportReview}>
            <Download size={16} aria-hidden="true" /> Export review record
          </button>
        </div>
      </header>

      <nav className="promo-tabs" aria-label="Promo Studio sections">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(id)}>
            <Icon size={17} aria-hidden="true" /> {label}
          </button>
        ))}
      </nav>

      {activeTab === "brief" ? (
        <section className="promo-panel" aria-label="Brief and shots">
          <div className="promo-hero-grid">
            <article className="promo-card padded promo-brand-lockup">
              <div className="promo-brand-title">
                <strong>{manifest.brand}</strong>
                <span>{manifest.tagline}</span>
              </div>
              <p className="promo-disclaimer"><CheckCircle2 size={18} aria-hidden="true" /> {manifest.disclaimer}</p>
              <p>
                The class goal is not "make the prettiest clip." The goal is to separate generation,
                editing, review, legal approval and provenance before an ad leaves the studio.
              </p>
              <div className="promo-kv">
                <div><span>Image model</span><strong>{manifest.models?.image ?? "Recorded fallback"}</strong></div>
                <div><span>Video model</span><strong>{manifest.models?.video ?? "Recorded fallback"}</strong></div>
              </div>
            </article>
            <article className="promo-card">
              <div className="promo-media-frame">
                <img src={assetUrl(manifest.design.hero)} alt={`${manifest.brand} design reference`} />
              </div>
              <div className="promo-card padded">
                <h3>Car description</h3>
                <p>{manifest.design.car_description}</p>
                <h3>Design QC notes</h3>
                <ul>
                  {manifest.design.qc_notes.map((note) => <li key={note}>{note}</li>)}
                </ul>
              </div>
            </article>
          </div>

          <article className="promo-card padded">
            <h2>Five-shot ad plan</h2>
            <ol className="promo-shot-list">
              {manifest.shots.map((shot, index) => (
                <li key={shot.id}>
                  <span className="promo-shot-index">{index + 1}</span>
                  <div>
                    <h3>{shot.title}</h3>
                    <p><strong>Picture:</strong> {shot.picture}</p>
                    <p><strong>Sound:</strong> {shot.sound}</p>
                  </div>
                </li>
              ))}
            </ol>
          </article>
        </section>
      ) : null}

      {activeTab === "image" ? (
        <section className="promo-panel" aria-label="Image generation">
          <div className="promo-two-col">
            <article className="promo-card padded">
              <h2>Image workflow</h2>
              <p className="promo-status-note">
                {liveImages
                  ? "LIVE mode is enabled. The browser sends only class choices to the server; the server builds the prompt and calls Azure."
                  : "RECORDED mode is active. Generate replays the design image; Edit cycles the five synced keyframes from the manifest."}
              </p>
              {statusError ? <p className="promo-status-note">{statusError}</p> : null}
              <div className="promo-controls">
                <label className="promo-field">
                  Shot prompt template
                  <select value={selectedShotId} onChange={(event) => setSelectedShotId(event.target.value)}>
                    {manifest.shots.map((shot) => <option key={shot.id} value={shot.id}>{shot.title}</option>)}
                  </select>
                </label>
                <div className="promo-control-grid">
                  <label className="promo-field">Paint color<select value={imageForm.paint} onChange={(event) => updateImageField("paint", event.target.value)}>{imageOptions.paint.map((item) => <option key={item}>{item}</option>)}</select></label>
                  <label className="promo-field">Time of day / lighting<select value={imageForm.lighting} onChange={(event) => updateImageField("lighting", event.target.value)}>{imageOptions.lighting.map((item) => <option key={item}>{item}</option>)}</select></label>
                  <label className="promo-field">Wheel style<select value={imageForm.wheels} onChange={(event) => updateImageField("wheels", event.target.value)}>{imageOptions.wheels.map((item) => <option key={item}>{item}</option>)}</select></label>
                  <label className="promo-field">Setting<select value={imageForm.setting} onChange={(event) => updateImageField("setting", event.target.value)}>{imageOptions.setting.map((item) => <option key={item}>{item}</option>)}</select></label>
                </div>
                <label className="promo-field">
                  Optional short direction
                  <input
                    maxLength={160}
                    value={imageForm.freeText}
                    onChange={(event) => updateImageField("freeText", event.target.value)}
                    placeholder="e.g., make the light sweep slower"
                  />
                </label>
                <div className="promo-button-row">
                  <button className="primary" type="button" disabled={imageBusy} onClick={() => void callImageApi("generate")}>
                    <Wand2 size={16} aria-hidden="true" /> {imageBusy ? "Working..." : "Generate"}
                  </button>
                  <button type="button" disabled={imageBusy} onClick={() => void callImageApi("edit")}>
                    <RefreshCw size={16} aria-hidden="true" /> Edit with options
                  </button>
                </div>
              </div>
              {imageError ? <p className="promo-error">{imageError}</p> : null}
            </article>

            <article className="promo-card">
              <div className="promo-media-frame">
                {imageResult ? (
                  <img src={imageResult.src} alt={imageResult.label} />
                ) : (
                  <img src={assetUrl(manifest.design.hero)} alt={`${manifest.brand} starting design`} />
                )}
              </div>
              <div className="promo-card padded">
                <h3>{imageResult?.label ?? "Starting design reference"}</h3>
                <div className="promo-result-meta">
                  {imageResult?.elapsedSeconds ? (
                    <span><Timer size={13} aria-hidden="true" /> {imageResult.elapsedSeconds.toFixed(1)} sec</span>
                  ) : <span><Timer size={13} aria-hidden="true" /> recorded</span>}
                  <span><Sparkles size={13} aria-hidden="true" /> {imageResult?.mode ?? "recorded"} mode</span>
                  <span>{imageResult?.file ?? manifest.design.hero}</span>
                </div>
                {imageResult?.prompt ? <div className="promo-prompt">{imageResult.prompt}</div> : null}
              </div>
            </article>
          </div>

          <article className="promo-card padded">
            <h2>Car QC checklist</h2>
            <div className="promo-checklist">
              {manifest.qc_checklist.map((item) => (
                <label key={item}>
                  <input
                    type="checkbox"
                    checked={Boolean(checklist[item])}
                    onChange={(event) => setChecklist((current) => ({ ...current, [item]: event.target.checked }))}
                  />
                  <span>{item}</span>
                </label>
              ))}
            </div>
          </article>
        </section>
      ) : null}

      {activeTab === "video" ? (
        <section className="promo-panel" aria-label="Video review">
          <article className="promo-card padded">
            <h2>Recorded Sora takes</h2>
            <div className="promo-stat-strip" aria-label="Running review totals">
              {revealVerdicts ? (
                <>
                  <div><strong>{passingQcCount}/{totalTakes}</strong><span>passing QC (keep + usable)</span></div>
                  <div><strong>{passRate}%</strong><span>pass rate</span></div>
                  <div><strong>{formatSeconds(generatedVideoSeconds)}</strong><span>video seconds generated</span></div>
                  <div><strong>{formatSeconds(manifest.stats?.mean_generation_seconds)}</strong><span>{manifest.stats?.generation_seconds_known_for ?? "mean generation seconds"}</span></div>
                </>
              ) : (
                <>
                  <div><strong>{totalTakes} takes</strong><span>{takesPerShot} per shot · avg {averageGenerationSeconds ? Math.round(averageGenerationSeconds) : "n/a"} s each</span></div>
                  <div><strong>{manifest.shots.length} shots</strong><span>recorded Sora grid</span></div>
                  <div><strong>{manifest.stats?.generation_seconds_known_for ?? "timed takes"}</strong><span>generation timing coverage</span></div>
                </>
              )}
              <div><strong>{keepChoiceCount} / {regenerateChoiceCount}</strong><span>Your picks: {keepChoiceCount} keep / {regenerateChoiceCount} regenerate of {judgedChoiceCount} judged</span></div>
            </div>
            <div className="promo-button-row">
              <button type="button" onClick={() => setRevealVerdicts((current) => !current)}>
                <Eye size={16} aria-hidden="true" /> {revealVerdicts ? "Hide" : "Reveal"} instructor verdicts
              </button>
            </div>
          </article>

          {manifest.shots.map((shot) => (
            <section key={shot.id} className="promo-shot-section" aria-label={`${shot.title} takes`}>
              <header>
                <div>
                  <span className="eyebrow">{shot.id}</span>
                  <h3>{shot.title}</h3>
                  <p>{shot.picture}</p>
                </div>
                <span className="promo-mode-pill">{shot.sound}</span>
              </header>
              <div className="promo-take-grid">
                {fourTakes(shot).map((take) => {
                  const choice = choiceFor(choices, take.id);
                  return (
                    <article key={take.id} className="promo-take-card">
                      <header>
                        <strong>{take.id}</strong>
                        <span>{take.generation_seconds ? `${take.generation_seconds}s gen` : "pending"}</span>
                      </header>
                      <div className="promo-media-frame">{renderVideo(take, take.id)}</div>
                      <div className="promo-choice">
                        <button className={choice === "keep" ? "active keep" : ""} type="button" onClick={() => updateChoice(take.id, "keep")}>Keep</button>
                        <button className={choice === "regenerate" ? "active regenerate" : ""} type="button" onClick={() => updateChoice(take.id, "regenerate")}>Regenerate</button>
                      </div>
                      {revealVerdicts ? (
                        <div className="promo-verdict">
                          <strong className={`promo-verdict-badge ${isPassingVerdict(take.qc?.verdict) ? "pass" : "review"}`}>
                            Instructor: {take.qc?.verdict ?? "pending"}
                          </strong>
                          {take.qc?.issues?.[0] ? <p className="promo-verdict-issue">First issue: {take.qc.issues[0]}</p> : null}
                          {take.qc?.note ? <p>{take.qc.note}</p> : null}
                          {take.qc?.metrics ? (
                            <span className="promo-metric-row">
                              {typeof take.qc.metrics.motion === "number" ? <span>motion {take.qc.metrics.motion}</span> : null}
                              {typeof take.qc.metrics.first_vs_last === "number" ? <span>first/last {take.qc.metrics.first_vs_last}</span> : null}
                              {typeof take.qc.metrics.mean_db === "number" ? <span>mean {take.qc.metrics.mean_db} dB</span> : null}
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}

          <article className="promo-card padded">
            <h2>Comparisons</h2>
            <div className="promo-comparison-grid">
              {renderComparison("Text-only", manifest.comparisons?.text_only)}
              {renderComparison("Keyframe-guided", manifest.comparisons?.keyframe_guided ?? {
                file: manifest.comparisons?.text_only?.keyframe_guided ?? manifest.shots[0]?.takes?.[0]?.file,
                poster: posterFromVideo(manifest.comparisons?.text_only?.keyframe_guided) ?? manifest.shots[0]?.takes?.[0]?.poster,
                prompt: manifest.shots.find((shot) => shot.id === "s2")?.keyframe_prompt ?? manifest.shots[0]?.keyframe_prompt,
                note: "Same shot reviewed with the keyframe guide so students can compare design drift.",
              })}
              {renderComparison("Remix", manifest.comparisons?.remix)}
            </div>
          </article>

          {liveVideo ? (
            <article className="promo-card padded">
              <h2>Generate one live take</h2>
              <div className="promo-live-video">
                <button type="button" disabled={liveVideoBusy} onClick={() => void startLiveVideo()}>
                  <Play size={16} aria-hidden="true" /> {liveVideoBusy ? "Generating..." : "Generate one live take"}
                </button>
                {liveVideoJob ? <span className="promo-mode-pill">Job {liveVideoJob.id}: {liveVideoJob.status} {liveVideoJob.progress ?? 0}%</span> : null}
              </div>
              {liveVideoError ? <p className="promo-error">{liveVideoError}</p> : null}
              {liveVideoJob?.video_data_url ? (
                <div className="promo-media-frame"><video controls src={liveVideoJob.video_data_url} /></div>
              ) : null}
            </article>
          ) : null}
        </section>
      ) : null}

      {activeTab === "guardrail" ? (
        <section className="promo-panel" aria-label="Guardrail review">
          <article className="promo-card padded promo-guardrail">
            <h2>What the guardrail missed</h2>
            <p>
              The vendor guardrail is not the brand-and-legal review. This in-class-only smoke test
              asked for a real car brand and was not refused, so students must still run trademark,
              trade dress and publishability review outside the model.
            </p>
            <div className="promo-kv">
              <div><span>Result</span><strong>{manifest.guardrail?.brand_test?.result ?? "Not recorded"}</strong></div>
              <div><span>Use boundary</span><strong>{manifest.guardrail?.brand_test?.in_class_only ? "In-class only" : "Manifest controlled"}</strong></div>
            </div>
            {manifest.guardrail?.brand_test?.note ? <p>{manifest.guardrail.brand_test.note}</p> : null}
            {manifest.guardrail?.brand_test?.prompt ? <div className="promo-prompt">{manifest.guardrail.brand_test.prompt}</div> : null}
          </article>
          <article className="promo-card padded promo-overblock">
            <h2>What the filter over-blocked</h2>
            <p>
              Guardrails can miss brand-risk prompts and also block harmless classroom prompts.
              Both outcomes still need human review and a fallback plan.
            </p>
            <div className="promo-kv">
              <div><span>Requests blocked</span><strong>{manifest.guardrail?.over_blocking?.requests_blocked ?? 0}</strong></div>
              <div><span>Shots affected</span><strong>{manifest.guardrail?.over_blocking?.shots_affected?.join(", ") || "Not recorded"}</strong></div>
            </div>
            {manifest.guardrail?.over_blocking?.tags?.length ? (
              <div className="promo-result-meta">
                {manifest.guardrail.over_blocking.tags.map((tag, index) => <span key={`${tag}-${index}`}>{tag}</span>)}
              </div>
            ) : null}
            {manifest.guardrail?.over_blocking?.note ? <p>{manifest.guardrail.over_blocking.note}</p> : null}
          </article>
          {manifest.guardrail?.brand_test?.file ? (
            <article className="promo-card promo-guardrail-clip">
              <div className="promo-media-frame">
                <span className="promo-media-label">In-class only</span>
                <video controls preload="metadata" poster={assetUrl(manifest.guardrail.brand_test.poster)} src={assetUrl(manifest.guardrail.brand_test.file)} />
              </div>
            </article>
          ) : (
            <p className="promo-status-note">The real-brand test clip is excluded from this build; discuss the prompt and result without projecting the media.</p>
          )}
        </section>
      ) : null}

      {activeTab === "provenance" ? (
        <section className="promo-panel" aria-label="Provenance">
          <div className="promo-two-col">
            <article className="promo-card">
              <div className="promo-media-frame">
                {manifest.final?.file ? (
                  <video controls preload="metadata" poster={assetUrl(manifest.final.poster)} src={assetUrl(manifest.final.file)} />
                ) : <div className="promo-placeholder">Final 20-second ad pending in the synced manifest.</div>}
              </div>
            </article>
            <article className="promo-card padded">
              <h2>Final ad provenance</h2>
              <p className="promo-disclaimer">{manifest.final?.label ?? manifest.final?.c2pa?.visible_label ?? manifest.disclaimer}</p>
              <div className="promo-kv">
                <div><span>Duration</span><strong>{manifest.final?.duration_seconds ? `${manifest.final.duration_seconds}s` : "Not recorded"}</strong></div>
                <div><span>Credential tool</span><strong>{manifest.provenance?.tool ?? "Not recorded"}</strong></div>
              </div>
              <ul className="promo-provenance-list">
                {(manifest.provenance?.steps?.length ? manifest.provenance.steps : [
                  { step: "Raw Sora credential", manifest_present: manifest.final?.c2pa?.raw_take, state: manifest.final?.c2pa?.raw_take ? "Present" : "Not recorded" },
                  { step: "After re-encode", manifest_present: manifest.final?.c2pa?.after_reencode, state: manifest.final?.c2pa?.after_reencode ? "Present" : "Not present" },
                ]).map((step) => (
                  <li key={`${step.step}-${step.file ?? ""}`}>
                    <span>
                      {step.step}
                      {step.file ? <small>{step.file}</small> : null}
                      {step.failures?.length ? <small>Failures: {step.failures.join(", ")}</small> : null}
                    </span>
                    <strong>{step.manifest_present ? displayProvenanceState(step) : "No manifest"}</strong>
                  </li>
                ))}
              </ul>
              <p className="promo-status-note">
                'untrusted' only means the checker's default trust list doesn't include Microsoft's certificate; it is not tampering.
              </p>
              {manifest.provenance?.takeaway ? <p>{manifest.provenance.takeaway}</p> : null}
              <h3>Edit list</h3>
              <ul>
                {(manifest.final?.edit_list ?? []).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </article>
          </div>
          {manifest.final?.end_card ? (
            <article className="promo-card">
              <div className="promo-media-frame">
                <img src={assetUrl(manifest.final.end_card)} alt={`${manifest.brand} final end card`} />
              </div>
            </article>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
