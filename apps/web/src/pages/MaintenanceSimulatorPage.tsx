import { useEffect, useEffectEvent, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleGauge,
  Clock3,
  DatabaseZap,
  Fan,
  Gauge,
  Pause,
  Play,
  RadioTower,
  RefreshCw,
  RotateCcw,
  Settings2,
  SkipForward,
  Thermometer,
  Timer,
  Waves,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  getMaintenanceSamples,
  getMaintenanceSimulation,
  type MaintenanceSimulation,
  type MaintenanceSimulatorFeature,
  type MaintenanceSimulatorHour,
  type MaintenanceSampleWindow,
} from "../maintenanceApi";

const simulatorStyles = `
.sim-page { min-height: 100vh; --sim-orange: #e8913c; --sim-teal: #7eaeb8; --sim-red: #e45a58; --sim-green: #62c890; --sim-border: #303644; color: #f5f3f0; background: #101319; background-image: linear-gradient(rgba(126,174,184,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(126,174,184,.035) 1px,transparent 1px); background-size: 28px 28px; }
.sim-shell { width: min(1680px,100%); min-height: 100vh; margin: 0 auto; padding: 20px 24px 32px; }
.sim-topbar { min-height: 54px; display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--sim-border); }
.sim-brand { display: flex; align-items: center; gap: 11px; }
.sim-brand-mark { width: 31px; height: 31px; display: grid; place-items: center; border: 1px solid rgba(232,145,60,.45); border-radius: 5px; background: rgba(232,145,60,.08); color: var(--sim-orange); }
.sim-brand strong,.sim-brand span { display: block; }
.sim-brand strong { font-size: 14px; }
.sim-brand span { margin-top: 2px; color: #9396a6; font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.sim-back { min-height: 44px; padding: 0 12px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--sim-border); border-radius: 5px; color: #c4c5ce; background: #181c24; font-size: 11px; text-decoration: none; }
.sim-back:hover { border-color: #596274; color: #fff; }
.sim-heading { padding: 20px 0 17px; display: flex; justify-content: space-between; gap: 28px; align-items: flex-end; }
.sim-heading span { color: var(--sim-orange); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.sim-heading h1 { margin: 5px 0 6px; font-size: 28px; line-height: 1.18; }
.sim-heading p { max-width: 820px; margin: 0; color: #b8bbc6; font-size: 12px; line-height: 1.6; }
.sim-runtime { flex: 0 0 auto; display: flex; align-items: center; gap: 9px; color: #c4c5ce; font-family: var(--font-mono); font-size: 10px; }
.sim-runtime i { width: 9px; height: 9px; border-radius: 50%; background: var(--sim-green); box-shadow: 0 0 0 5px rgba(98,200,144,.1); }
.sim-controls { min-height: 68px; padding: 10px 12px; display: grid; grid-template-columns: minmax(230px,1.35fr) minmax(150px,.55fr) auto; gap: 12px; align-items: end; border: 1px solid var(--sim-border); border-radius: 6px; background: rgba(24,28,36,.98); }
.sim-field label { display: block; margin-bottom: 5px; color: #9396a6; font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; }
.sim-field select { width: 100%; min-height: 44px; padding: 0 34px 0 11px; border: 1px solid #3b4252; border-radius: 4px; background: #12161d; color: #f5f3f0; font-size: 12px; }
.sim-actions { display: flex; gap: 7px; align-items: center; }
.sim-action { min-width: 44px; min-height: 44px; padding: 0 11px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; border: 1px solid #3b4252; border-radius: 4px; background: #151a22; color: #c4c5ce; font-size: 11px; transition: 160ms ease; }
.sim-action:hover:not(:disabled) { border-color: #687286; color: #fff; background: #202631; }
.sim-action.primary { min-width: 100px; border-color: rgba(232,145,60,.6); background: rgba(232,145,60,.11); color: #f0a050; }
.sim-action.primary:hover:not(:disabled) { background: rgba(232,145,60,.19); }
.sim-kpis { margin: 14px 0; display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); border-top: 1px solid var(--sim-border); border-bottom: 1px solid var(--sim-border); }
.sim-kpi { min-width: 0; min-height: 83px; padding: 12px 15px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--sim-border); }
.sim-kpi:last-child { border-right: 0; }
.sim-kpi span { color: #9396a6; font-size: 10px; }
.sim-kpi strong { margin-top: 5px; color: #f5f3f0; font-family: var(--font-mono); font-size: 19px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.sim-kpi small { margin-top: 3px; color: #73798a; font-size: 9px; line-height: 1.35; }
.sim-grid { display: grid; grid-template-columns: minmax(0,1.6fr) minmax(300px,.62fr); border: 1px solid var(--sim-border); border-radius: 6px; background: #171b23; overflow: hidden; }
.sim-panel { min-width: 0; min-height: 570px; border-right: 1px solid var(--sim-border); }
.sim-panel:last-child { border-right: 0; }
.sim-input-panel { grid-column: 1/-1; min-height: 0; border-right: 0; border-bottom: 1px solid var(--sim-border); }
.sim-panel-header { min-height: 66px; padding: 11px 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border-bottom: 1px solid var(--sim-border); background: #1a1f28; }
.sim-panel-header span,.sim-panel-header strong,.sim-panel-header small { display: block; }
.sim-panel-header span { color: var(--sim-orange); font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-panel-header strong { margin-top: 3px; font-size: 13px; }
.sim-panel-header small { margin-top: 3px; color: #858998; font-size: 9px; }
.sim-instrument-stage { padding: 18px; display: grid; grid-template-columns: minmax(220px,1fr) minmax(270px,.78fr) minmax(220px,1fr); grid-template-rows: repeat(3,minmax(98px,auto)); gap: 12px 30px; align-items: stretch; background: radial-gradient(circle at 50% 48%,rgba(126,174,184,.09),transparent 25%),linear-gradient(180deg,#151a22,#12161d); }
.sim-machine-core { grid-column: 2; grid-row: 1/4; min-height: 318px; padding: 16px; display: flex; flex-direction: column; position: relative; overflow: hidden; border: 1px solid #3a4251; border-radius: 6px; background: linear-gradient(145deg,#1d242d,#11151b 65%); box-shadow: inset 0 0 0 1px rgba(255,255,255,.018),0 18px 45px rgba(0,0,0,.23); }
.sim-machine-core::before { content: ""; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(90deg,transparent 49.7%,rgba(126,174,184,.06) 50%,transparent 50.3%); }
.sim-machine-meta { position: relative; z-index: 1; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.sim-machine-meta span,.sim-machine-meta strong { display: block; }
.sim-machine-meta span { color: var(--sim-orange); font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-machine-meta strong { margin-top: 4px; font-size: 13px; }
.sim-machine-health { display: flex; align-items: center; gap: 6px; color: #858998; font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-machine-health i { width: 7px; height: 7px; border-radius: 50%; background: #596171; box-shadow: 0 0 0 4px rgba(89,97,113,.1); }
.sim-machine-core.receiving .sim-machine-health { color: var(--sim-orange); }
.sim-machine-core.receiving .sim-machine-health i { background: var(--sim-orange); box-shadow: 0 0 0 4px rgba(232,145,60,.11); }
.sim-machine-core.scored .sim-machine-health { color: var(--sim-green); }
.sim-machine-core.scored .sim-machine-health i { background: var(--sim-green); box-shadow: 0 0 0 4px rgba(98,200,144,.1); }
.sim-machine-core.alert .sim-machine-health { color: var(--sim-red); }
.sim-machine-core.alert .sim-machine-health i { background: var(--sim-red); box-shadow: 0 0 0 4px rgba(228,90,88,.11); }
.sim-machine-visual { width: min(260px,100%); height: 176px; margin: auto; position: relative; }
.sim-machine-base { position: absolute; left: 8%; right: 5%; bottom: 17px; height: 10px; border: 1px solid #566070; border-radius: 2px; background: #252c36; box-shadow: 0 7px 0 -3px #0b0e13; }
.sim-machine-motor { width: 42%; height: 76px; position: absolute; left: 4%; bottom: 27px; display: grid; place-items: center; border: 1px solid #606a79; border-radius: 24px 5px 5px 24px; color: var(--sim-teal); background: repeating-linear-gradient(90deg,#252d37 0 7px,#303945 7px 10px); box-shadow: inset 0 0 18px rgba(126,174,184,.08); }
.sim-machine-motor svg { filter: drop-shadow(0 0 8px rgba(126,174,184,.25)); }
.sim-machine-core.receiving .sim-machine-motor svg { animation: sim-rotate 1.7s linear infinite; }
.sim-machine-coupling { width: 12%; height: 24px; position: absolute; left: 44%; bottom: 52px; border: 1px solid #5c6574; background: repeating-linear-gradient(90deg,#495260 0 4px,#202630 4px 7px); }
.sim-machine-pump { width: 34%; height: 88px; position: absolute; right: 7%; bottom: 26px; display: grid; place-items: center; border: 1px solid #6b7481; border-radius: 50% 14px 14px 50%; color: var(--sim-orange); background: linear-gradient(145deg,#303945,#1d242d); box-shadow: inset 0 0 24px rgba(232,145,60,.08); }
.sim-machine-pump::after { content: ""; width: 34px; height: 34px; border: 1px dashed #78818d; border-radius: 50%; }
.sim-machine-pipe { width: 48%; height: 51px; position: absolute; right: 3%; top: 15px; border-top: 9px solid #46505d; border-right: 9px solid #46505d; border-radius: 0 14px 0 0; }
.sim-machine-gauge { width: 38px; height: 38px; position: absolute; right: 3%; top: 0; display: grid; place-items: center; border: 1px solid #67717f; border-radius: 50%; color: var(--sim-teal); background: #151a21; }
.sim-machine-readout { position: relative; z-index: 1; min-height: 54px; padding: 9px 11px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid #333b48; border-radius: 4px; background: rgba(8,11,15,.55); }
.sim-machine-readout span,.sim-machine-readout strong { display: block; }
.sim-machine-readout span { color: #858998; font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-machine-readout small { display: block; margin-top: 4px; color: #c0c3ca; font-size: 9px; }
.sim-machine-readout strong { color: var(--sim-orange); font-family: var(--font-mono); font-size: 20px; font-variant-numeric: tabular-nums; }
.sim-machine-core.scored .sim-machine-readout strong { color: var(--sim-green); }
.sim-machine-core.alert .sim-machine-readout strong { color: var(--sim-red); }
.sim-sensor-card { min-width: 0; min-height: 98px; padding: 12px 13px; position: relative; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #303846; border-radius: 5px; background: linear-gradient(135deg,#1c222b,#141920); transition: border-color 220ms ease,background 220ms ease,opacity 220ms ease,transform 220ms ease; }
.sim-sensor-card.pending { opacity: .42; }
.sim-sensor-card.receiving { border-color: rgba(232,145,60,.8); background: linear-gradient(135deg,rgba(232,145,60,.12),#151920 75%); transform: translateY(-1px); box-shadow: 0 0 0 1px rgba(232,145,60,.08),0 10px 24px rgba(0,0,0,.16); }
.sim-sensor-card.received { border-color: rgba(126,174,184,.45); }
.sim-sensor-card.sensor-0 { grid-column: 1; grid-row: 1; }
.sim-sensor-card.sensor-1 { grid-column: 1; grid-row: 2; }
.sim-sensor-card.sensor-2 { grid-column: 1; grid-row: 3; }
.sim-sensor-card.sensor-3 { grid-column: 3; grid-row: 1; }
.sim-sensor-card.sensor-4 { grid-column: 3; grid-row: 2; }
.sim-sensor-card.sensor-5 { grid-column: 3; grid-row: 3; }
.sim-sensor-card.sensor-0::after,.sim-sensor-card.sensor-1::after,.sim-sensor-card.sensor-2::after,.sim-sensor-card.sensor-3::before,.sim-sensor-card.sensor-4::before,.sim-sensor-card.sensor-5::before { content: ""; width: 30px; position: absolute; top: 50%; border-top: 1px solid #394351; }
.sim-sensor-card.sensor-0::after,.sim-sensor-card.sensor-1::after,.sim-sensor-card.sensor-2::after { right: -31px; }
.sim-sensor-card.sensor-3::before,.sim-sensor-card.sensor-4::before,.sim-sensor-card.sensor-5::before { left: -31px; }
.sim-sensor-card.receiving::after,.sim-sensor-card.receiving::before { border-color: var(--sim-orange); }
.sim-sensor-card.received::after,.sim-sensor-card.received::before { border-color: rgba(126,174,184,.7); }
.sim-sensor-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.sim-sensor-identity { min-width: 0; display: flex; align-items: center; gap: 9px; }
.sim-sensor-icon { width: 30px; height: 30px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid #3a4351; border-radius: 4px; color: #717989; background: #12161c; }
.sim-sensor-card.receiving .sim-sensor-icon { color: var(--sim-orange); border-color: rgba(232,145,60,.65); }
.sim-sensor-card.received .sim-sensor-icon { color: var(--sim-teal); border-color: rgba(126,174,184,.48); }
.sim-sensor-name span,.sim-sensor-name strong { display: block; }
.sim-sensor-name span { color: #747b89; font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-sensor-name strong { margin-top: 3px; overflow-wrap: anywhere; font-size: 11px; line-height: 1.2; }
.sim-sensor-state { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; background: #4b5361; }
.sim-sensor-card.receiving .sim-sensor-state { background: var(--sim-orange); box-shadow: 0 0 0 5px rgba(232,145,60,.1); animation: sim-pulse 1s ease-in-out infinite; }
.sim-sensor-card.received .sim-sensor-state { background: var(--sim-teal); }
.sim-sensor-reading { margin-top: 9px; display: flex; align-items: end; justify-content: space-between; gap: 10px; }
.sim-sensor-reading strong { min-width: 0; color: #f5f3f0; font-family: var(--font-mono); font-size: 18px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.sim-sensor-reading small { max-width: 48%; color: #7e8492; font-size: 8px; line-height: 1.35; text-align: right; }
.sim-packet-progress { margin: 0 18px 15px; height: 5px; display: grid; grid-template-columns: repeat(6,1fr); gap: 4px; }
.sim-packet-progress i { border-radius: 2px; background: #2d3340; }
.sim-packet-progress i.done { background: var(--sim-teal); }
.sim-packet-progress i.live { background: var(--sim-orange); }
.sim-chart-wrap { padding: 17px 14px 10px; overflow-x: auto; }
.sim-chart svg { display: block; width: 100%; min-width: 590px; height: 340px; }
.sim-chart .axis,.sim-chart .grid { stroke: #353c4b; stroke-width: 1; }
.sim-chart .grid { stroke-dasharray: 2 4; }
.sim-chart .series { fill: none; stroke: var(--sim-teal); stroke-width: 2; stroke-linejoin: round; }
.sim-chart .threshold { stroke: var(--sim-orange); stroke-width: 1.6; stroke-dasharray: 6 4; }
.sim-chart .point { fill: var(--sim-teal); stroke: #11151b; stroke-width: 1.2; }
.sim-chart .point.alert { fill: var(--sim-red); }
.sim-chart .report-band { fill: rgba(98,200,144,.09); }
.sim-chart text { fill: #858998; font-family: var(--font-mono); font-size: 9px; }
.sim-chart text.threshold-label { fill: var(--sim-orange); }
.sim-chart text.report-label { fill: var(--sim-green); }
.sim-chart-empty { min-height: 340px; display: grid; place-content: center; justify-items: center; gap: 9px; color: #73798a; text-align: center; }
.sim-chart-empty p { margin: 0; font-size: 11px; }
.sim-chart-legend { padding: 0 14px 12px; display: flex; flex-wrap: wrap; gap: 9px 16px; color: #858998; font-size: 9px; }
.sim-chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sim-chart-legend i { width: 14px; border-top: 2px solid var(--sim-teal); }
.sim-chart-legend i.cutoff { border-top: 2px dashed var(--sim-orange); }
.sim-chart-legend i.alert { width: 7px; height: 7px; border: 0; border-radius: 50%; background: var(--sim-red); }
.sim-chart-legend i.report { width: 10px; height: 10px; border: 1px solid var(--sim-green); background: rgba(98,200,144,.09); }
.sim-event-log { margin: 6px 14px 14px; border-top: 1px solid var(--sim-border); }
.sim-log-row { min-height: 39px; padding: 7px 0; display: grid; grid-template-columns: 104px 80px minmax(0,1fr); gap: 9px; align-items: center; border-bottom: 1px solid #252b36; font-size: 9px; }
.sim-log-row time,.sim-log-row b { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.sim-log-row span { color: #858998; }
.sim-alert-panel { padding-bottom: 14px; }
.sim-signal { min-height: 252px; padding: 24px 17px; display: grid; place-content: center; justify-items: center; text-align: center; border-bottom: 1px solid var(--sim-border); background: #13171e; }
.sim-beacon { width: 86px; height: 86px; display: grid; place-items: center; border: 1px solid #3b4252; border-radius: 50%; color: #73798a; background: #171c24; transition: 180ms ease; }
.sim-signal.alert .sim-beacon { color: #fff; background: rgba(228,90,88,.17); border-color: var(--sim-red); box-shadow: 0 0 0 12px rgba(228,90,88,.06),0 0 34px rgba(228,90,88,.28); animation: sim-alert 1s ease-in-out infinite; }
.sim-signal.clear .sim-beacon { color: var(--sim-green); border-color: rgba(98,200,144,.55); background: rgba(98,200,144,.08); }
.sim-signal h2 { margin: 16px 0 6px; font-size: 18px; }
.sim-signal p { max-width: 245px; margin: 0; color: #9396a6; font-size: 10px; line-height: 1.5; }
.sim-signal.alert h2 { color: var(--sim-red); }
.sim-signal.clear h2 { color: var(--sim-green); }
.sim-signal-details { padding: 14px; display: grid; gap: 9px; }
.sim-detail { min-height: 65px; padding: 10px 11px; border-left: 2px solid #3b4252; background: #13171e; }
.sim-detail span { display: block; color: #73798a; font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; }
.sim-detail strong { display: block; margin-top: 5px; font-size: 11px; line-height: 1.4; }
.sim-detail small { display: block; margin-top: 3px; color: #858998; font-size: 9px; line-height: 1.4; }
.sim-detail.reported { border-left-color: var(--sim-green); }
.sim-footnote { margin: 13px 0 0; padding: 11px 13px; display: flex; gap: 9px; border-left: 3px solid var(--sim-teal); background: rgba(126,174,184,.06); color: var(--sim-teal); }
.sim-footnote p { margin: 0; color: #aeb1bc; font-size: 10px; line-height: 1.55; }
.sim-error,.sim-loading { min-height: 300px; display: grid; place-content: center; color: #aeb1bc; text-align: center; }
.sim-error { color: var(--sim-red); }
@keyframes sim-pulse { 50% { opacity: .48; } }
@keyframes sim-alert { 50% { box-shadow: 0 0 0 18px rgba(228,90,88,.03),0 0 44px rgba(228,90,88,.4); } }
@keyframes sim-rotate { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .sim-sensor-card,.sim-beacon { transition: none; } .sim-machine-core.receiving .sim-machine-motor svg,.sim-sensor-card.receiving .sim-sensor-state,.sim-signal.alert .sim-beacon { animation: none; } }
@media (max-width: 1180px) { .sim-grid { grid-template-columns: minmax(0,1fr) 310px; } .sim-instrument-stage { grid-template-columns: minmax(190px,1fr) 250px minmax(190px,1fr); gap-inline: 24px; } .sim-sensor-card.sensor-0::after,.sim-sensor-card.sensor-1::after,.sim-sensor-card.sensor-2::after,.sim-sensor-card.sensor-3::before,.sim-sensor-card.sensor-4::before,.sim-sensor-card.sensor-5::before { width: 24px; } .sim-sensor-card.sensor-0::after,.sim-sensor-card.sensor-1::after,.sim-sensor-card.sensor-2::after { right: -25px; } .sim-sensor-card.sensor-3::before,.sim-sensor-card.sensor-4::before,.sim-sensor-card.sensor-5::before { left: -25px; } .sim-kpis { grid-template-columns: repeat(3,minmax(0,1fr)); } .sim-kpi:nth-child(3) { border-right: 0; } }
@media (max-width: 900px) { .sim-grid { grid-template-columns: minmax(0,1fr); } .sim-panel { min-height: 0; border-right: 0; border-bottom: 1px solid var(--sim-border); } .sim-alert-panel { border-bottom: 0; } .sim-instrument-stage { grid-template-columns: repeat(2,minmax(0,1fr)); grid-template-rows: auto; gap: 10px; } .sim-machine-core { grid-column: 1/-1; grid-row: auto; min-height: 280px; } .sim-sensor-card.sensor-0,.sim-sensor-card.sensor-1,.sim-sensor-card.sensor-2,.sim-sensor-card.sensor-3,.sim-sensor-card.sensor-4,.sim-sensor-card.sensor-5 { grid-column: auto; grid-row: auto; } .sim-sensor-card::before,.sim-sensor-card::after { display: none; } .sim-signal { min-height: 190px; } }
@media (max-width: 760px) { .sim-shell { padding: 12px 12px 24px; } .sim-topbar,.sim-heading { align-items: flex-start; } .sim-heading { flex-direction: column; } .sim-heading h1 { font-size: 23px; } .sim-controls { grid-template-columns: minmax(0,1fr); } .sim-actions { display: grid; grid-template-columns: 1fr 44px 44px; } .sim-action.primary { width: 100%; } .sim-kpis { grid-template-columns: repeat(2,minmax(0,1fr)); } .sim-kpi { border-bottom: 1px solid var(--sim-border); } .sim-kpi:nth-child(2n) { border-right: 0; } .sim-instrument-stage { padding: 10px; gap: 8px; } .sim-machine-core { min-height: 260px; padding: 13px; } .sim-machine-visual { height: 160px; } .sim-sensor-card { min-height: 105px; padding: 10px; } .sim-sensor-reading { display: block; } .sim-sensor-reading strong { display: block; font-size: 15px; overflow-wrap: anywhere; } .sim-sensor-reading small { display: block; max-width: none; margin-top: 4px; text-align: left; } .sim-packet-progress { margin-inline: 10px; } .sim-chart svg { height: 300px; } .sim-log-row { grid-template-columns: 92px 70px minmax(0,1fr); } .sim-back span { display: none; } }
`;

type RunState = "idle" | "running" | "paused" | "complete";
type Phase = "receiving" | "scored" | "done";
type Cursor = { hourIndex: number; received: number; scoredHours: number; phase: Phase };

const intervals = [
  { value: 250, label: "Fast - 0.25 s" },
  { value: 600, label: "Normal - 0.6 s" },
  { value: 1200, label: "Slow - 1.2 s" },
  { value: 2000, label: "Study - 2 s" },
];

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const featureVisuals: Record<string, { label: string; icon: LucideIcon }> = {
  load_share: { label: "Working load", icon: Activity },
  cycles_per_hour: { label: "Starts per hour", icon: RefreshCw },
  rest_minutes_per_cycle: { label: "Rest per cycle", icon: Timer },
  oil_temp_mean: { label: "Oil temperature", icon: Thermometer },
  tp3_std: { label: "Pressure swing", icon: Waves },
  pressure_fall_rate: { label: "Pressure fall", icon: Gauge },
};

const compactFeatureValue = (feature: MaintenanceSimulatorFeature) => {
  if (!Number.isFinite(feature.value)) return feature.value_text;
  if (feature.name === "load_share") return `${Math.round(feature.value * 100)}%`;
  if (feature.name === "cycles_per_hour") return `${feature.value.toFixed(0)} starts`;
  if (feature.name === "rest_minutes_per_cycle") return `${feature.value.toFixed(1)} min`;
  if (feature.name === "oil_temp_mean") return `${feature.value.toFixed(1)} °C`;
  if (feature.name === "tp3_std") return `${feature.value.toFixed(2)} bar`;
  if (feature.name === "pressure_fall_rate") return `${feature.value.toFixed(3)} bar/min`;
  return feature.value_text;
};

const shortHour = (stamp: string) => {
  const [date, time = ""] = stamp.split(" ");
  const [, month, day] = date.split("-");
  return `${monthNames[Number(month) - 1]} ${Number(day)}, ${time.slice(0, 5)}`;
};

function StreamChart({ hours, threshold }: { hours: MaintenanceSimulatorHour[]; threshold: number }) {
  const width = 760;
  const height = 340;
  const left = 48;
  const right = 24;
  const top = 22;
  const bottom = 47;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  if (hours.length === 0) {
    return <div className="sim-chart-empty"><Activity size={30} /><p>Complete six features to create the first score.</p></div>;
  }
  const maximum = Math.max(threshold * 1.3, ...hours.map((hour) => hour.score)) * 1.08;
  const x = (index: number) => left + (hours.length === 1 ? plotWidth : (index / (hours.length - 1)) * plotWidth);
  const y = (value: number) => top + plotHeight - (value / maximum) * plotHeight;
  const points = hours.map((hour, index) => `${x(index)},${y(hour.score)}`).join(" ");
  const ticks = [0, threshold, maximum];
  const labelIndexes = [...new Set([0, Math.floor((hours.length - 1) / 2), hours.length - 1])];
  const reportRuns = hours.map((hour, index) => ({ hour, index })).filter(({ hour }) => hour.reported_event);
  const summary = `${hours.length} completed hours. ${hours.filter((hour) => hour.alert).length} crossed the cutoff ${threshold}.`;
  return (
    <div className="sim-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
        <title>{summary}</title>
        {reportRuns.map(({ hour, index }) => (
          <rect key={`${hour.hour}-report`} className="report-band" x={Math.max(left, x(index) - 4)} y={top} width={8} height={plotHeight} />
        ))}
        {ticks.map((tick) => <g key={tick}><line className="grid" x1={left} y1={y(tick)} x2={left + plotWidth} y2={y(tick)} /><text x={left - 8} y={y(tick) + 3} textAnchor="end">{tick.toFixed(tick === maximum ? 1 : 0)}</text></g>)}
        <line className="axis" x1={left} y1={top + plotHeight} x2={left + plotWidth} y2={top + plotHeight} />
        <line className="axis" x1={left} y1={top} x2={left} y2={top + plotHeight} />
        <line className="threshold" x1={left} y1={y(threshold)} x2={left + plotWidth} y2={y(threshold)} />
        <text className="threshold-label" x={left + plotWidth - 2} y={y(threshold) - 7} textAnchor="end">cutoff {threshold}</text>
        <polyline className="series" points={points} />
        {hours.map((hour, index) => <circle key={hour.hour} className={hour.alert ? "point alert" : "point"} cx={x(index)} cy={y(hour.score)} r={hour.alert ? 4.5 : 3.2}><title>{shortHour(hour.hour)}: {hour.score.toFixed(3)}{hour.alert ? ", review flag" : ""}</title></circle>)}
        {labelIndexes.map((index) => <text key={index} x={x(index)} y={top + plotHeight + 22} textAnchor={index === 0 ? "start" : index === hours.length - 1 ? "end" : "middle"}>{shortHour(hours[index].hour)}</text>)}
      </svg>
    </div>
  );
}

const initialCursor: Cursor = { hourIndex: 0, received: 0, scoredHours: 0, phase: "receiving" };

const nextCursor = (current: Cursor, simulation: MaintenanceSimulation): Cursor => {
  if (current.phase === "done") return current;
  if (current.phase === "receiving") {
    const received = current.received + 1;
    if (received >= simulation.feature_count) {
      return { ...current, received: simulation.feature_count,
        scoredHours: Math.max(current.scoredHours, current.hourIndex + 1), phase: "scored" };
    }
    return { ...current, received };
  }
  if (current.hourIndex >= simulation.hours.length - 1) {
    return { ...current, phase: "done" };
  }
  return { hourIndex: current.hourIndex + 1, received: 0,
           scoredHours: current.scoredHours, phase: "receiving" };
};

export default function MaintenanceSimulatorPage() {
  const [samples, setSamples] = useState<MaintenanceSampleWindow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [simulation, setSimulation] = useState<MaintenanceSimulation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [intervalMs, setIntervalMs] = useState(600);
  const [cursor, setCursor] = useState<Cursor>(initialCursor);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "Compressor Telemetry Simulator";
    return () => { document.title = previousTitle; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getMaintenanceSamples(24).then((windows) => {
      if (cancelled) return;
      setSamples(windows);
      const preferred = windows.find((window) => window.sample_id === "S5_F4_real_warning") ?? windows[0];
      setSelectedId(preferred?.sample_id ?? "");
    }).catch((reason: Error) => {
      if (!cancelled) setError(reason.message);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRunState("idle");
    setCursor(initialCursor);
    void getMaintenanceSimulation(selectedId).then((payload) => {
      if (!cancelled) setSimulation(payload);
    }).catch((reason: Error) => {
      if (!cancelled) setError(reason.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedId]);

  const advance = useEffectEvent(() => {
    if (!simulation) return;
    setCursor((current) => nextCursor(current, simulation));
  });

  useEffect(() => {
    if (runState !== "running" || !simulation) return;
    if (cursor.phase === "done") {
      setRunState("complete");
      return;
    }
    const timer = window.setTimeout(() => advance(), intervalMs);
    return () => window.clearTimeout(timer);
  }, [runState, intervalMs, simulation, cursor]);

  const reset = () => {
    setRunState("idle");
    setCursor(initialCursor);
  };

  const togglePlay = () => {
    if (runState === "running") {
      setRunState("paused");
      return;
    }
    if (runState === "complete" || cursor.phase === "done") setCursor(initialCursor);
    setRunState("running");
  };

  const step = () => {
    setRunState("paused");
    if (cursor.phase === "done") setCursor(initialCursor);
    else if (simulation) setCursor((current) => nextCursor(current, simulation));
  };

  const currentHour = simulation?.hours[Math.min(cursor.hourIndex, (simulation?.hours.length ?? 1) - 1)] ?? null;
  const completedHours = simulation?.hours.slice(0, cursor.scoredHours) ?? [];
  const lastCompleted = completedHours.at(-1) ?? null;
  const resultVisible = cursor.phase === "scored" || cursor.phase === "done";
  const currentResult = resultVisible ? currentHour : null;
  const alerts = completedHours.filter((hour) => hour.alert).length;
  const featureProgress = simulation ? `${cursor.received}/${simulation.feature_count}` : "0/6";
  const completedPercent = simulation?.hours.length ? Math.round(100 * cursor.scoredHours / simulation.hours.length) : 0;
  const machineMode = currentResult?.alert ? "alert" : resultVisible ? "scored" : cursor.received > 0 ? "receiving" : "idle";

  return (
    <div className="sim-page">
      <style>{simulatorStyles}</style>
      <main className="sim-shell">
        <div className="sim-topbar">
          <div className="sim-brand"><div className="sim-brand-mark"><RadioTower size={18} /></div><div><strong>Applied AI Studio</strong><span>Industrial telemetry simulator</span></div></div>
          <a className="sim-back" href="/maintenance"><ArrowLeft size={14} /><span>Evidence view</span></a>
        </div>

        <header className="sim-heading">
          <div><span>Condition monitoring simulator</span><h1>Compressor signal room</h1><p>Six feature readings arrive one at a time. When the packet is complete, the saved model produces one hourly score and the fixed policy decides whether to request review.</p></div>
          <div className="sim-runtime"><i /><span>{simulation ? `${simulation.model_type.replaceAll("_", " ")} · v${simulation.model_version}` : "connecting to model"}</span></div>
        </header>

        <section className="sim-controls" aria-label="Simulator controls">
          <div className="sim-field"><label htmlFor="sim-window">Sensor history</label><select id="sim-window" value={selectedId} onChange={(event) => setSelectedId(event.target.value)} disabled={loading}>{samples.map((sample) => <option key={sample.sample_id} value={sample.sample_id}>{sample.label}</option>)}</select></div>
          <div className="sim-field"><label htmlFor="sim-interval">Feature interval</label><select id="sim-interval" value={intervalMs} onChange={(event) => setIntervalMs(Number(event.target.value))}>{intervals.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
          <div className="sim-actions">
            <button className="sim-action primary" type="button" onClick={togglePlay} disabled={loading || !!error} aria-label={runState === "running" ? "Pause simulator" : runState === "complete" ? "Replay simulator" : "Run simulator"}>{runState === "running" ? <Pause size={16} /> : <Play size={16} />}{runState === "running" ? "Pause" : runState === "complete" ? "Replay" : "Run"}</button>
            <button className="sim-action" type="button" onClick={step} disabled={loading || !!error} title={cursor.phase === "scored" ? "Advance to next hour" : "Receive next feature"} aria-label={cursor.phase === "scored" ? "Advance to next hour" : "Receive next feature"}><SkipForward size={16} /></button>
            <button className="sim-action" type="button" onClick={reset} disabled={loading || !!error} title="Reset simulator" aria-label="Reset simulator"><RotateCcw size={16} /></button>
          </div>
        </section>

        {error ? <div className="sim-error" role="alert"><AlertTriangle size={30} /><p>{error}</p></div> : null}
        {loading && !error ? <div className="sim-loading"><RadioTower size={30} /><p>Loading packaged sensor history...</p></div> : null}

        {simulation && !loading ? <>
          <section className="sim-kpis" aria-label="Live simulator readings">
            <div className="sim-kpi"><span>Simulation clock</span><strong>{currentHour ? shortHour(currentHour.hour) : "--"}</strong><small>hour beginning</small></div>
            <div className="sim-kpi"><span>Feature packet</span><strong>{featureProgress}</strong><small>{cursor.phase === "scored" ? "score ready" : "arriving one by one"}</small></div>
            <div className="sim-kpi"><span>Latest score</span><strong>{lastCompleted ? lastCompleted.score.toFixed(3) : "Pending"}</strong><small>unusualness, not probability</small></div>
            <div className="sim-kpi"><span>Review cutoff</span><strong>{simulation.threshold.toFixed(1)}</strong><small>score at or above</small></div>
            <div className="sim-kpi"><span>Run progress</span><strong>{completedPercent}%</strong><small>{cursor.scoredHours} of {simulation.hours.length} hours · {alerts} flags</small></div>
          </section>

          <section className="sim-grid">
            <section className="sim-panel sim-input-panel">
              <header className="sim-panel-header"><div><span>Input stream</span><strong>Six-feature packet</strong><small>{currentHour ? shortHour(currentHour.hour) : "Waiting"}</small></div><DatabaseZap size={18} /></header>
              <div className="sim-instrument-stage">
                <div className={`sim-machine-core ${machineMode}`}>
                  <div className="sim-machine-meta">
                    <div><span>Asset CP-01</span><strong>Compressor train</strong></div>
                    <div className="sim-machine-health"><i />{machineMode === "alert" ? "review" : machineMode === "scored" ? "scored" : machineMode === "receiving" ? "streaming" : "standby"}</div>
                  </div>
                  <div className="sim-machine-visual" role="img" aria-label="Illustrated compressor motor, pump, pressure pipe, and gauge">
                    <div className="sim-machine-pipe" />
                    <div className="sim-machine-gauge"><Gauge size={21} /></div>
                    <div className="sim-machine-motor"><Fan size={35} /></div>
                    <div className="sim-machine-coupling" />
                    <div className="sim-machine-pump" />
                    <div className="sim-machine-base" />
                  </div>
                  <div className="sim-machine-readout"><div><span>Telemetry packet</span><small>{resultVisible ? "Model score published" : cursor.received ? "Sensors transmitting" : "Ready for incoming signals"}</small></div><strong>{featureProgress}</strong></div>
                </div>
                {currentHour?.features.map((feature, index) => {
                  const state = index < cursor.received ? "received" : index === cursor.received && cursor.phase === "receiving" ? "receiving" : "pending";
                  const visual = featureVisuals[feature.name] ?? { label: feature.display_name, icon: Activity };
                  const FeatureIcon = visual.icon;
                  return <article className={`sim-sensor-card sensor-${index} ${state}`} key={feature.name} aria-label={`${feature.display_name}: ${index < cursor.received ? feature.value_text : state === "receiving" ? "receiving" : "waiting"}. ${feature.direction_that_means_trouble}`}>
                    <div className="sim-sensor-head"><div className="sim-sensor-identity"><div className="sim-sensor-icon"><FeatureIcon size={16} /></div><div className="sim-sensor-name"><span>Input {String(index + 1).padStart(2, "0")}</span><strong>{visual.label}</strong></div></div><i className="sim-sensor-state" /></div>
                    <div className="sim-sensor-reading"><strong>{index < cursor.received ? compactFeatureValue(feature) : state === "receiving" ? "Receiving..." : "--"}</strong><small>{index < cursor.received ? `Typical ${feature.typical_text}` : "Awaiting signal"}</small></div>
                  </article>;
                })}
              </div>
              <div className="sim-packet-progress" aria-label={`${cursor.received} of ${simulation.feature_count} features received`}>{Array.from({ length: simulation.feature_count }, (_, index) => <i key={index} className={index < cursor.received ? "done" : index === cursor.received && cursor.phase === "receiving" ? "live" : ""} />)}</div>
            </section>

            <section className="sim-panel sim-chart-panel">
              <header className="sim-panel-header"><div><span>Model output</span><strong>Hourly anomaly score</strong><small>score appears after 6 of 6 readings</small></div><CircleGauge size={18} /></header>
              <div className="sim-chart-wrap"><StreamChart hours={completedHours} threshold={simulation.threshold} /></div>
              <div className="sim-chart-legend"><span><i /> hourly score</span><span><i className="cutoff" /> review cutoff</span><span><i className="alert" /> alert</span><span><i className="report" /> reported event hour</span></div>
              <div className="sim-event-log" aria-label="Latest simulator events">
                {completedHours.slice(-5).reverse().map((hour) => <div className="sim-log-row" key={hour.hour}><time>{shortHour(hour.hour)}</time><b>{hour.score.toFixed(3)}</b><span>{hour.alert ? "Review flag" : "No model flag"}{hour.reported_event ? ` · ${hour.event_name} report` : ""}</span></div>)}
              </div>
            </section>

            <section className="sim-panel sim-alert-panel" aria-live="polite">
              <header className="sim-panel-header"><div><span>Decision signal</span><strong>Alert state</strong><small>revealed after packet completion</small></div><Settings2 size={18} /></header>
              <div className={`sim-signal ${currentResult ? currentResult.alert ? "alert" : "clear" : "pending"}`}>
                <div className="sim-beacon">{currentResult ? currentResult.alert ? <AlertTriangle size={36} /> : <CheckCircle2 size={36} /> : <Clock3 size={34} />}</div>
                <h2>{currentResult ? currentResult.alert ? "REVIEW REQUIRED" : "NO MODEL FLAG" : "WAITING FOR DATA"}</h2>
                <p>{currentResult ? currentResult.alert ? `${currentResult.score.toFixed(3)} is at or above ${simulation.threshold.toFixed(1)}.` : `${currentResult.score.toFixed(3)} is below ${simulation.threshold.toFixed(1)}.` : `Receive all ${simulation.feature_count} readings before scoring this hour.`}</p>
              </div>
              <div className="sim-signal-details">
                <div className="sim-detail"><span>Current packet</span><strong>{currentHour ? shortHour(currentHour.hour) : "--"}</strong><small>{cursor.received} of {simulation.feature_count} features received</small></div>
                <div className={`sim-detail ${currentResult?.reported_event ? "reported" : ""}`}><span>Maintenance report</span><strong>{currentResult ? currentResult.reported_event ? `${currentResult.event_name} overlaps this hour` : "No report overlaps this hour" : "Withheld until score is ready"}</strong><small>Report labels never enter the feature packet.</small></div>
                <div className="sim-detail"><span>Next action</span><strong>{currentResult?.alert ? "Technician reviews equipment and context" : currentResult ? "Continue monitoring" : "Complete feature packet"}</strong><small>The model never diagnoses or authorizes work.</small></div>
              </div>
            </section>
          </section>
          <div className="sim-footnote"><Wrench size={17} /><p><strong>{simulation.label}.</strong> {simulation.purpose} {simulation.authority_boundary}</p></div>
        </> : null}
      </main>
    </div>
  );
}