import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Clock,
  Database,
  Gauge,
  Info,
  Layers3,
  RefreshCcw,
  Scale,
  SlidersHorizontal,
  Wrench,
} from "lucide-react";
import {
  getMaintenanceModel,
  getMaintenanceQueue,
  getMaintenanceSamples,
  scoreMaintenanceWindow,
  type MaintenanceHourScore,
  type MaintenanceModelInfo,
  type MaintenanceQueue,
  type MaintenanceSampleWindow,
  type MaintenanceTableRow,
  type MaintenanceWindowScore,
} from "../maintenanceApi";
import { navigate } from "../router";

/* Page styles live here, not in index.css, because this component had to ship as a
   single file. Every rule is prefixed .mnt-, so the block can be moved into
   index.css verbatim and this <style> element deleted, with no other change. */
const pageStyles = `
.mnt-page { width: min(1560px, 100%); --mnt-body: 13px; --mnt-support: 12px; --mnt-label: 10px; --mnt-alert: var(--red); --mnt-watch: var(--amber); --mnt-quiet: #6abf9b; }
.mnt-page .page-back-button { min-height: 44px; font-size: 11px; }
.mnt-page table { width: 100%; border-collapse: collapse; }
.mnt-page .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }

.mnt-header { min-height: 82px; margin-bottom: 14px; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.mnt-header h1 { margin: 3px 0 6px; font-size: 29px; line-height: 1.2; }
.mnt-header p { max-width: 920px; margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.55; }
.mnt-runtime-status { min-width: 262px; padding: 11px 13px; display: flex; align-items: center; gap: 10px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.mnt-runtime-status > span { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--amber); box-shadow: 0 0 0 4px rgba(240, 180, 41, 0.1); }
.mnt-runtime-status > span.ready { background: var(--green); box-shadow: 0 0 0 4px rgba(74, 222, 128, 0.1); }
.mnt-runtime-status strong, .mnt-runtime-status small { display: block; }
.mnt-runtime-status strong { font-size: var(--mnt-body); }
.mnt-runtime-status small { margin-top: 3px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--mnt-label); line-height: 1.4; }

.mnt-boundary-line { min-height: 49px; margin-bottom: 14px; padding: 10px 14px; display: grid; grid-template-columns: 20px auto minmax(0, 1fr); align-items: center; gap: 10px; border-top: 1px solid rgba(126, 174, 184, 0.45); border-bottom: 1px solid rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.06); color: var(--teal); }
.mnt-boundary-line strong { font-size: var(--mnt-support); }
.mnt-boundary-line span { color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.45; }

.mnt-metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: 15px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.mnt-metric-strip > div { min-width: 0; min-height: 88px; padding: 13px 17px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.mnt-metric-strip > div:last-child { border-right: 0; }
.mnt-metric-strip strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 21px; }
.mnt-metric-strip span { margin-top: 3px; color: var(--text-secondary); font-size: var(--mnt-support); }
.mnt-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.4; }

.mnt-view-switcher { min-height: 66px; margin-bottom: 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.mnt-view-switcher button { min-width: 0; min-height: 64px; padding: 10px 15px; display: flex; align-items: center; gap: 10px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.mnt-view-switcher button:last-child { border-right: 0; }
.mnt-view-switcher button:hover, .mnt-view-switcher button.active { background: var(--surface-raised); color: var(--orange); }
.mnt-view-switcher button.active { box-shadow: inset 0 -3px 0 var(--orange); }
.mnt-view-switcher button:focus-visible { outline-offset: -3px; }
.mnt-view-switcher strong, .mnt-view-switcher small { display: block; }
.mnt-view-switcher strong { color: var(--text); font-size: 14px; }
.mnt-view-switcher small { margin-top: 3px; font-size: 11px; }

.mnt-workspace { display: grid; grid-template-columns: minmax(250px, 0.36fr) minmax(400px, 1.1fr) minmax(330px, 0.72fr); border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.mnt-workspace > * { min-width: 0; }
.mnt-window-browser, .mnt-plot-panel { border-right: 1px solid var(--border); }
.mnt-workspace > section > header, .mnt-window-browser > header { min-height: 74px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); }
.mnt-workspace header span.step { color: var(--orange); font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-workspace header strong { display: block; margin-top: 3px; font-size: var(--mnt-body); }
.mnt-workspace header small { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.4; }
.mnt-window-list { max-height: 700px; overflow-y: auto; }
.mnt-window-list button { width: 100%; min-height: 96px; padding: 11px 13px; display: block; border: 0; border-bottom: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; }
.mnt-window-list button:hover, .mnt-window-list button.active { background: var(--surface-raised); box-shadow: inset 3px 0 0 var(--orange); }
.mnt-window-list button:focus-visible { outline-offset: -3px; }
.mnt-window-list button > span, .mnt-window-list button > strong, .mnt-window-list button > small { display: block; }
.mnt-window-list button > span.tag { color: var(--teal); font-size: var(--mnt-label); line-height: 1.4; }
.mnt-window-list button > span.tag.failure { color: var(--red); }
.mnt-window-list button > strong { margin-top: 4px; color: var(--text); font-size: var(--mnt-support); line-height: 1.4; }
.mnt-window-list button > small { margin-top: 5px; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.5; }
.mnt-window-list button > span.peak { margin-top: 6px; color: var(--text-secondary); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--mnt-label); }
.mnt-list-empty { padding: 26px 14px; color: var(--text-muted); font-size: var(--mnt-support); line-height: 1.6; }

.mnt-plot-panel, .mnt-reading-panel { display: flex; flex-direction: column; }
/* Children of a column flex container shrink by default; anything with its own
   scroll area would silently lose height and clip. Nothing here shrinks. */
.mnt-plot-panel > *, .mnt-reading-panel > * { flex: 0 0 auto; }
.mnt-purpose-note { padding: 11px 14px; display: flex; gap: 9px; border-bottom: 1px solid var(--border); background: rgba(126, 174, 184, 0.05); color: var(--teal); }
.mnt-purpose-note p { margin: 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-chart-scroll { padding: 12px 14px 0; overflow-x: auto; }
.mnt-chart svg { display: block; width: 100%; min-width: 540px; height: 300px; }
.mnt-chart .axis { stroke: var(--border); stroke-width: 1; }
.mnt-chart .grid { stroke: var(--border); stroke-width: 1; stroke-dasharray: 2 4; }
.mnt-chart .tick { fill: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.mnt-chart .series { fill: none; stroke: var(--teal); stroke-width: 2; stroke-linejoin: round; }
.mnt-chart .callout-line { stroke: var(--red); stroke-width: 1.6; stroke-dasharray: 6 4; }
.mnt-chart .watch-line { stroke: var(--amber); stroke-width: 1.3; stroke-dasharray: 3 4; }
.mnt-chart .callout-label { fill: var(--red); font-family: var(--font-mono); font-size: 10px; }
.mnt-chart .watch-label { fill: var(--amber); font-family: var(--font-mono); font-size: 10px; }
.mnt-chart .alert-dot { fill: var(--red); stroke: #12151b; stroke-width: 1.2; }
.mnt-chart .peak-mark { fill: none; stroke: var(--orange); stroke-width: 1.6; }
.mnt-chart .peak-label { fill: var(--orange); font-family: var(--font-mono); font-size: 10px; }
.mnt-chart .band-alert { fill: rgba(228, 90, 88, 0.08); }
.mnt-chart .band-watch { fill: rgba(240, 180, 41, 0.07); }
.mnt-chart-legend { margin: 8px 0 0; padding: 0 14px 12px; display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--text-muted); font-size: var(--mnt-label); }
.mnt-chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.mnt-chart-legend i { display: inline-block; width: 14px; height: 0; flex: 0 0 auto; border-top: 2px solid var(--teal); }
.mnt-chart-legend i.callout { border-top: 2px dashed var(--red); }
.mnt-chart-legend i.watch { border-top: 2px dashed var(--amber); }
.mnt-chart-legend i.dot { width: 8px; height: 8px; border: 0; border-radius: 50%; background: var(--red); }

.mnt-threshold-control { padding: 13px 14px; border-top: 1px solid var(--border); background: #14161c; }
.mnt-threshold-control > span { color: var(--orange); font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-threshold-control > strong { display: block; margin-top: 4px; font-size: var(--mnt-body); }
.mnt-threshold-control label { display: block; margin-top: 10px; }
.mnt-threshold-control label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--mnt-support); }
.mnt-threshold-control output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.mnt-page input[type="range"] { width: 100%; height: 44px; padding: 0; border: 0; background: transparent; box-shadow: none; accent-color: var(--orange); }
.mnt-scale-row { display: flex; justify-content: space-between; gap: 12px; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--mnt-label); }
.mnt-control-status { min-height: 17px; margin: 8px 0 0; color: var(--teal); font-family: var(--font-mono); font-size: var(--mnt-label); }
.mnt-control-actions { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
.mnt-control-actions .secondary-button { min-height: 44px; }

.mnt-route-band { margin: 14px 14px 0; padding: 12px 13px; display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 10px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.mnt-route-band.work_order { border-color: rgba(228, 90, 88, 0.5); color: var(--mnt-alert); }
.mnt-route-band.watch { border-color: rgba(240, 180, 41, 0.5); color: var(--mnt-watch); }
.mnt-route-band.no_action { border-color: rgba(106, 191, 155, 0.42); color: var(--mnt-quiet); }
.mnt-route-band span { display: block; color: var(--text-muted); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-route-band strong { display: block; margin-top: 4px; font-size: 15px; }
.mnt-route-band p { margin: 6px 0 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-hour-counts { margin: 12px 14px 14px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.mnt-hour-counts > div { min-width: 0; min-height: 74px; padding: 11px 12px; display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
.mnt-hour-counts strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 18px; }
.mnt-hour-counts span { margin-top: 3px; color: var(--text-secondary); font-size: var(--mnt-label); line-height: 1.4; }
.mnt-hour-table { margin: 0 14px 14px; }
.mnt-hour-table summary { min-height: 44px; padding: 11px 12px; display: flex; align-items: center; border: 1px solid var(--border); border-radius: 6px; background: var(--surface-raised); color: var(--text-secondary); font-size: var(--mnt-support); }
.mnt-hour-table summary:focus-visible { outline-offset: 2px; }
.mnt-hour-table > div { max-height: 300px; margin-top: 8px; border: 1px solid var(--border); border-radius: 6px; overflow: auto; }

.mnt-reading-panel { padding-bottom: 14px; }
.mnt-reading-body { padding: 14px; display: grid; gap: 10px; }
.mnt-reading-row { padding: 11px 12px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.mnt-reading-row.quiet { opacity: 0.75; }
.mnt-reading-row > div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.mnt-reading-row b { color: var(--text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--mnt-label); font-weight: 500; }
.mnt-reading-row strong { color: var(--text); font-size: var(--mnt-support); line-height: 1.4; }
.mnt-reading-row p { margin: 6px 0 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.5; }
.mnt-reading-row em { display: block; margin-top: 5px; color: var(--text-muted); font-size: var(--mnt-label); font-style: normal; line-height: 1.5; }
.mnt-reading-track { height: 6px; margin-top: 8px; border-radius: 3px; background: var(--surface-raised); overflow: hidden; }
.mnt-reading-track i { display: block; height: 100%; background: var(--orange); }
.mnt-authority { margin: 0 14px; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border-left: 3px solid var(--teal); background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.mnt-authority span { display: block; font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-authority p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-panel-empty { min-height: 240px; padding: 22px; display: grid; place-content: center; justify-items: center; gap: 8px; color: var(--text-muted); text-align: center; }
.mnt-panel-empty p { margin: 0; max-width: 320px; font-size: var(--mnt-support); line-height: 1.6; }

.mnt-section-heading { margin-bottom: 14px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.mnt-section-heading span { color: var(--orange); font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-section-heading h2 { margin: 5px 0 5px; font-size: 20px; }
.mnt-section-heading p { margin: 0; max-width: 920px; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.6; }
.mnt-section-heading > strong { display: inline-flex; align-items: center; gap: 7px; padding: 8px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--mnt-label); white-space: nowrap; }
.mnt-assumption-note { margin-bottom: 14px; padding: 10px 12px; display: flex; gap: 9px; border-left: 3px solid var(--amber); background: rgba(240, 180, 41, 0.07); color: var(--amber); }
.mnt-assumption-note p { margin: 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-assumption-note strong { color: var(--amber); }

.mnt-panel { margin-bottom: 14px; padding: 15px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.mnt-panel > header { margin-bottom: 12px; }
.mnt-panel > header span { color: var(--orange); font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-panel > header h3 { margin: 5px 0 0; font-size: 15px; }
.mnt-panel > header p { margin: 6px 0 0; max-width: 920px; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.6; }

.mnt-workload-control { margin-bottom: 14px; padding: 14px; display: grid; grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr); gap: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.mnt-workload-control > div { min-width: 0; }
.mnt-workload-control label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; color: var(--text-secondary); font-size: var(--mnt-support); }
.mnt-workload-control output { color: var(--orange); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 17px; }
.mnt-workload-help { margin: 8px 0 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }

.mnt-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.mnt-summary-grid > div { min-width: 0; min-height: 96px; padding: 13px 15px; display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
.mnt-summary-grid strong { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 20px; }
.mnt-summary-grid span { margin-top: 4px; color: var(--text-secondary); font-size: var(--mnt-support); }
.mnt-summary-grid small { margin-top: 3px; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.45; }

.mnt-table-wrap { margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow-x: auto; }
.mnt-table { min-width: 640px; }
.mnt-table caption { padding: 12px 14px; color: var(--text-secondary); font-size: var(--mnt-support); text-align: left; }
.mnt-table th, .mnt-table td { padding: 11px 14px; border-bottom: 1px solid var(--border); font-size: var(--mnt-support); text-align: left; vertical-align: top; }
.mnt-table thead th { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--mnt-label); font-weight: 500; text-transform: uppercase; white-space: nowrap; }
.mnt-table tbody th { color: var(--text); font-weight: 600; }
.mnt-table tbody tr:last-child th, .mnt-table tbody tr:last-child td { border-bottom: 0; }
.mnt-table td span { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.45; }
.mnt-row-current th, .mnt-row-current td { background: rgba(232, 145, 60, 0.08); }
.mnt-tag { display: inline-flex; align-items: center; gap: 5px; padding: 4px 7px; border: 1px solid var(--border-strong); border-radius: 3px; color: var(--text-secondary); font-size: var(--mnt-label); white-space: nowrap; }
.mnt-tag.good { border-color: rgba(106, 191, 155, 0.45); color: var(--mnt-quiet); }
.mnt-tag.bad { border-color: rgba(228, 90, 88, 0.45); color: var(--red); }
.mnt-tag.warn { border-color: rgba(240, 180, 41, 0.5); color: var(--amber); }

.mnt-month-bars { display: grid; gap: 10px; }
.mnt-month-row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 116px; align-items: center; gap: 12px; }
.mnt-month-row > b { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--mnt-support); font-weight: 500; line-height: 1.4; }
.mnt-month-track { display: block; height: 22px; border-radius: 3px; background: var(--surface-raised); overflow: hidden; }
.mnt-month-track i { display: block; height: 100%; min-width: 2px; background: var(--orange); }
.mnt-month-row > span { color: var(--text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: var(--mnt-label); text-align: right; }
.mnt-drift-callout { margin-top: 12px; padding: 11px 12px; display: flex; align-items: flex-start; gap: 10px; border: 1px solid rgba(240, 180, 41, 0.4); border-radius: 6px; background: rgba(240, 180, 41, 0.06); color: var(--amber); }
.mnt-drift-callout p { margin: 0; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }

.mnt-pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.mnt-pair > div { min-width: 0; padding: 13px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.mnt-pair > div.failure { border-color: rgba(228, 90, 88, 0.42); }
.mnt-pair > div.healthy { border-color: rgba(106, 191, 155, 0.42); }
.mnt-pair span { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-pair strong { display: block; margin-top: 5px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 26px; }
.mnt-pair b { display: block; margin-top: 5px; color: var(--text); font-size: var(--mnt-support); font-weight: 600; line-height: 1.4; }
.mnt-pair small { display: block; margin-top: 5px; color: var(--text-secondary); font-size: var(--mnt-label); line-height: 1.5; }
.mnt-pair-scale { margin-top: 12px; padding: 12px 13px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.mnt-pair-scale > div { display: grid; grid-template-columns: 150px minmax(0, 1fr); align-items: center; gap: 12px; margin-bottom: 8px; }
.mnt-pair-scale b { display: block; color: var(--text-secondary); font-size: var(--mnt-label); font-weight: 500; line-height: 1.4; }
.mnt-pair-track { position: relative; display: block; height: 20px; border-radius: 3px; background: var(--surface-raised); }
.mnt-pair-track i { display: block; height: 100%; border-radius: 3px; background: var(--teal); }
.mnt-pair-track i.failure { background: var(--red); }
.mnt-pair-track u { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--orange); text-decoration: none; }
.mnt-pair-scale p { margin: 4px 0 0; color: var(--text-muted); font-size: var(--mnt-label); line-height: 1.5; }

.mnt-fact-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--border); overflow: hidden; }
.mnt-fact-grid > div { min-width: 0; min-height: 112px; padding: 13px 15px; background: var(--surface); color: var(--teal); }
.mnt-fact-grid span { display: block; margin-top: 8px; color: var(--text-muted); font-size: var(--mnt-label); text-transform: uppercase; }
.mnt-fact-grid strong { display: block; margin-top: 4px; color: var(--text); font-size: var(--mnt-body); line-height: 1.35; }
.mnt-fact-grid small { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--mnt-label); line-height: 1.5; }
.mnt-limit-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 9px; }
.mnt-limit-list li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 10px; align-items: start; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-limit-list li > svg { margin-top: 1px; color: var(--amber); }
.mnt-plain-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
.mnt-plain-list li { padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; background: #14161c; }
.mnt-plain-list li strong { display: block; font-size: var(--mnt-support); }
.mnt-plain-list li span { display: block; margin-top: 4px; color: var(--text-secondary); font-size: var(--mnt-support); line-height: 1.55; }
.mnt-source-link { color: var(--teal); overflow-wrap: anywhere; font-size: var(--mnt-support); }

@media (max-width: 1180px) {
  .mnt-workspace { grid-template-columns: minmax(230px, 0.36fr) minmax(0, 1fr); }
  .mnt-plot-panel { border-right: 0; }
  .mnt-reading-panel { grid-column: 1 / -1; border-top: 1px solid var(--border); }
  .mnt-metric-strip, .mnt-summary-grid, .mnt-fact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mnt-workload-control { grid-template-columns: minmax(0, 1fr); }
  .mnt-pair { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 760px) {
  .mnt-header { flex-direction: column; }
  .mnt-header h1 { font-size: 23px; }
  .mnt-runtime-status { width: 100%; }
  .mnt-boundary-line { grid-template-columns: 20px minmax(0, 1fr); }
  .mnt-boundary-line span { grid-column: 1 / -1; }
  .mnt-metric-strip, .mnt-summary-grid, .mnt-fact-grid, .mnt-hour-counts { grid-template-columns: minmax(0, 1fr); }
  .mnt-view-switcher { grid-template-columns: minmax(0, 1fr); }
  .mnt-view-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .mnt-view-switcher button:last-child { border-bottom: 0; }
  .mnt-workspace { grid-template-columns: minmax(0, 1fr); }
  .mnt-window-browser, .mnt-plot-panel { border-right: 0; border-bottom: 1px solid var(--border); }
  .mnt-window-list { max-height: 340px; }
  .mnt-reading-panel { border-top: 0; }
  .mnt-section-heading { flex-direction: column; align-items: flex-start; }
  .mnt-month-row { grid-template-columns: 80px minmax(0, 1fr); }
  .mnt-month-row > span { grid-column: 1 / -1; text-align: left; }
  .mnt-pair-scale > div { grid-template-columns: minmax(0, 1fr); }
}
`;

type View = "window" | "workload" | "card";

const views = [
  {
    id: "window" as const,
    label: "Inspect one hour-by-hour window",
    detail: "The score, the sensors, the decision",
    icon: Activity,
  },
  {
    id: "workload" as const,
    label: "The alert workload",
    detail: "Move the callout line, see the queue",
    icon: SlidersHorizontal,
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

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);

const money = (value: number) => `$${Math.round(value).toLocaleString("en-US")}`;

const count = (value: number, digits = 0) =>
  value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/* "2020-04-18 02:00:00" -> "Apr 18, 02:00". The API hands back the notebook's own
   timestamp strings, so they are split rather than parsed into a local Date, which
   would shift every hour by the reader's time zone. */
const shortHour = (stamp: string) => {
  const [date, time = ""] = stamp.split(" ");
  const [, month, day] = date.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? month;
  return `${name} ${Number(day)}, ${time.slice(0, 5)}`;
};

const shortDate = (stamp: string) => {
  const [date] = stamp.split(" ");
  const [year, month, day] = date.split("-");
  const name = MONTH_NAMES[Number(month) - 1] ?? month;
  return `${name} ${Number(day)}, ${year}`;
};

const monthName = (period: string) => {
  const [year, month] = period.split("-");
  return `${MONTH_NAMES[Number(month) - 1] ?? month} ${year}`;
};

const cell = (row: MaintenanceTableRow, key: string) => {
  const value = row[key];
  if (value === null || value === undefined) return "-";
  return typeof value === "number" ? count(value, Number.isInteger(value) ? 0 : 2) : value;
};

type ChartProps = {
  hours: MaintenanceHourScore[];
  threshold: number;
  watchThreshold: number;
  peakAt: string;
  peakScore: number;
};

/* The window's score, hour by hour, against the line that turns it into a callout.
   Nothing here is decided by color alone: the callout line and the watch line are
   labeled on the plot, and every alerting hour is drawn as a dot, which is a shape. */
function ScoreChart({ hours, threshold, watchThreshold, peakAt, peakScore }: ChartProps) {
  const width = 760;
  const height = 300;
  const left = 42;
  const right = 96;
  const top = 20;
  const bottom = 46;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  if (hours.length === 0) {
    return (
      <p className="mnt-list-empty">
        No hour in this window had enough sensor data to score, so there is nothing to plot.
      </p>
    );
  }

  const highest = Math.max(
    peakScore,
    hours.reduce((most, hour) => Math.max(most, hour.score), 0),
  );
  const yMax = Math.max(highest * 1.12, threshold * 1.3, 4);
  const step = yMax <= 6 ? 2 : yMax <= 15 ? 3 : 5;
  const ticks: number[] = [];
  for (let value = 0; value <= yMax; value += step) ticks.push(value);

  const x = (index: number) =>
    left + (hours.length <= 1 ? plotWidth / 2 : (index / (hours.length - 1)) * plotWidth);
  const y = (value: number) => top + plotHeight - (Math.min(value, yMax) / yMax) * plotHeight;

  const series = hours.map((hour, index) => `${x(index).toFixed(1)},${y(hour.score).toFixed(1)}`);
  const alerting = hours
    .map((hour, index) => ({ hour, index }))
    .filter((entry) => entry.hour.alerts);
  const peakIndex = hours.findIndex((hour) => hour.hour === peakAt);
  const peak = peakIndex >= 0 ? hours[peakIndex] : null;
  const labelPositions = hours.length <= 1
    ? [0]
    : [0, Math.floor((hours.length - 1) / 2), hours.length - 1];

  const summary =
    `Hourly score for ${hours.length} hours, from ${shortHour(hours[0].hour)} to ` +
    `${shortHour(hours[hours.length - 1].hour)}. The highest hour scores ${highest.toFixed(2)}. ` +
    `${alerting.length} hours reach the callout line of ${threshold}.`;

  return (
    <div className="mnt-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
        <title>{summary}</title>
        <rect className="band-alert" x={left} y={top} width={plotWidth} height={Math.max(0, y(threshold) - top)} />
        <rect
          className="band-watch"
          x={left}
          y={y(threshold)}
          width={plotWidth}
          height={Math.max(0, y(watchThreshold) - y(threshold))}
        />
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={left} y1={y(tick)} x2={left + plotWidth} y2={y(tick)} />
            <text className="tick" x={left - 8} y={y(tick) + 3.5} textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        <line className="axis" x1={left} y1={top + plotHeight} x2={left + plotWidth} y2={top + plotHeight} />
        <line className="axis" x1={left} y1={top} x2={left} y2={top + plotHeight} />

        <line className="watch-line" x1={left} y1={y(watchThreshold)} x2={left + plotWidth} y2={y(watchThreshold)} />
        <text className="watch-label" x={left + plotWidth + 8} y={y(watchThreshold) + 3.5}>
          Watch {watchThreshold}
        </text>
        <line className="callout-line" x1={left} y1={y(threshold)} x2={left + plotWidth} y2={y(threshold)} />
        <text className="callout-label" x={left + plotWidth + 8} y={y(threshold) + 3.5}>
          Callout {threshold}
        </text>

        <polyline className="series" points={series.join(" ")} />
        {alerting.map((entry) => (
          <circle
            className="alert-dot"
            key={entry.hour.hour}
            cx={x(entry.index)}
            cy={y(entry.hour.score)}
            r={4}
          />
        ))}
        {peak ? (
          <g>
            <circle className="peak-mark" cx={x(peakIndex)} cy={y(peak.score)} r={8} />
            <text
              className="peak-label"
              x={clamp(x(peakIndex), left + 30, left + plotWidth - 30)}
              y={Math.max(top + 10, y(peak.score) - 14)}
              textAnchor="middle"
            >
              highest hour {peakScore.toFixed(2)}
            </text>
          </g>
        ) : null}

        {labelPositions.map((index) => (
          <text
            className="tick"
            key={`label-${index}`}
            x={clamp(x(index), left, left + plotWidth)}
            y={top + plotHeight + 20}
            textAnchor={index === 0 ? "start" : index === hours.length - 1 ? "end" : "middle"}
          >
            {shortHour(hours[index].hour)}
          </text>
        ))}
        <text className="tick" x={left} y={top + plotHeight + 38}>
          One point per clock hour. Hours with too little sensor data are not scored and are not plotted.
        </text>
      </svg>
    </div>
  );
}

export default function MaintenancePage() {
  const [view, setView] = useState<View>("window");
  const [model, setModel] = useState<MaintenanceModelInfo | null>(null);
  const [windows, setWindows] = useState<MaintenanceSampleWindow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [windowScore, setWindowScore] = useState<MaintenanceWindowScore | null>(null);
  const [windowThreshold, setWindowThreshold] = useState<number | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queue, setQueue] = useState<MaintenanceQueue | null>(null);
  const [queueThreshold, setQueueThreshold] = useState<number | null>(null);
  const [queueBusy, setQueueBusy] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [queueAttempt, setQueueAttempt] = useState(0);
  const skipFirstQueueFetch = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getMaintenanceModel(), getMaintenanceSamples(24), getMaintenanceQueue()])
      .then(async ([modelInfo, packaged, workload]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setWindows(packaged);
        setQueue(workload);
        skipFirstQueueFetch.current = true;
        setQueueThreshold(workload.threshold);
        setWindowThreshold(modelInfo.policy.threshold);
        const first = packaged.find((entry) => entry.covers_documented_failure) ?? packaged[0];
        if (!first) return;
        setSelectedId(first.sample_id);
        const initial = await scoreMaintenanceWindow(first.sample_id);
        if (cancelled) return;
        setWindowScore(initial);
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The workload control refetches the queue. The first run is skipped because the
  // initial load already carries the queue at the frozen operating threshold.
  useEffect(() => {
    if (queueThreshold === null) return;
    if (skipFirstQueueFetch.current) {
      skipFirstQueueFetch.current = false;
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setQueueBusy(true);
      getMaintenanceQueue(queueThreshold)
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
  }, [queueThreshold, queueAttempt]);

  const policyThreshold = model?.policy.threshold ?? 6;
  const watchThreshold = model?.policy.watch_threshold ?? 3;

  const runScore = (windowId: string, threshold: number) => {
    setScoring(true);
    setScoreError(null);
    void scoreMaintenanceWindow(windowId, threshold)
      .then((result) => setWindowScore(result))
      .catch((reason: Error) => setScoreError(reason.message))
      .finally(() => setScoring(false));
  };

  const chooseWindow = (entry: MaintenanceSampleWindow) => {
    setSelectedId(entry.sample_id);
    setWindowScore(null);
    runScore(entry.sample_id, windowThreshold ?? policyThreshold);
  };

  const changeWindowThreshold = (value: number) => {
    const next = clamp(Math.round(value * 2) / 2, 1, 14);
    setWindowThreshold(next);
    if (selectedId) runScore(selectedId, next);
  };

  const discussion = model?.discussion_case ?? null;
  const healthyWindow = discussion
    ? windows.find((entry) => entry.sample_id === discussion.healthy_window_id) ?? null
    : null;
  const failureWindow = discussion
    ? windows.find((entry) => entry.sample_id === discussion.failure_window_id) ?? null
    : null;
  const pairScale = discussion
    ? Math.max(discussion.healthy_peak_score, discussion.failure_peak_score) * 1.15
    : 1;

  const busiestLoad = queue
    ? queue.monthly_load.reduce((most, row) => Math.max(most, row.alert_hours), 0)
    : 0;

  return (
    <div className="page mnt-page">
      <style>{pageStyles}</style>

      <button
        className="page-back-button"
        type="button"
        onClick={() => navigate("/showcase?industry=manufacturing")}
      >
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="mnt-header">
        <div>
          <span className="eyebrow">Condition monitoring - maintenance planning</span>
          <h1>Compressor Air-leak Detection</h1>
          <p>
            An air compressor on a passenger train reports its sensors every few seconds. This tool
            scores each clock hour by how far it sits from the machine's own quiet-months normal, so
            a maintenance planner can decide which hours are worth a technician's time.
          </p>
        </div>
        <div className="mnt-runtime-status">
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

      <div className="mnt-boundary-line" role="note">
        <Scale size={17} aria-hidden="true" />
        <strong>Where this system's authority stops</strong>
        <span>
          It detects a fault developing now, within hours. It does not forecast days ahead, and it
          never locks out equipment or declares a machine safe to work on. A technician inspects the
          compressor and decides what happens next.
        </span>
      </div>

      {model ? (
        <section className="mnt-metric-strip" aria-label="Results on the frozen test window">
          <div>
            <strong>{count(model.frozen_test.alert_hours)}</strong>
            <span>hours raised an alert in the test window</span>
            <small>
              {shortDate(model.frozen_test.window[0])} to {shortDate(model.frozen_test.window[1])},
              scored once
            </small>
          </div>
          <div>
            <strong>{(model.frozen_test.false_alarm_rate_on_clean_hours * 100).toFixed(2)}%</strong>
            <span>of healthy hours raised a false alarm</span>
            <small>
              {count(model.frozen_test.false_alarm_hours)} hours out of{" "}
              {count(model.frozen_test.clean_hours)} with nothing wrong
            </small>
          </div>
          <div>
            <strong>{count(model.frozen_test.false_callouts_per_month, 2)}</strong>
            <span>wasted callouts per month</span>
            <small>A technician drove out and found nothing</small>
          </div>
          <div>
            <strong>
              {model.frozen_test.lead_hours === null
                ? "none"
                : `${count(model.frozen_test.lead_hours, 1)} h`}
            </strong>
            <span>warning before the one failure it caught early</span>
            <small>Three of the four documented failures gave no warning at all</small>
          </div>
        </section>
      ) : null}

      <nav className="mnt-view-switcher" aria-label="Predictive maintenance views">
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
          The maintenance service did not answer: {loadError}
        </div>
      ) : null}
      {!model && !loadError ? (
        <div className="loading-state">Loading the model and the packaged sensor windows...</div>
      ) : null}

      {view === "window" && model ? (
        <>
          <section className="mnt-workspace">
            <aside className="mnt-window-browser">
              <header>
                <div>
                  <span className="step">Step 1</span>
                  <strong>Choose a window</strong>
                  <small>Packaged stretches of real sensor history</small>
                </div>
              </header>
              {windows.length === 0 ? (
                <p className="mnt-list-empty">
                  No packaged windows came back from the service. Rebuild the notebook artifacts and
                  reload this page.
                </p>
              ) : (
                <div className="mnt-window-list">
                  {windows.map((entry) => (
                    <button
                      type="button"
                      key={entry.sample_id}
                      className={selectedId === entry.sample_id ? "active" : ""}
                      aria-pressed={selectedId === entry.sample_id}
                      onClick={() => chooseWindow(entry)}
                    >
                      <span className={entry.covers_documented_failure ? "tag failure" : "tag"}>
                        {entry.covers_documented_failure
                          ? "A repair report was filed"
                          : "No repair report filed"}
                      </span>
                      <strong>{entry.label}</strong>
                      <small>{entry.purpose}</small>
                      <span className="peak">
                        Highest hour {entry.peak_score.toFixed(2)} - {count(entry.hours_with_data)}{" "}
                        hours
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </aside>

            <section className="mnt-plot-panel">
              <header>
                <div>
                  <span className="step">Step 2</span>
                  <strong>Read the hours</strong>
                  <small>Every clock hour, against the callout line</small>
                </div>
                <Gauge size={19} aria-hidden="true" />
              </header>

              {scoreError ? (
                <div className="error-banner" role="alert">
                  This window could not be scored: {scoreError}
                  <div className="mnt-control-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() =>
                        selectedId ? runScore(selectedId, windowThreshold ?? policyThreshold) : null
                      }
                    >
                      <RefreshCcw size={15} aria-hidden="true" /> Try again
                    </button>
                  </div>
                </div>
              ) : null}

              {!windowScore && !scoreError ? (
                <div className="mnt-panel-empty">
                  <Activity size={30} aria-hidden="true" />
                  <p>Choose a window on the left to plot its hours.</p>
                </div>
              ) : null}

              {windowScore ? (
                <>
                  <div className="mnt-purpose-note">
                    <Info size={16} aria-hidden="true" />
                    <p>
                      {windowScore.purpose} Covering {shortHour(windowScore.start)} to{" "}
                      {shortHour(windowScore.end)}.
                    </p>
                  </div>

                  <div className="mnt-chart-scroll" aria-busy={scoring}>
                    <ScoreChart
                      hours={windowScore.hours}
                      threshold={windowScore.threshold}
                      watchThreshold={watchThreshold}
                      peakAt={windowScore.peak_at}
                      peakScore={windowScore.peak_score}
                    />
                  </div>
                  <p className="mnt-chart-legend">
                    <span>
                      <i /> hourly score
                    </span>
                    <span>
                      <i className="callout" /> callout line at {windowScore.threshold}
                    </span>
                    <span>
                      <i className="watch" /> watch line at {watchThreshold}
                    </span>
                    <span>
                      <i className="dot" /> an hour that raises a work order
                    </span>
                  </p>

                  <div className={`mnt-route-band ${windowScore.route_at_peak}`} role="status">
                    {windowScore.route_at_peak === "work_order" ? (
                      <AlertTriangle size={18} aria-hidden="true" />
                    ) : windowScore.route_at_peak === "watch" ? (
                      <Clock size={18} aria-hidden="true" />
                    ) : (
                      <CheckCircle2 size={18} aria-hidden="true" />
                    )}
                    <div>
                      <span>What happens at the highest hour</span>
                      <strong>{windowScore.route_label}</strong>
                      <p>{windowScore.technician_action}</p>
                      {windowScore.route_changed_by_threshold ? (
                        <p>
                          <strong>This is not what the frozen policy does.</strong> At the policy
                          line of {policyThreshold}, this window raises{" "}
                          {count(windowScore.alert_hours_at_policy)} work-order hours instead of{" "}
                          {count(windowScore.alert_hours)}.
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="mnt-hour-counts">
                    <div>
                      <strong>{count(windowScore.hours_with_data)}</strong>
                      <span>hours with enough sensor data to score</span>
                    </div>
                    <div>
                      <strong>{count(windowScore.alert_hours)}</strong>
                      <span>hours that raise a work order</span>
                    </div>
                    <div>
                      <strong>{count(windowScore.watch_hours)}</strong>
                      <span>hours only written to the shift report</span>
                    </div>
                    <div>
                      <strong>
                        {windowScore.first_alert_hour
                          ? shortHour(windowScore.first_alert_hour)
                          : "none"}
                      </strong>
                      <span>first hour to cross the callout line</span>
                    </div>
                  </div>

                  <details className="mnt-hour-table">
                    <summary>
                      Read the same hours as a table ({count(windowScore.hours_with_data)} rows)
                    </summary>
                    <div>
                      <table className="mnt-table">
                        <caption className="sr-only">
                          Hourly scores for {windowScore.label}
                        </caption>
                        <thead>
                          <tr>
                            <th scope="col">Hour</th>
                            <th scope="col">Score</th>
                            <th scope="col">What happens</th>
                          </tr>
                        </thead>
                        <tbody>
                          {windowScore.hours.map((hour) => (
                            <tr key={hour.hour} className={hour.alerts ? "mnt-row-current" : ""}>
                              <th scope="row" className="num">
                                {shortHour(hour.hour)}
                              </th>
                              <td className="num">{hour.score.toFixed(2)}</td>
                              <td>
                                {hour.route_at_threshold === "work_order"
                                  ? "Work order - a technician is called out"
                                  : hour.route_at_threshold === "watch"
                                    ? "Written to the shift report"
                                    : "Nothing happens"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>

                  <div className="mnt-threshold-control">
                    <span>Try a different callout line</span>
                    <strong>Move the line, and watch the same hours change their meaning</strong>
                    <label htmlFor="mnt-window-threshold">
                      <span>
                        Raise a work order at this score or above
                        <output htmlFor="mnt-window-threshold">
                          {(windowThreshold ?? policyThreshold).toFixed(1)}
                        </output>
                      </span>
                      <input
                        id="mnt-window-threshold"
                        type="range"
                        min={1}
                        max={14}
                        step={0.5}
                        value={windowThreshold ?? policyThreshold}
                        aria-describedby="mnt-window-threshold-help"
                        onChange={(event) => changeWindowThreshold(Number(event.target.value))}
                      />
                    </label>
                    <p className="mnt-scale-row">
                      <span>1 - almost every hour</span>
                      <span>14 - only the very worst</span>
                    </p>
                    <p className="mnt-control-status" role="status">
                      {scoring ? "Rescoring these hours..." : windowScore.threshold_note}
                    </p>
                    <p id="mnt-window-threshold-help" className="mnt-workload-help">
                      The scores never move. Only the line drawn through them moves, and with it the
                      decision about who gets called.
                    </p>
                    {windowScore.threshold_is_override ? (
                      <p className="mnt-control-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => changeWindowThreshold(policyThreshold)}
                        >
                          <RefreshCcw size={15} aria-hidden="true" /> Back to the policy line of{" "}
                          {policyThreshold}
                        </button>
                      </p>
                    ) : null}
                  </div>
                </>
              ) : null}
            </section>

            <section className="mnt-reading-panel" aria-live="polite" aria-busy={scoring}>
              <header>
                <div>
                  <span className="step">Step 3</span>
                  <strong>The sensors behind the score</strong>
                  <small>
                    {windowScore
                      ? `Readings at ${shortHour(windowScore.readings_at)}`
                      : "The highest hour in the window"}
                  </small>
                </div>
                <Wrench size={19} aria-hidden="true" />
              </header>

              {windowScore ? (
                <>
                  <div className="mnt-reading-body">
                    {windowScore.drivers.map((driver) => (
                      <div
                        className={driver.pushes_score_up ? "mnt-reading-row" : "mnt-reading-row quiet"}
                        key={driver.name}
                      >
                        <div>
                          <strong>{driver.display_name}</strong>
                          <b>
                            {driver.pushes_score_up
                              ? `${driver.share_of_score.toFixed(0)}% of the score`
                              : "adds nothing"}
                          </b>
                        </div>
                        <p>{driver.sentence}</p>
                        <em>{driver.planner_question}</em>
                        <div
                          className="mnt-reading-track"
                          aria-hidden="true"
                        >
                          <i style={{ width: `${clamp(driver.share_of_score, 0, 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mnt-authority">
                    <Scale size={17} aria-hidden="true" />
                    <div>
                      <span>What the technician does</span>
                      <p>{windowScore.score_note}</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="mnt-panel-empty">
                  <Wrench size={30} aria-hidden="true" />
                  <p>The six sensor readings appear here once a window is scored.</p>
                </div>
              )}
            </section>
          </section>

          {discussion && healthyWindow && failureWindow ? (
            <section className="mnt-panel" style={{ marginTop: "14px" }}>
              <header>
                <span>Worth arguing about</span>
                <h3>Two hours a hundredth of a point apart</h3>
                <p>{discussion.statement}</p>
              </header>
              <div className="mnt-pair">
                <div className="healthy">
                  <span>Healthy machine, busy day</span>
                  <strong>{discussion.healthy_peak_score.toFixed(2)}</strong>
                  <b>{healthyWindow.label}</b>
                  <small>
                    {healthyWindow.purpose} The strongest reading was {healthyWindow.top_driver_at_peak
                      .toLowerCase()}.
                  </small>
                  <p className="mnt-control-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => chooseWindow(healthyWindow)}
                    >
                      <ArrowRight size={15} aria-hidden="true" /> Plot this window
                    </button>
                  </p>
                </div>
                <div className="failure">
                  <span>A documented air leak</span>
                  <strong>{discussion.failure_peak_score.toFixed(2)}</strong>
                  <b>{failureWindow.label}</b>
                  <small>
                    {failureWindow.purpose} The strongest reading was {failureWindow.top_driver_at_peak
                      .toLowerCase()}.
                  </small>
                  <p className="mnt-control-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => chooseWindow(failureWindow)}
                    >
                      <ArrowRight size={15} aria-hidden="true" /> Plot this window
                    </button>
                  </p>
                </div>
              </div>
              <div className="mnt-pair-scale">
                <div>
                  <b>Healthy busy day</b>
                  <span className="mnt-pair-track">
                    <i style={{ width: `${(discussion.healthy_peak_score / pairScale) * 100}%` }} />
                    <u style={{ left: `${(policyThreshold / pairScale) * 100}%` }} />
                  </span>
                </div>
                <div>
                  <b>Documented air leak</b>
                  <span className="mnt-pair-track">
                    <i
                      className="failure"
                      style={{ width: `${(discussion.failure_peak_score / pairScale) * 100}%` }}
                    />
                    <u style={{ left: `${(policyThreshold / pairScale) * 100}%` }} />
                  </span>
                </div>
                <p>
                  The upright mark on both bars is the callout line at {policyThreshold}. The two
                  bars end {discussion.gap.toFixed(2)} apart, so there is no line you can draw that
                  calls out the leak and leaves the healthy day alone. Raising the line to skip the
                  false alarm also skips the failure.
                </p>
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {view === "workload" && model ? (
        <section aria-label="The alert workload">
          <div className="mnt-section-heading">
            <div>
              <span>View 2</span>
              <h2>What this threshold costs the maintenance team</h2>
              <p>
                Move the callout line and everything below is recomputed over the same{" "}
                {queue ? count(queue.months, 1) : "5"} months of real sensor history: how many
                callouts land on the team, how many technician hours they take, how many of the four
                documented failures get caught, and what it all costs against doing nothing.
              </p>
            </div>
            {queue ? (
              <strong>
                <ClipboardList size={14} aria-hidden="true" /> {count(queue.callouts)} callouts over{" "}
                {count(queue.months, 1)} months
              </strong>
            ) : null}
          </div>

          <div className="mnt-assumption-note" role="note">
            <AlertTriangle size={16} aria-hidden="true" />
            <p>
              <strong>Every dollar figure on this page is a classroom assumption.</strong>{" "}
              {queue ? queue.assumption_note : model.policy.cost_note}
            </p>
          </div>

          {queueError ? (
            <div className="error-banner" role="alert">
              The workload could not be recomputed: {queueError}
              <p className="mnt-control-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setQueueAttempt((attempt) => attempt + 1)}
                >
                  <RefreshCcw size={15} aria-hidden="true" /> Try again
                </button>
              </p>
            </div>
          ) : null}

          <div className="mnt-workload-control">
            <div>
              <label htmlFor="mnt-queue-threshold">
                <span>
                  Raise a work order at this score or above
                  <output htmlFor="mnt-queue-threshold">
                    {(queueThreshold ?? policyThreshold).toFixed(1)}
                  </output>
                </span>
                <input
                  id="mnt-queue-threshold"
                  type="range"
                  min={1}
                  max={14}
                  step={0.5}
                  value={queueThreshold ?? policyThreshold}
                  aria-describedby="mnt-queue-threshold-help"
                  onChange={(event) =>
                    setQueueThreshold(clamp(Math.round(Number(event.target.value) * 2) / 2, 1, 14))
                  }
                />
              </label>
              <p className="mnt-scale-row">
                <span>1 - almost every hour</span>
                <span>14 - only the very worst</span>
              </p>
              <p className="mnt-control-status" role="status">
                {queueBusy
                  ? "Recomputing the workload..."
                  : queue
                    ? queue.threshold_note
                    : "Waiting for the service..."}
              </p>
              {queue && !queue.is_operating_threshold ? (
                <p className="mnt-control-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => setQueueThreshold(policyThreshold)}
                  >
                    <RefreshCcw size={15} aria-hidden="true" /> Back to the policy line of{" "}
                    {policyThreshold}
                  </button>
                </p>
              ) : null}
            </div>
            <div>
              <p id="mnt-queue-threshold-help" className="mnt-workload-help">
                A low line buys warning time and floods the queue with callouts nobody needed. A high
                line keeps the queue quiet and lets faults run. There is no setting that avoids the
                trade: {model.drift.cruel_interaction}
              </p>
            </div>
          </div>

          {!queue ? (
            <div className="loading-state">Working out the alert workload...</div>
          ) : (
            <>
              <div className="mnt-summary-grid" aria-live="polite">
                <div>
                  <strong>{count(queue.alerts_per_month, 2)}</strong>
                  <span>callouts per month</span>
                  <small>
                    {count(queue.callouts)} in total, {count(queue.false_callouts)} of them found
                    nothing wrong
                  </small>
                </div>
                <div>
                  <strong>{count(queue.technician_hours, 1)}</strong>
                  <span>technician hours</span>
                  <small>Two hours per callout, a classroom assumption</small>
                </div>
                <div>
                  <strong>
                    {count(queue.failures_caught)} of {count(queue.failures_total)}
                  </strong>
                  <span>documented failures caught</span>
                  <small>
                    {queue.failures_missed === 0
                      ? "None were missed"
                      : `${count(queue.failures_missed)} ran to the end with nobody looking`}
                  </small>
                </div>
                <div>
                  <strong>{money(queue.net_vs_never_usd)}</strong>
                  <span>saved against never alerting</span>
                  <small>
                    {queue.beats_never_alert
                      ? "Cheaper than waiting for the machine to fail"
                      : "This line costs more than doing nothing at all"}
                  </small>
                </div>
              </div>

              <div className="mnt-table-wrap">
                <table className="mnt-table">
                  <caption>
                    The same {count(queue.months, 1)} months priced three ways. Every dollar figure is
                    a classroom assumption, not a real operator's number.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Way of working</th>
                      <th scope="col">Callouts</th>
                      <th scope="col">Technician hours</th>
                      <th scope="col">Failures caught</th>
                      <th scope="col">Cost of the callouts</th>
                      <th scope="col">Cost of faults running</th>
                      <th scope="col">Total (assumed)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="mnt-row-current">
                      <th scope="row">
                        This detector at {queue.threshold}
                        <span>A technician goes out when an hour crosses the line</span>
                      </th>
                      <td className="num">{count(queue.callouts)}</td>
                      <td className="num">{count(queue.technician_hours, 1)}</td>
                      <td className="num">
                        {count(queue.failures_caught)} of {count(queue.failures_total)}
                      </td>
                      <td className="num">{money(queue.callout_cost_usd)}</td>
                      <td className="num">{money(queue.fault_cost_usd)}</td>
                      <td className="num">{money(queue.total_cost_usd)}</td>
                    </tr>
                    <tr>
                      <th scope="row">
                        Never alert
                        <span>{queue.never_alert.plain_name}</span>
                      </th>
                      <td className="num">{count(queue.never_alert.callouts)}</td>
                      <td className="num">{count(queue.never_alert.technician_hours, 1)}</td>
                      <td className="num">
                        {count(queue.never_alert.failures_caught)} of{" "}
                        {count(queue.never_alert.failures_total)}
                      </td>
                      <td className="num">{money(queue.never_alert.callout_cost_usd)}</td>
                      <td className="num">{money(queue.never_alert.fault_cost_usd)}</td>
                      <td className="num">{money(queue.never_alert.total_cost_usd)}</td>
                    </tr>
                    <tr>
                      <th scope="row">
                        Scheduled inspection
                        <span>{queue.scheduled_inspection.plain_name}</span>
                      </th>
                      <td className="num">{count(queue.scheduled_inspection.callouts)}</td>
                      <td className="num">
                        {count(queue.scheduled_inspection.technician_hours, 1)}
                      </td>
                      <td className="num">
                        {count(queue.scheduled_inspection.failures_caught)} of{" "}
                        {count(queue.scheduled_inspection.failures_total)}
                      </td>
                      <td className="num">{money(queue.scheduled_inspection.callout_cost_usd)}</td>
                      <td className="num">{money(queue.scheduled_inspection.fault_cost_usd)}</td>
                      <td className="num">{money(queue.scheduled_inspection.total_cost_usd)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="mnt-panel">
                <header>
                  <span>The part that surprises people</span>
                  <h3>The same line, month after month, with no change to the machine</h3>
                  <p>
                    These are healthy hours only - no repair report was filed in any of them. The
                    compressor works harder in the summer than it did in the February baseline the
                    detector learned from, so the same threshold raises a different number of alerts
                    every month.
                  </p>
                </header>
                <div className="mnt-month-bars">
                  {queue.monthly_load.map((row) => (
                    <div className="mnt-month-row" key={row.month}>
                      <b>{monthName(row.month)}</b>
                      <span className="mnt-month-track">
                        <i
                          style={{
                            width: `${busiestLoad > 0 ? (row.alert_hours / busiestLoad) * 100 : 0}%`,
                          }}
                        />
                      </span>
                      <span>
                        {count(row.alert_hours)} alert {row.alert_hours === 1 ? "hour" : "hours"} (
                        {count(row.pct_of_clean_hours, 1)}% of {count(row.clean_hours)}),{" "}
                        {count(row.false_callouts)}{" "}
                        {row.false_callouts === 1 ? "callout" : "callouts"}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mnt-drift-callout" role="note">
                  <AlertTriangle size={17} aria-hidden="true" />
                  <p>{queue.drift.sentence}</p>
                </div>
              </div>

              <div className="mnt-table-wrap">
                <table className="mnt-table">
                  <caption>
                    Wasted callouts by month, at five different lines. Read across a row to see the
                    drift; read down a column to see what the line buys. Measured on healthy hours.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Callout line</th>
                      {Object.keys(model.drift.detector_false_callouts_by_month[0] ?? {})
                        .filter((key) => key !== "threshold")
                        .map((key) => (
                          <th scope="col" key={key}>
                            {monthName(key)}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {model.drift.detector_false_callouts_by_month.map((row) => (
                      <tr
                        key={String(row.threshold)}
                        className={
                          Number(row.threshold) === Math.round(queue.threshold)
                            ? "mnt-row-current"
                            : ""
                        }
                      >
                        <th scope="row" className="num">
                          {cell(row, "threshold")}
                        </th>
                        {Object.keys(row)
                          .filter((key) => key !== "threshold")
                          .map((key) => (
                            <td className="num" key={key}>
                              {cell(row, key)}
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      ) : null}

      {view === "card" && model ? (
        <section aria-label="Model card and evidence">
          <div className="mnt-section-heading">
            <div>
              <span>View 3</span>
              <h2>What this model is, and what it is not</h2>
              <p>{model.intended_use}</p>
            </div>
            <strong>
              <Database size={14} aria-hidden="true" /> version {model.model_version}
            </strong>
          </div>

          <div className="mnt-fact-grid">
            <div>
              <BrainCircuit size={18} aria-hidden="true" />
              <span>How it works</span>
              <strong>{model.model_type.replaceAll("_", " ")}</strong>
              <small>{model.how_it_works}</small>
            </div>
            <div>
              <Layers3 size={18} aria-hidden="true" />
              <span>What it reads</span>
              <strong>{model.features.length} readings per hour</strong>
              <small>
                The whole fitted model is twelve numbers: a normal value and a normal spread for each
                of the six.
              </small>
            </div>
            <div>
              <Database size={18} aria-hidden="true" />
              <span>What it learned from</span>
              <strong>
                {shortDate(model.dataset.training_window[0])} to{" "}
                {shortDate(model.dataset.training_window[1])}
              </strong>
              <small>
                {model.dataset.population}. Nothing after March was ever used to fit the model.
              </small>
            </div>
            <div>
              <Scale size={18} aria-hidden="true" />
              <span>Where its authority stops</span>
              <strong>It raises work orders. People decide.</strong>
              <small>{model.boundary_short}</small>
            </div>
          </div>

          <div className="mnt-panel">
            <header>
              <span>The rule, in plain words</span>
              <h3>What happens to an hour once it has a score</h3>
              <p>{model.policy.plain_rule}</p>
            </header>
            <ul className="mnt-plain-list">
              <li>
                <strong>Score {model.policy.threshold} or above</strong>
                <span>{model.policy.route_work_order}</span>
              </li>
              <li>
                <strong>
                  Score {model.policy.watch_threshold} up to {model.policy.threshold}
                </strong>
                <span>{model.policy.route_watch}</span>
              </li>
              <li>
                <strong>Below {model.policy.watch_threshold}</strong>
                <span>{model.policy.route_no_action}</span>
              </li>
              <li>
                <strong>An hour with too little sensor data</strong>
                <span>{model.policy.fallback}</span>
              </li>
              <li>
                <strong>Keeping it honest over time</strong>
                <span>{model.policy.recalibration}</span>
              </li>
            </ul>
          </div>

          <div className="mnt-panel">
            <header>
              <span>Measured once, on data the model had never seen</span>
              <h3>
                {shortDate(model.frozen_test.window[0])} to {shortDate(model.frozen_test.window[1])}
              </h3>
              <p>
                The threshold was chosen on April through June and frozen. These July to September
                numbers were produced by scoring that window a single time, and they have not been
                tuned since.
              </p>
            </header>
            <div className="mnt-summary-grid">
              <div>
                <strong>{count(model.frozen_test.scored_hours)}</strong>
                <span>hours scored</span>
                <small>{count(model.frozen_test.clean_hours)} of them with nothing wrong</small>
              </div>
              <div>
                <strong>{count(model.frozen_test.alert_hours)}</strong>
                <span>hours raised a work order</span>
                <small>
                  {count(model.frozen_test.false_alarm_hours)} of them were false alarms
                </small>
              </div>
              <div>
                <strong>{count(model.frozen_test.false_callouts_per_month, 2)}</strong>
                <span>wasted callouts per month</span>
                <small>Over {count(model.frozen_test.months, 2)} months</small>
              </div>
              <div>
                <strong>
                  {count(Number(model.frozen_test.policy.failures_caught ?? 0))} of{" "}
                  {count(Number(model.frozen_test.policy.failures_total ?? 0))}
                </strong>
                <span>documented failures in this window, caught</span>
                <small>
                  {model.frozen_test.first_alert
                    ? `First alert ${shortHour(model.frozen_test.first_alert)}`
                    : "No alert was raised"}
                </small>
              </div>
            </div>
            <div className="mnt-assumption-note" role="note">
              <AlertTriangle size={16} aria-hidden="true" />
              <p>
                <strong>The honest reading of the money.</strong>{" "}
                {model.frozen_test.honest_roi_note}
              </p>
            </div>
          </div>

          <div className="mnt-panel">
            <header>
              <span>The limits, stated by the people who built it</span>
              <h3>What this evidence cannot support</h3>
              <p>
                Four events is not a sample. There is no confidence interval anywhere on this page,
                because four events cannot produce one.
              </p>
            </header>
            <ul className="mnt-limit-list">
              {model.limitations.map((limitation) => (
                <li key={limitation}>
                  <AlertTriangle size={16} aria-hidden="true" />
                  <span>{limitation}</span>
                </li>
              ))}
              <li>
                <AlertTriangle size={16} aria-hidden="true" />
                <span>{model.data_coverage.note}</span>
              </li>
            </ul>
          </div>

          <div className="mnt-panel">
            <header>
              <span>Not for</span>
              <h3>Uses this model is not fit for</h3>
              <p>{model.authority_boundary}</p>
            </header>
            <ul className="mnt-limit-list">
              {model.not_for.map((item) => (
                <li key={item}>
                  <AlertTriangle size={16} aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mnt-table-wrap">
            <table className="mnt-table">
              <caption>
                The six readings the model uses, what each one asks, and what counts as normal for
                this compressor.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Reading</th>
                  <th scope="col">The question it answers</th>
                  <th scope="col">Normal for this machine</th>
                  <th scope="col">Which way means trouble</th>
                </tr>
              </thead>
              <tbody>
                {model.features.map((feature) => (
                  <tr key={feature.name}>
                    <th scope="row">{feature.display_name}</th>
                    <td>{feature.planner_question}</td>
                    <td className="num">{feature.training_normal_text}</td>
                    <td>{feature.plain_direction}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mnt-table-wrap">
            <table className="mnt-table">
              <caption>
                How much of the record is missing, and where the gaps land. An hour with under half
                its minutes is never scored.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Fact</th>
                  <th scope="col">Value</th>
                </tr>
              </thead>
              <tbody>
                {model.data_coverage.summary.map((row) => (
                  <tr key={String(row.Fact)}>
                    <th scope="row">{cell(row, "Fact")}</th>
                    <td className="num">{cell(row, "Value")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mnt-table-wrap">
            <table className="mnt-table">
              <caption>
                What each callout line costs and catches over the whole scored period. The line in
                use is highlighted. Dollar figures are classroom assumptions.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Callout line</th>
                  <th scope="col">Callouts</th>
                  <th scope="col">Wasted callouts</th>
                  <th scope="col">Per month</th>
                  <th scope="col">Technician hours</th>
                  <th scope="col">Failures caught</th>
                  <th scope="col">Total (assumed)</th>
                </tr>
              </thead>
              <tbody>
                {model.threshold_sweep.map((row) => (
                  <tr
                    key={String(row.threshold)}
                    className={
                      Number(row.threshold) === model.policy.threshold ? "mnt-row-current" : ""
                    }
                  >
                    <th scope="row" className="num">
                      {cell(row, "threshold")}
                      {Number(row.threshold) === model.policy.threshold ? (
                        <span>the frozen operating line</span>
                      ) : null}
                    </th>
                    <td className="num">{cell(row, "callouts")}</td>
                    <td className="num">{cell(row, "false_callouts")}</td>
                    <td className="num">{cell(row, "callouts_per_month")}</td>
                    <td className="num">{cell(row, "technician_hours")}</td>
                    <td className="num">
                      {cell(row, "failures_caught")} of {cell(row, "failures_total")}
                    </td>
                    <td className="num">{money(Number(row.total_cost_usd ?? 0))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mnt-panel">
            <header>
              <span>A bug worth remembering</span>
              <h3>The first version of the features deleted the worst failures</h3>
              <p>{model.feature_bug.description}</p>
            </header>
            <div className="mnt-table-wrap" style={{ marginBottom: 0 }}>
              <table className="mnt-table">
                <caption className="sr-only">Hours deleted by the naive feature code</caption>
                <thead>
                  <tr>
                    <th scope="col">Failure</th>
                    <th scope="col">Hours with data</th>
                    <th scope="col">Hours left after the bug</th>
                    <th scope="col">Hours silently deleted</th>
                  </tr>
                </thead>
                <tbody>
                  {model.feature_bug.hours_deleted_per_failure.map((row) => (
                    <tr key={String(row.Failure)}>
                      <th scope="row">{cell(row, "Failure")}</th>
                      <td className="num">{cell(row, "Hours with data")}</td>
                      <td className="num">{cell(row, "Hours surviving dropna()")}</td>
                      <td className="num">{cell(row, "Hours silently deleted")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mnt-panel">
            <header>
              <span>Provenance</span>
              <h3>Where the data came from</h3>
              <p>{model.dataset.citation}</p>
            </header>
            <ul className="mnt-plain-list">
              <li>
                <strong>Dataset</strong>
                <span>
                  {model.dataset.dataset}, published under {model.dataset.license}.{" "}
                  <a className="mnt-source-link" href={model.dataset.url} target="_blank" rel="noreferrer">
                    {model.dataset.url}
                  </a>
                </span>
              </li>
              <li>
                <strong>How often the sensors reported</strong>
                <span>{model.dataset.raw_sampling}</span>
              </li>
              <li>
                <strong>What this service reads</strong>
                <span>
                  {model.dataset.committed_resolution}. {count(model.scored_hours)} hours could be
                  scored, and {count(model.packaged_windows)} of them are packaged as the windows in
                  view one.
                </span>
              </li>
              <li>
                <strong>Built with</strong>
                <span>
                  {Object.entries(model.environment)
                    .map(([key, value]) => `${key.replaceAll("_", " ")} ${value}`)
                    .join(", ")}
                </span>
              </li>
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}
