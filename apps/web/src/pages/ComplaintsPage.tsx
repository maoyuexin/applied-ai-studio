import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Copy,
  FileText,
  Inbox,
  Info,
  Layers3,
  ListFilter,
  Play,
  Scale,
  Search,
  Type,
  UserCheck,
  Users,
  XCircle,
} from "lucide-react";
import {
  classifyComplaint,
  getComplaintsModel,
  getComplaintsQueues,
  getComplaintsSamples,
  type ComplaintClassification,
  type ComplaintModelInfo,
  type ComplaintPackaged,
  type ComplaintQueueBoard,
  type ComplaintQueueItem,
} from "../complaintsApi";
import { navigate } from "../router";

type View = "route" | "queues" | "evidence";

const views = [
  {
    id: "route" as const,
    label: "Route one complaint",
    detail: "Read the text, see the team",
    icon: Search,
  },
  {
    id: "queues" as const,
    label: "Team queues",
    detail: "The worklist this creates",
    icon: ListFilter,
  },
  {
    id: "evidence" as const,
    label: "Model card and evidence",
    detail: "What was measured, and how",
    icon: Layers3,
  },
];

const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const decimal = (value: number, digits = 3): string => value.toFixed(digits);
const integer = (value: number): string => new Intl.NumberFormat("en-US").format(value);
const shortDate = (value: string): string => {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(parsed);
};

const pageStyles = `
.complaints-page .page-back-button { min-height: 44px; }
.complaints-page h2 { margin: 0; font-size: 18px; line-height: 1.3; }
.complaints-page h3 { margin: 0; font-size: 14px; line-height: 1.35; }
.cx-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 18px; }
.cx-header h1 { margin: 3px 0 6px; font-size: 27px; line-height: 1.2; font-weight: 750; }
.cx-header p { margin: 0; max-width: 720px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.cx-status { min-height: 44px; display: flex; align-items: center; gap: 10px; padding: 8px 13px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.cx-status span { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--text-muted); }
.cx-status span.ready { background: var(--green); box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.12); }
.cx-status strong { display: block; font-size: 12px; }
.cx-status small { display: block; margin-top: 2px; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }

.cx-metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin-bottom: 18px; }
.cx-metric-strip div { min-height: 74px; padding: 13px 16px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.cx-metric-strip div:last-child { border-right: 0; }
.cx-metric-strip strong { font-family: var(--font-mono); font-size: 20px; }
.cx-metric-strip span { margin-top: 2px; font-size: 11px; }
.cx-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: 10px; line-height: 1.4; }

.cx-boundary { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 11px; margin-bottom: 16px; padding: 13px 15px; border: 1px solid rgba(126, 174, 184, 0.4); border-left: 3px solid var(--teal); border-radius: 6px; background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.cx-boundary strong { display: block; color: var(--text); font-size: 13px; }
.cx-boundary p { margin: 5px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }

.cx-switcher { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; margin-bottom: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.cx-switcher button { min-height: 62px; padding: 11px 14px; display: flex; align-items: center; gap: 11px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; transition: 160ms ease; }
.cx-switcher button:last-child { border-right: 0; }
.cx-switcher button:hover { background: var(--surface-raised); color: var(--text-secondary); }
.cx-switcher button.active { background: rgba(232, 145, 60, 0.09); box-shadow: inset 0 -3px 0 var(--orange); color: var(--orange); }
.cx-switcher strong { display: block; color: var(--text); font-size: 13px; }
.cx-switcher small { display: block; margin-top: 3px; color: var(--text-muted); font-size: 11px; }

.cx-panel { border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.cx-panel > header { padding: 13px 16px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); }
.cx-panel > header span { display: block; color: var(--teal); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-panel > header strong { display: block; margin-top: 4px; font-size: 14px; }
.cx-panel > header small { display: block; margin-top: 4px; color: var(--text-muted); font-size: 11px; line-height: 1.5; }

.cx-route-grid { display: grid; grid-template-columns: minmax(250px, 0.85fr) minmax(0, 1.15fr) minmax(0, 1.25fr); gap: 14px; align-items: start; }

.cx-sample-shortcut { min-height: 46px; width: calc(100% - 28px); margin: 12px 14px 0; padding: 9px 12px; display: flex; align-items: center; gap: 9px; border: 1px dashed rgba(240, 180, 41, 0.55); border-radius: 5px; background: rgba(240, 180, 41, 0.07); color: var(--amber); font-size: 11px; line-height: 1.45; text-align: left; }
.cx-sample-shortcut:hover { background: rgba(240, 180, 41, 0.13); }
.cx-sample-list { max-height: 620px; overflow-y: auto; padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 7px; }
.cx-sample-list button { min-height: 76px; height: auto; flex: 0 0 auto; padding: 10px 12px; display: block; width: 100%; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); color: var(--text-secondary); text-align: left; transition: 140ms ease; }
.cx-sample-list button > span.cx-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; color: inherit; font-family: inherit; font-size: inherit; text-transform: none; }
.cx-sample-list button:hover { border-color: var(--teal); color: var(--text); }
.cx-sample-list button.active { border-color: var(--orange); background: rgba(232, 145, 60, 0.1); color: var(--text); }
.cx-sample-list button > span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-sample-list button strong { display: block; margin: 4px 0 5px; font-size: 12px; }
.cx-sample-list button small { display: block; color: var(--text-muted); font-size: 10px; line-height: 1.5; }

.cx-chip { display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border: 1px solid var(--border-strong); border-radius: 20px; color: var(--text-secondary); font-family: var(--font-mono); font-size: 9px; font-style: normal; text-transform: none; white-space: nowrap; }
.cx-chip.auto { border-color: rgba(126, 174, 184, 0.5); background: rgba(126, 174, 184, 0.1); color: var(--teal); }
.cx-chip.person { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.1); color: var(--amber); }
.cx-chip.wrong { border-color: rgba(228, 90, 88, 0.5); background: rgba(228, 90, 88, 0.1); color: #f4a5a4; }
.cx-chip.right { border-color: rgba(74, 222, 128, 0.4); background: rgba(74, 222, 128, 0.08); color: var(--green); }
.cx-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }

.cx-complaint-meta { padding: 12px 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; border-bottom: 1px solid var(--border); }
.cx-complaint-meta span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-complaint-meta strong { display: block; margin-top: 4px; font-size: 12px; }
.cx-editor { padding: 14px 16px; }
.cx-editor label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 600; }
.cx-editor textarea { width: 100%; min-height: 300px; padding: 12px 13px; border: 1px solid var(--border); border-radius: 5px; background: #14161c; color: var(--text); font-family: var(--font-body); font-size: 12px; line-height: 1.7; white-space: pre-wrap; resize: vertical; }
.cx-editor textarea:hover { border-color: var(--border-strong); }
.cx-editor-foot { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.cx-counter { color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.cx-counter.over { color: #f4a5a4; }
.cx-editor .primary-button { margin-top: 0; min-height: 44px; }
.cx-privacy { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 9px; margin: 12px 16px 14px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-muted); font-size: 11px; line-height: 1.55; }

.cx-result-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 14px; }
.cx-verdict { padding: 14px 15px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 14px; align-items: center; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface-raised); }
.cx-verdict.auto { border-color: rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.08); }
.cx-verdict.person { border-color: rgba(240, 180, 41, 0.45); background: rgba(240, 180, 41, 0.07); }
.cx-verdict span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-verdict strong { display: block; margin: 5px 0 4px; font-size: 19px; line-height: 1.25; }
.cx-verdict small { display: block; color: var(--text-secondary); font-size: 11px; line-height: 1.5; }
.cx-verdict-score { text-align: right; }
.cx-verdict-score b { display: block; font-family: var(--font-mono); font-size: 26px; }

.cx-track { padding: 2px 0 0; }
.cx-track-rail { position: relative; height: 34px; margin: 16px 0 6px; border: 1px solid var(--border); border-radius: 4px; background: linear-gradient(90deg, rgba(240, 180, 41, 0.14) 0%, rgba(240, 180, 41, 0.14) 55%, rgba(126, 174, 184, 0.14) 55%, rgba(126, 174, 184, 0.14) 100%); }
.cx-track-cut { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--text); }
.cx-track-cut b { position: absolute; left: 50%; bottom: calc(100% + 4px); transform: translateX(-50%); color: var(--text); font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }
.cx-track-dot { position: absolute; top: 50%; width: 14px; height: 14px; margin: -7px 0 0 -7px; border: 2px solid var(--bg); border-radius: 50%; background: var(--orange); }
.cx-track-dot b { position: absolute; left: 50%; top: calc(100% + 6px); transform: translateX(-50%); color: var(--orange); font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }
.cx-track-ends { display: flex; justify-content: space-between; margin-top: 20px; color: var(--text-muted); font-size: 10px; }

.cx-chain { display: grid; grid-template-columns: minmax(0, 1fr) 17px minmax(0, 1fr) 17px minmax(0, 1fr); gap: 9px; align-items: center; }
.cx-chain > div { min-height: 74px; padding: 10px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); }
.cx-chain > div.auto { border-color: rgba(126, 174, 184, 0.45); }
.cx-chain > div.person { border-color: rgba(240, 180, 41, 0.45); }
.cx-chain span { display: block; margin-top: 5px; color: var(--text-muted); font-size: 10px; }
.cx-chain strong { display: block; margin-top: 3px; font-size: 11px; line-height: 1.4; }
.cx-chain > svg { color: var(--text-muted); }

.cx-known { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 11px; padding: 12px 13px; border: 1px solid var(--border); border-radius: 5px; }
.cx-known.right { border-color: rgba(74, 222, 128, 0.35); background: rgba(74, 222, 128, 0.06); color: var(--green); }
.cx-known.wrong { border-color: rgba(228, 90, 88, 0.4); background: rgba(228, 90, 88, 0.07); color: #f4a5a4; }
.cx-known.neutral { color: var(--text-muted); }
.cx-known span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-known strong { display: block; margin: 4px 0 4px; color: var(--text); font-size: 13px; }
.cx-known small { display: block; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }

.cx-block > h3 { margin-bottom: 4px; }
.cx-block > p { margin: 0 0 10px; color: var(--text-muted); font-size: 11px; line-height: 1.55; }
.cx-prob-row { display: grid; grid-template-columns: minmax(0, 1fr) 52px; gap: 10px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(46, 49, 64, 0.6); }
.cx-prob-row:last-child { border-bottom: 0; }
.cx-prob-row > div:first-child > b { display: block; font-size: 12px; font-weight: 600; }
.cx-prob-row > div:first-child > em { display: block; margin: 2px 0 5px; color: var(--text-muted); font-size: 10px; font-style: normal; line-height: 1.45; }
.cx-bar { height: 7px; border-radius: 4px; background: var(--surface-raised); overflow: hidden; }
.cx-bar i { display: block; height: 100%; border-radius: 4px; background: var(--text-muted); }
.cx-prob-row.chosen .cx-bar i { background: var(--orange); }
.cx-prob-value { font-family: var(--font-mono); font-size: 12px; text-align: right; }
.cx-prob-row.chosen .cx-prob-value { color: var(--orange); }

.cx-word-row { display: grid; grid-template-columns: minmax(0, 1fr) 54px; gap: 10px; align-items: center; padding: 6px 0; }
.cx-word-row b { display: block; margin-bottom: 5px; font-family: var(--font-mono); font-size: 12px; }
.cx-word-row .cx-bar i { background: var(--teal); }
.cx-word-value { color: var(--teal); font-family: var(--font-mono); font-size: 11px; text-align: right; }

.cx-note { margin: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-muted); font-size: 11px; line-height: 1.6; }
.cx-result-empty { min-height: 320px; display: grid; place-content: center; justify-items: center; gap: 9px; padding: 30px; text-align: center; color: var(--text-muted); }
.cx-result-empty strong { color: var(--text); font-size: 14px; }
.cx-result-empty p { margin: 0; max-width: 330px; font-size: 11px; line-height: 1.6; }

.cx-summary-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.cx-summary-strip > div { min-height: 92px; padding: 13px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.cx-summary-strip strong { display: block; font-family: var(--font-mono); font-size: 22px; }
.cx-summary-strip span { display: block; margin-top: 3px; font-size: 11px; }
.cx-summary-strip small { display: block; margin-top: 4px; color: var(--text-muted); font-size: 10px; line-height: 1.45; }

.cx-discussion { margin-bottom: 14px; padding: 15px 16px; border: 1px solid rgba(228, 90, 88, 0.45); border-left: 3px solid var(--red); border-radius: 6px; background: rgba(228, 90, 88, 0.06); }
.cx-discussion header { display: flex; align-items: center; gap: 9px; color: #f4a5a4; }
.cx-discussion header strong { font-size: 14px; }
.cx-discussion-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 12px 0; }
.cx-discussion-grid span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-discussion-grid strong { display: block; margin-top: 4px; font-size: 13px; }
.cx-discussion blockquote { margin: 0 0 12px; padding: 10px 12px; border-left: 2px solid var(--border-strong); color: var(--text-secondary); font-size: 11px; line-height: 1.65; }
.cx-discussion p { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.cx-discussion p + p { margin-top: 8px; }
.cx-discussion q { color: var(--text); font-style: italic; }

.cx-queue-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(268px, 1fr)); gap: 12px; margin-bottom: 14px; }
.cx-queue-lane { display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.cx-queue-lane.triage { border-color: rgba(240, 180, 41, 0.45); }
.cx-queue-lane > header { padding: 11px 13px; border-bottom: 1px solid var(--border); }
.cx-queue-lane > header > div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.cx-queue-lane > header strong { font-size: 13px; }
.cx-queue-lane > header b { font-family: var(--font-mono); font-size: 16px; }
.cx-queue-lane > header small { display: block; margin-top: 4px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.cx-queue-items { flex: 1; max-height: 340px; overflow-y: auto; padding: 10px 13px 12px; display: flex; flex-direction: column; gap: 8px; }
.cx-queue-item { flex: 0 0 auto; padding: 9px 10px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); }
.cx-queue-item.flagged { border-color: rgba(228, 90, 88, 0.45); }
.cx-queue-item > div { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.cx-queue-item b { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); }
.cx-queue-item i { color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px; font-style: normal; }
.cx-queue-item p { margin: 6px 0 0; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }
.cx-queue-empty { padding: 14px 0; color: var(--text-muted); font-size: 11px; line-height: 1.55; text-align: center; }

.cx-evidence-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; margin-bottom: 14px; }
.cx-fact { min-height: 96px; padding: 13px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.cx-fact span { display: block; margin-top: 8px; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-fact strong { display: block; margin-top: 5px; font-size: 13px; line-height: 1.35; }
.cx-fact small { display: block; margin-top: 5px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.cx-fact svg { color: var(--teal); }

.cx-table-wrap { overflow-x: auto; }
.cx-table { width: 100%; min-width: 520px; border-collapse: collapse; font-size: 12px; }
.cx-table th, .cx-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); text-align: left; }
.cx-table th { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; font-weight: 500; text-transform: uppercase; }
.cx-table td.num, .cx-table th.num { font-family: var(--font-mono); text-align: right; }
.cx-table tr.macro td { border-top: 1px solid var(--border-strong); color: var(--text); font-weight: 600; }
.cx-table tr.chosen td { background: rgba(232, 145, 60, 0.08); color: var(--orange); }
.cx-table tbody tr:last-child td { border-bottom: 0; }

.cx-honest { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; margin-bottom: 14px; align-items: start; }
.cx-honest-panel { border: 1px solid rgba(240, 180, 41, 0.4); border-radius: 6px; background: rgba(240, 180, 41, 0.05); overflow: hidden; }
.cx-honest-panel > header { padding: 13px 15px; display: flex; align-items: center; gap: 9px; border-bottom: 1px solid rgba(240, 180, 41, 0.3); color: var(--amber); }
.cx-honest-panel > header strong { font-size: 14px; }
.cx-honest-body { padding: 13px 15px; }
.cx-honest-headline { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.cx-honest-headline b { color: var(--amber); font-family: var(--font-mono); font-size: 26px; }
.cx-honest-headline span { color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.cx-honest-body p { margin: 0 0 10px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.cx-honest-body p:last-child { margin-bottom: 0; }
.cx-swap { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.cx-swap div { flex: 1; }
.cx-swap span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-swap strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-size: 15px; }
.cx-swap svg { color: var(--text-muted); flex: 0 0 auto; }

.cx-list-panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.cx-list-panel { padding: 14px 16px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.cx-list-panel ul { margin: 10px 0 0; padding-left: 18px; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.cx-list-panel li + li { margin-top: 6px; }

.cx-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin: 20px 0 12px; }
.cx-section-heading span { display: block; color: var(--teal); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.cx-section-heading h2 { margin: 5px 0 5px; }
.cx-section-heading p { margin: 0; max-width: 760px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }

@media (max-width: 1180px) {
  .cx-route-grid { grid-template-columns: minmax(0, 1fr); }
  .cx-sample-list { max-height: 340px; }
  .cx-metric-strip, .cx-summary-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cx-switcher { grid-template-columns: minmax(0, 1fr); }
  .cx-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .cx-switcher button:last-child { border-bottom: 0; }
}
@media (max-width: 760px) {
  .cx-metric-strip, .cx-summary-strip { grid-template-columns: minmax(0, 1fr); }
  .cx-metric-strip div { border-right: 0; border-bottom: 1px solid var(--border); }
  .cx-metric-strip div:last-child { border-bottom: 0; }
  .cx-chain { grid-template-columns: minmax(0, 1fr); }
  .cx-chain > svg { transform: rotate(90deg); justify-self: center; }
  .cx-verdict { grid-template-columns: minmax(0, 1fr); }
  .cx-verdict-score { text-align: left; }
  .cx-queue-grid { grid-template-columns: minmax(0, 1fr); }
  .cx-editor textarea { min-height: 220px; }
  .cx-editor-foot { flex-direction: column; align-items: stretch; }
  .cx-editor .primary-button { width: 100%; }
}
`;

function routeChip(route: string) {
  return route === "auto_route"
    ? { className: "cx-chip auto", label: "Auto-routed" }
    : { className: "cx-chip person", label: "To a person" };
}

export default function ComplaintsPage() {
  const [view, setView] = useState<View>("route");
  const [model, setModel] = useState<ComplaintModelInfo | null>(null);
  const [samples, setSamples] = useState<ComplaintPackaged[]>([]);
  const [board, setBoard] = useState<ComplaintQueueBoard | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<ComplaintClassification | null>(null);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getComplaintsModel(), getComplaintsSamples(12), getComplaintsQueues(60)])
      .then(async ([modelInfo, packaged, queueBoard]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setSamples(packaged);
        setBoard(queueBoard);
        const first = packaged[0];
        if (!first) return;
        setSelectedId(first.scenario_id);
        setDraft(first.narrative);
        const firstResult = await classifyComplaint(first.narrative);
        if (!cancelled) setResult(firstResult);
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = samples.find((sample) => sample.scenario_id === selectedId) ?? null;
  const maxCharacters = model?.max_narrative_characters ?? 8000;
  const trimmed = draft.trim();
  const overCap = draft.length > maxCharacters;
  const canRoute = trimmed.length > 0 && !overCap && !running;
  const edited = selected ? selected.narrative !== draft : draft.length > 0;

  const unsureSample = useMemo(
    () =>
      samples
        .filter((sample) => sample.route === "human_triage")
        .sort((left, right) => left.confidence - right.confidence)[0] ?? null,
    [samples],
  );
  const misroute = useMemo<ComplaintQueueItem | null>(
    () =>
      board?.teams.flatMap((team) => team.items).find((item) => item.is_misroute_example) ?? null,
    [board],
  );

  const chooseSample = (sample: ComplaintPackaged) => {
    setSelectedId(sample.scenario_id);
    setDraft(sample.narrative);
    setResult(null);
    setRouteError(null);
  };

  const runRoute = async () => {
    if (!canRoute) return;
    setRunning(true);
    setRouteError(null);
    try {
      setResult(await classifyComplaint(draft));
    } catch (reason) {
      setResult(null);
      setRouteError(
        reason instanceof Error ? reason.message : "The model could not read this complaint.",
      );
    } finally {
      setRunning(false);
    }
  };

  const strongestWord = result?.routing_words[0]?.push ?? 1;

  return (
    <div className="page complaints-page">
      <style>{pageStyles}</style>

      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="cx-header">
        <div>
          <span className="eyebrow">Text classification · Complaint handling</span>
          <h1>From a complaint letter to the right specialist team</h1>
          <p>
            A consumer writes a complaint about a financial company. Eight specialist teams answer
            different products. This model reads the letter and picks the queue it should land in
            first — and stops there.
          </p>
        </div>
        <div className="cx-status">
          <span className={model ? "ready" : ""} aria-hidden="true" />
          <div>
            <strong>{model ? "Model ready" : "Connecting to the model"}</strong>
            <small>FastAPI · scikit-learn · {model ? model.representation.kind.split(" ")[0] : "TF-IDF"}</small>
          </div>
        </div>
      </header>

      {model ? (
        <section className="cx-metric-strip" aria-label="Results measured once on the untouched test complaints">
          <div>
            <strong>{percent(model.test_metrics.accuracy)}</strong>
            <span>complaints sent to the right team</span>
            <small>Across all {integer(model.test_metrics.complaints)} test complaints</small>
          </div>
          <div>
            <strong>{decimal(model.test_metrics.macro_f1)}</strong>
            <span>macro-F1</span>
            <small>Averages the eight teams equally, so small teams count too</small>
          </div>
          <div>
            <strong>{percent(model.test_metrics.coverage)}</strong>
            <span>routed without a person</span>
            <small>The rest go to the triage queue</small>
          </div>
          <div>
            <strong>{percent(model.test_metrics.accuracy_among_auto_routed)}</strong>
            <span>right among those routed</span>
            <small>Higher, because the unsure ones were held back</small>
          </div>
        </section>
      ) : null}

      <div className="cx-boundary">
        <Scale size={19} aria-hidden="true" />
        <div>
          <strong>The model routes. It never judges whether a complaint is valid.</strong>
          <p>
            It does not decide whether the consumer is right, what the company owes, or how the case
            ends. It does not write a reply and it never contacts the consumer. A person answers
            every complaint; a wrong route costs days, not the case.
          </p>
        </div>
      </div>

      <nav className="cx-switcher" aria-label="Complaint routing views">
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
        <div className="loading-state">Loading the model, the packaged complaints, and the queues...</div>
      ) : null}

      {view === "route" && model ? (
        <section className="cx-route-grid">
          <section className="cx-panel">
            <header>
              <div>
                <span>Step 1</span>
                <strong>Pick a packaged complaint</strong>
                <small>
                  Real complaints from the held-out test set. The publisher removed personal details
                  before these were published.
                </small>
              </div>
              <FileText size={18} aria-hidden="true" />
            </header>
            {unsureSample ? (
              <button
                type="button"
                className="cx-sample-shortcut"
                onClick={() => chooseSample(unsureSample)}
              >
                <UserCheck size={16} aria-hidden="true" />
                <span>
                  Show one the model was unsure about — {percent(unsureSample.confidence)} confidence,
                  so it goes to a person
                </span>
              </button>
            ) : null}
            <div className="cx-sample-list">
              {samples.length === 0 ? (
                <p className="cx-queue-empty">No packaged complaints came back from the service.</p>
              ) : null}
              {samples.map((sample) => {
                const chip = routeChip(sample.route);
                return (
                  <button
                    type="button"
                    key={sample.scenario_id}
                    className={selectedId === sample.scenario_id ? "active" : ""}
                    aria-pressed={selectedId === sample.scenario_id}
                    onClick={() => chooseSample(sample)}
                  >
                    <span>{sample.scenario_label}</span>
                    <strong>{sample.predicted_team}</strong>
                    <small>{sample.issue}</small>
                    <span className="cx-chip-row">
                      <em className={chip.className}>{chip.label}</em>
                      <em className="cx-chip">{percent(sample.confidence)} confidence</em>
                      {sample.correct ? null : <em className="cx-chip wrong">Wrong team</em>}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="cx-panel">
            <header>
              <div>
                <span>Step 2</span>
                <strong>Read the complaint</strong>
                <small>Shown exactly as the consumer wrote it. This text is all the model reads.</small>
              </div>
              <Type size={18} aria-hidden="true" />
            </header>
            {selected ? (
              <div className="cx-complaint-meta">
                <div>
                  <span>Complaint</span>
                  <strong>#{selected.complaint_id}</strong>
                </div>
                <div>
                  <span>Received</span>
                  <strong>{shortDate(selected.date_received)}</strong>
                </div>
                <div>
                  <span>Issue the consumer picked</span>
                  <strong>{selected.issue}</strong>
                </div>
                <div>
                  <span>Team it belonged to</span>
                  <strong>{edited ? "You changed the text" : selected.known_team}</strong>
                </div>
              </div>
            ) : null}
            <div className="cx-editor">
              <label htmlFor="cx-narrative">Complaint text</label>
              <textarea
                id="cx-narrative"
                value={draft}
                aria-describedby="cx-narrative-help"
                aria-invalid={overCap || undefined}
                spellCheck={false}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setResult(null);
                  setRouteError(null);
                }}
              />
              <div className="cx-editor-foot">
                <span className={overCap ? "cx-counter over" : "cx-counter"} id="cx-narrative-help">
                  {integer(draft.length)} of {integer(maxCharacters)} characters
                  {overCap ? " — too long to read, trim it" : ""}
                </span>
                <button className="primary-button" type="button" onClick={runRoute} disabled={!canRoute}>
                  <Play size={15} fill="currentColor" aria-hidden="true" />
                  {running ? "Reading..." : "Route this complaint"}
                </button>
              </div>
            </div>
            <p className="cx-privacy">
              <Info size={15} aria-hidden="true" />
              <span>
                You can paste your own words to see how the routing changes. Do not paste anyone's
                real personal details — a name, an account number, an address. Nothing typed here is
                saved, and this demo never files a complaint anywhere.
              </span>
            </p>
          </section>

          <section className="cx-panel" aria-live="polite">
            <header>
              <div>
                <span>Step 3</span>
                <strong>See the team and the reason</strong>
                <small>A score, then the 0.55 rule, then a queue. Nothing else happens here.</small>
              </div>
              <Users size={18} aria-hidden="true" />
            </header>
            {routeError ? (
              <div style={{ padding: "14px 16px" }}>
                <div className="error-banner" role="alert">
                  {routeError}
                </div>
              </div>
            ) : null}
            {result ? (
              <div className="cx-result-body">
                <div className={result.route === "auto_route" ? "cx-verdict auto" : "cx-verdict person"}>
                  <div>
                    <span>{result.route === "auto_route" ? "Goes straight to" : "Goes to a person"}</span>
                    <strong>
                      {result.route === "auto_route" ? result.predicted_team : "Human triage queue"}
                    </strong>
                    <small>
                      {result.route === "auto_route"
                        ? result.predicted_team_description
                        : `The model leaned toward ${result.predicted_team}, but not strongly enough to act on.`}
                    </small>
                  </div>
                  <div className="cx-verdict-score">
                    <span>Confidence</span>
                    <b>{percent(result.confidence)}</b>
                  </div>
                </div>

                <div className="cx-track">
                  <div
                    className="cx-track-rail"
                    role="img"
                    aria-label={`Confidence ${percent(result.confidence)} against the ${percent(result.threshold, 0)} cutoff.`}
                  >
                    <span className="cx-track-cut" style={{ left: `${result.threshold * 100}%` }}>
                      <b>Cutoff {percent(result.threshold, 0)}</b>
                    </span>
                    <span className="cx-track-dot" style={{ left: `${result.confidence * 100}%` }}>
                      <b>{percent(result.confidence)}</b>
                    </span>
                  </div>
                  <div className="cx-track-ends">
                    <span>Left of the cutoff: a person reads it</span>
                    <span>Right: straight to the team</span>
                  </div>
                </div>

                <div className="cx-chain">
                  <div>
                    <Search size={15} aria-hidden="true" />
                    <span>Strongest team score</span>
                    <strong>
                      {result.predicted_team} · {percent(result.confidence)}
                    </strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div>
                    <Scale size={15} aria-hidden="true" />
                    <span>The rule</span>
                    <strong>
                      {result.confidence >= result.threshold
                        ? `${percent(result.confidence)} is at or above ${percent(result.threshold, 0)}`
                        : `${percent(result.confidence)} is below ${percent(result.threshold, 0)}`}
                    </strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div className={result.route === "auto_route" ? "auto" : "person"}>
                    <Inbox size={15} aria-hidden="true" />
                    <span>What happens</span>
                    <strong>{result.route_label}</strong>
                  </div>
                </div>

                <p className="cx-note">{result.route_action}</p>

                {result.known_team ? (
                  <div className={result.correct ? "cx-known right" : "cx-known wrong"}>
                    {result.correct ? (
                      <CheckCircle2 size={19} aria-hidden="true" />
                    ) : (
                      <XCircle size={19} aria-hidden="true" />
                    )}
                    <div>
                      <span>Compared with the team it belonged to</span>
                      <strong>
                        {result.correct
                          ? "Right team"
                          : `Wrong team — it belonged to ${result.known_team}`}
                      </strong>
                      <small>{result.outcome_note}</small>
                    </div>
                  </div>
                ) : (
                  <div className="cx-known neutral">
                    <Info size={19} aria-hidden="true" />
                    <div>
                      <span>Your own text</span>
                      <strong>No recorded team to compare with</strong>
                      <small>{result.outcome_note}</small>
                    </div>
                  </div>
                )}

                <div className="cx-block">
                  <h3>The words that pushed it to this team</h3>
                  <p>{model.explanation.plain_mechanism}</p>
                  {result.routing_words.length === 0 ? (
                    <p className="cx-queue-empty">
                      None of these words appear in the model's vocabulary, so it had nothing to go
                      on and fell back on what it sees most often.
                    </p>
                  ) : (
                    result.routing_words.map((word) => (
                      <div className="cx-word-row" key={word.word}>
                        <div>
                          <b>{word.word}</b>
                          <div className="cx-bar">
                            <i style={{ width: `${Math.max(3, (word.push / strongestWord) * 100)}%` }} />
                          </div>
                        </div>
                        <div className="cx-word-value">{word.push.toFixed(2)}</div>
                      </div>
                    ))
                  )}
                  <p className="cx-note" style={{ marginTop: 10 }}>
                    {result.routing_words_note}
                  </p>
                </div>

                <div className="cx-block">
                  <h3>How the eight teams scored</h3>
                  <p>
                    The eight scores always add up to 100%. The largest one is the confidence above.
                  </p>
                  {result.probabilities.map((team) => (
                    <div
                      className={team.is_predicted ? "cx-prob-row chosen" : "cx-prob-row"}
                      key={team.team}
                    >
                      <div>
                        <b>
                          {team.team}
                          {team.is_predicted ? " — chosen" : ""}
                        </b>
                        <em>{team.description}</em>
                        <div className="cx-bar">
                          <i style={{ width: `${Math.max(1, team.probability * 100)}%` }} />
                        </div>
                      </div>
                      <div className="cx-prob-value">{percent(team.probability)}</div>
                    </div>
                  ))}
                </div>

                <p className="cx-note">{result.score_note}</p>
              </div>
            ) : !routeError ? (
              <div className="cx-result-empty">
                <Users size={30} aria-hidden="true" />
                <strong>{running ? "Reading the complaint..." : "Nothing routed yet"}</strong>
                <p>
                  {running
                    ? "The model is scoring the text against all eight teams."
                    : "Pick a complaint on the left, or paste your own text, then choose Route this complaint."}
                </p>
              </div>
            ) : null}
          </section>
        </section>
      ) : null}

      {view === "queues" && model && board ? (
        <section>
          <header className="cx-section-heading">
            <div>
              <span>The worklist</span>
              <h2>Where these {integer(board.summary.packaged_complaints)} complaints landed</h2>
              <p>{board.summary.plain_rule}</p>
            </div>
          </header>

          <div className="cx-summary-strip">
            <div>
              <strong>{integer(board.summary.auto_routed)}</strong>
              <span>went straight to a team</span>
              <small>No person picked the queue</small>
            </div>
            <div>
              <strong>{integer(board.summary.sent_to_triage)}</strong>
              <span>went to a person</span>
              <small>Below the {percent(board.summary.threshold, 0)} cutoff</small>
            </div>
            <div>
              <strong>{percent(board.test.triage_share)}</strong>
              <span>hand-sorting workload</span>
              <small>
                {integer(board.test.triage_rows)} of {integer(board.test.complaints)} test complaints
                reach a person
              </small>
            </div>
            <div>
              <strong>{integer(board.summary.misroutes_in_auto_routed)}</strong>
              <span>sent to the wrong team</span>
              <small>Auto-routed here and still wrong</small>
            </div>
          </div>

          <p className="cx-note" style={{ marginBottom: 14 }}>
            <strong>Workload, not accuracy.</strong> {board.summary.workload_note} {board.summary.selection_note}
          </p>

          {misroute ? (
            <div className="cx-discussion">
              <header>
                <AlertTriangle size={19} aria-hidden="true" />
                <strong>Discussion case: auto-routed with confidence, and wrong</strong>
              </header>
              <div className="cx-discussion-grid">
                <div>
                  <span>Complaint</span>
                  <strong>#{misroute.complaint_id}</strong>
                </div>
                <div>
                  <span>Confidence</span>
                  <strong>{percent(misroute.confidence)}</strong>
                </div>
                <div>
                  <span>Team it went to</span>
                  <strong>{misroute.predicted_team}</strong>
                </div>
                <div>
                  <span>Team it belonged to</span>
                  <strong>{misroute.known_team}</strong>
                </div>
              </div>
              <blockquote>{misroute.excerpt}</blockquote>
              <p>
                This one cleared the cutoff comfortably, so nothing in the routing flagged it. It sat
                in the {misroute.predicted_team} queue until a specialist noticed the complaint was
                not theirs — and the days it waited were days on a regulatory clock.
              </p>
              <p>
                <q>What monitoring would catch this?</q> The route itself cannot: confidence says how
                sure the model is, not whether it is right. Something outside the model has to
                notice — a count of complaints each team sends back, a weekly sample read by a
                person, or an alert when one team's share of the intake suddenly moves.
              </p>
            </div>
          ) : null}

          <div className="cx-queue-grid">
            {board.teams.map((team) => (
              <section className="cx-queue-lane" key={team.team}>
                <header>
                  <div>
                    <strong>{team.team}</strong>
                    <b>{integer(team.complaints)}</b>
                  </div>
                  <small>{team.description}</small>
                  <div className="cx-chip-row">
                    <em className="cx-chip auto">{percent(team.share_of_auto_routed, 0)} of routed</em>
                    {team.misrouted > 0 ? (
                      <em className="cx-chip wrong">
                        {team.misrouted} not {team.misrouted === 1 ? "this team's" : "these teams'"}
                      </em>
                    ) : (
                      <em className="cx-chip right">All belong here</em>
                    )}
                  </div>
                </header>
                <div className="cx-queue-items">
                  {team.items.length === 0 ? (
                    <p className="cx-queue-empty">
                      Nothing in this queue right now. This team still exists and still answers
                      complaints; none of the packaged ones scored highest for it.
                    </p>
                  ) : (
                    team.items.map((item) => (
                      <article
                        className={item.correct ? "cx-queue-item" : "cx-queue-item flagged"}
                        key={item.complaint_id}
                      >
                        <div>
                          <b>#{item.complaint_id}</b>
                          <i>{percent(item.confidence)}</i>
                        </div>
                        <p>{item.excerpt}</p>
                        {item.correct ? null : (
                          <div className="cx-chip-row">
                            <em className="cx-chip wrong">Belonged to {item.known_team}</em>
                          </div>
                        )}
                      </article>
                    ))
                  )}
                </div>
              </section>
            ))}

            <section className="cx-queue-lane triage">
              <header>
                <div>
                  <strong>Human triage queue</strong>
                  <b>{integer(board.triage.complaints)}</b>
                </div>
                <small>{board.triage.action}</small>
                <div className="cx-chip-row">
                  <em className="cx-chip person">{percent(board.triage.share, 0)} of these complaints</em>
                </div>
              </header>
              <div className="cx-queue-items">
                {board.triage.items.length === 0 ? (
                  <p className="cx-queue-empty">
                    Nothing is waiting for a person. Every packaged complaint cleared the cutoff.
                  </p>
                ) : (
                  board.triage.items.map((item) => (
                    <article className="cx-queue-item" key={item.complaint_id}>
                      <div>
                        <b>#{item.complaint_id}</b>
                        <i>{percent(item.confidence)}</i>
                      </div>
                      <p>{item.excerpt}</p>
                      <div className="cx-chip-row">
                        <em className="cx-chip person">Leaned toward {item.predicted_team}</em>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>

          <p className="cx-note">{board.triage.workload_note} {board.summary.boundary_detail}</p>
        </section>
      ) : null}

      {view === "evidence" && model ? (
        <section>
          <header className="cx-section-heading">
            <div>
              <span>Deployment record</span>
              <h2>{model.model_name}</h2>
              <p>{model.intended_use}</p>
            </div>
            <div className="cx-chip">Version {model.model_version.slice(0, 10)}</div>
          </header>

          <div className="cx-evidence-grid">
            <div className="cx-fact">
              <BookOpenCheck size={18} aria-hidden="true" />
              <span>How it reads text</span>
              <strong>{model.representation.kind}</strong>
              <small>
                {integer(model.representation.columns_learned)} words and 2-word phrases, each one a
                column the model holds a weight for
              </small>
            </div>
            <div className="cx-fact">
              <Layers3 size={18} aria-hidden="true" />
              <span>How it decides</span>
              <strong>{model.estimator.split("(")[0]}</strong>
              <small>{model.packaging}</small>
            </div>
            <div className="cx-fact">
              <FileText size={18} aria-hidden="true" />
              <span>What it reads</span>
              <strong>{model.input}</strong>
              <small>
                Never the company, the state, the issue field, or anything said on the phone
              </small>
            </div>
            <div className="cx-fact">
              <Users size={18} aria-hidden="true" />
              <span>Where the complaints come from</span>
              <strong>{model.dataset.name}</strong>
              <small>
                {model.dataset.publisher} · {model.dataset.rights}
              </small>
            </div>
          </div>

          <header className="cx-section-heading">
            <div>
              <span>Measured once, after the rules were frozen</span>
              <h2>Results on the {integer(model.test_metrics.complaints)} untouched test complaints</h2>
              <p>{model.test_metrics.note}</p>
            </div>
          </header>

          <div className="cx-metric-strip">
            <div>
              <strong>{percent(model.test_metrics.accuracy)}</strong>
              <span>accuracy</span>
              <small>{model.test_metrics.baseline_note}</small>
            </div>
            <div>
              <strong>{decimal(model.test_metrics.macro_f1)}</strong>
              <span>macro-F1</span>
              <small>
                Against {decimal(model.test_metrics.baseline_macro_f1)} for that always-one-answer
                rule
              </small>
            </div>
            <div>
              <strong>{percent(model.test_metrics.coverage)}</strong>
              <span>coverage</span>
              <small>
                {integer(model.test_metrics.auto_routed)} complaints went to a team with nobody
                sorting them
              </small>
            </div>
            <div>
              <strong>{percent(model.test_metrics.accuracy_among_auto_routed)}</strong>
              <span>accuracy among those routed</span>
              <small>
                The unsure {percent(model.test_metrics.triage_share)} went to a person instead
              </small>
            </div>
          </div>

          <div className="cx-panel" style={{ marginBottom: 14 }}>
            <header>
              <div>
                <span>The operating rule</span>
                <strong>{model.policy.name}</strong>
                <small>{model.policy.selected_on}</small>
              </div>
              <Scale size={18} aria-hidden="true" />
            </header>
            <div style={{ padding: "14px 16px", display: "grid", gap: 12 }}>
              <p className="cx-note" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                {model.policy.plain_rule}
              </p>
              <div className="cx-evidence-grid" style={{ margin: 0 }}>
                <div className="cx-fact">
                  <span>When {model.policy.auto_route_when}</span>
                  <strong>Straight to the team</strong>
                  <small>{model.policy.auto_route_action}</small>
                </div>
                <div className="cx-fact">
                  <span>When {model.policy.triage_when}</span>
                  <strong>To a person</strong>
                  <small>{model.policy.triage_action}</small>
                </div>
                <div className="cx-fact">
                  <span>If the complaint is blank</span>
                  <strong>Never scored</strong>
                  <small>{model.policy.fallback}</small>
                </div>
              </div>
              <div className="cx-boundary" style={{ marginBottom: 0 }}>
                <Scale size={19} aria-hidden="true" />
                <div>
                  <strong>{model.policy.boundary}</strong>
                  <p>{model.policy.boundary_detail}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="cx-panel" style={{ marginBottom: 14 }}>
            <header>
              <div>
                <span>Per team</span>
                <strong>The eight queues are not equally easy</strong>
                <small>
                  Precision is how often a complaint sent to this team belonged to it. Recall is how
                  many of the team's own complaints reached it.
                </small>
              </div>
            </header>
            <div className="cx-table-wrap">
              <table className="cx-table">
                <thead>
                  <tr>
                    <th scope="col">Team</th>
                    <th scope="col">What it answers</th>
                    <th scope="col" className="num">Precision</th>
                    <th scope="col" className="num">Recall</th>
                    <th scope="col" className="num">F1</th>
                    <th scope="col" className="num">Test complaints</th>
                  </tr>
                </thead>
                <tbody>
                  {model.per_team.map((row) => {
                    const team = model.teams.find((entry) => entry.name === row.team);
                    return (
                      <tr key={row.team} className={team ? "" : "macro"}>
                        <td>{team ? row.team : "All eight, averaged equally"}</td>
                        <td style={{ color: "var(--text-muted)", fontSize: 11 }}>
                          {team?.description ?? "Each team counts the same, however small"}
                        </td>
                        <td className="num">{decimal(row.precision)}</td>
                        <td className="num">{decimal(row.recall)}</td>
                        <td className="num">{decimal(row.f1)}</td>
                        <td className="num">{integer(row.complaints)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <header className="cx-section-heading">
            <div>
              <span>Honest data</span>
              <h2>Two findings that changed the numbers</h2>
              <p>
                Neither of these is a modeling trick. One is about the data the model learned from,
                the other about the choice of how to turn text into numbers.
              </p>
            </div>
          </header>

          <div className="cx-honest">
            <section className="cx-honest-panel">
              <header>
                <Copy size={18} aria-hidden="true" />
                <strong>Nearly half the letters were copies</strong>
              </header>
              <div className="cx-honest-body">
                <div className="cx-honest-headline">
                  <b>{percent(model.dedupe.share_removed)}</b>
                  <span>
                    of complaints in this window repeated a letter someone had already filed —{" "}
                    {integer(model.dedupe.rows_removed)} of {integer(model.dedupe.mapped_rows_in_window)}
                  </span>
                </div>
                <p>
                  Credit-repair services file the same template letter for thousands of consumers.
                  The copies were removed before the data was split into training and test sets.
                </p>
                <div className="cx-swap">
                  <div>
                    <span>If the copies had stayed</span>
                    <strong>{percent(model.dedupe.inflated_test_accuracy)}</strong>
                  </div>
                  <ArrowRight size={17} aria-hidden="true" />
                  <div>
                    <span>Honest score</span>
                    <strong>{percent(model.dedupe.honest_test_accuracy)}</strong>
                  </div>
                </div>
                <p>
                  <strong>The lesson.</strong> {model.dedupe.lesson}
                </p>
                <p>
                  The copying is not spread evenly: {model.dedupe.share_removed_by_team[0]?.team} lost{" "}
                  {percent(model.dedupe.share_removed_by_team[0]?.share_removed ?? 0, 0)} of its rows,
                  while{" "}
                  {model.dedupe.share_removed_by_team[model.dedupe.share_removed_by_team.length - 1]?.team}{" "}
                  lost almost none. Removing them changes which teams the model sees most.
                </p>
              </div>
            </section>

            <section className="cx-honest-panel">
              <header>
                <Layers3 size={18} aria-hidden="true" />
                <strong>The transformer scored lower here</strong>
              </header>
              <div className="cx-honest-body">
                <p>{model.representation_comparison.design}</p>
                <div className="cx-table-wrap">
                  <table className="cx-table" style={{ minWidth: 320 }}>
                    <thead>
                      <tr>
                        <th scope="col">Way of reading the text</th>
                        <th scope="col" className="num">Accuracy</th>
                        <th scope="col" className="num">Macro-F1</th>
                      </tr>
                    </thead>
                    <tbody>
                      {model.representation_comparison.results.map((row) => (
                        <tr
                          key={row.model}
                          className={row.model === model.representation_comparison.winner ? "chosen" : ""}
                        >
                          <td>
                            {row.representation}
                            <div style={{ color: "var(--text-muted)", fontSize: 10, marginTop: 3 }}>
                              {row.explanation_available}
                            </div>
                          </td>
                          <td className="num">{percent(row.validation_accuracy)}</td>
                          <td className="num">{decimal(row.validation_macro_f1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p style={{ marginTop: 11 }}>
                  <strong>A trade, not an upgrade.</strong> {model.representation_comparison.lesson}
                </p>
                <p>
                  The newer method reads at most{" "}
                  {model.representation_comparison.embedding_facts["Longest input it reads"] ??
                    "256 tokens"}
                  , and it gives back {model.representation_comparison.embedding_facts["Output vector per complaint"] ?? "one vector"}{" "}
                  with no word a triage clerk could point at.
                </p>
              </div>
            </section>
          </div>

          <div className="cx-list-panels">
            <section className="cx-list-panel">
              <h3>What this model cannot tell you</h3>
              <ul>
                {model.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="cx-list-panel">
              <h3>What it must never be used for</h3>
              <ul>
                {model.excluded_uses.map((item) => (
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
