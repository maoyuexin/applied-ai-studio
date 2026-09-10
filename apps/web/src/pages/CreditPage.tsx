import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Database,
  Info,
  Layers3,
  ListFilter,
  Play,
  RefreshCcw,
  Scale,
  ShieldAlert,
  SlidersHorizontal,
  TrendingUp,
  UserCheck,
  Users,
  Wallet,
} from "lucide-react";
import {
  getCreditModel,
  getCreditReviewQueue,
  getCreditSamples,
  scoreCreditAccount,
  type CreditAccountInput,
  type CreditBehavior,
  type CreditModelInfo,
  type CreditPackagedAccount,
  type CreditReviewQueue,
  type CreditScore,
} from "../creditApi";
import { navigate } from "../router";

/* Page styles live here, not in index.css, because this component had to ship as a
   single file. Every rule is prefixed .credit-, so the block can be moved into
   index.css verbatim and this <style> element deleted, with no other change. */
const pageStyles = `
.credit-page { width: min(1560px, 100%); --credit-body: 13px; --credit-support: 12px; --credit-label: 10px; --credit-flag: var(--amber); --credit-monitor: #6abf9b; }
.credit-page .page-back-button { min-height: 44px; font-size: 11px; }
.credit-page table { width: 100%; border-collapse: collapse; }
.credit-page .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

.credit-header { min-height: 82px; margin-bottom: 14px; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.credit-header h1 { margin: 3px 0 6px; font-size: 29px; line-height: 1.2; }
.credit-header p { max-width: 900px; margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.55; }
.credit-runtime-status { min-width: 258px; padding: 11px 13px; display: flex; align-items: center; gap: 10px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.credit-runtime-status > span { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--amber); box-shadow: 0 0 0 4px rgba(240, 180, 41, 0.1); }
.credit-runtime-status > span.ready { background: var(--green); box-shadow: 0 0 0 4px rgba(74, 222, 128, 0.1); }
.credit-runtime-status strong, .credit-runtime-status small { display: block; }
.credit-runtime-status strong { font-size: var(--credit-body); }
.credit-runtime-status small { margin-top: 3px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--credit-label); line-height: 1.4; }

.credit-boundary-line { min-height: 49px; margin-bottom: 14px; padding: 10px 14px; display: grid; grid-template-columns: 20px auto minmax(0, 1fr); align-items: center; gap: 10px; border-top: 1px solid rgba(126, 174, 184, 0.45); border-bottom: 1px solid rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.06); color: var(--teal); }
.credit-boundary-line strong { font-size: var(--credit-support); }
.credit-boundary-line span { color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.45; }

.credit-metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: 15px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.credit-metric-strip > div { min-width: 0; min-height: 84px; padding: 13px 17px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.credit-metric-strip > div:last-child { border-right: 0; }
.credit-metric-strip strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 21px; }
.credit-metric-strip span { margin-top: 3px; color: var(--text-secondary); font-size: var(--credit-support); }
.credit-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }

.credit-workspace-switcher { min-height: 66px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.credit-workspace-switcher button { min-width: 0; min-height: 64px; padding: 10px 15px; display: flex; align-items: center; gap: 10px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.credit-workspace-switcher button:last-child { border-right: 0; }
.credit-workspace-switcher button:hover, .credit-workspace-switcher button.active { background: var(--surface-raised); color: var(--orange); }
.credit-workspace-switcher button.active { box-shadow: inset 0 -3px 0 var(--orange); }
.credit-workspace-switcher button:focus-visible { outline-offset: -3px; }
.credit-workspace-switcher strong, .credit-workspace-switcher small { display: block; }
.credit-workspace-switcher strong { color: var(--text); font-size: 14px; }
.credit-workspace-switcher small { margin-top: 3px; font-size: 11px; }

.credit-account-workspace { display: grid; grid-template-columns: minmax(235px, 0.34fr) minmax(360px, 0.88fr) minmax(370px, 0.78fr); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.credit-account-workspace > * { min-width: 0; }
.credit-account-browser, .credit-behavior-panel { border-right: 1px solid var(--border); }
.credit-account-workspace > section > header, .credit-account-browser > header { min-height: 74px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); }
.credit-account-workspace header span.step { color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-account-workspace header strong { display: block; margin-top: 3px; font-size: var(--credit-body); }
.credit-account-workspace header small { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }
.credit-account-list { max-height: 720px; overflow-y: auto; }
.credit-account-list button { width: 100%; min-height: 92px; padding: 11px 13px; display: block; border: 0; border-bottom: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.credit-account-list button:hover, .credit-account-list button.active { background: var(--surface-raised); box-shadow: inset 3px 0 0 var(--orange); }
.credit-account-list button:focus-visible { outline-offset: -3px; }
.credit-account-list span { display: block; color: var(--teal); font-size: var(--credit-label); line-height: 1.4; }
.credit-account-list strong { display: block; margin-top: 4px; color: var(--text); font-family: var(--font-mono); font-size: 11px; }
.credit-account-list small { display: block; margin-top: 5px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.5; }
.credit-list-empty { padding: 26px 14px; color: var(--text-muted); font-size: var(--credit-support); line-height: 1.6; }

.credit-behavior-panel, .credit-result-panel { display: flex; flex-direction: column; }
.credit-scenario-note { padding: 11px 14px; display: flex; gap: 9px; border-bottom: 1px solid var(--border); background: rgba(126, 174, 184, 0.05); color: var(--teal); }
.credit-scenario-note p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-balance-path { padding: 14px; display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1fr); align-items: center; gap: 10px; border-bottom: 1px solid var(--border); }
.credit-balance-path > div { min-width: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; background: #14161c; }
.credit-balance-path span { display: block; color: var(--text-muted); font-size: var(--credit-label); }
.credit-balance-path strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 16px; }
.credit-balance-path small { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--credit-label); line-height: 1.4; }
.credit-behavior-table { padding: 4px 14px 12px; }
.credit-behavior-table caption { padding: 10px 0 6px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; text-align: left; }
.credit-behavior-table th, .credit-behavior-table td { padding: 9px 0; border-bottom: 1px solid var(--border); font-size: var(--credit-support); text-align: left; vertical-align: top; }
.credit-behavior-table th { width: 58%; color: var(--text-secondary); font-weight: 500; }
.credit-behavior-table td { color: var(--text); font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; }
.credit-behavior-table td b { display: block; margin-top: 4px; color: var(--text-muted); font-family: var(--font-body); font-size: var(--credit-label); font-weight: 400; }
.credit-behavior-table tr.changed th, .credit-behavior-table tr.changed td { color: var(--orange); }
.credit-behavior-table th em { display: block; margin-top: 4px; color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); font-style: normal; }
.credit-derivation-note { margin: 0; padding: 0 14px 12px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.55; }

.credit-whatif { margin-top: auto; padding: 13px 14px; border-top: 1px solid var(--border); background: #14161c; }
.credit-whatif > span { color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-whatif > strong { display: block; margin-top: 4px; font-size: var(--credit-body); }
.credit-whatif-controls { margin-top: 11px; display: grid; gap: 12px; }
.credit-whatif-controls label { display: block; }
.credit-whatif-controls label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--credit-support); }
.credit-whatif-controls output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--credit-body); }
.credit-page input[type="range"] { width: 100%; height: 44px; padding: 0; border: 0; background: transparent; box-shadow: none; accent-color: var(--orange); }
.credit-whatif-controls small { display: block; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.5; }
.credit-whatif-actions { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.credit-whatif-actions .primary-button, .credit-whatif-actions .secondary-button { min-height: 44px; margin-top: 0; }
.credit-whatif-pending { margin: 10px 0 0; padding: 9px 11px; display: flex; gap: 8px; border-left: 3px solid var(--amber); background: rgba(240, 180, 41, 0.07); color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.5; }

.credit-result-panel { padding-bottom: 14px; }
.credit-result-body { padding: 14px; display: grid; gap: 12px; }
.credit-score-summary { padding: 14px; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; border: 1px solid var(--border-strong); border-radius: 6px; background: #14161c; }
.credit-score-summary.priority_review { border-color: rgba(240, 180, 41, 0.55); background: rgba(240, 180, 41, 0.06); }
.credit-score-summary.standard_monitoring { border-color: rgba(106, 191, 155, 0.45); background: rgba(106, 191, 155, 0.05); }
.credit-score-summary span { display: block; color: var(--text-muted); font-size: var(--credit-label); }
.credit-score-summary strong { display: block; margin-top: 4px; font-size: 16px; line-height: 1.3; }
.credit-score-summary small { display: block; margin-top: 5px; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.45; }
.credit-score-value { text-align: right; }
.credit-score-value strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 27px; }
.credit-math-chain { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.credit-math-chain > div { min-width: 0; padding: 10px 12px; background: var(--surface); }
.credit-math-chain span { display: block; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }
.credit-math-chain strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--credit-body); }
.credit-math-result { padding: 11px 12px; display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1fr); align-items: center; gap: 10px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.credit-math-result span { display: block; color: var(--text-muted); font-size: var(--credit-label); }
.credit-math-result strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--credit-body); }
.credit-route-line { padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-raised); }
.credit-route-line.priority_review { color: var(--credit-flag); border-color: rgba(240, 180, 41, 0.45); }
.credit-route-line.standard_monitoring { color: var(--credit-monitor); border-color: rgba(106, 191, 155, 0.4); }
.credit-route-line strong { display: block; font-size: var(--credit-body); }
.credit-route-line p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }

.credit-outcome-band { padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-radius: 6px; border: 1px solid var(--border); background: #14161c; }
.credit-outcome-band.missed { border-color: rgba(228, 90, 88, 0.42); color: var(--red); }
.credit-outcome-band.paid { border-color: rgba(106, 191, 155, 0.42); color: var(--credit-monitor); }
.credit-outcome-band.what-if { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.07); color: var(--credit-flag); }
.credit-outcome-band span { display: block; color: var(--text-muted); font-size: var(--credit-label); }
.credit-outcome-band strong { display: block; margin-top: 4px; font-size: var(--credit-body); }
.credit-outcome-band p { margin: 6px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-changed-chips { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px; }
.credit-changed-chips span { padding: 4px 7px; border: 1px solid rgba(240, 180, 41, 0.42); border-radius: 3px; color: var(--credit-flag); font-size: var(--credit-label); }
.credit-whatif-shift { margin-top: 9px; padding-top: 9px; display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1fr); align-items: center; gap: 10px; border-top: 1px solid rgba(240, 180, 41, 0.28); }
.credit-whatif-shift span { display: block; color: var(--text-muted); font-size: var(--credit-label); }
.credit-whatif-shift strong { display: block; margin-top: 3px; color: var(--text); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--credit-body); }

.credit-reasons { border: 1px solid var(--border); border-radius: 6px; background: #14161c; overflow: hidden; }
.credit-reasons > header { padding: 11px 12px; border-bottom: 1px solid var(--border); }
.credit-reasons > header span { color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-reasons > header strong { display: block; margin-top: 4px; font-size: var(--credit-body); }
.credit-reason-row { padding: 10px 12px; border-bottom: 1px solid var(--border); }
.credit-reason-row:last-of-type { border-bottom: 0; }
.credit-reason-row div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.credit-reason-row b { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--credit-label); font-weight: 500; text-transform: uppercase; }
.credit-reason-row strong { color: var(--text); font-size: var(--credit-support); }
.credit-reason-row p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.5; }
.credit-reason-track { height: 6px; margin-top: 7px; border-radius: 3px; background: var(--surface-raised); overflow: hidden; }
.credit-reason-track i { display: block; height: 100%; background: var(--orange); }
.credit-reasons footer { padding: 10px 12px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: var(--credit-label); line-height: 1.55; }
.credit-authority { padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-left: 3px solid var(--teal); background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.credit-authority span { display: block; font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-authority p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-result-empty { min-height: 260px; padding: 22px; display: grid; place-content: center; justify-items: center; gap: 8px; color: var(--text-muted); text-align: center; }
.credit-result-empty p { margin: 0; max-width: 320px; font-size: var(--credit-support); line-height: 1.6; }

.credit-section-heading { margin-bottom: 14px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.credit-section-heading span { color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-section-heading h2 { margin: 5px 0 5px; font-size: 20px; }
.credit-section-heading h3 { margin: 5px 0 0; font-size: 15px; }
.credit-section-heading p { margin: 0; max-width: 900px; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.6; }
.credit-section-heading > strong { display: inline-flex; align-items: center; gap: 7px; padding: 8px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--credit-label); white-space: nowrap; }
.credit-assumption-note { margin-bottom: 14px; padding: 10px 12px; display: flex; gap: 9px; border-left: 3px solid var(--amber); background: rgba(240, 180, 41, 0.07); color: var(--amber); }
.credit-assumption-note p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-assumption-note strong { color: var(--amber); }

.credit-cost-control { margin-bottom: 14px; padding: 14px; display: grid; grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr); gap: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.credit-cost-control > div { min-width: 0; }
.credit-cost-control label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--credit-support); }
.credit-cost-control output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.credit-cost-scale { display: flex; justify-content: space-between; gap: 12px; color: var(--text-muted); font-size: var(--credit-label); }
.credit-cost-help { margin: 8px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-cost-status { min-height: 18px; margin: 8px 0 0; color: var(--teal); font-family: var(--font-mono); font-size: var(--credit-label); }
.credit-queue-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.credit-queue-summary > div { min-width: 0; min-height: 88px; padding: 13px 15px; display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
.credit-queue-summary strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 20px; }
.credit-queue-summary span { margin-top: 4px; color: var(--text-secondary); font-size: var(--credit-support); }
.credit-queue-summary small { margin-top: 3px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }
.credit-capacity-line { margin-bottom: 12px; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; color: var(--teal); }
.credit-capacity-line strong { display: block; color: var(--text); font-size: var(--credit-support); }
.credit-capacity-line p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-note-row { margin-bottom: 12px; padding: 10px 12px; display: flex; gap: 9px; border: 1px dashed var(--border-strong); border-radius: 6px; color: var(--text-muted); }
.credit-note-row p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }

.credit-table-wrap { margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow-x: auto; }
.credit-table { min-width: 720px; }
.credit-table caption { padding: 12px 14px; color: var(--text-secondary); font-size: var(--credit-support); text-align: left; }
.credit-table th, .credit-table td { padding: 11px 14px; border-bottom: 1px solid var(--border); font-size: var(--credit-support); text-align: left; vertical-align: top; }
.credit-table thead th { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--credit-label); font-weight: 500; text-transform: uppercase; white-space: nowrap; }
.credit-table tbody th { color: var(--text); font-weight: 600; }
.credit-table tbody tr:last-child th, .credit-table tbody tr:last-child td { border-bottom: 0; }
.credit-table td span { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.45; }
.credit-table .num { white-space: nowrap; }
.credit-tag { display: inline-flex; align-items: center; gap: 5px; padding: 4px 7px; border: 1px solid var(--border-strong); border-radius: 3px; color: var(--text-secondary); font-size: var(--credit-label); white-space: nowrap; }
.credit-tag.within { border-color: rgba(106, 191, 155, 0.45); color: var(--credit-monitor); }
.credit-tag.beyond { border-color: rgba(240, 180, 41, 0.5); color: var(--credit-flag); }
.credit-tag.missed { border-color: rgba(228, 90, 88, 0.45); color: var(--red); }
.credit-tag.paid { border-color: rgba(106, 191, 155, 0.45); color: var(--credit-monitor); }
.credit-tag.small-group { border-color: rgba(240, 180, 41, 0.5); color: var(--credit-flag); }
.credit-table-empty { padding: 26px 14px; color: var(--text-muted); font-size: var(--credit-support); line-height: 1.6; }
.credit-row-current th, .credit-row-current td { background: rgba(232, 145, 60, 0.08); }

.credit-frozen-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.credit-frozen-strip > div { min-width: 0; min-height: 82px; padding: 12px 14px; display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
.credit-frozen-strip strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 18px; }
.credit-frozen-strip span { margin-top: 4px; color: var(--text-secondary); font-size: var(--credit-support); }
.credit-frozen-strip small { margin-top: 3px; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }

.credit-governance-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.credit-governance-grid > div { min-width: 0; min-height: 108px; padding: 13px 15px; background: var(--surface); color: var(--teal); }
.credit-governance-grid span { display: block; margin-top: 8px; color: var(--text-muted); font-size: var(--credit-label); text-transform: uppercase; }
.credit-governance-grid strong { display: block; margin-top: 4px; color: var(--text); font-size: var(--credit-body); line-height: 1.35; }
.credit-governance-grid small { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--credit-label); line-height: 1.5; }
.credit-panel { margin-bottom: 14px; padding: 15px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.credit-panel > header { margin-bottom: 12px; }
.credit-panel > header span { color: var(--orange); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-panel > header h3 { margin: 5px 0 0; font-size: 15px; }
.credit-panel > header p { margin: 6px 0 0; max-width: 900px; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.6; }
.credit-plain-rule { margin: 0 0 12px; padding: 12px 14px; border-left: 3px solid var(--orange); background: rgba(232, 145, 60, 0.07); color: var(--text); font-size: var(--credit-body); line-height: 1.65; }
.credit-definition-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.credit-definition-grid > div { padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; background: #14161c; }
.credit-definition-grid dt { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-definition-grid dd { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-definition-grid dd b { color: var(--text); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-weight: 600; }
.credit-list-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.credit-list-columns section > span { color: var(--teal); font-family: var(--font-mono); font-size: var(--credit-label); text-transform: uppercase; }
.credit-list-columns ul { margin: 8px 0 0; padding-left: 18px; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.7; }
.credit-comparison { display: grid; grid-template-columns: minmax(0, 1fr) 18px minmax(0, 1fr) minmax(0, 1.2fr); align-items: center; gap: 12px; margin-bottom: 12px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.credit-comparison > div { min-width: 0; }
.credit-comparison span { display: block; color: var(--text-muted); font-size: var(--credit-label); line-height: 1.4; }
.credit-comparison strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.credit-comparison p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-small-group-caution { margin-bottom: 12px; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border: 1px solid rgba(240, 180, 41, 0.5); border-radius: 6px; background: rgba(240, 180, 41, 0.07); color: var(--credit-flag); }
.credit-small-group-caution p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-module-preview { margin: 0; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-left: 3px solid var(--teal); background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.credit-module-preview p { margin: 0; color: var(--text-secondary); font-size: var(--credit-support); line-height: 1.55; }
.credit-small-group-caution p strong, .credit-module-preview p strong { color: var(--text); }
.credit-inline-actions { margin-top: 10px; display: flex; gap: 8px; }
.credit-inline-actions .secondary-button { min-height: 44px; }
.credit-source-link { color: var(--teal); overflow-wrap: anywhere; font-size: var(--credit-support); }

@media (max-width: 1180px) {
  .credit-account-workspace { grid-template-columns: minmax(215px, 0.35fr) minmax(0, 1fr); }
  .credit-behavior-panel { border-right: 0; }
  .credit-result-panel { grid-column: 1 / -1; border-top: 1px solid var(--border); }
  .credit-metric-strip, .credit-queue-summary, .credit-frozen-strip, .credit-governance-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .credit-cost-control { grid-template-columns: minmax(0, 1fr); }
  .credit-comparison { grid-template-columns: minmax(0, 1fr); }
  .credit-comparison > svg { transform: rotate(90deg); }
}

@media (max-width: 760px) {
  .credit-header { flex-direction: column; }
  .credit-header h1 { font-size: 23px; }
  .credit-runtime-status { width: 100%; }
  .credit-boundary-line { grid-template-columns: 20px minmax(0, 1fr); }
  .credit-boundary-line span { grid-column: 1 / -1; }
  .credit-metric-strip, .credit-queue-summary, .credit-frozen-strip, .credit-governance-grid, .credit-math-chain, .credit-definition-grid, .credit-list-columns { grid-template-columns: minmax(0, 1fr); }
  .credit-workspace-switcher { grid-template-columns: minmax(0, 1fr); }
  .credit-workspace-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .credit-workspace-switcher button:last-child { border-bottom: 0; }
  .credit-account-workspace { grid-template-columns: minmax(0, 1fr); }
  .credit-account-browser, .credit-behavior-panel { border-right: 0; border-bottom: 1px solid var(--border); }
  .credit-account-list { max-height: 340px; }
  .credit-result-panel { border-top: 0; }
  .credit-balance-path, .credit-math-result, .credit-whatif-shift { grid-template-columns: minmax(0, 1fr); }
  .credit-balance-path > svg, .credit-math-result > svg, .credit-whatif-shift > svg { transform: rotate(90deg); justify-self: center; }
  .credit-section-heading { flex-direction: column; align-items: flex-start; }
  .credit-score-summary { grid-template-columns: minmax(0, 1fr); }
  .credit-score-value { text-align: left; }
  .credit-whatif-actions .primary-button, .credit-whatif-actions .secondary-button { flex: 1 1 100%; justify-content: center; }
}
`;

type Workspace = "account" | "queue" | "governance";

const workspaces = [
  { id: "account" as const, label: "Review one account", detail: "Behavior, score, reasons", icon: SlidersHorizontal },
  { id: "queue" as const, label: "This month's queue", detail: "Ranked by expected loss", icon: ListFilter },
  { id: "governance" as const, label: "Model card and governance", detail: "Evidence, limits, fairness", icon: Layers3 },
];

const SMALL_GROUP = 100;
const QUEUE_LIMIT = 25;

const numberFormat = new Intl.NumberFormat("en-US");
const money = (value: number): string =>
  `${value < 0 ? "-" : ""}NT$${numberFormat.format(Math.abs(Math.round(value)))}`;
const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const count = (value: number): string => numberFormat.format(Math.round(value));
const monthWord = (value: number): string => `${value.toFixed(0)} month${Math.round(value) === 1 ? "" : "s"}`;
const clamp = (value: number, low: number, high: number): number => Math.min(high, Math.max(low, value));
const sameInputs = (left: CreditAccountInput, right: CreditAccountInput): boolean =>
  left.account_id === right.account_id
  && left.credit_limit === right.credit_limit
  && left.current_bill === right.current_bill
  && left.last_payment === right.last_payment
  && left.months_late_now === right.months_late_now
  && left.worst_delay_6m === right.worst_delay_6m
  && left.num_late_months_6m === right.num_late_months_6m
  && left.payment_ratio_6m === right.payment_ratio_6m
  && left.bill_trend_6m === right.bill_trend_6m;
const buildDate = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" }).format(parsed);
};

/* Mirrors the service's own arithmetic (runtime.CreditRuntime._behavior) so the
   six-month panel follows the sliders before anything is sent to the model. */
const deriveBehavior = (input: CreditAccountInput, note: string): CreditBehavior => ({
  credit_limit_NT: input.credit_limit,
  current_bill_NT: input.current_bill,
  bill_six_months_ago_NT: input.current_bill - input.bill_trend_6m * input.credit_limit,
  last_payment_NT: input.last_payment,
  utilization: clamp(input.current_bill / input.credit_limit, 0, 2),
  months_late_now: input.months_late_now,
  worst_delay_6m: input.worst_delay_6m,
  num_late_months_6m: input.num_late_months_6m,
  payment_ratio_6m: input.payment_ratio_6m,
  bill_trend_6m: input.bill_trend_6m,
  derivation_note: note,
});

export default function CreditPage() {
  const [workspace, setWorkspace] = useState<Workspace>("account");
  const [model, setModel] = useState<CreditModelInfo | null>(null);
  const [accounts, setAccounts] = useState<CreditPackagedAccount[]>([]);
  const [queue, setQueue] = useState<CreditReviewQueue | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<CreditAccountInput | null>(null);
  const [scoredInputs, setScoredInputs] = useState<CreditAccountInput | null>(null);
  const [score, setScore] = useState<CreditScore | null>(null);
  const [packagedScore, setPackagedScore] = useState<CreditScore | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reviewCost, setReviewCost] = useState<number | null>(null);
  const [queueBusy, setQueueBusy] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [queueAttempt, setQueueAttempt] = useState(0);
  const skipFirstQueueFetch = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getCreditModel(), getCreditSamples(12), getCreditReviewQueue(QUEUE_LIMIT)])
      .then(async ([modelInfo, packagedAccounts, reviewQueue]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setAccounts(packagedAccounts);
        setQueue(reviewQueue);
        skipFirstQueueFetch.current = true;
        setReviewCost(reviewQueue.summary.review_cost_NT);
        const first = packagedAccounts[0];
        if (!first) return;
        setSelectedId(first.scenario_id);
        setDraft({ ...first.inputs });
        const initial = await scoreCreditAccount(first.inputs);
        if (cancelled) return;
        setScore(initial);
        setPackagedScore(initial);
        setScoredInputs({ ...first.inputs });
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The review-cost control refetches the queue; the first run is skipped because
  // the initial load already carries the queue at the frozen cost.
  useEffect(() => {
    if (reviewCost === null) return;
    if (skipFirstQueueFetch.current) {
      skipFirstQueueFetch.current = false;
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setQueueBusy(true);
      getCreditReviewQueue(QUEUE_LIMIT, reviewCost)
        .then((next) => {
          if (cancelled) return;
          setQueue(next);
          setQueueError(null);
        })
        .catch((reason: Error) => {
          if (!cancelled) setQueueError(reason.message);
        })
        .finally(() => {
          if (!cancelled) setQueueBusy(false);
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [reviewCost, queueAttempt]);

  const selected = accounts.find((account) => account.scenario_id === selectedId) ?? null;
  const behaviorNote = score?.behavior.derivation_note ?? selected?.behavior.derivation_note ?? "";
  const behavior = draft ? deriveBehavior(draft, behaviorNote) : null;
  const changedFields: string[] = [];
  if (selected && draft) {
    if (draft.months_late_now !== selected.inputs.months_late_now) changedFields.push("months_late_now");
    if (draft.worst_delay_6m !== selected.inputs.worst_delay_6m) changedFields.push("worst_delay_6m");
    if (draft.num_late_months_6m !== selected.inputs.num_late_months_6m) changedFields.push("num_late_months_6m");
    if (draft.current_bill !== selected.inputs.current_bill) changedFields.push("current_bill");
    if (draft.bill_trend_6m !== selected.inputs.bill_trend_6m) changedFields.push("bill_trend_6m");
  }
  const hasEdits = changedFields.length > 0;
  // Staleness is judged against the exact payload that produced the visible score,
  // so a second edit on top of a what-if is still marked as unscored.
  const staleScore = score !== null && !scoring && draft !== null && scoredInputs !== null
    && !sameInputs(scoredInputs, draft);
  const isWhatIf = score?.is_what_if === true;
  const topReason = score?.reasons[0];
  const billAnchor = selected ? selected.behavior.bill_six_months_ago_NT : 0;
  const billMaximum = selected ? Math.max(selected.inputs.credit_limit, selected.inputs.current_bill) : 0;
  const smallSlices = model
    ? model.fairness.slices.flatMap((group) =>
      group.rows
        .filter((row) => row.accounts < SMALL_GROUP)
        .map((row) => ({ key: `${group.key}-${row.group}`, label: group.label, row })),
    )
    : [];

  // Never signal a changed row with color alone: the marker carries the meaning.
  const changedMark = (field: string) =>
    changedFields.includes(field) ? <em>Changed for this what-if</em> : null;

  const chooseAccount = (account: CreditPackagedAccount) => {
    setSelectedId(account.scenario_id);
    setDraft({ ...account.inputs });
    setScore(null);
    setPackagedScore(null);
    setScoredInputs(null);
    setScoreError(null);
    setScoring(true);
    void scoreCreditAccount(account.inputs)
      .then((result) => {
        setScore(result);
        setPackagedScore(result);
        setScoredInputs({ ...account.inputs });
      })
      .catch((reason: Error) => setScoreError(reason.message))
      .finally(() => setScoring(false));
  };

  const changeMonthsLate = (value: number) => {
    if (!draft) return;
    const monthsLate = clamp(Math.round(value), 0, 9);
    setDraft({
      ...draft,
      months_late_now: monthsLate,
      // Both rules the service enforces: the worst delay of the last six months
      // includes this month, and being behind now is itself one late month.
      worst_delay_6m: Math.max(draft.worst_delay_6m, monthsLate),
      num_late_months_6m: monthsLate >= 1 ? Math.max(1, draft.num_late_months_6m) : draft.num_late_months_6m,
    });
  };

  const changeCurrentBill = (value: number) => {
    if (!draft || !selected) return;
    const bill = clamp(Math.round(value), 0, billMaximum);
    const sameAsPackaged = bill === selected.inputs.current_bill;
    setDraft({
      ...draft,
      current_bill: bill,
      // Balance growth is (this month - six months ago) / limit. The balance six
      // months ago has not moved, so a changed bill has to move the growth too.
      bill_trend_6m: sameAsPackaged
        ? selected.inputs.bill_trend_6m
        : clamp((bill - billAnchor) / draft.credit_limit, -2, 2),
    });
  };

  const resetDraft = () => {
    if (!selected) return;
    setDraft({ ...selected.inputs });
    setScore(packagedScore);
    setScoredInputs(packagedScore ? { ...selected.inputs } : null);
    setScoreError(null);
  };

  const runScore = async () => {
    if (!draft) return;
    setScoring(true);
    setScoreError(null);
    try {
      const result = await scoreCreditAccount(draft);
      setScore(result);
      setScoredInputs({ ...draft });
      if (!result.is_what_if) setPackagedScore(result);
    } catch (reason) {
      setScoreError(reason instanceof Error ? reason.message : "The model could not score this account.");
    } finally {
      setScoring(false);
    }
  };

  return (
    <div className="page credit-page">
      <style>{pageStyles}</style>

      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=financial-services")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="credit-header">
        <div>
          <span className="eyebrow">Risk scoring - analyst review</span>
          <h1>Credit-account Review Prioritization</h1>
          <p>
            A card issuer's credit-risk team can only look at a few accounts each month. This tool ranks existing accounts
            by what a missed payment would likely cost, and shows the behavior behind every number.
          </p>
        </div>
        <div className="credit-runtime-status">
          <span className={model ? "ready" : ""} />
          <div>
            <strong>{model ? "Live model ready" : "Connecting"}</strong>
            <small>FastAPI - scikit-learn - SHAP reasons</small>
          </div>
        </div>
      </header>

      <div className="credit-boundary-line" role="note">
        <Scale size={17} aria-hidden="true" />
        <strong>Where the model's authority stops</strong>
        <span>
          A score estimates a chance and sets a queue position. It is not a decision that an account will miss a payment,
          and no account here is a defaulter. A credit analyst reviews the account and chooses what happens next.
        </span>
      </div>

      {model ? (
        <section className="credit-metric-strip" aria-label="Frozen test-set results">
          <div>
            <strong>{model.test_metrics.auc.toFixed(3)}</strong>
            <span>ranking quality (AUC)</span>
            <small>1.000 is perfect ranking, 0.500 is a coin flip</small>
          </div>
          <div>
            <strong>{percent(model.test_metrics.precision)}</strong>
            <span>flagged accounts that later missed the payment</span>
            <small>The rest were reviewed and paid anyway</small>
          </div>
          <div>
            <strong>{percent(model.test_metrics.recall)}</strong>
            <span>later missed payments the queue caught</span>
            <small>{count(model.test_metrics.confusion.FN)} were missed by this policy</small>
          </div>
          <div>
            <strong>{money(model.policy.review_cost_NT)}</strong>
            <span>assumed cost of one review</span>
            <small>Classroom assumption, not a measured bank cost</small>
          </div>
        </section>
      ) : null}

      <nav className="credit-workspace-switcher" aria-label="Credit review views">
        {workspaces.map(({ id, label, detail, icon: Icon }) => (
          <button
            type="button"
            className={workspace === id ? "active" : ""}
            aria-label={`${label}: ${detail}`}
            aria-pressed={workspace === id}
            key={id}
            onClick={() => setWorkspace(id)}
          >
            <Icon size={18} aria-hidden="true" />
            <span>
              <strong>{label}</strong>
              <small>{detail}</small>
            </span>
          </button>
        ))}
      </nav>

      {loadError ? (
        <div className="error-banner" role="alert">
          The credit service did not answer: {loadError}
        </div>
      ) : null}
      {!model && !loadError ? <div className="loading-state">Loading the model and this month's packaged accounts...</div> : null}

      {workspace === "account" && model ? (
        <section className="credit-account-workspace">
          <aside className="credit-account-browser">
            <header>
              <div>
                <span className="step">Step 1</span>
                <strong>Choose an account</strong>
                <small>Packaged held-out accounts</small>
              </div>
            </header>
            <div className="credit-account-list">
              {accounts.length === 0 ? (
                <p className="credit-list-empty">No packaged accounts came back from the service. Reload the page once the credit service is running.</p>
              ) : (
                accounts.map((account) => (
                  <button
                    type="button"
                    className={selectedId === account.scenario_id ? "active" : ""}
                    aria-pressed={selectedId === account.scenario_id}
                    key={account.scenario_id}
                    onClick={() => chooseAccount(account)}
                  >
                    <span>{account.scenario_label}</span>
                    <strong>Account {account.account_id}</strong>
                    <small>
                      {percent(account.probability)} chance of missing - {money(account.expected_loss_NT)} expected loss
                    </small>
                  </button>
                ))
              )}
            </div>
          </aside>

          <section className="credit-behavior-panel">
            <header>
              <div>
                <span className="step">Step 2</span>
                <strong>Read the last six months</strong>
                <small>Behavior first, score second</small>
              </div>
              <Wallet size={19} aria-hidden="true" />
            </header>

            {selected && behavior && draft ? (
              <>
                <div className="credit-scenario-note">
                  <Info size={16} aria-hidden="true" />
                  <p>{selected.learning_note}</p>
                </div>

                <div className="credit-balance-path">
                  <div>
                    <span>Balance six months ago</span>
                    <strong className="num">{money(behavior.bill_six_months_ago_NT)}</strong>
                    <small>Starting point of the window</small>
                  </div>
                  <ArrowRight size={18} aria-hidden="true" />
                  <div>
                    <span>Balance now</span>
                    <strong className="num">{money(behavior.current_bill_NT)}</strong>
                    <small>
                      {behavior.bill_trend_6m >= 0 ? "Grew by " : "Fell by "}
                      {percent(Math.abs(behavior.bill_trend_6m), 0)} of the credit limit
                    </small>
                  </div>
                </div>

                <div className="credit-behavior-table">
                  <table>
                    <caption>Account {selected.account_id} - six-month summary</caption>
                    <tbody>
                      <tr>
                        <th scope="row">Credit limit</th>
                        <td className="num">{money(behavior.credit_limit_NT)}</td>
                      </tr>
                      <tr className={changedFields.includes("current_bill") ? "changed" : undefined}>
                        <th scope="row">Share of the credit limit in use{changedMark("current_bill")}</th>
                        <td className="num">
                          {percent(behavior.utilization, 0)}
                          <b>{money(behavior.current_bill_NT)} owed against {money(behavior.credit_limit_NT)}</b>
                        </td>
                      </tr>
                      <tr>
                        <th scope="row">Last payment received</th>
                        <td className="num">
                          {money(behavior.last_payment_NT)}
                          <b>Recorded for the analyst; not one of the model's seven inputs</b>
                        </td>
                      </tr>
                      <tr className={changedFields.includes("months_late_now") ? "changed" : undefined}>
                        <th scope="row">Months behind on payments right now{changedMark("months_late_now")}</th>
                        <td className="num">{monthWord(behavior.months_late_now)}</td>
                      </tr>
                      <tr className={changedFields.includes("worst_delay_6m") ? "changed" : undefined}>
                        <th scope="row">Worst delay in the last six months{changedMark("worst_delay_6m")}</th>
                        <td className="num">{monthWord(behavior.worst_delay_6m)}</td>
                      </tr>
                      <tr className={changedFields.includes("num_late_months_6m") ? "changed" : undefined}>
                        <th scope="row">Months paid late, out of the last six{changedMark("num_late_months_6m")}</th>
                        <td className="num">{behavior.num_late_months_6m.toFixed(0)} of 6</td>
                      </tr>
                      <tr>
                        <th scope="row">Share of billed amounts actually paid</th>
                        <td className="num">
                          {percent(behavior.payment_ratio_6m, 0)}
                          <b>Across all six statements</b>
                        </td>
                      </tr>
                      <tr className={changedFields.includes("bill_trend_6m") ? "changed" : undefined}>
                        <th scope="row">Balance growth over six months{changedMark("bill_trend_6m")}</th>
                        <td className="num">
                          {behavior.bill_trend_6m >= 0 ? "+" : ""}
                          {percent(behavior.bill_trend_6m, 0)}
                          <b>Measured against the credit limit</b>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="credit-derivation-note">{behavior.derivation_note}</p>

                <div className="credit-whatif">
                  <span>Step 3 - optional</span>
                  <strong>Try a what-if</strong>
                  <div className="credit-whatif-controls">
                    <label htmlFor="credit-months-late">
                      <span>
                        Months behind on payments right now
                        <output id="credit-months-late-value">{monthWord(draft.months_late_now)}</output>
                      </span>
                      <input
                        id="credit-months-late"
                        type="range"
                        min="0"
                        max="9"
                        step="1"
                        value={draft.months_late_now}
                        aria-describedby="credit-months-late-help"
                        onChange={(event) => changeMonthsLate(Number(event.target.value))}
                      />
                      <small id="credit-months-late-help">
                        0 to 9 months. Raising this also raises the worst delay in the last six months, because that worst
                        delay includes this month.
                      </small>
                    </label>
                    <label htmlFor="credit-current-bill">
                      <span>
                        Balance owed now (NT$)
                        <output id="credit-current-bill-value">{money(draft.current_bill)}</output>
                      </span>
                      <input
                        id="credit-current-bill"
                        type="range"
                        min="0"
                        max={billMaximum}
                        step="1000"
                        value={draft.current_bill}
                        aria-describedby="credit-current-bill-help"
                        onChange={(event) => changeCurrentBill(Number(event.target.value))}
                      />
                      <small id="credit-current-bill-help">
                        Moves the share of the limit in use, the six-month balance growth, and the money at risk. The
                        balance six months ago stays where it was.
                      </small>
                    </label>
                  </div>
                  <div className="credit-whatif-actions">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => void runScore()}
                      disabled={scoring}
                    >
                      <Play size={15} fill="currentColor" aria-hidden="true" />
                      {scoring ? "Scoring..." : hasEdits ? "Score this what-if" : "Score this account again"}
                    </button>
                    <button className="secondary-button" type="button" onClick={resetDraft} disabled={!hasEdits || scoring}>
                      <RefreshCcw size={15} aria-hidden="true" /> Back to the real account
                    </button>
                  </div>
                  {staleScore ? (
                    <p className="credit-whatif-pending">
                      <AlertTriangle size={15} aria-hidden="true" />
                      You changed an input. The panel on the right still shows the previous result, so choose
                      {hasEdits ? " “Score this what-if”" : " “Score this account again”"} to update it.
                    </p>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="credit-list-empty">Choose an account on the left to see its six-month behavior.</p>
            )}
          </section>

          <section className="credit-result-panel" aria-live="polite" aria-busy={scoring}>
            <header>
              <div>
                <span className="step">Step 4</span>
                <strong>Score, policy, and reasons</strong>
                <small>An estimate, then a rule, then a person</small>
              </div>
              <BrainCircuit size={19} aria-hidden="true" />
            </header>

            {scoreError ? (
              <div className="credit-result-body">
                <div className="error-banner" role="alert">
                  {scoreError}
                </div>
                <div className="credit-inline-actions">
                  <button className="secondary-button" type="button" onClick={() => void runScore()}>
                    <RefreshCcw size={15} aria-hidden="true" /> Try again
                  </button>
                </div>
              </div>
            ) : score ? (
              <div className="credit-result-body">
                <div className={`credit-score-summary ${score.route}`}>
                  <div>
                    <span>What the policy does with this account</span>
                    <strong>{score.route_label}</strong>
                    <small>{score.route_action}</small>
                  </div>
                  <div className="credit-score-value">
                    <span>Chance of missing the next payment</span>
                    <strong className="num">{percent(score.probability)}</strong>
                    <small>Model version {buildDate(score.model_version)}</small>
                  </div>
                </div>

                <div className="credit-math-chain">
                  <div>
                    <span>Chance of missing the next payment</span>
                    <strong>{percent(score.probability)}</strong>
                  </div>
                  <div>
                    <span>Money at risk on this account</span>
                    <strong>{money(score.exposure_NT)}</strong>
                  </div>
                  <div>
                    <span>Share of that money lost if it happens</span>
                    <strong>{percent(score.loss_given_default, 0)}</strong>
                  </div>
                </div>

                <div className="credit-math-result">
                  <div>
                    <span>Multiply the three: expected loss</span>
                    <strong>{money(score.expected_loss_NT)}</strong>
                  </div>
                  <ArrowRight size={18} aria-hidden="true" />
                  <div>
                    <span>Compared with one review at</span>
                    <strong>{money(score.review_cost_NT)}</strong>
                  </div>
                </div>

                <div className={`credit-route-line ${score.route}`}>
                  {score.route === "priority_review" ? (
                    <ShieldAlert size={18} aria-hidden="true" />
                  ) : (
                    <CheckCircle2 size={18} aria-hidden="true" />
                  )}
                  <div>
                    <strong>
                      {score.expected_loss_NT > score.review_cost_NT
                        ? "Expected loss is larger than one review, so this account is flagged"
                        : "Expected loss is smaller than one review, so this account is not flagged"}
                    </strong>
                    <p>{score.route_label}. {score.score_note}</p>
                  </div>
                </div>

                {isWhatIf ? (
                  <div className="credit-outcome-band what-if">
                    <AlertTriangle size={18} aria-hidden="true" />
                    <div>
                      <span>What-if scenario</span>
                      <strong>No known outcome for this version of the account</strong>
                      <p>{score.outcome_note}</p>
                      {score.changed_inputs.length > 0 ? (
                        <div className="credit-changed-chips">
                          {score.changed_inputs.map((item) => (
                            <span key={item}>Changed: {item}</span>
                          ))}
                        </div>
                      ) : null}
                      {packagedScore ? (
                        <div className="credit-whatif-shift">
                          <div>
                            <span>Real account</span>
                            <strong>{percent(packagedScore.probability)} - {money(packagedScore.expected_loss_NT)}</strong>
                          </div>
                          <ArrowRight size={16} aria-hidden="true" />
                          <div>
                            <span>Your what-if</span>
                            <strong>{percent(score.probability)} - {money(score.expected_loss_NT)}</strong>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : score.actual_outcome ? (
                  <div
                    className={`credit-outcome-band ${score.actual_outcome === "Later missed the payment" ? "missed" : "paid"}`}
                  >
                    {score.actual_outcome === "Later missed the payment" ? (
                      <AlertTriangle size={18} aria-hidden="true" />
                    ) : (
                      <CheckCircle2 size={18} aria-hidden="true" />
                    )}
                    <div>
                      <span>What happened next, in the historical record</span>
                      <strong>{score.actual_outcome}</strong>
                      <p>
                        {score.outcome_note} An outcome is visible here only because this is held-out historical data; a
                        live queue would not know it yet.
                      </p>
                    </div>
                  </div>
                ) : null}

                <section className="credit-reasons" aria-label="Reason codes for this score">
                  <header>
                    <span>Top reasons - {model.reason_code_mechanism}</span>
                    <strong>Why this account scored the way it did</strong>
                  </header>
                  {score.reasons.length === 0 ? (
                    <p className="credit-table-empty">
                      Nothing about this account pushed its risk above the model's starting point, so there are no
                      risk-raising reasons to list.
                    </p>
                  ) : (
                    score.reasons.map((reason, index) => (
                      <div className="credit-reason-row" key={reason.feature}>
                        <div>
                          <strong>{reason.display_name}</strong>
                          <b>{index === 0 ? "Strongest" : index === 1 ? "Second" : "Third"}</b>
                        </div>
                        <p>This account {reason.text}.</p>
                        <div className="credit-reason-track" aria-hidden="true">
                          <i
                            style={{
                              width: `${Math.max(6, (reason.contribution / Math.max(topReason?.contribution ?? 1, 0.0001)) * 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))
                  )}
                  <footer>
                    Bars compare the three reasons with each other, strongest first. They describe this model's
                    arithmetic on these inputs, not the customer's intent or circumstances.
                  </footer>
                </section>

                <div className="credit-authority">
                  <UserCheck size={18} aria-hidden="true" />
                  <div>
                    <span>Human authority</span>
                    <p>{model.policy.boundary}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="credit-result-empty">
                <BrainCircuit size={30} aria-hidden="true" />
                <strong>{scoring ? "Scoring..." : "No score yet"}</strong>
                <p>Choose an account, or run the model again after moving one of the what-if controls.</p>
              </div>
            )}
          </section>
        </section>
      ) : null}

      {workspace === "queue" && model ? (
        <section className="credit-queue-workspace">
          <header className="credit-section-heading">
            <div>
              <span>Operating view</span>
              <h2>This month's review queue</h2>
              <p>{queue ? queue.summary.rule : "Accounts are ranked by expected loss: the chance of a missed payment, times the money at risk, times the share that would be lost."}</p>
            </div>
            {queue ? (
              <strong>
                <ClipboardList size={14} aria-hidden="true" /> {count(queue.summary.flagged_accounts)} of{" "}
                {count(queue.summary.packaged_accounts)} accounts flagged
              </strong>
            ) : null}
          </header>

          <div className="credit-assumption-note">
            <Info size={16} aria-hidden="true" />
            <p>
              <strong>Classroom assumption.</strong>{" "}
              {queue ? queue.summary.assumption_note : model.policy.parameter_note} Every amount on this page is in NT$
              (New Taiwan dollars).
            </p>
          </div>

          {queueError ? (
            <div className="error-banner" role="alert">
              The queue did not update: {queueError}
              <div className="credit-inline-actions">
                <button className="secondary-button" type="button" onClick={() => setQueueAttempt((value) => value + 1)}>
                  <RefreshCcw size={15} aria-hidden="true" /> Try again
                </button>
              </div>
            </div>
          ) : null}

          {queue && reviewCost !== null ? (
            <>
              <div className="credit-cost-control">
                <div>
                  <label htmlFor="credit-review-cost">
                    <span>
                      Cost of reviewing one account
                      <output id="credit-review-cost-value">{money(reviewCost)}</output>
                    </span>
                    <input
                      id="credit-review-cost"
                      type="range"
                      min={queue.policy_sweep[0]?.review_cost_NT ?? 1000}
                      max={queue.policy_sweep[queue.policy_sweep.length - 1]?.review_cost_NT ?? 20000}
                      step="500"
                      value={reviewCost}
                      aria-describedby="credit-review-cost-help"
                      onChange={(event) => setReviewCost(Number(event.target.value))}
                    />
                  </label>
                  <div className="credit-cost-scale">
                    <span>Cheaper reviews, longer queue</span>
                    <span>Costlier reviews, shorter queue</span>
                  </div>
                  <p className="credit-cost-status" role="status">
                    {queueBusy ? "Recalculating the queue..." : `Queue calculated at ${money(queue.summary.review_cost_NT)} per review`}
                  </p>
                </div>
                <div>
                  <p className="credit-cost-help" id="credit-review-cost-help">
                    An account joins the queue when its expected loss is worth more than one review. Make reviews cheaper
                    and more accounts clear that bar, so the queue grows past what the team can work. The frozen policy
                    the model card reports uses {money(queue.summary.frozen_review_cost_NT)}.
                  </p>
                  <p className="credit-cost-help">
                    Nothing here changes the model. The control changes only the money rule applied to the model's
                    scores.
                  </p>
                </div>
              </div>

              <div className="credit-queue-summary" aria-live="polite">
                <div>
                  <strong className="num">{count(queue.summary.flagged_accounts)}</strong>
                  <span>accounts flagged for review</span>
                  <small>Out of {count(queue.summary.packaged_accounts)} packaged accounts</small>
                </div>
                <div>
                  <strong className="num">{money(queue.summary.total_expected_loss_NT)}</strong>
                  <span>total expected loss in the queue</span>
                  <small>Added up across every flagged account</small>
                </div>
                <div>
                  <strong className="num">{count(queue.summary.review_capacity)}</strong>
                  <span>accounts the team can review</span>
                  <small>Capacity assumed for one month</small>
                </div>
                <div>
                  <strong className="num">{count(queue.summary.accounts_over_capacity)}</strong>
                  <span>flagged accounts nobody can reach</span>
                  <small>Beyond this month's capacity</small>
                </div>
              </div>

              <div className="credit-capacity-line">
                <Users size={17} aria-hidden="true" />
                <div>
                  <strong>
                    Capacity: {count(queue.summary.review_capacity)} accounts a month.{" "}
                    {count(queue.summary.flagged_accounts)} flagged at {money(queue.summary.review_cost_NT)} per review,
                    so {count(queue.summary.accounts_over_capacity)} sit beyond what the team can reach.
                  </strong>
                  <p>{queue.summary.capacity_note}</p>
                </div>
              </div>

              <div className="credit-note-row">
                <Info size={16} aria-hidden="true" />
                <p>
                  {queue.summary.selection_note} Outcomes are shown because these are historical held-out accounts; a
                  live queue would not know them yet.
                </p>
              </div>

              <div className="credit-table-wrap">
                <table className="credit-table">
                  <caption>Flagged accounts, highest expected loss first (top {count(queue.items.length)} shown)</caption>
                  <thead>
                    <tr>
                      <th scope="col">Rank</th>
                      <th scope="col">Account</th>
                      <th scope="col">Chance of missing</th>
                      <th scope="col">Money at risk</th>
                      <th scope="col">Expected loss</th>
                      <th scope="col">Behavior now</th>
                      <th scope="col">This month's capacity</th>
                      <th scope="col">What happened next</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queue.items.length === 0 ? (
                      <tr>
                        <td colSpan={8}>
                          <p className="credit-table-empty">
                            No packaged account has an expected loss above {money(queue.summary.review_cost_NT)}, so
                            nobody is flagged at this review cost. Lower the cost to fill the queue.
                          </p>
                        </td>
                      </tr>
                    ) : (
                      queue.items.map((item) => (
                        <tr key={item.account_id}>
                          <th scope="row" className="num">
                            {item.rank}
                          </th>
                          <td className="num">{item.account_id}</td>
                          <td className="num">{percent(item.probability)}</td>
                          <td className="num">{money(item.exposure_NT)}</td>
                          <td className="num">{money(item.expected_loss_NT)}</td>
                          <td>
                            {monthWord(item.months_late_now)} behind
                            <span>{percent(item.utilization, 0)} of the credit limit in use</span>
                          </td>
                          <td>
                            <span className={`credit-tag ${item.within_capacity ? "within" : "beyond"}`}>
                              {item.within_capacity ? (
                                <CheckCircle2 size={13} aria-hidden="true" />
                              ) : (
                                <AlertTriangle size={13} aria-hidden="true" />
                              )}
                              {item.within_capacity ? "Within capacity" : "Beyond capacity"}
                            </span>
                          </td>
                          <td>
                            <span
                              className={`credit-tag ${item.actual_outcome === "Later missed the payment" ? "missed" : "paid"}`}
                            >
                              {item.actual_outcome === "Later missed the payment" ? (
                                <AlertTriangle size={13} aria-hidden="true" />
                              ) : (
                                <CheckCircle2 size={13} aria-hidden="true" />
                              )}
                              {item.actual_outcome}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <header className="credit-section-heading">
                <div>
                  <span>Frozen record</span>
                  <h3>The same policy on the whole test set</h3>
                  <p>{queue.population.note}</p>
                </div>
              </header>

              <div className="credit-frozen-strip">
                <div>
                  <strong className="num">{count(queue.population.accounts)}</strong>
                  <span>accounts in the test set</span>
                  <small>Scored once, after the policy was frozen</small>
                </div>
                <div>
                  <strong className="num">{count(queue.population.flagged)}</strong>
                  <span>flagged for review</span>
                  <small>{percent(queue.population.flagged_share)} of the test set</small>
                </div>
                <div>
                  <strong className="num">{percent(queue.population.precision)}</strong>
                  <span>flagged accounts that later missed the payment</span>
                  <small>The rest paid anyway</small>
                </div>
                <div>
                  <strong className="num">{money(queue.population.net_savings_NT)}</strong>
                  <span>net saving against reviewing nobody</span>
                  <small>Using the classroom cost assumptions</small>
                </div>
              </div>

              <div className="credit-table-wrap">
                <table className="credit-table">
                  <caption>
                    How each review cost compared on the validation split, the data used to choose this policy. The test
                    split above was scored once, afterwards. This is a frozen record and does not move with the control.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Cost of one review</th>
                      <th scope="col">Accounts flagged</th>
                      <th scope="col">Share of the test set</th>
                      <th scope="col">Flagged that later missed</th>
                      <th scope="col">Missed payments caught</th>
                      <th scope="col">Net saving</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queue.policy_sweep.map((row) => (
                      <tr
                        key={row.review_cost_NT}
                        className={row.review_cost_NT === queue.summary.frozen_review_cost_NT ? "credit-row-current" : undefined}
                      >
                        <th scope="row" className="num">
                          {money(row.review_cost_NT)}
                          {row.review_cost_NT === queue.summary.frozen_review_cost_NT ? <span>The policy in use</span> : null}
                        </th>
                        <td className="num">{count(row.flagged)}</td>
                        <td className="num">{percent(row.flagged_share)}</td>
                        <td className="num">{percent(row.precision)}</td>
                        <td className="num">{percent(row.recall)}</td>
                        <td className="num">{money(row.net_savings_NT)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : !queueError ? (
            <div className="loading-state">Building this month's queue...</div>
          ) : null}
        </section>
      ) : null}

      {workspace === "governance" && model ? (
        <section className="credit-governance-workspace">
          <header className="credit-section-heading">
            <div>
              <span>Deployment record</span>
              <h2>{model.model_name}</h2>
              <p>{model.intended_use}</p>
            </div>
            <strong>
              <Database size={14} aria-hidden="true" /> Built {buildDate(model.model_version)}
            </strong>
          </header>

          <div className="credit-governance-grid">
            <div>
              <BrainCircuit size={18} aria-hidden="true" />
              <span>How it was trained</span>
              <strong>{model.framework}</strong>
              <small>{model.estimator}</small>
            </div>
            <div>
              <Layers3 size={18} aria-hidden="true" />
              <span>How it is packaged</span>
              <strong>Saved pipeline</strong>
              <small>{model.packaging}</small>
            </div>
            <div>
              <Database size={18} aria-hidden="true" />
              <span>What it learned from</span>
              <strong>{model.dataset.name}</strong>
              <small>{model.dataset.population}</small>
            </div>
            <div>
              <Scale size={18} aria-hidden="true" />
              <span>What a score means</span>
              <strong>An estimate, not a determination</strong>
              <small>{model.score_note}</small>
            </div>
          </div>

          <section className="credit-panel">
            <header>
              <span>Model inputs</span>
              <h3>Seven pieces of account behavior, and nothing else</h3>
              <p>{model.reason_code_mechanism} produces the plain-language reasons on the account tab from these same inputs.</p>
            </header>
            <div className="credit-definition-grid">
              {model.features.map((feature) => (
                <div key={feature.name}>
                  <dt>{feature.name}</dt>
                  <dd>{feature.display_name}</dd>
                </div>
              ))}
            </div>
          </section>

          <section className="credit-panel">
            <header>
              <span>The operating policy, in plain words</span>
              <h3>{model.policy.name}</h3>
            </header>
            <p className="credit-plain-rule">{model.policy.plain_rule}</p>
            <div className="credit-definition-grid">
              <div>
                <dt>The rule as written</dt>
                <dd>{model.policy.rule}</dd>
              </div>
              <div>
                <dt>Money settings</dt>
                <dd>
                  One review costs <b>{money(model.policy.review_cost_NT)}</b>. If a payment is missed,{" "}
                  <b>{percent(model.policy.loss_given_default, 0)}</b> of the balance at risk is assumed lost. Currency:{" "}
                  {model.policy.currency}.
                </dd>
              </div>
              <div>
                <dt>Money at risk</dt>
                <dd>{model.policy.exposure}</dd>
              </div>
              <div>
                <dt>How the cutoff was chosen</dt>
                <dd>{model.policy.selected_on}</dd>
              </div>
              <div>
                <dt>If the account is flagged</dt>
                <dd>{model.policy.route_priority_review}</dd>
              </div>
              <div>
                <dt>If the account is not flagged</dt>
                <dd>{model.policy.route_standard_monitoring}</dd>
              </div>
              <div>
                <dt>When the data is not usable</dt>
                <dd>{model.policy.fallback}</dd>
              </div>
              <div>
                <dt>Where the model's authority stops</dt>
                <dd>{model.policy.boundary}</dd>
              </div>
            </div>
            <p className="credit-derivation-note">{model.policy.parameter_note}</p>
          </section>

          <section className="credit-panel">
            <header>
              <span>Measured once on the untouched test set</span>
              <h3>What this model did on data it never saw</h3>
              <p>
                The test split was scored a single time, after the policy was frozen on the validation split. These
                numbers do not move when anyone adjusts the review-cost control.
              </p>
            </header>
            <div className="credit-frozen-strip">
              <div>
                <strong className="num">{model.test_metrics.auc.toFixed(3)}</strong>
                <span>ranking quality (AUC)</span>
                <small>How well higher scores line up with later missed payments</small>
              </div>
              <div>
                <strong className="num">{model.test_metrics.pr_auc.toFixed(3)}</strong>
                <span>precision-recall area</span>
                <small>Fairer view when missed payments are the smaller group</small>
              </div>
              <div>
                <strong className="num">{model.test_metrics.brier.toFixed(4)}</strong>
                <span>Brier score</span>
                <small>How close the probabilities land; lower is better</small>
              </div>
              <div>
                <strong className="num">{percent(model.test_metrics.flagged_share)}</strong>
                <span>of the test set flagged</span>
                <small>{count(model.test_metrics.flagged)} accounts sent to analysts</small>
              </div>
            </div>
            <div className="credit-table-wrap">
              <table className="credit-table">
                <caption>
                  Every metric above comes from this table: {count(model.dataset.split_counts.test?.n ?? 0)} test accounts,
                  split by what the policy did and what happened next.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">What happened next</th>
                    <th scope="col">Flagged for review</th>
                    <th scope="col">Not flagged</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Later missed the payment</th>
                    <td className="num">
                      {count(model.test_metrics.confusion.TP)}
                      <span>Caught in time for a review</span>
                    </td>
                    <td className="num">
                      {count(model.test_metrics.confusion.FN)}
                      <span>Nobody looked, and the payment was missed</span>
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Later paid</th>
                    <td className="num">
                      {count(model.test_metrics.confusion.FP)}
                      <span>A review spent on an account that paid anyway</span>
                    </td>
                    <td className="num">
                      {count(model.test_metrics.confusion.TN)}
                      <span>Left in ordinary monitoring, correctly</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="credit-definition-grid">
              <div>
                <dt>This policy</dt>
                <dd>
                  <b>{money(model.test_metrics.net_savings_NT)}</b> better than reviewing nobody, using the classroom cost
                  assumptions.
                </dd>
              </div>
              <div>
                <dt>Reviewing every account instead</dt>
                <dd>
                  <b>{money(model.test_metrics.review_everybody_NT)}</b>, because most accounts pay and the review is
                  spent anyway.
                </dd>
              </div>
            </div>
          </section>

          <section className="credit-panel">
            <header>
              <span>Fairness check</span>
              <h3>Leaving protected attributes out, then checking anyway</h3>
              <p>{model.fairness.exclusion_reason}</p>
            </header>
            <div className="credit-definition-grid">
              <div>
                <dt>Kept out of the model</dt>
                <dd>{model.fairness.excluded_columns.join(", ")}. Exported only as audit columns.</dd>
              </div>
              <div>
                <dt>Why exclusion is not the whole answer</dt>
                <dd>{model.fairness.note}</dd>
              </div>
            </div>
            <div className="credit-comparison">
              <div>
                <span>Ranking quality without those attributes (the model in use)</span>
                <strong className="num">{model.fairness.auc_without_protected.toFixed(4)}</strong>
              </div>
              <ArrowRight size={18} aria-hidden="true" />
              <div>
                <span>Ranking quality if they were added back</span>
                <strong className="num">{model.fairness.auc_with_protected.toFixed(4)}</strong>
              </div>
              <p>{model.fairness.delta_note}</p>
            </div>

            {smallSlices.map((entry) => (
              <div className="credit-small-group-caution" role="note" key={entry.key}>
                <AlertTriangle size={17} aria-hidden="true" />
                <p>
                  <strong>Small group.</strong> {entry.label} “{entry.row.group}” holds only {count(entry.row.accounts)}{" "}
                  accounts. A group that small cannot support a strong claim in either direction, so read that row as a
                  prompt to look closer, not as evidence.
                </p>
              </div>
            ))}

            {model.fairness.slices.map((group) => (
              <div className="credit-table-wrap" key={group.key}>
                <table className="credit-table">
                  <caption>
                    {group.label}: how scores and outcomes landed across groups the model never saw.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{group.label}</th>
                      <th scope="col">Accounts</th>
                      <th scope="col">Average score</th>
                      <th scope="col">Share flagged</th>
                      <th scope="col">Share that later missed the payment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.rows.map((row) => (
                      <tr key={row.group}>
                        <th scope="row">
                          {row.group}
                          {row.accounts < SMALL_GROUP ? (
                            <span className="credit-tag small-group">
                              <AlertTriangle size={13} aria-hidden="true" /> Small group
                            </span>
                          ) : null}
                        </th>
                        <td className="num">{count(row.accounts)}</td>
                        <td className="num">{percent(row.mean_score)}</td>
                        <td className="num">{percent(row.flagged_share)}</td>
                        <td className="num">{percent(row.actual_default_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

            <div className="credit-module-preview">
              <Users size={17} aria-hidden="true" />
              <p>
                <strong>Module 10 preview.</strong> {model.fairness.module_10_preview}
              </p>
            </div>
          </section>

          <section className="credit-panel">
            <header>
              <span>Limits and boundaries</span>
              <h3>What this model cannot be used for</h3>
            </header>
            <div className="credit-list-columns">
              <section>
                <span>Known limitations</span>
                <ul>
                  {model.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
              <section>
                <span>Excluded uses</span>
                <ul>
                  {model.excluded_uses.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            </div>
          </section>

          <section className="credit-panel">
            <header>
              <span>Data source</span>
              <h3>{model.dataset.name}</h3>
              <p>{model.dataset.citation}</p>
            </header>
            <div className="credit-definition-grid">
              <div>
                <dt>License</dt>
                <dd>{model.dataset.license}</dd>
              </div>
              <div>
                <dt>Where it came from</dt>
                <dd>
                  <a className="credit-source-link" href={model.dataset.url} target="_blank" rel="noreferrer">
                    {model.dataset.url}
                  </a>
                </dd>
              </div>
              {Object.entries(model.dataset.split_counts).map(([split, values]) => (
                <div key={split}>
                  <dt>{split} split</dt>
                  <dd>
                    <b>{count(values.n)}</b> accounts, {percent(values.default_rate)} of them later missed the payment.
                  </dd>
                </div>
              ))}
              <div>
                <dt>Software used</dt>
                <dd>
                  {Object.entries(model.environment)
                    .map(([name, version]) => `${name} ${version}`)
                    .join(", ")}
                </dd>
              </div>
            </div>
            <div className="credit-authority">
              <TrendingUp size={18} aria-hidden="true" />
              <div>
                <span>Read this before quoting any number</span>
                <p>
                  Every result on this page comes from one Taiwanese card issuer's accounts in 2005, with synthetic cost
                  assumptions on top. It demonstrates a workflow; it does not measure any bank operating today.
                </p>
              </div>
            </div>
          </section>
        </section>
      ) : null}
    </div>
  );
}
