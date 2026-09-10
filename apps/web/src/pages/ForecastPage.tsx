import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Boxes,
  CheckCircle2,
  ClipboardList,
  Database,
  Info,
  LineChart,
  PackageSearch,
  RefreshCcw,
  Scale,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import {
  getForecastModel,
  getForecastPolicySweep,
  getForecastProducts,
  planForecast,
  type ForecastModelInfo,
  type ForecastPlan,
  type ForecastPolicySweep,
  type ForecastProductSummary,
  type ForecastTableRow,
} from "../forecastApi";
import { navigate } from "../router";

/* Page styles live here, not in index.css, because this component had to ship as a
   single file. Every rule is prefixed .fc-, so the block can be moved into
   index.css verbatim and this <style> element deleted, with no other change. */
const pageStyles = `
.fc-page { width: min(1560px, 100%); --fc-body: 13px; --fc-support: 12px; --fc-label: 10px; --fc-band: #8f97f5; --fc-order: #52c08f; --fc-miss: var(--red); }
.fc-page .page-back-button { min-height: 44px; font-size: 11px; }
.fc-page table { width: 100%; border-collapse: collapse; }
.fc-page .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }

.fc-header { min-height: 82px; margin-bottom: 14px; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.fc-header h1 { margin: 3px 0 6px; font-size: 29px; line-height: 1.2; }
.fc-header p { max-width: 920px; margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.55; }
.fc-runtime-status { min-width: 262px; padding: 11px 13px; display: flex; align-items: center; gap: 10px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.fc-runtime-status > span { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--amber); box-shadow: 0 0 0 4px rgba(240, 180, 41, 0.1); }
.fc-runtime-status > span.ready { background: var(--green); box-shadow: 0 0 0 4px rgba(74, 222, 128, 0.1); }
.fc-runtime-status strong, .fc-runtime-status small { display: block; }
.fc-runtime-status strong { font-size: var(--fc-body); }
.fc-runtime-status small { margin-top: 3px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--fc-label); line-height: 1.4; }

.fc-boundary-line { min-height: 49px; margin-bottom: 14px; padding: 10px 14px; display: grid; grid-template-columns: 20px auto minmax(0, 1fr); align-items: center; gap: 10px; border-top: 1px solid rgba(126, 174, 184, 0.45); border-bottom: 1px solid rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.06); color: var(--teal); }
.fc-boundary-line strong { font-size: var(--fc-support); }
.fc-boundary-line span { color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.45; }

.fc-metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: 15px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.fc-metric-strip > div { min-width: 0; min-height: 88px; padding: 13px 17px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.fc-metric-strip > div:last-child { border-right: 0; }
.fc-metric-strip strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 21px; }
.fc-metric-strip span { margin-top: 3px; color: var(--text-secondary); font-size: var(--fc-support); }
.fc-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: var(--fc-label); line-height: 1.4; }

.fc-view-switcher { min-height: 66px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.fc-view-switcher button { min-width: 0; min-height: 64px; padding: 10px 15px; display: flex; align-items: center; gap: 10px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.fc-view-switcher button:last-child { border-right: 0; }
.fc-view-switcher button:hover, .fc-view-switcher button.active { background: var(--surface-raised); color: var(--orange); }
.fc-view-switcher button.active { box-shadow: inset 0 -3px 0 var(--orange); }
.fc-view-switcher button:focus-visible { outline-offset: -3px; }
.fc-view-switcher strong, .fc-view-switcher small { display: block; }
.fc-view-switcher strong { color: var(--text); font-size: 14px; }
.fc-view-switcher small { margin-top: 3px; font-size: 11px; }

.fc-workspace { display: grid; grid-template-columns: minmax(250px, 0.36fr) minmax(420px, 1.15fr) minmax(340px, 0.76fr); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.fc-workspace > * { min-width: 0; }
.fc-product-browser, .fc-plot-panel { border-right: 1px solid var(--border); }
.fc-workspace > section > header, .fc-product-browser > header { min-height: 74px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); }
.fc-workspace header span.step { color: var(--orange); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-workspace header strong { display: block; margin-top: 3px; font-size: var(--fc-body); }
.fc-workspace header small { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--fc-label); line-height: 1.4; }

/* The list scrolls inside a fixed height. Its parent is a column flex container,
   so every child is pinned with flex: 0 0 auto - a shrinkable child in here
   silently loses height and clips the last product off the bottom. */
.fc-product-browser { display: flex; flex-direction: column; }
.fc-product-browser > * { flex: 0 0 auto; }
.fc-product-list { max-height: 720px; overflow-y: auto; }
.fc-product-list button { width: 100%; min-height: 96px; padding: 11px 13px; display: block; border: 0; border-bottom: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.fc-product-list button:hover, .fc-product-list button.active { background: var(--surface-raised); box-shadow: inset 3px 0 0 var(--orange); }
.fc-product-list button:focus-visible { outline-offset: -3px; }
.fc-product-list button > span, .fc-product-list button > strong, .fc-product-list button > small { display: block; }
.fc-product-list button > span.tag { color: var(--teal); font-size: var(--fc-label); line-height: 1.4; }
.fc-product-list button > span.tag.loses { color: var(--red); }
.fc-product-list button > strong { margin-top: 4px; color: var(--text); font-size: var(--fc-support); line-height: 1.4; }
.fc-product-list button > small { margin-top: 5px; color: var(--text-muted); font-size: var(--fc-label); line-height: 1.5; }
.fc-product-list button > span.stat { margin-top: 6px; color: var(--text-secondary); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--fc-label); }
.fc-list-empty { padding: 26px 14px; color: var(--text-muted); font-size: var(--fc-support); line-height: 1.6; }

.fc-plot-panel, .fc-order-panel { display: flex; flex-direction: column; }
.fc-plot-panel > *, .fc-order-panel > * { flex: 0 0 auto; }
.fc-purpose-note { padding: 11px 14px; display: flex; gap: 9px; border-bottom: 1px solid var(--border); background: rgba(126, 174, 184, 0.05); color: var(--teal); }
.fc-purpose-note p { margin: 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-chart-scroll { padding: 12px 14px 0; overflow-x: auto; }
.fc-chart svg { display: block; width: 100%; min-width: 580px; height: 330px; }
.fc-chart .axis { stroke: var(--border); stroke-width: 1; }
.fc-chart .grid { stroke: var(--border); stroke-width: 1; stroke-dasharray: 2 4; }
.fc-chart .tick { fill: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.fc-chart .band-fill { fill: rgba(143, 151, 245, 0.22); }
.fc-chart .band-hatch { fill: url(#fc-band-hatch); }
.fc-chart .band-edge { fill: none; stroke: var(--fc-band); stroke-width: 1.3; stroke-dasharray: 4 3; }
.fc-chart .actual { fill: none; stroke: var(--text); stroke-width: 2.1; stroke-linejoin: round; }
.fc-chart .actual-dot { fill: var(--text); }
.fc-chart .point-line { fill: none; stroke: var(--teal); stroke-width: 1.9; stroke-dasharray: 7 4; }
.fc-chart .order-line { fill: none; stroke: var(--fc-order); stroke-width: 2.4; stroke-linejoin: round; }
.fc-chart .miss-mark { fill: var(--fc-miss); }
.fc-chart .split-line { stroke: var(--border-strong); stroke-width: 1.2; }
.fc-chart .split-label { fill: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.fc-chart .band-label { fill: var(--fc-band); font-family: var(--font-mono); font-size: 10px; }
.fc-chart-legend { margin: 8px 0 0; padding: 0 14px 12px; display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--text-muted); font-size: var(--fc-label); }
.fc-chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.fc-chart-legend i { display: inline-block; width: 16px; height: 0; flex: 0 0 auto; border-top: 2px solid var(--text); }
.fc-chart-legend i.point { border-top: 2px dashed var(--teal); }
.fc-chart-legend i.order { border-top: 3px solid var(--fc-order); }
.fc-chart-legend i.band { height: 11px; border: 1px dashed var(--fc-band); background: rgba(143, 151, 245, 0.22); }
.fc-chart-legend i.miss { width: 0; height: 0; border: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 9px solid var(--fc-miss); }

.fc-ratio-control { padding: 13px 14px; border-top: 1px solid var(--border); background: #14161c; }
.fc-ratio-control > span { color: var(--orange); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-ratio-control > strong { display: block; margin-top: 4px; font-size: var(--fc-body); }
.fc-ratio-control label { display: block; margin-top: 10px; }
.fc-ratio-control label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--fc-support); }
.fc-ratio-control output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.fc-page input[type="range"] { width: 100%; height: 44px; padding: 0; border: 0; background: transparent; box-shadow: none; accent-color: var(--orange); }
.fc-scale-row { display: flex; justify-content: space-between; gap: 12px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--fc-label); }
.fc-control-status { min-height: 17px; margin: 8px 0 0; color: var(--teal); font-family: var(--font-mono); font-size: var(--fc-label); }
.fc-control-actions { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
.fc-control-actions .secondary-button { min-height: 44px; }
.fc-ratio-preset { min-height: 44px; padding: 0 12px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); color: var(--text-secondary); font-size: var(--fc-support); }
.fc-ratio-preset:hover { border-color: var(--teal); color: var(--text); }
.fc-ratio-preset[aria-pressed="true"] { border-color: var(--orange); color: var(--orange); }

.fc-order-panel { padding-bottom: 14px; }
.fc-order-body { padding: 14px; display: grid; gap: 10px; }
.fc-order-card { padding: 12px 13px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.fc-order-card.chosen { border-color: rgba(82, 192, 143, 0.55); }
.fc-order-card > span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-order-card > strong { display: block; margin-top: 5px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 26px; }
.fc-order-card > b { display: block; margin-top: 3px; color: var(--text); font-size: var(--fc-support); font-weight: 600; line-height: 1.4; }
.fc-order-card > p { margin: 6px 0 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.5; }
.fc-order-facts { margin-top: 10px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--border); border-radius: 5px; background: var(--border); overflow: hidden; }
.fc-order-facts > span { min-width: 0; padding: 9px 10px; display: block; background: var(--surface); color: var(--text-muted); font-size: var(--fc-label); line-height: 1.4; }
.fc-order-facts > span b { display: block; margin-bottom: 3px; color: var(--text); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 15px; font-weight: 600; }
.fc-order-verdict { padding: 11px 12px; display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 10px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.fc-order-verdict.cheaper { border-color: rgba(82, 192, 143, 0.5); color: var(--fc-order); }
.fc-order-verdict.dearer { border-color: rgba(228, 90, 88, 0.5); color: var(--red); }
.fc-order-verdict span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-order-verdict strong { display: block; margin-top: 4px; font-size: 15px; }
.fc-order-verdict p { margin: 6px 0 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-authority { margin: 0 14px; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-left: 3px solid var(--teal); background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.fc-authority span { display: block; font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-authority p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-panel-empty { min-height: 240px; padding: 22px; display: grid; place-content: center; justify-items: center; gap: 8px; color: var(--text-muted); text-align: center; }
.fc-panel-empty p { margin: 0; max-width: 320px; font-size: var(--fc-support); line-height: 1.6; }
.fc-band-note { margin: 0 14px 14px; padding: 11px 12px; border: 1px solid rgba(143, 151, 245, 0.4); border-radius: 6px; background: rgba(143, 151, 245, 0.07); }
.fc-band-note strong { display: block; color: var(--fc-band); font-size: var(--fc-support); }
.fc-band-note p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }

.fc-week-table { margin: 0 14px 14px; }
.fc-week-table summary { min-height: 44px; padding: 11px 12px; display: flex; align-items: center; border: 1px solid var(--border); border-radius: 6px; background: var(--surface-raised); color: var(--text-secondary); font-size: var(--fc-support); }
.fc-week-table summary:focus-visible { outline-offset: 2px; }
.fc-week-table > div { max-height: 300px; margin-top: 8px; border: 1px solid var(--border); border-radius: 6px; overflow: auto; }

.fc-section-heading { margin-bottom: 14px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.fc-section-heading span { color: var(--orange); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-section-heading h2 { margin: 5px 0 5px; font-size: 20px; }
.fc-section-heading p { margin: 0; max-width: 920px; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.6; }
.fc-section-heading > strong { display: inline-flex; align-items: center; gap: 7px; padding: 8px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--fc-label); white-space: nowrap; }
.fc-assumption-note { margin-bottom: 14px; padding: 10px 12px; display: flex; gap: 9px; border-left: 3px solid var(--amber); background: rgba(240, 180, 41, 0.07); color: var(--amber); }
.fc-assumption-note p { margin: 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-assumption-note strong { color: var(--amber); }

.fc-panel { margin-bottom: 14px; padding: 15px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.fc-panel > header { margin-bottom: 12px; }
.fc-panel > header span { color: var(--orange); font-family: var(--font-mono); font-size: var(--fc-label); text-transform: uppercase; }
.fc-panel > header h3 { margin: 5px 0 0; font-size: 15px; }
.fc-panel > header p { margin: 6px 0 0; max-width: 920px; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.6; }

.fc-cohort-control { margin-bottom: 14px; padding: 14px; display: grid; grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr); gap: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.fc-cohort-control > div { min-width: 0; }
.fc-cohort-control label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--fc-support); }
.fc-cohort-control output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.fc-cohort-help { margin: 8px 0 0; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }

.fc-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.fc-summary-grid > div { min-width: 0; min-height: 100px; padding: 13px 15px; display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
.fc-summary-grid strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 20px; }
.fc-summary-grid span { margin-top: 4px; color: var(--text-secondary); font-size: var(--fc-support); }
.fc-summary-grid small { margin-top: 3px; color: var(--text-muted); font-size: var(--fc-label); line-height: 1.45; }

.fc-table-wrap { margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow-x: auto; }
.fc-table { min-width: 660px; }
.fc-table caption { padding: 12px 14px; color: var(--text-secondary); font-size: var(--fc-support); text-align: left; }
.fc-table th, .fc-table td { padding: 11px 14px; border-bottom: 1px solid var(--border); font-size: var(--fc-support); text-align: left; vertical-align: top; }
.fc-table thead th { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--fc-label); font-weight: 500; text-transform: uppercase; white-space: nowrap; }
.fc-table tbody th { color: var(--text); font-weight: 600; }
.fc-table tbody tr:last-child th, .fc-table tbody tr:last-child td { border-bottom: 0; }
.fc-table td span { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--fc-label); line-height: 1.45; }
.fc-row-current th, .fc-row-current td { background: rgba(232, 145, 60, 0.08); }
.fc-row-worst th, .fc-row-worst td { background: rgba(228, 90, 88, 0.07); }
.fc-tag { display: inline-flex; align-items: center; gap: 5px; padding: 4px 7px; border: 1px solid var(--border-strong); border-radius: 3px; color: var(--text-secondary); font-size: var(--fc-label); white-space: nowrap; }
.fc-tag.good { border-color: rgba(82, 192, 143, 0.45); color: var(--fc-order); }
.fc-tag.bad { border-color: rgba(228, 90, 88, 0.45); color: var(--red); }
.fc-tag.warn { border-color: rgba(240, 180, 41, 0.5); color: var(--amber); }

.fc-split-bar { margin-bottom: 12px; }
.fc-split-track { display: flex; height: 30px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); overflow: hidden; }
.fc-split-track i { display: block; height: 100%; }
.fc-split-track i.cheaper { background: rgba(82, 192, 143, 0.55); }
.fc-split-track i.worse { background: rgba(228, 90, 88, 0.6); }
.fc-split-legend { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--text-secondary); font-size: var(--fc-support); }
.fc-split-legend span { display: inline-flex; align-items: center; gap: 7px; }
.fc-split-legend i { width: 12px; height: 12px; flex: 0 0 auto; border-radius: 2px; }
.fc-split-legend i.cheaper { background: rgba(82, 192, 143, 0.55); }
.fc-split-legend i.worse { background: rgba(228, 90, 88, 0.6); }

.fc-fact-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.fc-fact-grid > div { min-width: 0; min-height: 112px; padding: 13px 15px; background: var(--surface); color: var(--teal); }
.fc-fact-grid span { display: block; margin-top: 8px; color: var(--text-muted); font-size: var(--fc-label); text-transform: uppercase; }
.fc-fact-grid strong { display: block; margin-top: 4px; color: var(--text); font-size: var(--fc-body); line-height: 1.35; }
.fc-fact-grid small { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--fc-label); line-height: 1.5; }
.fc-limit-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 9px; }
.fc-limit-list li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 10px; align-items: start; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-limit-list li > svg { margin-top: 1px; color: var(--amber); }
.fc-plain-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
.fc-plain-list li { padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.fc-plain-list li strong { display: block; font-size: var(--fc-support); }
.fc-plain-list li span { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--fc-support); line-height: 1.55; }
.fc-source-link { color: var(--teal); overflow-wrap: anywhere; font-size: var(--fc-support); }

@media (max-width: 1180px) {
  .fc-workspace { grid-template-columns: minmax(230px, 0.36fr) minmax(0, 1fr); }
  .fc-plot-panel { border-right: 0; }
  .fc-order-panel { grid-column: 1 / -1; border-top: 1px solid var(--border); }
  .fc-metric-strip, .fc-summary-grid, .fc-fact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fc-cohort-control { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 760px) {
  .fc-header { flex-direction: column; }
  .fc-header h1 { font-size: 23px; }
  .fc-runtime-status { width: 100%; }
  .fc-boundary-line { grid-template-columns: 20px minmax(0, 1fr); }
  .fc-boundary-line span { grid-column: 1 / -1; }
  .fc-metric-strip, .fc-summary-grid, .fc-fact-grid, .fc-order-facts { grid-template-columns: minmax(0, 1fr); }
  .fc-view-switcher { grid-template-columns: minmax(0, 1fr); }
  .fc-view-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .fc-view-switcher button:last-child { border-bottom: 0; }
  .fc-workspace { grid-template-columns: minmax(0, 1fr); }
  .fc-product-browser, .fc-plot-panel { border-right: 0; border-bottom: 1px solid var(--border); }
  .fc-product-list { max-height: 360px; }
  .fc-order-panel { border-top: 0; }
  .fc-section-heading { flex-direction: column; align-items: flex-start; }
}
`;

type View = "plan" | "cohort" | "card";

const views = [
  {
    id: "plan" as const,
    label: "Plan one product",
    detail: "The forecast, the band, and how many to order",
    icon: LineChart,
  },
  {
    id: "cohort" as const,
    label: "The whole catalog",
    detail: "All 469 products, and where the rule loses",
    icon: Boxes,
  },
  {
    id: "card" as const,
    label: "Model card and evidence",
    detail: "What was measured, and what was not",
    icon: ClipboardList,
  },
];

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/* The ratio slider moves in half steps between these two ends. Below 1:1 a unit
   left over would cost more than a unit not on the shelf, which is a different
   business; above 20:1 the implied cost of a stockout is many times the price of
   the item and the arithmetic stops meaning anything. */
const MIN_RATIO = 1;
const MAX_RATIO = 20;
const POLICY_RATIO = 4;
const RATIO_PRESETS = [2, 4, 9];

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);

const money = (value: number) => `$${Math.round(value).toLocaleString("en-US")}`;

const count = (value: number, digits = 0) =>
  value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const percent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

const signedPercent = (value: number, digits = 1) =>
  `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;

const ratioLabel = (ratio: number) =>
  `${Number.isInteger(ratio) ? ratio : ratio.toFixed(1)}:1`;

/* "2011-11-28" -> "Nov 28". The API hands back the notebook's own date strings, so
   they are split rather than parsed into a local Date, which would shift every week
   by the reader's time zone. */
const shortWeek = (stamp: string) => {
  const [, month, day] = stamp.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? month;
  return `${name} ${Number(day)}`;
};

const longWeek = (stamp: string) => {
  const [year, month, day] = stamp.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? month;
  return `${name} ${Number(day)}, ${year}`;
};

const cell = (row: ForecastTableRow, key: string) => {
  const value = row[key];
  if (value === null || value === undefined) return "-";
  return typeof value === "number" ? count(value, Number.isInteger(value) ? 0 : 2) : value;
};

const numberCell = (row: ForecastTableRow, key: string, digits = 2) => {
  const value = row[key];
  return typeof value === "number" ? count(value, digits) : cell(row, key);
};

type FanChartProps = {
  history: { week: string; actual: number }[];
  weekly: {
    week: string;
    actual: number;
    point: number;
    low: number;
    high: number;
    order_quantile: number;
  }[];
  criticalRatio: number;
  productName: string;
};

/* The band is the point of this chart, so it is drawn first, filled, hatched and
   edged - it should be the first thing anyone sees. Nothing here is carried by
   color alone: the band is hatched, the forecast is dashed, the order line is the
   thickest stroke, and a week the band missed is marked with a triangle. */
function FanChart({ history, weekly, criticalRatio, productName }: FanChartProps) {
  const width = 840;
  const height = 330;
  const left = 52;
  const right = 18;
  const top = 26;
  const bottom = 56;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  if (weekly.length === 0) {
    return (
      <p className="fc-list-empty">
        This product came back with no planned weeks, so there is nothing to plot.
      </p>
    );
  }

  const points = [
    ...history.map((week) => ({ ...week, planned: false as const })),
    ...weekly.map((week) => ({ ...week, planned: true as const })),
  ];
  const total = points.length;
  const firstPlanned = history.length;

  const highest = Math.max(
    ...points.map((week) => week.actual),
    ...weekly.map((week) => Math.max(week.high, week.order_quantile)),
  );
  const yMax = Math.max(highest * 1.1, 10);
  const rawStep = yMax / 4;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const step = Math.ceil(rawStep / magnitude) * magnitude;
  const ticks: number[] = [];
  for (let value = 0; value <= yMax; value += step) ticks.push(value);

  const x = (index: number) =>
    left + (total <= 1 ? plotWidth / 2 : (index / (total - 1)) * plotWidth);
  const y = (value: number) => top + plotHeight - (clamp(value, 0, yMax) / yMax) * plotHeight;
  const at = (index: number, value: number) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`;

  const bandTop = weekly.map((week, index) => at(firstPlanned + index, week.high));
  const bandBottom = weekly
    .map((week, index) => at(firstPlanned + index, week.low))
    .reverse();
  const bandPolygon = [...bandTop, ...bandBottom].join(" ");
  const pointLine = weekly.map((week, index) => at(firstPlanned + index, week.point)).join(" ");
  const orderLine = weekly
    .map((week, index) => at(firstPlanned + index, week.order_quantile))
    .join(" ");
  const actualLine = points.map((week, index) => at(index, week.actual)).join(" ");
  const misses = weekly
    .map((week, index) => ({ week, index: firstPlanned + index }))
    .filter((entry) => entry.week.actual > entry.week.high);

  const splitX = x(firstPlanned) - (x(firstPlanned) - x(firstPlanned - 1)) / 2;
  const labelIndexes = [0, firstPlanned, total - 1];
  const middlePlanned = firstPlanned + Math.floor(weekly.length / 2);

  const summary =
    `Weekly units for ${productName}. ${history.length} weeks of history, then ` +
    `${weekly.length} planned weeks showing what actually sold, the point forecast, ` +
    `the 80% band around it, and the order quantity read at the ` +
    `${(criticalRatio * 100).toFixed(0)}% mark of that band. ` +
    `${misses.length} ${misses.length === 1 ? "week ran" : "weeks ran"} above the top of ` +
    "the band.";

  return (
    <div className="fc-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
        <title>{summary}</title>
        <defs>
          <pattern
            id="fc-band-hatch"
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="7" stroke="rgba(143, 151, 245, 0.45)" strokeWidth="1.4" />
          </pattern>
        </defs>

        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={left} y1={y(tick)} x2={left + plotWidth} y2={y(tick)} />
            <text className="tick" x={left - 8} y={y(tick) + 3.5} textAnchor="end">
              {count(tick)}
            </text>
          </g>
        ))}

        <polygon className="band-fill" points={bandPolygon} />
        <polygon className="band-hatch" points={bandPolygon} />
        <polyline className="band-edge" points={bandTop.join(" ")} />
        <polyline className="band-edge" points={bandBottom.join(" ")} />
        <text
          className="band-label"
          x={x(middlePlanned)}
          y={Math.max(top + 10, y(weekly[Math.floor(weekly.length / 2)].high) - 7)}
          textAnchor="middle"
        >
          80% band
        </text>

        <line className="split-line" x1={splitX} y1={top} x2={splitX} y2={top + plotHeight} />
        <text className="split-label" x={splitX + 6} y={top + 11}>
          forecasting starts here
        </text>

        <polyline className="point-line" points={pointLine} />
        <polyline className="order-line" points={orderLine} />
        <polyline className="actual" points={actualLine} />
        {points.map((week, index) => (
          <circle key={week.week} className="actual-dot" cx={x(index)} cy={y(week.actual)} r={2.2} />
        ))}
        {misses.map((entry) => (
          <polygon
            key={entry.week.week}
            className="miss-mark"
            points={`${x(entry.index)},${y(entry.week.actual) - 9} ${x(entry.index) - 5.5},${
              y(entry.week.actual) + 1
            } ${x(entry.index) + 5.5},${y(entry.week.actual) + 1}`}
          />
        ))}

        <line className="axis" x1={left} y1={top + plotHeight} x2={left + plotWidth} y2={top + plotHeight} />
        <line className="axis" x1={left} y1={top} x2={left} y2={top + plotHeight} />
        {labelIndexes.map((index, position) => (
          <text
            className="tick"
            key={`label-${index}`}
            x={clamp(x(index), left, left + plotWidth)}
            y={top + plotHeight + 20}
            textAnchor={position === 0 ? "start" : position === 2 ? "end" : "middle"}
          >
            {shortWeek(points[index].week)}
          </text>
        ))}
        <text className="tick" x={left} y={top + plotHeight + 40}>
          One point per week, in units. The forecast never looks more than one week ahead.
        </text>
      </svg>
    </div>
  );
}

export default function ForecastPage() {
  const [view, setView] = useState<View>("plan");
  const [model, setModel] = useState<ForecastModelInfo | null>(null);
  const [products, setProducts] = useState<ForecastProductSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [plan, setPlan] = useState<ForecastPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [sweep, setSweep] = useState<ForecastPolicySweep | null>(null);
  const [sweepBusy, setSweepBusy] = useState(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [ratio, setRatio] = useState<number>(POLICY_RATIO);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const skipFirstRatioFetch = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getForecastModel(), getForecastProducts(24), getForecastPolicySweep()])
      .then(async ([modelInfo, packaged, cohort]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setProducts(packaged);
        setSweep(cohort);
        skipFirstRatioFetch.current = true;
        setRatio(cohort.cost_ratio);
        const first = packaged[0];
        if (!first) return;
        setSelectedId(first.product_id);
        const initial = await planForecast(first.product_id);
        if (cancelled) return;
        setPlan(initial);
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  /* One control moves both views, so one effect refetches both. The first run is
     skipped because the initial load already carries the plan and the cohort at
     the frozen 4:1 ratio. */
  useEffect(() => {
    if (!model) return;
    if (skipFirstRatioFetch.current) {
      skipFirstRatioFetch.current = false;
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setSweepBusy(true);
      if (selectedId) setPlanning(true);
      void Promise.all([
        getForecastPolicySweep(ratio),
        selectedId ? planForecast(selectedId, ratio) : Promise.resolve(null),
      ])
        .then(([cohort, planned]) => {
          if (cancelled) return;
          setSweep(cohort);
          setSweepError(null);
          if (planned) {
            setPlan(planned);
            setPlanError(null);
          }
        })
        .catch((reason: Error) => {
          if (cancelled) return;
          setSweepError(reason.message);
          setPlanError(reason.message);
        })
        .finally(() => {
          if (cancelled) return;
          setSweepBusy(false);
          setPlanning(false);
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [ratio, attempt, selectedId, model]);

  const chooseProduct = (entry: ForecastProductSummary) => {
    if (entry.product_id === selectedId) return;
    setSelectedId(entry.product_id);
    setPlan(null);
    setPlanError(null);
    // The ratio effect owns the fetch, and selectedId is one of its inputs.
  };

  const changeRatio = (value: number) => {
    setRatio(clamp(Math.round(value * 2) / 2, MIN_RATIO, MAX_RATIO));
  };

  const evaluation = model?.evaluation ?? null;
  const outcome4 = model?.per_product_outcomes.find((row) => row["ratio"] === "4:1") ?? null;
  const cheaperCount = typeof outcome4?.["cheaper"] === "number" ? outcome4["cheaper"] : 354;
  const cohortSize = model?.policy.cohort_size ?? 469;

  const ratioIsPolicy = ratio === POLICY_RATIO;
  const ratioSentence = ratioIsPolicy
    ? `The frozen policy: a unit not on the shelf counts as ${POLICY_RATIO} times as costly as a unit left in the box.`
    : `A what-if at ${ratioLabel(ratio)}. The frozen policy is ${ratioLabel(POLICY_RATIO)}.`;

  return (
    <div className="page fc-page">
      <style>{pageStyles}</style>

      <button
        className="page-back-button"
        type="button"
        onClick={() => navigate("/showcase?industry=retail")}
      >
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="fc-header">
        <div>
          <span className="eyebrow">Demand planning - retail and supply chain</span>
          <h1>Weekly Demand Forecast and Order Plan</h1>
          <p>
            A gift wholesaler has to decide, every week, how many of each product to have on the
            shelf. This tool forecasts next week's units for one product, puts an honest range
            around that forecast, and turns the range into a quantity a buyer can approve, adjust
            or throw away.
          </p>
        </div>
        <div className="fc-runtime-status">
          <span className={model ? "ready" : ""} />
          <div>
            <strong>{model ? "Live model ready" : "Connecting"}</strong>
            <small>
              {model
                ? `FastAPI - ${model.model_type} - version ${model.model_version}`
                : "FastAPI - reading notebook artifacts"}
            </small>
          </div>
        </div>
      </header>

      <div className="fc-boundary-line" role="note">
        <Scale size={17} aria-hidden="true" />
        <strong>Where this system's authority stops</strong>
        <span>
          The forecast is not a promise. The interval is not a guarantee. A planner approves every
          order, and the system never places one.
        </span>
      </div>

      {evaluation ? (
        <section className="fc-metric-strip" aria-label="Results on the held-out weeks">
          <div>
            <strong>{count(evaluation.mae_units, 2)}</strong>
            <span>units off, on an average week</span>
            <small>
              Across {count(evaluation.rows)} product-weeks that the model never saw while it was
              being built
            </small>
          </div>
          <div>
            <strong>{percent(evaluation.coverage_delivered, 2)}</strong>
            <span>of weeks landed inside the band</span>
            <small>Against the {percent(evaluation.coverage_promised, 0)} the band promised</small>
          </div>
          <div>
            <strong>{count(evaluation.median_band_units, 2)}</strong>
            <span>units wide, in a typical week</span>
            <small>
              {count(evaluation.band_over_median_demand, 2)} times a normal week's demand. An
              honest range is wider than the forecast.
            </small>
          </div>
          <div>
            <strong>
              {count(cheaperCount)} of {count(cohortSize)}
            </strong>
            <span>products cost less under the order rule</span>
            <small>
              Which means {count(cohortSize - cheaperCount)} cost more. They are shown, not hidden.
            </small>
          </div>
        </section>
      ) : null}

      <nav className="fc-view-switcher" aria-label="Demand forecasting views">
        {views.map(({ id, label, detail, icon: Icon }) => (
          <button
            type="button"
            className={view === id ? "active" : ""}
            aria-label={`${label}: ${detail}`}
            aria-pressed={view === id}
            key={id}
            onClick={() => setView(id)}
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
          The forecast service did not answer: {loadError}
          <div className="fc-control-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={() => window.location.reload()}
            >
              <RefreshCcw size={15} aria-hidden="true" /> Reload the page
            </button>
          </div>
        </div>
      ) : null}
      {!model && !loadError ? (
        <div className="loading-state">Loading the model and the packaged products...</div>
      ) : null}

      {view === "plan" && model ? (
        <section className="fc-workspace">
          <aside className="fc-product-browser">
            <header>
              <div>
                <span className="step">Step 1</span>
                <strong>Choose a product</strong>
                <small>Ten packaged products, chosen by rule</small>
              </div>
            </header>
            {products.length === 0 ? (
              <p className="fc-list-empty">
                No packaged products came back from the service. Rebuild the notebook artifacts and
                reload this page.
              </p>
            ) : (
              <div className="fc-product-list">
                {products.map((entry) => (
                  <button
                    type="button"
                    key={entry.product_id}
                    className={selectedId === entry.product_id ? "active" : ""}
                    aria-pressed={selectedId === entry.product_id}
                    onClick={() => chooseProduct(entry)}
                  >
                    <span className={entry.policy_is_cheaper ? "tag" : "tag loses"}>
                      {entry.policy_is_cheaper
                        ? "The order rule saved money here"
                        : "The order rule LOST money here"}
                    </span>
                    <strong>{entry.product}</strong>
                    <small>{entry.why_this_product}</small>
                    <span className="stat">
                      {count(entry.mean_units_per_week)} units a week - band{" "}
                      {count(entry.band_over_demand, 2)}x demand
                    </span>
                  </button>
                ))}
              </div>
            )}
          </aside>

          <section className="fc-plot-panel">
            <header>
              <div>
                <span className="step">Step 2</span>
                <strong>Read the forecast and the band</strong>
                <small>Every week, against what actually sold</small>
              </div>
              <TrendingUp size={19} aria-hidden="true" />
            </header>

            {plan ? (
              <div className="fc-purpose-note">
                <Info size={16} aria-hidden="true" />
                <p>
                  <strong>{plan.product}</strong> is packaged because it is{" "}
                  {plan.why_this_product}. The chart replays {plan.weeks_planned} weeks the model
                  never saw while it was being built, from {longWeek(plan.week_start)} to{" "}
                  {longWeek(plan.week_end)}.
                </p>
              </div>
            ) : null}

            {planError ? (
              <div className="error-banner" role="alert">
                This product could not be planned: {planError}
                <div className="fc-control-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => setAttempt((value) => value + 1)}
                  >
                    <RefreshCcw size={15} aria-hidden="true" /> Try again
                  </button>
                </div>
              </div>
            ) : null}

            {plan ? (
              <>
                <div className="fc-chart-scroll">
                  <FanChart
                    history={plan.history}
                    weekly={plan.weekly}
                    criticalRatio={plan.critical_ratio}
                    productName={plan.product}
                  />
                </div>
                <div className="fc-chart-legend">
                  <span>
                    <i aria-hidden="true" /> What actually sold
                  </span>
                  <span>
                    <i className="point" aria-hidden="true" /> The forecast
                  </span>
                  <span>
                    <i className="band" aria-hidden="true" /> The 80% band
                  </span>
                  <span>
                    <i className="order" aria-hidden="true" /> How many to order at{" "}
                    {ratioLabel(plan.cost_ratio)}
                  </span>
                  <span>
                    <i className="miss" aria-hidden="true" /> A week that ran above the band
                  </span>
                </div>
              </>
            ) : (
              <div className="fc-panel-empty">
                <PackageSearch size={26} aria-hidden="true" />
                <p>
                  {planning || !planError
                    ? "Building the plan for this product..."
                    : "Pick a product on the left to see its forecast."}
                </p>
              </div>
            )}

            <div className="fc-ratio-control">
              <span>The one number a buyer has to supply</span>
              <strong>What does a unit not on the shelf cost, against a unit left in the box?</strong>
              <label htmlFor="fc-ratio">
                <span>
                  Cost of being short, per unit left over
                  <output htmlFor="fc-ratio">{ratioLabel(ratio)}</output>
                </span>
                <input
                  id="fc-ratio"
                  type="range"
                  min={MIN_RATIO}
                  max={MAX_RATIO}
                  step={0.5}
                  value={ratio}
                  onChange={(event) => changeRatio(Number(event.target.value))}
                  aria-describedby="fc-ratio-help"
                />
              </label>
              <p className="fc-scale-row">
                <span>1:1 both hurt the same</span>
                <span>20:1 a stockout is unaffordable</span>
              </p>
              <p className="fc-control-status" role="status">
                {planning || sweepBusy ? "Recalculating the order..." : ratioSentence}
              </p>
              <p className="fc-cohort-help" id="fc-ratio-help">
                Moving this changes only how many units to buy. The forecast and the band do not
                move, because nothing about the product changed - only what a mistake costs.
              </p>
              <div className="fc-control-actions">
                {RATIO_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className="fc-ratio-preset"
                    aria-pressed={ratio === preset}
                    onClick={() => changeRatio(preset)}
                  >
                    {ratioLabel(preset)}
                    {preset === POLICY_RATIO ? " - the policy" : ""}
                  </button>
                ))}
              </div>
            </div>

            {plan ? (
              <details className="fc-week-table">
                <summary>Week by week, all {plan.weeks_planned} planned weeks</summary>
                <div>
                  <table className="fc-table">
                    <caption>
                      What sold, what the model expected, where the band sat, and what each rule
                      would have ordered. Units, rounded to one decimal place.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Week</th>
                        <th scope="col">Sold</th>
                        <th scope="col">Forecast</th>
                        <th scope="col">Band</th>
                        <th scope="col">Order at {ratioLabel(plan.cost_ratio)}</th>
                        <th scope="col">Inside the band?</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.weekly.map((week) => (
                        <tr key={week.week}>
                          <th scope="row" className="num">
                            {shortWeek(week.week)}
                          </th>
                          <td className="num">{count(week.actual)}</td>
                          <td className="num">{count(week.point)}</td>
                          <td className="num">
                            {count(week.low)} to {count(week.high)}
                          </td>
                          <td className="num">{count(week.order_quantile)}</td>
                          <td>
                            {week.covered ? (
                              <span className="fc-tag good">
                                <CheckCircle2 size={12} aria-hidden="true" /> Inside
                              </span>
                            ) : (
                              <span className="fc-tag bad">
                                <AlertTriangle size={12} aria-hidden="true" />{" "}
                                {week.actual > week.high ? "Above the band" : "Below the band"}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ) : null}
          </section>

          <section className="fc-order-panel">
            <header>
              <div>
                <span className="step">Step 3</span>
                <strong>How many to order</strong>
                <small>Two rules, side by side</small>
              </div>
              <SlidersHorizontal size={19} aria-hidden="true" />
            </header>

            {plan ? (
              <>
                <div className="fc-order-body">
                  <div className="fc-order-card">
                    <span>If you order the forecast</span>
                    <strong>{count(plan.latest.order_point)} units</strong>
                    <b>for the week of {longWeek(plan.latest.week)}</b>
                    <p>
                      {plan.point_plan.plain_rule} Over all {plan.weeks_planned} planned weeks:
                    </p>
                    <div className="fc-order-facts">
                      <span>
                        <b>{count(plan.point_plan.units_short)}</b>
                        units short
                      </span>
                      <span>
                        <b>{count(plan.point_plan.units_excess)}</b>
                        units left over
                      </span>
                      <span>
                        <b>{money(plan.point_plan.cost)}</b>
                        classroom cost
                      </span>
                    </div>
                  </div>

                  <div className="fc-order-card chosen">
                    <span>
                      If you order the band at the {(plan.critical_ratio * 100).toFixed(0)}% mark
                    </span>
                    <strong>{count(plan.latest.order_quantile)} units</strong>
                    <b>for the week of {longWeek(plan.latest.week)}</b>
                    <p>
                      {plan.quantile_plan.plain_rule} Over all {plan.weeks_planned} planned weeks:
                    </p>
                    <div className="fc-order-facts">
                      <span>
                        <b>{count(plan.quantile_plan.units_short)}</b>
                        units short
                      </span>
                      <span>
                        <b>{count(plan.quantile_plan.units_excess)}</b>
                        units left over
                      </span>
                      <span>
                        <b>{money(plan.quantile_plan.cost)}</b>
                        classroom cost
                      </span>
                    </div>
                  </div>

                  <div
                    className={
                      plan.policy_is_cheaper ? "fc-order-verdict cheaper" : "fc-order-verdict dearer"
                    }
                    role="status"
                  >
                    {plan.policy_is_cheaper ? (
                      <CheckCircle2 size={18} aria-hidden="true" />
                    ) : (
                      <AlertTriangle size={18} aria-hidden="true" />
                    )}
                    <div>
                      <span>The difference</span>
                      <strong>
                        {count(Math.abs(plan.latest.extra_units))} more units this week,{" "}
                        {signedPercent(plan.cost_change_pct)} on cost
                      </strong>
                      <p>
                        Ordering at the band instead of the forecast buys{" "}
                        {count(Math.abs(plan.latest.extra_units))} more units in the week of{" "}
                        {longWeek(plan.latest.week)}, and over all {plan.weeks_planned} weeks it
                        was {money(Math.abs(plan.saving))}{" "}
                        {plan.policy_is_cheaper ? "cheaper" : "MORE EXPENSIVE"}. {plan.ratio_note}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="fc-band-note">
                  <strong>What the band did on this product</strong>
                  <p>
                    The band caught what actually sold in {percent(plan.coverage, 1)} of these
                    weeks - {plan.weeks_planned - plan.misses} of {plan.weeks_planned}. It missed{" "}
                    {plan.misses}, and {plan.misses_above_band} of those misses were above the top
                    of the band, which is the direction that empties a shelf. The band is{" "}
                    {count(plan.band_over_demand, 2)} times as wide as a normal week's demand for
                    this product.
                  </p>
                </div>

                <div className="fc-authority">
                  <Scale size={17} aria-hidden="true" />
                  <div>
                    <span>Who decides</span>
                    <p>{model.policy.human_authority}</p>
                  </div>
                </div>
              </>
            ) : (
              <div className="fc-panel-empty">
                <PackageSearch size={26} aria-hidden="true" />
                <p>
                  The order quantities appear here once a product is planned. Nothing on this page
                  places an order.
                </p>
              </div>
            )}
          </section>
        </section>
      ) : null}

      {view === "cohort" && model ? (
        <>
          <div className="fc-section-heading">
            <div>
              <span>The whole catalog</span>
              <h2>The same rule, run across all {count(cohortSize)} products</h2>
              <p>
                One product is a story. This is what the order rule did to every product it is
                allowed to forecast, over the same {sweep?.test_weeks ?? 26} weeks the model never
                saw. The rule is cheaper overall and more expensive on a real minority, and both
                halves are on this page.
              </p>
            </div>
            <strong>
              <Database size={14} aria-hidden="true" />
              {count(sweep?.product_weeks ?? 12194)} product-weeks
            </strong>
          </div>

          <div className="fc-assumption-note" role="note">
            <AlertTriangle size={17} aria-hidden="true" />
            <p>
              <strong>Every dollar on this page is a classroom assumption.</strong>{" "}
              {model.policy.cost_assumption_note} No real retailer's economics are involved, and
              the two numbers behind them are the two only a company's own operations and finance
              teams can supply.
            </p>
          </div>

          <div className="fc-cohort-control">
            <div>
              <label htmlFor="fc-cohort-ratio">
                <span>
                  Cost of being short, per unit left over
                  <output htmlFor="fc-cohort-ratio">{ratioLabel(ratio)}</output>
                </span>
                <input
                  id="fc-cohort-ratio"
                  type="range"
                  min={MIN_RATIO}
                  max={MAX_RATIO}
                  step={0.5}
                  value={ratio}
                  onChange={(event) => changeRatio(Number(event.target.value))}
                />
              </label>
              <p className="fc-scale-row">
                <span>1:1</span>
                <span>20:1</span>
              </p>
              <p className="fc-control-status" role="status">
                {sweepBusy ? "Repricing all 469 products..." : ratioSentence}
              </p>
            </div>
            <div>
              <p className="fc-cohort-help">
                {sweep
                  ? sweep.quantile_plan.plain_rule
                  : "The order rule reads each product's own band at the point the cost ratio implies."}
              </p>
              <p className="fc-cohort-help">
                Nothing here is stored and read back. Every number is recalculated through the
                notebook's own pricing code each time this control moves.
              </p>
              <div className="fc-control-actions">
                {RATIO_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className="fc-ratio-preset"
                    aria-pressed={ratio === preset}
                    onClick={() => changeRatio(preset)}
                  >
                    {ratioLabel(preset)}
                    {preset === POLICY_RATIO ? " - the policy" : ""}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {sweepError ? (
            <div className="error-banner" role="alert">
              The cohort could not be repriced: {sweepError}
              <div className="fc-control-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setAttempt((value) => value + 1)}
                >
                  <RefreshCcw size={15} aria-hidden="true" /> Try again
                </button>
              </div>
            </div>
          ) : null}

          {sweep ? (
            <>
              <section className="fc-summary-grid" aria-label="The cohort at this cost ratio">
                <div>
                  <strong>{count(sweep.quantile_plan.units_ordered)}</strong>
                  <span>units ordered under the rule</span>
                  <small>
                    {signedPercent(sweep.units_uplift_pct)} against ordering the forecast
                  </small>
                </div>
                <div>
                  <strong>{money(sweep.quantile_plan.cost)}</strong>
                  <span>classroom cost of the rule</span>
                  <small>
                    Not a price paid to anyone: it is the assumed cost of being short plus the
                    assumed cost of holding, added up over every product-week
                  </small>
                </div>
                <div>
                  <strong>{signedPercent(sweep.vs_point_pct)}</strong>
                  <span>against ordering the forecast</span>
                  <small>
                    {money(sweep.point_plan.cost)} becomes {money(sweep.quantile_plan.cost)}
                  </small>
                </div>
                <div>
                  <strong>{signedPercent(sweep.vs_mean_pct)}</strong>
                  <span>against ordering the average</span>
                  <small>
                    {money(sweep.mean_plan.cost)} becomes {money(sweep.quantile_plan.cost)}
                  </small>
                </div>
              </section>

              <div className="fc-table-wrap">
                <table className="fc-table">
                  <caption>
                    Three ways to decide how many to buy, priced over the same{" "}
                    {count(sweep.product_weeks)} product-weeks at {ratioLabel(sweep.cost_ratio)}.
                    Units are units; every dollar is a classroom assumption.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Ordering rule</th>
                      <th scope="col">Units ordered</th>
                      <th scope="col">Units short</th>
                      <th scope="col">Units left over</th>
                      <th scope="col">Demand met</th>
                      <th scope="col">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { key: "rule", outcome: sweep.quantile_plan, current: true },
                      { key: "point", outcome: sweep.point_plan, current: false },
                      { key: "mean", outcome: sweep.mean_plan, current: false },
                    ].map(({ key, outcome, current }) => (
                      <tr key={key} className={current ? "fc-row-current" : ""}>
                        <th scope="row">
                          {outcome.rule}
                          <span>{outcome.plain_rule}</span>
                        </th>
                        <td className="num">{count(outcome.units_ordered)}</td>
                        <td className="num">{count(outcome.units_short)}</td>
                        <td className="num">{count(outcome.units_excess)}</td>
                        <td className="num">{percent(outcome.fill_rate, 1)}</td>
                        <td className="num">{money(outcome.cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <section className="fc-panel">
                <header>
                  <span>The part a slide would leave out</span>
                  <h3>
                    The rule costs more on {count(sweep.products_worse)} of {count(sweep.products)}{" "}
                    products
                  </h3>
                  <p>
                    At {ratioLabel(sweep.cost_ratio)} the rule is cheaper on{" "}
                    {count(sweep.products_cheaper)} products and more expensive on{" "}
                    {count(sweep.products_worse)} - {percent(sweep.products_worse_share, 1)} of the
                    catalog, costing {money(sweep.extra_cost_on_losers)} more than ordering the
                    forecast would have. A planner whose name is on those orders will notice.
                  </p>
                </header>

                <div className="fc-split-bar">
                  <div className="fc-split-track" role="img" aria-label={
                    `${sweep.products_cheaper} of ${sweep.products} products cost less under the ` +
                    `rule and ${sweep.products_worse} cost more.`
                  }>
                    <i
                      className="cheaper"
                      style={{ width: `${(100 * sweep.products_cheaper) / sweep.products}%` }}
                    />
                    <i
                      className="worse"
                      style={{ width: `${(100 * sweep.products_worse) / sweep.products}%` }}
                    />
                  </div>
                  <p className="fc-split-legend">
                    <span>
                      <i className="cheaper" aria-hidden="true" />
                      {count(sweep.products_cheaper)} products cost less
                    </span>
                    <span>
                      <i className="worse" aria-hidden="true" />
                      {count(sweep.products_worse)} products cost more
                    </span>
                  </p>
                </div>

                <div className="fc-table-wrap">
                  <table className="fc-table">
                    <caption>
                      The {sweep.worst_products.length} products the rule hurt most at{" "}
                      {ratioLabel(sweep.cost_ratio)}. All of them are declining sellers: the band
                      still remembers weeks that are not coming back, so the rule keeps buying for
                      them.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Product</th>
                        <th scope="col">Sold</th>
                        <th scope="col">Ordered</th>
                        <th scope="col">Left over</th>
                        <th scope="col">Cost before</th>
                        <th scope="col">Cost after</th>
                        <th scope="col">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sweep.worst_products.map((item) => (
                        <tr key={item.product_id} className="fc-row-worst">
                          <th scope="row">
                            {item.product}
                            <span>Stock code {item.product_id}</span>
                          </th>
                          <td className="num">{count(item.actual_units)}</td>
                          <td className="num">{count(item.ordered_units)}</td>
                          <td className="num">{count(item.units_left_over)}</td>
                          <td className="num">{money(item.cost_point)}</td>
                          <td className="num">{money(item.cost_quantile)}</td>
                          <td className="num">
                            <span className="fc-tag bad">
                              <AlertTriangle size={12} aria-hidden="true" />{" "}
                              {signedPercent(item.change_pct)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="fc-table-wrap">
                  <table className="fc-table">
                    <caption>
                      And the {sweep.best_products.length} products it helped most, for contrast.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Product</th>
                        <th scope="col">Sold</th>
                        <th scope="col">Ordered</th>
                        <th scope="col">Cost before</th>
                        <th scope="col">Cost after</th>
                        <th scope="col">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sweep.best_products.map((item) => (
                        <tr key={item.product_id}>
                          <th scope="row">
                            {item.product}
                            <span>Stock code {item.product_id}</span>
                          </th>
                          <td className="num">{count(item.actual_units)}</td>
                          <td className="num">{count(item.ordered_units)}</td>
                          <td className="num">{money(item.cost_point)}</td>
                          <td className="num">{money(item.cost_quantile)}</td>
                          <td className="num">
                            <span className="fc-tag good">
                              <CheckCircle2 size={12} aria-hidden="true" />{" "}
                              {signedPercent(item.change_pct)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="fc-authority">
                  <Scale size={17} aria-hidden="true" />
                  <div>
                    <span>Who decides</span>
                    <p>{sweep.boundary}</p>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="loading-state">Pricing the catalog...</div>
          )}
        </>
      ) : null}

      {view === "card" && model && evaluation ? (
        <>
          <div className="fc-section-heading">
            <div>
              <span>Model card and evidence</span>
              <h2>{model.model_name}</h2>
              <p>
                {model.intended_use} Every number on this page is read from the service, which
                reads it from the file the notebook wrote. Nothing here is typed in by hand.
              </p>
            </div>
            <strong>
              <ClipboardList size={14} aria-hidden="true" />
              {model.model_version} / {model.policy.policy_version}
            </strong>
          </div>

          <section className="fc-fact-grid" aria-label="Model facts">
            <div>
              <Info size={18} aria-hidden="true" />
              <span>What it is</span>
              <strong>{model.model_type}</strong>
              <small>
                {model.cohort_products} products, {model.residuals_per_product} past errors each.
                No learned weights at all.
              </small>
            </div>
            <div>
              <TrendingUp size={18} aria-hidden="true" />
              <span>How far ahead</span>
              <strong>
                {model.policy.horizon_weeks} week, one product, one number
              </strong>
              <small>
                Built from the last {model.policy.window_weeks} observed weeks. There is no
                forecast for next month here, and no seasonality in the model at all.
              </small>
            </div>
            <div>
              <PackageSearch size={18} aria-hidden="true" />
              <span>What it refuses</span>
              <strong>
                {count(model.policy.products_refused)} products are not forecast
              </strong>
              <small>
                {model.policy.cohort_rule} Anything else is handed to a buyer as "not
                forecastable", never given a silent zero.
              </small>
            </div>
            <div>
              <Scale size={18} aria-hidden="true" />
              <span>Who decides</span>
              <strong>A planner, every time</strong>
              <small>{model.policy.human_authority}</small>
            </div>
          </section>

          <section className="fc-panel">
            <header>
              <span>In plain words</span>
              <h3>How the forecast and the band are built</h3>
            </header>
            <ul className="fc-plain-list">
              <li>
                <strong>The forecast</strong>
                <span>{model.how_it_works}</span>
              </li>
              <li>
                <strong>The order rule</strong>
                <span>{model.policy.plain_rule}</span>
              </li>
              <li>
                <strong>What the numbers are not</strong>
                <span>
                  {model.prohibited_claims.join(" ")} {model.interval_note}
                </span>
              </li>
              <li>
                <strong>If the band stops holding</strong>
                <span>{model.policy.recalibration}</span>
              </li>
            </ul>
          </section>

          <section className="fc-panel">
            <header>
              <span>Not for</span>
              <h3>Uses this model was not built for and must not be put to</h3>
            </header>
            <ul className="fc-limit-list">
              {model.not_for.map((item) => (
                <li key={item}>
                  <AlertTriangle size={15} aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <div className="fc-table-wrap">
            <table className="fc-table">
              <caption>
                Measured once on {count(evaluation.rows)} product-weeks from{" "}
                {longWeek(evaluation.held_out_window[0])} to{" "}
                {longWeek(evaluation.held_out_window[1])}, which the model never saw while it was
                being built. Scored once and never re-tuned.
              </caption>
              <thead>
                <tr>
                  <th scope="col">What was measured</th>
                  <th scope="col">Result</th>
                  <th scope="col">What it means</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Average error, in units</th>
                  <td className="num">{count(evaluation.mae_units, 2)}</td>
                  <td>
                    Missing by about {count(evaluation.mae_units, 0)} units on a typical week.
                    Forecasting zero forever misses by {count(evaluation.mae_of_flat_zero, 2)}.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Root mean squared error</th>
                  <td className="num">{count(evaluation.rmse_units, 2)}</td>
                  <td>
                    Much larger than the average error, which is what a handful of very big weeks
                    looks like.
                  </td>
                </tr>
                <tr className="fc-row-current">
                  <th scope="row">Weeks that landed inside the band</th>
                  <td className="num">{percent(evaluation.coverage_delivered, 2)}</td>
                  <td>
                    Against {percent(evaluation.coverage_promised, 0)} promised. The band held
                    slightly more often than it claimed, on average - see the Christmas table
                    below for where that average stops being true.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Width of the band, typical week</th>
                  <td className="num">{count(evaluation.median_band_units, 2)} units</td>
                  <td>
                    {count(evaluation.band_over_median_demand, 2)} times a normal week's demand. A
                    narrower band would simply be a band that lies.
                  </td>
                </tr>
                <tr>
                  <th scope="row">Pinball loss at 10 / 50 / 90</th>
                  <td className="num">
                    {count(evaluation.pinball_10, 3)} / {count(evaluation.pinball_50, 3)} /{" "}
                    {count(evaluation.pinball_90, 3)}
                  </td>
                  <td>
                    The score for a range rather than a single number. Lower is better; it is here
                    so the band can be compared with other ways of building one.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="fc-table-wrap">
            <table className="fc-table">
              <caption>
                The order rule at every cost ratio the notebook swept, over the same held-out
                weeks. Every dollar is a classroom assumption.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Cost ratio</th>
                  <th scope="col">Order at</th>
                  <th scope="col">Units vs the forecast</th>
                  <th scope="col">Units short</th>
                  <th scope="col">Cost change</th>
                </tr>
              </thead>
              <tbody>
                {model.newsvendor_sweep.map((row) => (
                  <tr
                    key={String(row["ratio"])}
                    className={row["ratio"] === "4:1" ? "fc-row-current" : ""}
                  >
                    <th scope="row" className="num">
                      {cell(row, "ratio")}
                      {row["ratio"] === "4:1" ? <span>the frozen policy</span> : null}
                    </th>
                    <td className="num">
                      {typeof row["critical_ratio"] === "number"
                        ? percent(row["critical_ratio"], 1)
                        : cell(row, "critical_ratio")}
                    </td>
                    <td className="num">
                      {typeof row["units_uplift_pct"] === "number"
                        ? signedPercent(row["units_uplift_pct"])
                        : cell(row, "units_uplift_pct")}
                    </td>
                    <td className="num">
                      {numberCell(row, "shortfall_point", 0)} to{" "}
                      {numberCell(row, "shortfall_quantile", 0)}
                    </td>
                    <td className="num">
                      {typeof row["vs_point_pct"] === "number"
                        ? signedPercent(row["vs_point_pct"])
                        : cell(row, "vs_point_pct")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="fc-panel">
            <header>
              <span>The honest limitations</span>
              <h3>Four things that are measured, not suspected</h3>
              <p>{model.seasonal_coverage.note}</p>
            </header>

            <div className="fc-table-wrap">
              <table className="fc-table">
                <caption>
                  Coverage sliced by season. The headline{" "}
                  {percent(evaluation.coverage_delivered, 2)} is an average over{" "}
                  {count(evaluation.rows)} rows; inside {model.seasonal_coverage.ramp_months} on the
                  most Christmas-heavy products it collapses.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Slice</th>
                    <th scope="col">Product-weeks</th>
                    <th scope="col">Coverage</th>
                    <th scope="col">Misses above the band</th>
                  </tr>
                </thead>
                <tbody>
                  {model.seasonal_coverage.slices.map((row) => {
                    const label = String(row["Slice"] ?? "");
                    const worst = label === model.seasonal_coverage.worst_slice_label;
                    return (
                      <tr key={label} className={worst ? "fc-row-worst" : ""}>
                        <th scope="row">
                          {label}
                          {worst ? <span>the failure</span> : null}
                        </th>
                        <td className="num">{cell(row, "Product-weeks")}</td>
                        <td className="num">
                          {worst ? (
                            <span className="fc-tag bad">
                              <AlertTriangle size={12} aria-hidden="true" />{" "}
                              {cell(row, "Coverage (promised 80%)")}
                            </span>
                          ) : (
                            cell(row, "Coverage (promised 80%)")
                          )}
                        </td>
                        <td className="num">{cell(row, "Misses that were ABOVE the band")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <ul className="fc-limit-list">
              <li>
                <AlertTriangle size={15} aria-hidden="true" />
                <span>
                  <strong>The band fails at Christmas.</strong> On the most Christmas-heavy
                  products inside the October-November ramp it caught only{" "}
                  {model.seasonal_coverage.worst_slice_coverage}% of weeks against a promised{" "}
                  {percent(evaluation.coverage_promised, 0)}, and{" "}
                  {model.seasonal_coverage.misses_above_band_share} of those misses were above the
                  band - the direction that empties a shelf.
                </span>
              </li>
              <li>
                <AlertTriangle size={15} aria-hidden="true" />
                <span>
                  <strong>There is only one full Christmas in the training window.</strong> The
                  model was fitted on {model.dataset.training_window[0]} to{" "}
                  {model.dataset.training_window[1]}, so "the same week last year" is one noisy
                  number rather than a season, and the model carries no seasonality at all.
                </span>
              </li>
              <li>
                <AlertTriangle size={15} aria-hidden="true" />
                <span>
                  <strong>The textbook seasonal method loses to forecasting nothing.</strong>{" "}
                  Seasonal-naive - "order what you sold this week last year" - scores worse on
                  average error than a flat zero forecast on this data, for the same reason.
                </span>
              </li>
              <li>
                <AlertTriangle size={15} aria-hidden="true" />
                <span>
                  <strong>MAPE is unusable here and is shown only as a warning.</strong> The
                  percentage-error metric scores the real forecast at{" "}
                  {evaluation.mape_of_the_point_forecast.toExponential(2)} and a flat zero forecast
                  at {count(evaluation.mape_of_a_flat_zero_forecast, 4)}, because it divides by an
                  actual that is often zero. By that metric the right answer is to close the
                  warehouse.
                </span>
              </li>
            </ul>
          </section>

          <div className="fc-table-wrap">
            <table className="fc-table">
              <caption>
                Six ways to produce the single-number forecast, all scored the same way on the same
                held-out weeks. The one that was adopted is the one at the top.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Point forecast</th>
                  <th scope="col">Average error</th>
                  <th scope="col">RMSE</th>
                  <th scope="col">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {model.point_baselines.map((row) => (
                  <tr key={String(row["Point forecast"])}>
                    <th scope="row">{cell(row, "Point forecast")}</th>
                    <td className="num">{numberCell(row, "MAE", 2)}</td>
                    <td className="num">{numberCell(row, "RMSE", 2)}</td>
                    <td>{cell(row, "Verdict")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="fc-table-wrap">
            <table className="fc-table">
              <caption>
                Seven ways to build the band. The deployed method is not the most accurate one: a
                gradient booster scored a lower average error and delivered a band that held far
                less often than it promised.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Method</th>
                  <th scope="col">Coverage</th>
                  <th scope="col">Band width</th>
                  <th scope="col">Average error</th>
                  <th scope="col">Note</th>
                </tr>
              </thead>
              <tbody>
                {model.interval_methods.map((row) => {
                  const method = String(row["method"] ?? "");
                  return (
                    <tr key={method} className={method.includes("DEPLOYED") ? "fc-row-current" : ""}>
                      <th scope="row">{method}</th>
                      <td className="num">
                        {typeof row["coverage"] === "number"
                          ? percent(row["coverage"], 2)
                          : cell(row, "coverage")}
                      </td>
                      <td className="num">{numberCell(row, "median_band", 1)}</td>
                      <td className="num">{numberCell(row, "MAE_of_median", 2)}</td>
                      <td>{cell(row, "note") === "" ? "-" : cell(row, "note")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <section className="fc-panel">
            <header>
              <span>Known limitations, in the model card's own words</span>
              <h3>What the people who built this wrote down about it</h3>
            </header>
            <ul className="fc-limit-list">
              {model.limitations.map((item) => (
                <li key={item}>
                  <AlertTriangle size={15} aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="fc-panel">
            <header>
              <span>Where the data came from</span>
              <h3>{model.dataset.dataset}</h3>
              <p>{model.dataset.population}</p>
            </header>
            <ul className="fc-plain-list">
              <li>
                <strong>What one row is</strong>
                <span>{model.dataset.grain}</span>
              </li>
              <li>
                <strong>Training window</strong>
                <span>
                  {longWeek(model.dataset.training_window[0])} to{" "}
                  {longWeek(model.dataset.training_window[1])}, split in time and never shuffled.
                  The held-out weeks come after the training weeks, the way a real week does.
                </span>
              </li>
              <li>
                <strong>License and citation</strong>
                <span>
                  {model.dataset.license}, DOI {model.dataset.doi}. {model.dataset.citation}
                </span>
              </li>
              <li>
                <strong>Source</strong>
                <span>
                  <a
                    className="fc-source-link"
                    href={model.dataset.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {model.dataset.url}
                  </a>
                </span>
              </li>
              <li>
                <strong>Monitoring</strong>
                <span>{model.monitoring}</span>
              </li>
              <li>
                <strong>If a product falls outside the cohort</strong>
                <span>{model.policy.fallback}</span>
              </li>
            </ul>
          </section>

          <div className="fc-assumption-note" role="note">
            <AlertTriangle size={17} aria-hidden="true" />
            <p>
              <strong>The dollars are made up, and deliberately so.</strong>{" "}
              {model.policy.cost_assumption_note}
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}
