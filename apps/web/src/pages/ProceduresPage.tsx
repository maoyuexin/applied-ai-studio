import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  FileText,
  Gauge,
  Info,
  Layers3,
  Library,
  ListChecks,
  Lock,
  Play,
  Scale,
  ScrollText,
  Search,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import {
  askProcedureQuestion,
  getProceduresCorpus,
  getProceduresModel,
  getProceduresQuestions,
  type ProcedureAnswer,
  type ProcedureCorpus,
  type ProcedureModelInfo,
  type ProcedureQuestion,
} from "../proceduresApi";
import { navigate } from "../router";

type View = "ask" | "library" | "evidence";

const views = [
  {
    id: "ask" as const,
    label: "Ask a question",
    detail: "Passages, the score, then an answer or a refusal",
    icon: Search,
  },
  {
    id: "library" as const,
    label: "The library and its licenses",
    detail: "Four layers, and what we are allowed to hold",
    icon: Library,
  },
  {
    id: "evidence" as const,
    label: "Evidence",
    detail: "What was measured, and what the numbers hide",
    icon: Layers3,
  },
];

const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const score = (value: number): string => value.toFixed(2);
const integer = (value: number): string => new Intl.NumberFormat("en-US").format(value);
const clampPercent = (value: number): number => Math.min(100, Math.max(0, value * 100));
const shortDate = (value: string): string => {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(
      parsed,
    );
};
const layerClass = (layer: string): string => `prc-layer-${layer.replace(/_/g, "-")}`;

const pageStyles = `
.prc-page .page-back-button { min-height: 44px; }
.prc-page h2 { margin: 0; font-size: 18px; line-height: 1.3; }
.prc-page h3 { margin: 0; font-size: 14px; line-height: 1.35; }
.prc-page .prc-num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

.prc-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 18px; }
.prc-header h1 { margin: 3px 0 6px; font-size: 27px; line-height: 1.2; font-weight: 750; }
.prc-header p { margin: 0; max-width: 740px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.prc-status { min-height: 44px; display: flex; align-items: center; gap: 10px; padding: 8px 13px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.prc-status span.prc-lamp { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--text-muted); }
.prc-status span.prc-lamp.ready { background: var(--green); box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.12); }
.prc-status strong { display: block; font-size: 12px; }
.prc-status small { display: block; margin-top: 2px; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }

.prc-metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin-bottom: 18px; }
.prc-metric-strip > div { min-height: 82px; padding: 13px 16px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.prc-metric-strip > div:last-child { border-right: 0; }
.prc-metric-strip strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 20px; }
.prc-metric-strip span { margin-top: 2px; font-size: 11px; }
.prc-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: 10px; line-height: 1.45; }

.prc-boundary { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 11px; margin-bottom: 16px; padding: 13px 15px; border: 1px solid rgba(126, 174, 184, 0.4); border-left: 3px solid var(--teal); border-radius: 6px; background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.prc-boundary strong { display: block; color: var(--text); font-size: 13px; }
.prc-boundary p { margin: 5px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }

.prc-switcher { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.prc-switcher button { min-height: 62px; padding: 11px 14px; display: flex; align-items: center; gap: 11px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; transition: 160ms ease; }
.prc-switcher button:last-child { border-right: 0; }
.prc-switcher button:hover { background: var(--surface-raised); color: var(--text-secondary); }
.prc-switcher button.active { background: rgba(232, 145, 60, 0.09); box-shadow: inset 0 -3px 0 var(--orange); color: var(--orange); }
.prc-switcher strong { display: block; color: var(--text); font-size: 13px; }
.prc-switcher small { display: block; margin-top: 3px; color: var(--text-muted); font-size: 11px; line-height: 1.4; }

.prc-panel { min-width: 0; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.prc-panel > header { padding: 13px 16px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); }
.prc-panel > header > svg { flex: 0 0 auto; color: var(--text-muted); }
.prc-panel > header span { display: block; color: var(--teal); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-panel > header strong { display: block; margin-top: 4px; font-size: 14px; }
.prc-panel > header small { display: block; margin-top: 4px; color: var(--text-muted); font-size: 11px; line-height: 1.5; }

.prc-ask-grid { display: grid; grid-template-columns: minmax(260px, 0.9fr) minmax(0, 0.95fr) minmax(0, 1.5fr); gap: 14px; align-items: start; }

.prc-shortcut { min-height: 52px; width: calc(100% - 28px); margin: 12px 14px 0; padding: 10px 12px; display: flex; align-items: center; gap: 9px; border: 1px dashed rgba(126, 174, 184, 0.6); border-radius: 5px; background: rgba(126, 174, 184, 0.08); color: var(--teal); font-size: 11px; line-height: 1.5; text-align: left; }
.prc-shortcut:hover { background: rgba(126, 174, 184, 0.16); }
.prc-shortcut svg { flex: 0 0 auto; }

.prc-question-list { max-height: 560px; overflow-y: auto; padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 7px; }
.prc-question-list button { min-height: 76px; flex: 0 0 auto; padding: 10px 12px; display: block; width: 100%; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); color: var(--text-secondary); text-align: left; transition: 140ms ease; }
.prc-question-list button:hover { border-color: var(--teal); color: var(--text); }
.prc-question-list button:focus-visible { outline-offset: -2px; }
.prc-question-list button.active { border-color: var(--orange); background: rgba(232, 145, 60, 0.1); color: var(--text); }
.prc-question-list button > span.prc-qid { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-question-list button strong { display: block; margin: 4px 0 5px; font-size: 12px; line-height: 1.45; }
.prc-question-list button small { display: block; color: var(--text-muted); font-size: 10px; line-height: 1.5; }

.prc-chip { display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border: 1px solid var(--border-strong); border-radius: 20px; color: var(--text-secondary); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 9px; font-style: normal; text-transform: none; white-space: nowrap; }
.prc-chip.prc-refuse { border-color: rgba(126, 174, 184, 0.55); background: rgba(126, 174, 184, 0.12); color: var(--teal); }
.prc-chip.prc-answered { border-color: rgba(74, 222, 128, 0.4); background: rgba(74, 222, 128, 0.08); color: var(--green); }
.prc-chip.prc-caution { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.1); color: var(--amber); }
.prc-chip.prc-off { border-color: rgba(228, 90, 88, 0.5); background: rgba(228, 90, 88, 0.1); color: #f4a5a4; }
.prc-chip.prc-layer-regulation { border-color: rgba(240, 180, 41, 0.5); color: var(--amber); }
.prc-chip.prc-layer-site-procedure { border-color: rgba(126, 174, 184, 0.55); color: var(--teal); }
.prc-chip.prc-layer-equipment { border-color: rgba(232, 145, 60, 0.55); color: var(--orange); }
.prc-chip.prc-layer-plain-language { border-color: rgba(201, 106, 150, 0.55); color: var(--pink); }
.prc-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }

.prc-editor { padding: 14px 16px; }
.prc-editor label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 600; }
.prc-editor textarea { width: 100%; min-height: 108px; padding: 11px 12px; border: 1px solid var(--border); border-radius: 5px; background: #14161c; color: var(--text); font-family: var(--font-body); font-size: 13px; line-height: 1.6; resize: vertical; }
.prc-editor textarea:hover { border-color: var(--border-strong); }
.prc-editor-foot { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.prc-counter { color: var(--text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 10px; }
.prc-counter.over { color: #f4a5a4; }
.prc-editor .primary-button { margin-top: 0; min-height: 44px; }
.prc-side-note { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 9px; margin: 0 16px 14px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-muted); font-size: 11px; line-height: 1.6; }
.prc-side-note svg { margin-top: 1px; }
.prc-side-note + .prc-side-note { margin-top: -6px; }

.prc-result-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 16px; }
.prc-result-empty { min-height: 320px; display: grid; place-content: center; justify-items: center; gap: 9px; padding: 30px; text-align: center; color: var(--text-muted); }
.prc-result-empty strong { color: var(--text); font-size: 14px; }
.prc-result-empty p { margin: 0; max-width: 340px; font-size: 11px; line-height: 1.65; }

.prc-block > h3 { margin-bottom: 4px; }
.prc-block > p.prc-lede { margin: 0 0 10px; color: var(--text-muted); font-size: 11px; line-height: 1.6; }

.prc-passage { margin-bottom: 9px; padding: 11px 13px; border: 1px solid var(--border); border-left: 3px solid var(--border-strong); border-radius: 5px; background: var(--surface-raised); }
.prc-passage:last-child { margin-bottom: 0; }
.prc-passage.prc-layer-regulation { border-left-color: var(--amber); }
.prc-passage.prc-layer-site-procedure { border-left-color: var(--teal); }
.prc-passage.prc-layer-equipment { border-left-color: var(--orange); }
.prc-passage.prc-layer-plain-language { border-left-color: var(--pink); }
.prc-passage-top { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.prc-passage-top b { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 12px; color: var(--text); }
.prc-passage-top i { color: var(--text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 11px; font-style: normal; }
.prc-passage-source { margin: 6px 0 0; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.prc-passage-text { margin: 9px 0 0; padding: 9px 11px; border-radius: 4px; background: #14161c; color: var(--text-secondary); font-size: 12px; line-height: 1.75; white-space: pre-wrap; }
.prc-passage-also { margin: 7px 0 0; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; line-height: 1.6; word-break: break-word; }

.prc-rail-wrap { padding: 4px 2px 0; }
.prc-rail { position: relative; height: 34px; margin: 22px 0 6px; border: 1px solid var(--border); border-radius: 4px; background: linear-gradient(90deg, rgba(126, 174, 184, 0.16) 0%, rgba(126, 174, 184, 0.16) 48%, rgba(74, 222, 128, 0.12) 48%, rgba(74, 222, 128, 0.12) 100%); }
.prc-rail-cut { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--text); }
.prc-rail-cut b { position: absolute; left: 50%; bottom: calc(100% + 5px); transform: translateX(-50%); color: var(--text); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 9px; white-space: nowrap; }
.prc-rail-dot { position: absolute; top: 50%; width: 14px; height: 14px; margin: -7px 0 0 -7px; border: 2px solid var(--bg); border-radius: 50%; background: var(--orange); }
.prc-rail-dot b { position: absolute; left: 50%; top: calc(100% + 6px); transform: translateX(-50%); color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 9px; white-space: nowrap; }
.prc-rail-ends { display: flex; justify-content: space-between; gap: 14px; margin-top: 22px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.prc-rail-ends span { max-width: 46%; }
.prc-rail-ends span:last-child { text-align: right; }

.prc-verdict { min-height: 96px; padding: 14px 15px; display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 12px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface-raised); }
.prc-verdict.prc-answered { border-color: rgba(74, 222, 128, 0.4); background: rgba(74, 222, 128, 0.06); color: var(--green); }
.prc-verdict.prc-refuse { border-color: rgba(126, 174, 184, 0.5); background: rgba(126, 174, 184, 0.08); color: var(--teal); }
.prc-verdict.prc-none { color: var(--text-muted); }
.prc-verdict > svg { margin-top: 2px; }
.prc-verdict span.prc-kicker { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-verdict strong { display: block; margin: 5px 0 6px; color: var(--text); font-size: 15px; line-height: 1.35; }
.prc-verdict p { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.prc-verdict p + p { margin-top: 9px; }
.prc-verdict blockquote { margin: 10px 0 0; padding: 11px 13px; border-left: 2px solid var(--border-strong); border-radius: 0 4px 4px 0; background: rgba(20, 22, 28, 0.65); color: var(--text); font-size: 12.5px; line-height: 1.8; }

.prc-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 12px; }
.prc-facts > div { min-height: 60px; padding: 9px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.prc-facts span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-facts strong { display: block; margin-top: 4px; color: var(--text); font-size: 12px; line-height: 1.45; word-break: break-word; }

.prc-note { margin: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-muted); font-size: 11px; line-height: 1.65; }
.prc-note strong { color: var(--text); }
.prc-note.prc-caution { border-color: rgba(240, 180, 41, 0.45); background: rgba(240, 180, 41, 0.06); color: var(--text-secondary); }

.prc-teaching { padding: 13px 15px; border: 1px solid rgba(240, 180, 41, 0.45); border-left: 3px solid var(--amber); border-radius: 6px; background: rgba(240, 180, 41, 0.06); }
.prc-teaching > div { display: flex; align-items: center; gap: 9px; color: var(--amber); }
.prc-teaching strong { font-size: 13px; }
.prc-teaching p { margin: 9px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }

.prc-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin: 22px 0 12px; }
.prc-section-heading:first-child { margin-top: 0; }
.prc-section-heading span.prc-kicker { display: block; color: var(--teal); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-section-heading h2 { margin: 5px 0; }
.prc-section-heading p { margin: 0; max-width: 780px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }

.prc-lesson { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 11px; margin: 0 0 14px; padding: 13px 15px; border: 1px solid rgba(232, 145, 60, 0.4); border-left: 3px solid var(--orange); border-radius: 6px; background: rgba(232, 145, 60, 0.06); color: var(--orange); }
.prc-lesson strong { display: block; color: var(--text); font-size: 13px; }
.prc-lesson p { margin: 6px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.prc-lesson p + p { margin-top: 8px; }

.prc-layer-grid { display: flex; flex-direction: column; gap: 12px; margin-bottom: 14px; }
.prc-layer-head { padding: 13px 16px; display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; flex-wrap: wrap; border-bottom: 1px solid var(--border); }
.prc-layer-head strong { display: block; font-size: 14px; }
.prc-layer-head p { margin: 5px 0 0; max-width: 640px; color: var(--text-secondary); font-size: 11px; line-height: 1.6; }
.prc-layer-counts { display: flex; gap: 18px; flex-wrap: wrap; }
.prc-layer-counts div { min-width: 74px; }
.prc-layer-counts span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-layer-counts b { display: block; margin-top: 3px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 15px; }

.prc-table-wrap { overflow-x: auto; }
.prc-table { width: 100%; min-width: 560px; border-collapse: collapse; font-size: 12px; }
.prc-table th, .prc-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
.prc-table th { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; font-weight: 500; text-transform: uppercase; }
.prc-table td.num, .prc-table th.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.prc-table tbody tr:last-child td { border-bottom: 0; }
.prc-table tr.prc-chosen td { background: rgba(232, 145, 60, 0.08); }
.prc-table tr.prc-held td { color: var(--text-muted); }
.prc-table td small { display: block; margin-top: 3px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }

.prc-two-up { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 12px; margin-bottom: 14px; align-items: start; }
.prc-honest { border: 1px solid rgba(240, 180, 41, 0.4); border-radius: 6px; background: rgba(240, 180, 41, 0.05); overflow: hidden; }
.prc-honest > header { padding: 13px 15px; display: flex; align-items: center; gap: 9px; border-bottom: 1px solid rgba(240, 180, 41, 0.3); color: var(--amber); }
.prc-honest > header strong { font-size: 14px; line-height: 1.35; }
.prc-honest-body { padding: 13px 15px; }
.prc-headline { display: flex; align-items: baseline; gap: 10px; margin-bottom: 11px; }
.prc-headline b { color: var(--amber); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 26px; }
.prc-headline span { color: var(--text-secondary); font-size: 12px; line-height: 1.55; }
.prc-honest-body p { margin: 0 0 10px; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.prc-honest-body p:last-child { margin-bottom: 0; }

.prc-swap { display: flex; align-items: center; gap: 12px; margin-bottom: 11px; padding: 11px 13px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.prc-swap > div { flex: 1 1 0; min-width: 0; }
.prc-swap span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; line-height: 1.45; }
.prc-swap strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 16px; }
.prc-swap > svg { flex: 0 0 auto; color: var(--text-muted); }

.prc-card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; margin-bottom: 14px; }
.prc-card { min-height: 104px; padding: 13px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.prc-card > svg { color: var(--teal); }
.prc-card span { display: block; margin-top: 8px; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.prc-card strong { display: block; margin-top: 5px; font-size: 13px; line-height: 1.4; }
.prc-card small { display: block; margin-top: 5px; color: var(--text-muted); font-size: 10px; line-height: 1.6; }

.prc-list-panel { padding: 14px 16px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.prc-list-panel ul { margin: 10px 0 0; padding-left: 18px; color: var(--text-secondary); font-size: 12px; line-height: 1.75; }
.prc-list-panel li + li { margin-top: 7px; }

.prc-body-pad { padding: 14px 16px; }

@media (max-width: 1240px) {
  .prc-ask-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .prc-ask-grid > .prc-result-panel { grid-column: 1 / -1; }
  .prc-question-list { max-height: 400px; }
}
@media (max-width: 900px) {
  .prc-ask-grid { grid-template-columns: minmax(0, 1fr); }
  .prc-metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .prc-switcher { grid-template-columns: minmax(0, 1fr); }
  .prc-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .prc-switcher button:last-child { border-bottom: 0; }
}
@media (max-width: 640px) {
  .prc-metric-strip { grid-template-columns: minmax(0, 1fr); }
  .prc-metric-strip > div { border-right: 0; border-bottom: 1px solid var(--border); }
  .prc-metric-strip > div:last-child { border-bottom: 0; }
  .prc-question-list { max-height: 340px; }
  .prc-editor-foot { flex-direction: column; align-items: stretch; }
  .prc-editor .primary-button { width: 100%; }
  .prc-swap { flex-direction: column; align-items: stretch; }
  .prc-swap > svg { transform: rotate(90deg); align-self: center; }
  .prc-rail-ends { flex-direction: column; gap: 6px; }
  .prc-rail-ends span, .prc-rail-ends span:last-child { max-width: none; text-align: left; }
  .prc-verdict { grid-template-columns: minmax(0, 1fr); }
  .prc-verdict > svg { display: none; }
}
`;

export default function ProceduresPage() {
  const [view, setView] = useState<View>("ask");
  const [model, setModel] = useState<ProcedureModelInfo | null>(null);
  const [questions, setQuestions] = useState<ProcedureQuestion[]>([]);
  const [corpus, setCorpus] = useState<ProcedureCorpus | null>(null);
  const [selectedQid, setSelectedQid] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<ProcedureAnswer | null>(null);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [askError, setAskError] = useState<string | null>(null);
  const askSequence = useRef(0);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getProceduresModel(), getProceduresQuestions(20), getProceduresCorpus()])
      .then(async ([modelInfo, packaged, corpusView]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setQuestions(packaged);
        setCorpus(corpusView);
        const first = packaged[0];
        if (!first) return;
        setSelectedQid(first.qid);
        setDraft(first.question);
        const firstResult = await askProcedureQuestion(first.question);
        if (!cancelled) setResult(firstResult);
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxCharacters = model?.max_question_characters ?? 500;
  const threshold = model?.policy.refusal_threshold ?? 0.48;
  const trimmed = draft.trim();
  const overCap = draft.length > maxCharacters;
  const canAsk = trimmed.length > 0 && !overCap && !running;

  const referenceRefusal =
    questions.find(
      (item) => item.refusal_kind === "refused_incorporated_by_reference" && item.is_discussion_case,
    ) ??
    questions.find((item) => item.refusal_kind === "refused_incorporated_by_reference") ??
    questions.find((item) => item.is_refusal) ??
    null;

  const runAsk = async (question: string, qid: string | null) => {
    const text = question.trim();
    if (!text || text.length > maxCharacters) return;
    const ticket = askSequence.current + 1;
    askSequence.current = ticket;
    setSelectedQid(qid);
    setDraft(question);
    setResult(null);
    setAskError(null);
    setRunning(true);
    try {
      const answer = await askProcedureQuestion(text);
      if (askSequence.current === ticket) setResult(answer);
    } catch (reason) {
      if (askSequence.current === ticket) {
        setResult(null);
        setAskError(
          reason instanceof Error ? reason.message : "The library could not be searched just now.",
        );
      }
    } finally {
      if (askSequence.current === ticket) setRunning(false);
    }
  };

  const refused = result ? result.decision !== "answered" : false;
  const hasDraftedAnswer = Boolean(result?.answer);

  return (
    <div className="page prc-page">
      <style>{pageStyles}</style>

      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="prc-header">
        <div>
          <span className="eyebrow">Search over documents · Maintenance and safety</span>
          <h1>Find the rule that governs the job, and the passage it comes from</h1>
          <p>
            A technician asks a question in their own words. The assistant searches a fixed library
            of safety law, one operator's own written procedures, one equipment manual and two
            plain-language guides, and hands back the closest passages with the citation beside each
            one. Then it either shows an answer written from those passages, or it says it cannot
            answer and points somewhere else.
          </p>
        </div>
        <div className="prc-status">
          <span className={model ? "prc-lamp ready" : "prc-lamp"} aria-hidden="true" />
          <div>
            <strong>{model ? "Library loaded" : "Connecting to the library"}</strong>
            <small>
              FastAPI · {model ? model.representation.embedder.split("/").pop() : "MiniLM"} ·{" "}
              {model ? model.version : "raglab"}
            </small>
          </div>
        </div>
      </header>

      {model ? (
        <section className="prc-metric-strip" aria-label="What is in the library and how it answers">
          <div>
            <strong className="prc-num">{integer(model.corpus.documents_indexed)}</strong>
            <span>documents in the library</span>
            <small>
              Downloaded once and committed. Pinned to {shortDate(model.corpus.date_pin)}; nothing
              here reaches the internet.
            </small>
          </div>
          <div>
            <strong className="prc-num">{integer(model.corpus.chunks)}</strong>
            <span>passages it can return</span>
            <small>
              Each one carries the citation a person looks up. It shows the closest{" "}
              {model.policy.top_k_shown}.
            </small>
          </div>
          <div>
            <strong className="prc-num">{score(model.policy.refusal_threshold)}</strong>
            <span>the line it refuses below</span>
            <small>Closeness runs 0 to 1. Below this line, nothing is close enough to use.</small>
          </div>
          <div>
            <strong className="prc-num">
              {integer(model.packaged_refusals)} of {integer(model.packaged_questions)}
            </strong>
            <span>packaged questions it refuses</span>
            <small>Refusing is a correct answer here, not a failure.</small>
          </div>
        </section>
      ) : null}

      <div className="prc-boundary">
        <ShieldCheck size={19} aria-hidden="true" />
        <div>
          <strong>The assistant retrieves and drafts. It never authorizes work.</strong>
          <p>
            {model?.boundary ??
              "The assistant retrieves and drafts. It never authorizes work, never approves a lockout, and never answers a safety question from the model's own memory. A qualified person reads the cited passage and decides."}{" "}
            Nothing on this page clears a machine, issues a permit or releases a lock.
          </p>
        </div>
      </div>

      <nav className="prc-switcher" aria-label="Procedure assistant views">
        {views.map(({ id, label, detail, icon: Icon }) => (
          <button
            type="button"
            key={id}
            className={view === id ? "active" : ""}
            aria-pressed={view === id}
            onClick={() => setView(id)}
          >
            <Icon size={19} aria-hidden="true" />
            <span>
              <strong>{label}</strong>
              <small>{detail}</small>
            </span>
          </button>
        ))}
      </nav>

      {loadError ? (
        <div className="error-banner" role="alert">
          {loadError}
        </div>
      ) : null}
      {!model && !loadError ? (
        <div className="loading-state">Loading the library, the packaged questions and the licenses...</div>
      ) : null}

      {view === "ask" && model ? (
        <section className="prc-ask-grid">
          <section className="prc-panel">
            <header>
              <div>
                <span>Step 1</span>
                <strong>Pick a question</strong>
                <small>
                  {integer(model.packaged_questions)} questions written the way a technician asks
                  them. Each one was answered or refused before this demo shipped, and checked by
                  hand.
                </small>
              </div>
              <ListChecks size={18} aria-hidden="true" />
            </header>

            {referenceRefusal ? (
              <button
                type="button"
                className="prc-shortcut"
                onClick={() => void runAsk(referenceRefusal.question, referenceRefusal.qid)}
              >
                <ShieldCheck size={17} aria-hidden="true" />
                <span>
                  Show one it refuses — the rule names an outside standard the library does not hold,
                  so the only correct answer is to say so
                </span>
              </button>
            ) : null}

            <div className="prc-question-list">
              {questions.length === 0 ? (
                <p className="prc-note">No packaged questions came back from the service.</p>
              ) : null}
              {questions.map((item) => (
                <button
                  type="button"
                  key={item.qid}
                  className={selectedQid === item.qid ? "active" : ""}
                  aria-pressed={selectedQid === item.qid}
                  onClick={() => void runAsk(item.question, item.qid)}
                >
                  <span className="prc-qid">
                    {item.qid} · {item.bucket_label}
                  </span>
                  <strong>{item.question}</strong>
                  <small>{item.summary}</small>
                  <span className="prc-chip-row">
                    <em className={item.is_refusal ? "prc-chip prc-refuse" : "prc-chip prc-answered"}>
                      {item.is_refusal ? "Refuses" : "Answers"}
                    </em>
                    <em className={`prc-chip ${layerClass(item.top_layer)}`}>
                      {item.top_layer_label}
                    </em>
                    <em className="prc-chip">closeness {score(item.top_score)}</em>
                    {item.is_discussion_case ? (
                      <em className="prc-chip prc-caution">Discussion case</em>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="prc-panel">
            <header>
              <div>
                <span>Step 2</span>
                <strong>Or type your own</strong>
                <small>
                  Your words, not the wording of the rule. That is the hard case, and the one this
                  was measured on.
                </small>
              </div>
              <FileText size={18} aria-hidden="true" />
            </header>
            <div className="prc-editor">
              <label htmlFor="prc-question">Your question</label>
              <textarea
                id="prc-question"
                value={draft}
                aria-describedby="prc-question-help"
                aria-invalid={overCap || undefined}
                spellCheck={false}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setSelectedQid(null);
                  setResult(null);
                  setAskError(null);
                }}
              />
              <div className="prc-editor-foot">
                <span className={overCap ? "prc-counter over" : "prc-counter"} id="prc-question-help">
                  {integer(draft.length)} of {integer(maxCharacters)} characters
                  {overCap ? " — too long, ask the shorter question" : ""}
                </span>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => void runAsk(draft, null)}
                  disabled={!canAsk}
                >
                  <Play size={15} fill="currentColor" aria-hidden="true" />
                  {running ? "Searching..." : "Search the library"}
                </button>
              </div>
            </div>
            <p className="prc-side-note">
              <Lock size={15} aria-hidden="true" />
              <span>
                There is nothing to upload and no setting to change. The library is fixed and pinned
                to {shortDate(model.corpus.date_pin)}, and the only thing this page sends is the
                sentence you typed. Nothing you type is saved.
              </span>
            </p>
            <p className="prc-side-note">
              <Info size={15} aria-hidden="true" />
              <span>
                Type a question of your own and you get the passages and nothing more. The assistant
                does not write new prose while you wait; the {integer(model.packaged_questions)}{" "}
                packaged answers were written from their passages and checked before they shipped.
              </span>
            </p>
          </section>

          <section className="prc-panel prc-result-panel" aria-live="polite">
            <header>
              <div>
                <span>Step 3</span>
                <strong>What came back</strong>
                <small>
                  The passages first, then how close the closest one was, then what the assistant did
                  with it.
                </small>
              </div>
              <Search size={18} aria-hidden="true" />
            </header>

            {askError ? (
              <div className="prc-body-pad">
                <div className="error-banner" role="alert">
                  {askError}
                </div>
              </div>
            ) : null}

            {result ? (
              <div className="prc-result-body">
                <div className="prc-block">
                  <h3>The passages the search returned</h3>
                  <p className="prc-lede">
                    Ranked by how closely each passage reads like the question. The citation is what
                    a qualified person looks up; the label under it says which layer of the library
                    it came from. Nothing here is rewritten — this is the document's own text.
                  </p>
                  {result.passages.length === 0 ? (
                    <p className="prc-note">
                      The search returned no passages at all for this question.
                    </p>
                  ) : (
                    result.passages.map((passage) => (
                      <article
                        className={`prc-passage ${layerClass(passage.layer)}`}
                        key={passage.chunk_id}
                      >
                        <div className="prc-passage-top">
                          <b>
                            {passage.rank}. {passage.citation}
                          </b>
                          <i>closeness {score(passage.score)}</i>
                        </div>
                        <p className="prc-passage-source">
                          {passage.source} · {passage.source_title} · {integer(passage.words)} words
                        </p>
                        <span className="prc-chip-row">
                          <em className={`prc-chip ${layerClass(passage.layer)}`}>
                            {passage.layer_label}
                          </em>
                          <em
                            className={
                              passage.above_threshold ? "prc-chip prc-answered" : "prc-chip prc-off"
                            }
                          >
                            {passage.above_threshold
                              ? `at or above ${score(threshold)}`
                              : `below ${score(threshold)}`}
                          </em>
                        </span>
                        <p className="prc-passage-text">{passage.text}</p>
                        {passage.citations.length > 1 ? (
                          <p className="prc-passage-also">
                            This passage also carries text from: {passage.citations.slice(1).join(" · ")}
                          </p>
                        ) : null}
                      </article>
                    ))
                  )}
                </div>

                <div className="prc-block">
                  <h3>How close the closest passage was</h3>
                  <p className="prc-lede">{result.score_note}</p>
                  <div className="prc-rail-wrap">
                    <div
                      className="prc-rail"
                      role="img"
                      aria-label={`Closeness ${score(result.top_score)} against the ${score(
                        result.threshold,
                      )} line. The closest passage is ${
                        result.above_threshold ? "at or above" : "below"
                      } the line.`}
                    >
                      <span
                        className="prc-rail-cut"
                        style={{ left: `${clampPercent(result.threshold)}%` }}
                      >
                        <b>the {score(result.threshold)} line</b>
                      </span>
                      <span
                        className="prc-rail-dot"
                        style={{ left: `${clampPercent(result.top_score)}%` }}
                      >
                        <b>{score(result.top_score)}</b>
                      </span>
                    </div>
                    <div className="prc-rail-ends">
                      <span>Left of the line: nothing is close enough, so it refuses</span>
                      <span>Right of the line: the passages are close enough to read</span>
                    </div>
                  </div>
                  <p className="prc-note" style={{ marginTop: 12 }}>
                    <strong>Closeness is not authority.</strong> A plain-language booklet can score
                    higher than the regulation it describes, because the booklet is written in
                    ordinary words and the question is too. A high score means the wording matches,
                    not that the passage governs your machine.
                  </p>
                </div>

                <div className="prc-block">
                  <h3>What the assistant did with it</h3>
                  <p className="prc-lede">{result.decision_detail}</p>

                  {refused ? (
                    <div className="prc-verdict prc-refuse">
                      <ShieldCheck size={20} aria-hidden="true" />
                      <div>
                        <span className="prc-kicker">Refused — and that is the right outcome</span>
                        <strong>{result.decision_label}</strong>
                        {result.answer ? <blockquote>{result.answer}</blockquote> : null}
                        <div className="prc-facts">
                          {result.refusal_reason ? (
                            <div>
                              <span>Why it stopped</span>
                              <strong>{result.refusal_reason}</strong>
                            </div>
                          ) : null}
                          {result.consult ? (
                            <div>
                              <span>Look here instead</span>
                              <strong>{result.consult}</strong>
                            </div>
                          ) : null}
                          {result.standards_named.length > 0 ? (
                            <div>
                              <span>Outside standard the rule names</span>
                              <strong>{result.standards_named.join(", ")}</strong>
                            </div>
                          ) : null}
                          {result.rule_fired ? (
                            <div>
                              <span>The rule that fired</span>
                              <strong>{result.rule_fired}</strong>
                            </div>
                          ) : null}
                        </div>
                        <p style={{ marginTop: 12 }}>{result.answer_note}</p>
                      </div>
                    </div>
                  ) : hasDraftedAnswer ? (
                    <div className="prc-verdict prc-answered">
                      <CheckCircle2 size={20} aria-hidden="true" />
                      <div>
                        <span className="prc-kicker">Answered from the passages above</span>
                        <strong>{result.decision_label}</strong>
                        <blockquote>{result.answer}</blockquote>
                        {result.answer_citations.length > 0 ? (
                          <div className="prc-facts">
                            <div>
                              <span>Written from these citations</span>
                              <strong>{result.answer_citations.join(" · ")}</strong>
                            </div>
                          </div>
                        ) : null}
                        <p style={{ marginTop: 12 }}>{result.answer_note}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="prc-verdict prc-none">
                      <Info size={20} aria-hidden="true" />
                      <div>
                        <span className="prc-kicker">Passages only</span>
                        <strong>No answer was written for this question</strong>
                        <p>
                          This is not one of the packaged questions, so there is no answer on file
                          for it and nothing was written just now. What you see above is exactly what
                          the search returned. Read the passages, look up the citations, and decide.
                        </p>
                        <p>{result.answer_note}</p>
                      </div>
                    </div>
                  )}

                  <p className="prc-note" style={{ marginTop: 12 }}>
                    <strong>A qualified person verifies the cited passage before any work happens.</strong>{" "}
                    {result.boundary}
                  </p>
                </div>

                {result.teaching_note ? (
                  <div className="prc-teaching">
                    <div>
                      <AlertTriangle size={18} aria-hidden="true" />
                      <strong>Why this one is worth arguing about</strong>
                    </div>
                    <p>{result.teaching_note}</p>
                  </div>
                ) : null}

                <div className="prc-block">
                  <h3>Two checks on this result</h3>
                  <p className="prc-lede">
                    Neither of these changes the answer. They are here so you can see what a second
                    opinion says, and what a subject expert said before the demo shipped.
                  </p>
                  <div className="prc-facts" style={{ marginTop: 0 }}>
                    <div>
                      <span>Plain keyword search ({result.keyword_comparison.retriever})</span>
                      <strong>
                        {result.keyword_comparison.citation} · closeness{" "}
                        {score(result.keyword_comparison.score)}
                      </strong>
                    </div>
                    <div>
                      <span>Does it agree?</span>
                      <strong>
                        {result.keyword_comparison.agrees_with_deployed
                          ? "Yes — same passage"
                          : "No — a different passage"}
                      </strong>
                    </div>
                    {result.gold_citations.length > 0 ? (
                      <div>
                        <span>The passage an expert says governs it</span>
                        <strong>{result.gold_citations.join(" · ")}</strong>
                      </div>
                    ) : null}
                    <div>
                      <span>Search took</span>
                      <strong>{result.retrieval_ms.toFixed(1)} ms</strong>
                    </div>
                  </div>
                  <p className="prc-note" style={{ marginTop: 12 }}>
                    {result.keyword_comparison.note}
                  </p>
                  {result.gold_citations.length > 0 &&
                  result.answer_citations.length > 0 &&
                  !result.gold_citations.some((citation) =>
                    result.answer_citations.includes(citation),
                  ) ? (
                    <p className="prc-note prc-caution" style={{ marginTop: 10 }}>
                      <strong>Read that line again.</strong> The citation the answer leans on is not
                      the one the expert named. Both point into the same rule, but the paragraph is
                      not the same paragraph — and the paragraph is the part a technician acts on.
                    </p>
                  ) : null}
                </div>
              </div>
            ) : !askError ? (
              <div className="prc-result-empty">
                <Search size={30} aria-hidden="true" />
                <strong>{running ? "Searching the library..." : "Nothing searched yet"}</strong>
                <p>
                  {running
                    ? `Comparing the question against all ${integer(model.corpus.chunks)} passages.`
                    : "Pick a question on the left, or type your own, then choose Search the library."}
                </p>
              </div>
            ) : null}
          </section>
        </section>
      ) : null}

      {view === "library" && corpus ? (
        <section>
          <header className="prc-section-heading">
            <div>
              <span className="prc-kicker">The library</span>
              <h2>Four layers of document, and what we are allowed to hold</h2>
              <p>
                The same question is answered differently by the law, by a site's own program, by
                the manual for one machine, and by a booklet that explains the law in ordinary
                words. All four are here, and every passage says which one it came from.
              </p>
            </div>
            <div className="prc-chip">Pinned to {shortDate(corpus.date_pin)}</div>
          </header>

          <div className="prc-metric-strip">
            <div>
              <strong className="prc-num">{integer(corpus.documents_indexed)}</strong>
              <span>documents searched</span>
              <small>
                {integer(corpus.documents)} were collected; one is held out of the search index on
                purpose.
              </small>
            </div>
            <div>
              <strong className="prc-num">{integer(corpus.chunks)}</strong>
              <span>passages in the index</span>
              <small>Each carries the citation of the paragraph it starts in.</small>
            </div>
            <div>
              <strong className="prc-num">{integer(corpus.words)}</strong>
              <span>words of source text</span>
              <small>Real regulation and real manuals, not written for this demo.</small>
            </div>
            <div>
              <strong className="prc-num">{shortDate(corpus.retrieved)}</strong>
              <span>downloaded once</span>
              <small>{corpus.fetch_policy}</small>
            </div>
          </div>

          <div className="prc-lesson">
            <Scale size={19} aria-hidden="true" />
            <div>
              <strong>Public domain is not the same as redistributable.</strong>
              <p>{corpus.licence_rule}</p>
              <p>{corpus.licence_lesson}</p>
            </div>
          </div>

          <div className="prc-layer-grid">
            {corpus.layers.map((layer) => (
              <section className="prc-panel" key={layer.layer}>
                <div className="prc-layer-head">
                  <div>
                    <strong>{layer.label}</strong>
                    <p>{layer.description}</p>
                  </div>
                  <div className="prc-layer-counts">
                    <div>
                      <span>Documents</span>
                      <b>{integer(layer.documents)}</b>
                    </div>
                    <div>
                      <span>Passages</span>
                      <b>{integer(layer.chunks)}</b>
                    </div>
                    <div>
                      <span>Words</span>
                      <b>{integer(layer.words)}</b>
                    </div>
                    <div>
                      <span>Share of index</span>
                      <b>{percent(layer.share_of_chunks, 0)}</b>
                    </div>
                  </div>
                </div>
                <div className="prc-table-wrap">
                  <table className="prc-table">
                    <caption className="sr-only">
                      Documents in the {layer.label} layer, with word count, license and
                      distribution status
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Document</th>
                        <th scope="col">License</th>
                        <th scope="col">May it be redistributed?</th>
                        <th scope="col" className="num">Words</th>
                        <th scope="col" className="num">Passages</th>
                      </tr>
                    </thead>
                    <tbody>
                      {layer.items.map((item) => (
                        <tr key={item.document} className={item.in_base_corpus ? "" : "prc-held"}>
                          <td>
                            {item.document}
                            <small>
                              {item.title} · {item.publisher}
                            </small>
                          </td>
                          <td>
                            {item.license}
                            <small>{item.distribution}</small>
                          </td>
                          <td>
                            <span className="prc-chip-row" style={{ marginTop: 0 }}>
                              <em
                                className={
                                  item.redistributable ? "prc-chip prc-answered" : "prc-chip prc-off"
                                }
                              >
                                {item.redistributable ? "Yes" : "No"}
                              </em>
                              {item.is_statement_a ? (
                                <em className="prc-chip prc-refuse">Statement A verified</em>
                              ) : null}
                              {item.in_base_corpus ? null : (
                                <em className="prc-chip prc-caution">Held back from the index</em>
                              )}
                            </span>
                            <small>{item.indexed_note}</small>
                          </td>
                          <td className="num">{integer(item.words)}</td>
                          <td className="num">{integer(item.chunks)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>

          <div className="prc-two-up">
            <section className="prc-panel">
              <header>
                <div>
                  <span>The check on page one</span>
                  <strong>Reading the distribution statement before indexing the manual</strong>
                  <small>
                    A US Government manual carries no copyright and can still be forbidden from
                    public release. The only way to know is to read page one of the document itself.
                  </small>
                </div>
                <ScrollText size={18} aria-hidden="true" />
              </header>
              <div className="prc-body-pad">
                <div className="prc-facts" style={{ marginTop: 0 }}>
                  <div>
                    <span>Document checked</span>
                    <strong>{corpus.licence_gate.document}</strong>
                  </div>
                  <div>
                    <span>Statement A found?</span>
                    <strong>
                      {corpus.licence_gate.statement_a_present ? "Yes — approved for public release" : "No"}
                    </strong>
                  </div>
                  <div>
                    <span>Any restrictive statement?</span>
                    <strong>
                      {corpus.licence_gate.restrictive_statement_present ? "Yes" : "None found"}
                    </strong>
                  </div>
                  <div>
                    <span>Any destruction notice?</span>
                    <strong>{corpus.licence_gate.destruction_notice ? "Yes" : "None found"}</strong>
                  </div>
                </div>
                <p className="prc-note" style={{ marginTop: 12 }}>
                  <strong>Verdict: {corpus.licence_gate.verdict}</strong> {corpus.licence_gate.note}
                </p>
                <p className="prc-note" style={{ marginTop: 10 }}>
                  A plain text search found the statement {integer(corpus.licence_gate.naive_matches)}{" "}
                  time. Tidying up the line breaks the PDF left behind found it{" "}
                  {integer(corpus.licence_gate.normalised_matches)} times. The document had not
                  changed — the search had.
                </p>
              </div>
            </section>

            <section className="prc-panel">
              <header>
                <div>
                  <span>Left out on purpose</span>
                  <strong>The documents we could not use</strong>
                  <small>
                    Each of these would have made the library better. Each was refused for a
                    different reason, and none of the reasons is about quality.
                  </small>
                </div>
                <AlertTriangle size={18} aria-hidden="true" />
              </header>
              <div className="prc-body-pad">
                {corpus.excluded.length === 0 ? (
                  <p className="prc-note">Nothing was excluded from this library.</p>
                ) : (
                  corpus.excluded.map((item, index) => (
                    <div
                      className="prc-note"
                      key={item.document}
                      style={{ marginTop: index === 0 ? 0 : 10 }}
                    >
                      <strong>{item.document}</strong>
                      <br />
                      {item.why_excluded}
                      <br />
                      <strong>The lesson.</strong> {item.lesson}
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>

          <p className="prc-note">
            <strong>Boundary.</strong> {corpus.boundary}
          </p>
        </section>
      ) : null}

      {view === "evidence" && model ? (
        <section>
          <header className="prc-section-heading">
            <div>
              <span className="prc-kicker">Evidence</span>
              <h2>What was measured, and what the numbers hide</h2>
              <p>
                {model.evaluation.questions_scored} questions were scored, written the way a
                technician asks rather than copied out of the passages. {model.evaluation_set_written_by}
              </p>
            </div>
            <div className="prc-chip">Version {model.version}</div>
          </header>

          <section className="prc-panel" style={{ marginBottom: 14 }}>
            <header>
              <div>
                <span>The leaderboard</span>
                <strong>Two ways of searching the same library</strong>
                <small>
                  Hit@1 is how often the right passage came back first. Hit@5 is how often it was
                  anywhere in the top five. Section@1 and @5 are the looser test: the right section,
                  not necessarily the right paragraph.
                </small>
              </div>
              <Gauge size={18} aria-hidden="true" />
            </header>
            <div className="prc-table-wrap">
              <table className="prc-table">
                <caption className="sr-only">
                  Retrieval leaderboard comparing keyword search with sentence embeddings
                </caption>
                <thead>
                  <tr>
                    <th scope="col">How it searches</th>
                    <th scope="col" className="num">Questions</th>
                    <th scope="col" className="num">Hit@1</th>
                    <th scope="col" className="num">Hit@5</th>
                    <th scope="col" className="num">Section@1</th>
                    <th scope="col" className="num">Section@5</th>
                    <th scope="col" className="num">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {model.evaluation.leaderboard.map((row) => (
                    <tr key={row.retriever} className={row.is_deployed ? "prc-chosen" : ""}>
                      <td>
                        {row.retriever}
                        <small>{row.is_deployed ? "This is the one in use" : "Kept for comparison only"}</small>
                      </td>
                      <td className="num">{integer(row.questions)}</td>
                      <td className="num">{percent(row.hit_at_1, 1)}</td>
                      <td className="num">{percent(row.hit_at_5, 1)}</td>
                      <td className="num">{percent(row.sec_at_1, 1)}</td>
                      <td className="num">{percent(row.sec_at_5, 1)}</td>
                      <td className="num">{row.query_time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="prc-lesson">
            <AlertTriangle size={19} aria-hidden="true" />
            <div>
              <strong>
                The same keyword search scored{" "}
                {percent(model.evaluation.question_phrasing.research_tfidf_hit_at_1, 0)} on an earlier
                benchmark and{" "}
                {percent(model.evaluation.question_phrasing.technician_tfidf_hit_at_1, 1)} here.
              </strong>
              <p>
                Nothing about the search changed. The earlier benchmark's questions had been generated
                from the passage text, so the question already contained the words of its own answer —
                which is exactly what a keyword matcher needs and exactly what a technician never
                gives it. {model.evaluation.question_phrasing.note}
              </p>
              <p>
                <strong>The lesson.</strong> {model.evaluation.question_phrasing.lesson}
              </p>
              <div className="prc-swap" style={{ marginTop: 12, marginBottom: 0 }}>
                <div>
                  <span>Keyword search, questions copied from the text</span>
                  <strong>{percent(model.evaluation.question_phrasing.research_tfidf_hit_at_1, 1)}</strong>
                </div>
                <ArrowRight size={17} aria-hidden="true" />
                <div>
                  <span>Keyword search, questions a technician wrote</span>
                  <strong>{percent(model.evaluation.question_phrasing.technician_tfidf_hit_at_1, 1)}</strong>
                </div>
                <ArrowRight size={17} aria-hidden="true" />
                <div>
                  <span>Deployed search, same technician questions</span>
                  <strong>{percent(model.evaluation.question_phrasing.technician_minilm_hit_at_1, 1)}</strong>
                </div>
              </div>
            </div>
          </div>

          <section className="prc-panel" style={{ marginBottom: 14 }}>
            <header>
              <div>
                <span>Per kind of question</span>
                <strong>Some questions are much harder than others</strong>
                <small>
                  Questions whose answer is not in the library at all are not scored here — there is
                  no passage to find. They are in the refusal table below instead.
                </small>
              </div>
              <Layers3 size={18} aria-hidden="true" />
            </header>
            <div className="prc-table-wrap">
              <table className="prc-table">
                <caption className="sr-only">Retrieval accuracy per kind of question</caption>
                <thead>
                  <tr>
                    <th scope="col">Kind of question</th>
                    <th scope="col" className="num">Questions</th>
                    <th scope="col" className="num">Keyword Hit@1</th>
                    <th scope="col" className="num">Keyword Hit@5</th>
                    <th scope="col" className="num">Deployed Hit@1</th>
                    <th scope="col" className="num">Deployed Hit@5</th>
                  </tr>
                </thead>
                <tbody>
                  {model.evaluation.per_bucket.map((row) => (
                    <tr key={row.bucket}>
                      <td>
                        {row.label}
                        <small>Bucket {row.bucket}</small>
                      </td>
                      <td className="num">{integer(row.questions)}</td>
                      <td className="num">{percent(row.tfidf_hit_at_1, 1)}</td>
                      <td className="num">{percent(row.tfidf_hit_at_5, 1)}</td>
                      <td className="num">{percent(row.minilm_hit_at_1, 1)}</td>
                      <td className="num">{percent(row.minilm_hit_at_5, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <header className="prc-section-heading">
            <div>
              <span className="prc-kicker">Saying no</span>
              <h2>How often it refuses, and whether it refuses the right questions</h2>
              <p>{model.policy.plain_rule}</p>
            </div>
          </header>

          <div className="prc-card-grid">
            <div className="prc-card">
              <ShieldCheck size={18} aria-hidden="true" />
              <span>Questions outside the library</span>
              <strong>{percent(model.evaluation.refusal.correct_refusal_outside_corpus, 1)} refused</strong>
              <small>Nothing in the library is close enough, and it says so.</small>
            </div>
            <div className="prc-card">
              <ScrollText size={18} aria-hidden="true" />
              <span>Rules that point at an outside standard</span>
              <strong>
                {percent(model.evaluation.refusal.correct_refusal_incorporated_by_reference, 1)} refused
              </strong>
              <small>The rule names a standard it does not contain, so there is no answer to give.</small>
            </div>
            <div className="prc-card">
              <AlertTriangle size={18} aria-hidden="true" />
              <span>Refused when it should have answered</span>
              <strong>{percent(model.evaluation.refusal.false_refusal_rate, 1)}</strong>
              <small>
                {model.evaluation.refusal.false_refusals.length} questions:{" "}
                {model.evaluation.refusal.false_refusals.join(", ")}. A refusal costs a person a
                search; a wrong answer costs more.
              </small>
            </div>
            <div className="prc-card">
              <Wrench size={18} aria-hidden="true" />
              <span>Answered when it should have refused</span>
              <strong>{integer(model.evaluation.refusal.missed_refusals.length)} questions</strong>
              <small>
                {model.evaluation.refusal.missed_refusals.join(", ")}. These are the ones worth
                arguing about in class.
              </small>
            </div>
          </div>

          <div className="prc-two-up">
            <section className="prc-panel">
              <header>
                <div>
                  <span>By kind of question</span>
                  <strong>Refusal rate, and whether refusing was correct</strong>
                </div>
              </header>
              <div className="prc-table-wrap">
                <table className="prc-table" style={{ minWidth: 400 }}>
                  <caption className="sr-only">Refusal rate per kind of question</caption>
                  <thead>
                    <tr>
                      <th scope="col">Kind of question</th>
                      <th scope="col" className="num">Questions</th>
                      <th scope="col" className="num">Refused</th>
                      <th scope="col">Should it?</th>
                    </tr>
                  </thead>
                  <tbody>
                    {model.evaluation.refusal.by_bucket.map((row) => (
                      <tr key={row.bucket}>
                        <td>
                          {row.label}
                          <small>Bucket {row.bucket}</small>
                        </td>
                        <td className="num">{integer(row.questions)}</td>
                        <td className="num">
                          {integer(row.refused)} · {percent(row.rate, 1)}
                        </td>
                        <td>
                          <em
                            className={
                              row.should_refuse ? "prc-chip prc-refuse" : "prc-chip prc-answered"
                            }
                          >
                            {row.should_refuse ? "Yes, refuse" : "No, answer"}
                          </em>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="prc-panel">
              <header>
                <div>
                  <span>Choosing the line</span>
                  <strong>
                    Why the line sits at {score(model.evaluation.refusal.tau)} and not higher
                  </strong>
                  <small>
                    Raising it refuses more of the questions it should refuse, and starts refusing
                    questions it could have answered.
                  </small>
                </div>
                <Scale size={18} aria-hidden="true" />
              </header>
              <div className="prc-table-wrap">
                <table className="prc-table" style={{ minWidth: 420 }}>
                  <caption className="sr-only">
                    Refusal outcomes at each candidate cutoff, with the chosen one marked
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="num">Line</th>
                      <th scope="col" className="num">Outside the library</th>
                      <th scope="col" className="num">Outside standard</th>
                      <th scope="col" className="num">Refused wrongly</th>
                    </tr>
                  </thead>
                  <tbody>
                    {model.evaluation.refusal.sweep.map((row) => (
                      <tr key={row.tau} className={row.is_chosen ? "prc-chosen" : ""}>
                        <td className="num">
                          {score(row.tau)}
                          {row.is_chosen ? (
                            <small style={{ textAlign: "right" }}>chosen</small>
                          ) : null}
                        </td>
                        <td className="num">{row.correct_refusal_outside_corpus}</td>
                        <td className="num">{row.correct_refusal_incorporated_by_reference}</td>
                        <td className="num">{row.false_refusal}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <div className="prc-lesson">
            <ShieldCheck size={19} aria-hidden="true" />
            <div>
              <strong>One score cannot see the second kind of refusal.</strong>
              <p>{model.evaluation.refusal.lesson}</p>
            </div>
          </div>

          <header className="prc-section-heading">
            <div>
              <span className="prc-kicker">The collapse</span>
              <h2>Two near-identical regulations in one library</h2>
              <p>
                MSHA writes one set of rules for surface mines and a nearly identical set for
                underground mines. {integer(model.evaluation.duplicate_corpus.byte_identical)} sections
                are word-for-word the same and{" "}
                {integer(model.evaluation.duplicate_corpus.at_least_95_percent_similar)} are at least
                95% the same. Loading both grew the library by{" "}
                {percent(model.evaluation.duplicate_corpus.corpus_growth, 1)} — and this is what it did.
              </p>
            </div>
          </header>

          <div className="prc-two-up">
            <section className="prc-panel">
              <header>
                <div>
                  <span>Deployed search</span>
                  <strong>Right text, wrong rule</strong>
                  <small>
                    The passage it returns still says the right thing. The citation printed beside it
                    now points at the wrong regulation.
                  </small>
                </div>
                <BookOpenCheck size={18} aria-hidden="true" />
              </header>
              <div className="prc-body-pad">
                <div className="prc-swap">
                  <div>
                    <span>Right citation first, before</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.minilm_cite_hit_at_1_before, 1)}</strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div>
                    <span>Right citation first, after</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.minilm_cite_hit_at_1_after, 1)}</strong>
                  </div>
                </div>
                <div className="prc-swap">
                  <div>
                    <span>Right text first, before</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.minilm_text_hit_at_1_before, 1)}</strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div>
                    <span>Right text first, after</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.minilm_text_hit_at_1_after, 1)}</strong>
                  </div>
                </div>
                <p className="prc-note">
                  <strong>
                    {percent(model.evaluation.duplicate_corpus.minilm_right_text_wrong_rule, 1)} of
                    questions came back with the right text under the wrong citation.
                  </strong>{" "}
                  Keyword search fared worse: its right-citation rate fell from{" "}
                  {percent(model.evaluation.duplicate_corpus.tfidf_cite_hit_at_1_before, 1)} to{" "}
                  {percent(model.evaluation.duplicate_corpus.tfidf_cite_hit_at_1_after, 1)}.
                </p>
              </div>
            </section>

            <section className="prc-panel">
              <header>
                <div>
                  <span>Why nobody would have noticed</span>
                  <strong>The headline number barely moved</strong>
                  <small>
                    The metric most teams watch is whether the right text turns up in the top five.
                    It stayed almost exactly where it was.
                  </small>
                </div>
                <Gauge size={18} aria-hidden="true" />
              </header>
              <div className="prc-body-pad">
                <div className="prc-swap">
                  <div>
                    <span>Hit@5 before</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.main_hit_at_5_before, 1)}</strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div>
                    <span>Hit@5 after</span>
                    <strong>{percent(model.evaluation.duplicate_corpus.main_hit_at_5_after, 1)}</strong>
                  </div>
                </div>
                <p className="prc-note" style={{ marginBottom: 10 }}>
                  A technician does not act on the text. They act on the citation, because that is
                  what they are held to and what they can look up. The number that collapsed is the
                  one that mattered, and it was not on the dashboard.
                </p>
                <p className="prc-note">
                  <strong>The lesson.</strong> {model.evaluation.duplicate_corpus.lesson}
                </p>
              </div>
            </section>
          </div>

          <header className="prc-section-heading">
            <div>
              <span className="prc-kicker">Honesty</span>
              <h2>Two checks that pass, and what they still miss</h2>
              <p>
                Both of these checks were built to catch a citation that is wrong. Both report a
                clean result. Neither can see the mistake that actually matters here, and knowing
                which mistake each one is blind to is the point.
              </p>
            </div>
          </header>

          <div className="prc-two-up">
            <section className="prc-honest">
              <header>
                <AlertTriangle size={18} aria-hidden="true" />
                <strong>A check that passed while the citation was wrong</strong>
              </header>
              <div className="prc-honest-body">
                <div className="prc-headline">
                  <b>{integer(model.evaluation.citations.stateful_structurally_invalid)}</b>
                  <span>
                    citations were flagged as malformed across{" "}
                    {integer(model.evaluation.citations.labelled_paragraphs)} labelled paragraphs in{" "}
                    {model.evaluation.citations.scope} — and a wrong citation still got through
                  </span>
                </div>
                <p>
                  The structural check asks whether a citation is shaped correctly and whether the
                  paragraph tree it names could exist. {model.evaluation.citations.structural_check_is_a_self_check}{" "}
                  It cannot see a label that is perfectly well-formed and attached to the wrong rule.
                </p>
                <p>
                  What did catch it was the regulation's own cross-references — the places where one
                  paragraph says "see paragraph (e)(2)". Those have an answer that does not come from
                  the chunker.{" "}
                  {percent(model.evaluation.citations.cross_references_resolved_stateful, 1)} of{" "}
                  {integer(model.evaluation.citations.internal_cross_references)} resolved with the
                  deployed labelling, against{" "}
                  {percent(model.evaluation.citations.cross_references_resolved_naive, 1)} with the
                  simple approach. {model.evaluation.citations.hand_audited} were also read by hand.
                </p>
                <p>
                  <strong>The lesson.</strong> {model.evaluation.citations.lesson}
                </p>
              </div>
            </section>

            <section className="prc-honest">
              <header>
                <AlertTriangle size={18} aria-hidden="true" />
                <strong>A check that catches invented numbers, not misattributed ones</strong>
              </header>
              <div className="prc-honest-body">
                <div className="prc-headline">
                  <b>{integer(model.evaluation.unsupported_claim_check.unsupported_numerals)}</b>
                  <span>
                    of {integer(model.evaluation.unsupported_claim_check.numerals_checked)} numbers in
                    the packaged answers could not be traced back to a retrieved passage
                  </span>
                </div>
                <p>{model.evaluation.unsupported_claim_check.what_it_catches}</p>
                <p>
                  <strong>What it misses.</strong>{" "}
                  {model.evaluation.unsupported_claim_check.what_it_misses}
                </p>
                <p>
                  That is exactly the failure the forging-machine question sets up: a real,
                  correctly-copied pressure figure sits in a nearby rule about welding gas piping. It
                  would pass this check and still be the wrong answer. Open the first view and choose
                  the refusal to see it.
                </p>
              </div>
            </section>
          </div>

          <div className="prc-two-up">
            <section className="prc-list-panel">
              <h3>What this assistant does not do</h3>
              <ul>
                {model.what_it_does_not_do.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="prc-list-panel">
              <h3>What it still gets wrong</h3>
              <ul>
                {model.known_limits.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          </div>
        </section>
      ) : null}
    </div>
  );
}
