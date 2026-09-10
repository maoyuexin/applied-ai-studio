import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  BadgeCheck,
  Ban,
  CheckCircle2,
  Circle,
  Layers3,
  Minus,
  RefreshCcw,
  Repeat,
  Scale,
  ShoppingBag,
  Sparkles,
  Table2,
  UserRound,
} from "lucide-react";
import {
  getRecommendCompare,
  getRecommendCustomers,
  getRecommendModel,
  getRecommendSlots,
  type RecommendCompareResult,
  type RecommendLeaderboardRow,
  type RecommendModelInfo,
  type RecommendPackagedCustomer,
  type RecommendProtocol,
  type RecommendSlotsResult,
} from "../recommendApi";
import { navigate } from "../router";

type View = "shopper" | "leaderboards" | "evidence";

const views = [
  {
    id: "shopper" as const,
    label: "Recommend for one shopper",
    detail: "Ten slots, and why each one is there",
    icon: ShoppingBag,
  },
  {
    id: "leaderboards" as const,
    label: "The two leaderboards",
    detail: "Same models, opposite verdicts",
    icon: Table2,
  },
  {
    id: "evidence" as const,
    label: "Model card and evidence",
    detail: "What was measured, and what it is not",
    icon: Layers3,
  },
];

const REORDER = "Reorder (already-bought)";
const POPULARITY = "Popularity";

const percent = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;
const decimal = (value: number, digits = 4): string => value.toFixed(digits);
const integer = (value: number): string => new Intl.NumberFormat("en-US").format(value);
const money = (value: number): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "GBP", maximumFractionDigits: 0 })
    .format(value);

const pageStyles = `
.recommend-page .page-back-button { min-height: 44px; }
.recommend-page h2 { margin: 0; font-size: 18px; line-height: 1.3; }
.recommend-page h3 { margin: 0; font-size: 14px; line-height: 1.35; }
.recommend-page button { min-height: 44px; cursor: pointer; }

.rc-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 18px; }
.rc-header h1 { margin: 3px 0 6px; font-size: 27px; line-height: 1.2; font-weight: 750; }
.rc-header p { margin: 0; max-width: 760px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.rc-status { min-height: 44px; display: flex; align-items: center; gap: 10px; padding: 8px 13px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.rc-status i { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: var(--text-muted); }
.rc-status i.ready { background: var(--green); box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.12); }
.rc-status strong { display: block; font-size: 12px; font-style: normal; }
.rc-status small { display: block; margin-top: 2px; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }

.rc-metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin-bottom: 18px; }
.rc-metric-strip div { min-height: 86px; padding: 13px 16px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid var(--border); }
.rc-metric-strip div:last-child { border-right: 0; }
.rc-metric-strip strong { font-family: var(--font-mono); font-size: 20px; }
.rc-metric-strip span { margin-top: 2px; font-size: 11px; }
.rc-metric-strip small { margin-top: 3px; color: var(--text-muted); font-size: 10px; line-height: 1.45; }

.rc-boundary { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 11px; margin-bottom: 16px; padding: 13px 15px; border: 1px solid rgba(126, 174, 184, 0.4); border-left: 3px solid var(--teal); border-radius: 6px; background: rgba(126, 174, 184, 0.07); color: var(--teal); }
.rc-boundary strong { display: block; color: var(--text); font-size: 13px; }
.rc-boundary p { margin: 5px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }

.rc-switcher { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); overflow: hidden; }
.rc-switcher button { min-height: 62px; padding: 11px 14px; display: flex; align-items: center; gap: 11px; border: 0; border-right: 1px solid var(--border); background: transparent; color: var(--text-muted); text-align: left; transition: 160ms ease; }
.rc-switcher button:last-child { border-right: 0; }
.rc-switcher button:hover { background: var(--surface-raised); color: var(--text-secondary); }
.rc-switcher button.active { background: rgba(232, 145, 60, 0.09); box-shadow: inset 0 -3px 0 var(--orange); color: var(--orange); }
.rc-switcher strong { display: block; color: var(--text); font-size: 13px; }
.rc-switcher small { display: block; margin-top: 3px; color: var(--text-muted); font-size: 11px; line-height: 1.35; }

.rc-panel { border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }
.rc-panel > header { padding: 13px 16px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--border); }
.rc-panel > header span.rc-kicker { display: block; color: var(--teal); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; }
.rc-panel > header strong { display: block; margin-top: 4px; font-size: 14px; }
.rc-panel > header small { display: block; margin-top: 4px; max-width: 720px; color: var(--text-muted); font-size: 11px; line-height: 1.55; }
.rc-panel-body { padding: 14px 16px; }

.rc-stack { display: flex; flex-direction: column; gap: 14px; }
.rc-shopper-grid { display: grid; grid-template-columns: minmax(260px, 0.9fr) minmax(0, 2.1fr); gap: 14px; align-items: start; }

.rc-customer-list { max-height: 620px; overflow-y: auto; padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 7px; }
.rc-customer-list button { flex: 0 0 auto; min-height: 78px; height: auto; width: 100%; padding: 10px 12px; display: block; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); color: var(--text-secondary); text-align: left; transition: 140ms ease; }
.rc-customer-list button:hover { border-color: var(--teal); color: var(--text); }
.rc-customer-list button.active { border-color: var(--orange); background: rgba(232, 145, 60, 0.1); color: var(--text); }
.rc-customer-list button.cold { border-style: dashed; }
.rc-customer-list button > span.rc-id { display: block; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; }
.rc-customer-list button strong { display: block; margin: 4px 0 5px; font-size: 12px; line-height: 1.35; }
.rc-customer-list button small { display: block; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.rc-customer-list button > span.rc-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }

.rc-chip { display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px; border: 1px solid var(--border-strong); border-radius: 20px; color: var(--text-secondary); font-family: var(--font-mono); font-size: 9px; white-space: nowrap; }
.rc-chip.good { border-color: rgba(74, 222, 128, 0.45); background: rgba(74, 222, 128, 0.1); color: var(--green); }
.rc-chip.warn { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.1); color: var(--amber); }
.rc-chip.risk { border-color: rgba(228, 90, 88, 0.45); background: rgba(228, 90, 88, 0.1); color: var(--red); }
.rc-chip.info { border-color: rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.1); color: var(--teal); }

.rc-protocol-switch { display: flex; flex-wrap: wrap; gap: 8px; }
.rc-protocol-switch button { min-height: 46px; padding: 8px 14px; display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--border-strong); border-radius: 5px; background: var(--surface-raised); color: var(--text-secondary); font-size: 12px; }
.rc-protocol-switch button:hover { border-color: var(--teal); color: var(--text); }
.rc-protocol-switch button.active { border-color: var(--orange); background: rgba(232, 145, 60, 0.12); color: var(--orange); font-weight: 600; }

.rc-protocol-note { margin-top: 12px; padding: 11px 13px; border: 1px dashed var(--border-strong); border-radius: 5px; background: rgba(34, 37, 48, 0.6); }
.rc-protocol-note dl { margin: 0; display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px 12px; }
.rc-protocol-note dt { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; padding-top: 2px; }
.rc-protocol-note dd { margin: 0; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }

.rc-history { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 12px; }
.rc-history > div { padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); }
.rc-history strong { display: block; font-family: var(--font-mono); font-size: 17px; }
.rc-history span { display: block; margin-top: 3px; color: var(--text-secondary); font-size: 10px; line-height: 1.45; }
.rc-history-products { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 6px; }
.rc-history-products li { padding: 4px 9px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface-raised); color: var(--text-secondary); font-size: 10px; }
.rc-history-products li b { color: var(--text); font-weight: 600; }

.rc-module { border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface-raised); }
.rc-module > header { padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; border-bottom: 1px solid var(--border); }
.rc-module h3 { display: flex; align-items: center; gap: 8px; }
.rc-module.fallback { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.05); }
.rc-module.reorder { border-style: dashed; border-color: rgba(201, 106, 150, 0.55); background: rgba(201, 106, 150, 0.05); }

.rc-slot-list { margin: 0; padding: 12px 14px; list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 9px; }
.rc-slot { padding: 10px 12px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.rc-slot.hit { border-color: rgba(74, 222, 128, 0.45); }
.rc-slot.owned { border-color: rgba(228, 90, 88, 0.45); }
.rc-slot-head { display: flex; align-items: baseline; gap: 8px; }
.rc-slot-head b { color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; }
.rc-slot-head span { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; margin-left: auto; }
.rc-slot p { margin: 5px 0 0; color: var(--text); font-size: 12px; line-height: 1.4; font-weight: 600; }
.rc-slot small { display: block; margin-top: 5px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.rc-slot-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }

.rc-reorder-list { margin: 0; padding: 12px 14px; list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
.rc-reorder-list li { padding: 9px 11px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.rc-reorder-list b { display: block; color: var(--text); font-size: 11px; line-height: 1.4; }
.rc-reorder-list span { display: block; margin-top: 4px; color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; }

.rc-note { margin: 0; padding: 11px 14px; color: var(--text-muted); font-size: 11px; line-height: 1.6; border-top: 1px solid var(--border); }
.rc-callout { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 10px; padding: 12px 14px; border-radius: 5px; border: 1px solid var(--border-strong); background: var(--surface-raised); }
.rc-callout strong { display: block; font-size: 12px; }
.rc-callout p { margin: 5px 0 0; color: var(--text-secondary); font-size: 11px; line-height: 1.6; }
.rc-callout.warn { border-color: rgba(240, 180, 41, 0.5); background: rgba(240, 180, 41, 0.07); color: var(--amber); }
.rc-callout.risk { border-color: rgba(228, 90, 88, 0.45); background: rgba(228, 90, 88, 0.07); color: var(--red); }
.rc-callout.info { border-color: rgba(126, 174, 184, 0.45); background: rgba(126, 174, 184, 0.07); color: var(--teal); }

.rc-scroll { width: 100%; overflow-x: auto; }
.rc-table { width: 100%; min-width: 520px; border-collapse: collapse; font-size: 11px; }
.rc-table caption { padding: 0 0 9px; color: var(--text-muted); font-size: 10px; line-height: 1.5; text-align: left; }
.rc-table th, .rc-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: middle; }
.rc-table th { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 500; }
.rc-table td.num, .rc-table th.num { text-align: right; font-family: var(--font-mono); }
.rc-table tbody tr.deployed { background: rgba(74, 222, 128, 0.07); }
.rc-table tbody tr.flagged { background: rgba(228, 90, 88, 0.09); }
.rc-table tbody tr.muted td { color: var(--text-muted); }
.rc-table td b { font-weight: 600; }
.rc-rank { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 22px; padding: 0 6px; border: 1px solid var(--border-strong); border-radius: 4px; font-family: var(--font-mono); font-size: 10px; }
.rc-rank.top { border-color: rgba(74, 222, 128, 0.5); background: rgba(74, 222, 128, 0.12); color: var(--green); }
.rc-rank.bottom { border-color: rgba(228, 90, 88, 0.5); background: rgba(228, 90, 88, 0.12); color: var(--red); }
.rc-bar { display: block; height: 6px; margin-top: 4px; border-radius: 3px; background: var(--border); overflow: hidden; }
.rc-bar i { display: block; height: 100%; background: var(--teal); }
.rc-bar i.deployed { background: var(--green); }
.rc-bar i.flagged { background: var(--red); }
.rc-bar i.tiny { background: var(--amber); }

.rc-two-up { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }
.rc-inversion { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.rc-inversion > div { padding: 12px 14px; border: 1px solid var(--border); border-radius: 5px; background: var(--surface-raised); }
.rc-inversion strong { display: block; font-family: var(--font-mono); font-size: 20px; }
.rc-inversion span { display: block; margin-top: 3px; font-size: 11px; }
.rc-inversion small { display: block; margin-top: 4px; color: var(--text-muted); font-size: 10px; line-height: 1.5; }
.rc-inversion > div.risk { border-color: rgba(228, 90, 88, 0.45); background: rgba(228, 90, 88, 0.07); }
.rc-inversion > div.risk strong { color: var(--red); }
.rc-inversion > div.good { border-color: rgba(74, 222, 128, 0.4); background: rgba(74, 222, 128, 0.06); }
.rc-inversion > div.good strong { color: var(--green); }

.rc-facts { margin: 0; display: grid; grid-template-columns: minmax(150px, max-content) minmax(0, 1fr); gap: 8px 16px; }
.rc-facts dt { color: var(--text-muted); font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; padding-top: 2px; }
.rc-facts dd { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.55; }
.rc-facts dd b { color: var(--text); }

.rc-list { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.rc-list li { margin-bottom: 6px; }
.rc-list li:last-child { margin-bottom: 0; }

.rc-policy-statement { margin: 0; padding: 12px 14px; border: 1px solid var(--border); border-radius: 5px; background: #14161c; color: var(--text-secondary); font-family: var(--font-mono); font-size: 10px; line-height: 1.7; white-space: pre-wrap; overflow-x: auto; }

.rc-gap { display: flex; flex-direction: column; gap: 10px; }
.rc-gap-row { display: grid; grid-template-columns: minmax(120px, 190px) minmax(0, 1fr) minmax(58px, max-content); gap: 10px; align-items: center; }
.rc-gap-row span { font-size: 11px; color: var(--text-secondary); }
.rc-gap-row b { font-family: var(--font-mono); font-size: 12px; text-align: right; }
.rc-gap-track { height: 14px; border-radius: 3px; background: var(--border); overflow: hidden; }
.rc-gap-track i { display: block; height: 100%; background: var(--teal); }
.rc-gap-track i.deployed { background: var(--green); }
.rc-gap-track i.none { background: var(--amber); }

.rc-empty { padding: 26px 16px; color: var(--text-muted); font-size: 12px; line-height: 1.6; text-align: center; }

@media (max-width: 1120px) {
  .rc-shopper-grid { grid-template-columns: minmax(0, 1fr); }
  .rc-customer-list { max-height: 340px; }
  .rc-two-up { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 760px) {
  .rc-metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rc-metric-strip div:nth-child(2) { border-right: 0; }
  .rc-switcher { grid-template-columns: minmax(0, 1fr); }
  .rc-switcher button { border-right: 0; border-bottom: 1px solid var(--border); }
  .rc-switcher button:last-child { border-bottom: 0; }
  .rc-facts { grid-template-columns: minmax(0, 1fr); gap: 3px; }
  .rc-facts dd { margin-bottom: 8px; }
  .rc-protocol-note dl { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  .rc-protocol-note dd { margin-bottom: 7px; }
  .rc-gap-row { grid-template-columns: minmax(0, 1fr); }
  .rc-gap-row b { text-align: left; }
  .rc-slot-list, .rc-reorder-list { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 430px) {
  .recommend-page .rc-header h1 { font-size: 22px; }
  .rc-metric-strip { grid-template-columns: minmax(0, 1fr); }
  .rc-metric-strip div { border-right: 0; border-bottom: 1px solid var(--border); }
  .rc-metric-strip div:last-child { border-bottom: 0; }
}
`;

function HitBar({ value, tone }: { value: number; tone: "deployed" | "flagged" | "tiny" | "" }) {
  return (
    <span className="rc-bar" aria-hidden="true">
      <i className={tone} style={{ width: `${Math.max(1.5, Math.min(100, value * 100))}%` }} />
    </span>
  );
}

function Leaderboard({
  title,
  kicker,
  rows,
  question,
  groundTruth,
  candidates,
  scored,
}: {
  title: string;
  kicker: string;
  rows: RecommendLeaderboardRow[];
  question: string;
  groundTruth: string;
  candidates: string;
  scored: number;
}) {
  return (
    <section className="rc-panel">
      <header>
        <span>
          <span className="rc-kicker">{kicker}</span>
          <strong>{title}</strong>
          <small>
            Asks: {question} Correct answers are {groundTruth}. Candidates are {candidates}.{" "}
            {integer(scored)} customers scored.
          </small>
        </span>
      </header>
      <div className="rc-panel-body rc-scroll">
        <table className="rc-table">
          <caption>
            Coverage and novelty are printed beside every accuracy number, always. Coverage is the
            share of the 4,443-product catalog that appeared in anybody&apos;s ten slots. Novelty is
            higher when the list is made of less-bought products.
          </caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Model</th>
              <th scope="col" className="num">Hit rate @10</th>
              <th scope="col" className="num">Catalog coverage</th>
              <th scope="col" className="num">Novelty</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const flagged = row.model === REORDER;
              const tiny = row.model === POPULARITY;
              return (
                <tr
                  key={row.model}
                  className={row.is_deployed ? "deployed" : flagged ? "flagged" : ""}
                >
                  <td>
                    <span
                      className={`rc-rank ${row.rank === 1 ? "top" : row.rank === rows.length ? "bottom" : ""}`}
                    >
                      {row.rank}
                    </span>
                  </td>
                  <td>
                    <b>{row.model}</b>
                    {row.is_deployed ? (
                      <span className="rc-chip good" style={{ marginLeft: 7 }}>
                        <BadgeCheck size={11} aria-hidden="true" /> shipped
                      </span>
                    ) : null}
                    {flagged ? (
                      <span className="rc-chip risk" style={{ marginLeft: 7 }}>
                        <AlertTriangle size={11} aria-hidden="true" /> learns nothing
                      </span>
                    ) : null}
                  </td>
                  <td className="num">
                    {percent(row.hr_at_10, 2)}
                    <HitBar
                      value={row.hr_at_10}
                      tone={row.is_deployed ? "deployed" : flagged ? "flagged" : ""}
                    />
                  </td>
                  <td className="num">
                    {percent(row.coverage, 2)}
                    <HitBar value={row.coverage} tone={tiny ? "tiny" : ""} />
                  </td>
                  <td className="num">{decimal(row.novelty, 2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function RecommendPage() {
  const [view, setView] = useState<View>("shopper");
  const [model, setModel] = useState<RecommendModelInfo | null>(null);
  const [customers, setCustomers] = useState<RecommendPackagedCustomer[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [protocol, setProtocol] = useState<RecommendProtocol>("discovery");
  const [result, setResult] = useState<RecommendSlotsResult | null>(null);
  const [comparison, setComparison] = useState<RecommendCompareResult | null>(null);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getRecommendModel(), getRecommendCustomers(24)])
      .then(([modelInfo, roster]) => {
        if (cancelled) return;
        setModel(modelInfo);
        setCustomers(roster);
        const first = roster[0];
        if (first) setSelectedId(first.customer_id);
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    setRunning(true);
    setSlotError(null);
    void Promise.all([getRecommendSlots(selectedId, protocol), getRecommendCompare(selectedId)])
      .then(([slots, compare]) => {
        if (cancelled) return;
        setResult(slots);
        setComparison(compare);
      })
      .catch((reason: Error) => {
        if (cancelled) return;
        setResult(null);
        setComparison(null);
        setSlotError(reason.message);
      })
      .finally(() => {
        if (!cancelled) setRunning(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, protocol]);

  const selected = customers.find((entry) => entry.customer_id === selectedId) ?? null;

  const inversion = useMemo(
    () => model?.leaderboards.side_by_side.find((row) => row.model === REORDER) ?? null,
    [model],
  );
  const randomDiscovery = useMemo(
    () => model?.leaderboards.discovery.find((row) => row.model === "Random 10") ?? null,
    [model],
  );
  const deployedDiscovery = useMemo(
    () => model?.leaderboards.discovery.find((row) => row.is_deployed) ?? null,
    [model],
  );
  const popularityStandard = useMemo(
    () => model?.leaderboards.standard.find((row) => row.model === POPULARITY) ?? null,
    [model],
  );
  const standardProtocol = model?.protocols.find((row) => row.id === "standard") ?? null;
  const discoveryProtocol = model?.protocols.find((row) => row.id === "discovery") ?? null;
  const incoherentProtocol = model?.protocols.find((row) => row.id === "incoherent-middle") ?? null;

  return (
    <div className="page recommend-page">
      <style>{pageStyles}</style>

      <button className="page-back-button" type="button" onClick={() => navigate("/showcase")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>

      <header className="rc-header">
        <div>
          <span className="eyebrow">Recommender systems · Storefront merchandising</span>
          <h1>Which ten products should this shopper see?</h1>
          <p>
            One merchandising module on a giftware storefront has ten slots in it. This model ranks
            products the shopper has never bought and fills those ten slots. The whole case is in
            one detail: change what you count as a correct answer, and the winning model changes
            with it.
          </p>
        </div>
        <div className="rc-status">
          <i className={model ? "ready" : ""} aria-hidden="true" />
          <div>
            <strong>{model ? "Model ready" : "Connecting to the model"}</strong>
            <small>
              FastAPI · {model ? model.deployed_model.label : "item-item CF"} ·{" "}
              {model ? `${model.deployed_model.stored_megabytes.toFixed(2)} MB` : "0.55 MB"}
            </small>
          </div>
        </div>
      </header>

      {model ? (
        <section
          className="rc-metric-strip"
          aria-label="Results measured once on the untouched test window"
        >
          <div>
            <strong>{percent(model.leaderboards.discovery[0].hr_at_10)}</strong>
            <span>best discovery hit rate</span>
            <small>
              At least one of ten slots bought next, among products new to that shopper. The
              shipped model reaches {deployedDiscovery ? percent(deployedDiscovery.hr_at_10) : "-"}.
            </small>
          </div>
          <div>
            <strong>{inversion ? percent(inversion.standard_hr10) : "-"}</strong>
            <span>a baseline that learns nothing</span>
            <small>
              Listing what the shopper already buys wins the standard table outright, then falls to{" "}
              {inversion ? percent(inversion.discovery_hr10, 2) : "-"} on discovery.
            </small>
          </div>
          <div>
            <strong>{percent(model.incremental_revenue.deployed_share, 2)}</strong>
            <span>of new-product revenue reached</span>
            <small>
              Against {percent(model.incremental_revenue.no_personalization_share, 2)} with no
              personalization at all. A {model.incremental_revenue.gain_percentage_points}-point
              gap, and an upper bound.
            </small>
          </div>
          <div>
            <strong>{percent(model.cold_start.unservable_share)}</strong>
            <span>of shoppers cannot be served</span>
            <small>
              No history, or too little of it. They get a generic list that says so on the label.
            </small>
          </div>
        </section>
      ) : null}

      <div className="rc-boundary">
        <Scale size={19} aria-hidden="true" />
        <div>
          <strong>An offline ranking score is not evidence of revenue.</strong>
          <p>
            Merchandisers own placement and exclusions; the model only ranks products inside the
            rules they set. A recommendation is not a statement about what the shopper needs, and a
            hit rate measured on one 13-week window of one retailer&apos;s history in 2011 is not a
            business case. Nothing here describes any real retailer&apos;s current operations.
          </p>
        </div>
      </div>

      <nav className="rc-switcher" aria-label="Product recommendation views">
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
        <div className="loading-state">
          Loading the model card, the packaged shoppers, and the operating policy...
        </div>
      ) : null}

      {model && view === "shopper" ? (
        <div className="rc-shopper-grid">
          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Packaged shoppers</span>
                <strong>Pick a shopper</strong>
                <small>
                  Ten of these were chosen by the notebook using rules anyone can re-run. Two more
                  are shoppers the model cannot serve at all.
                </small>
              </span>
            </header>
            <div className="rc-customer-list">
              {customers.map((entry) => (
                <button
                  type="button"
                  key={entry.customer_id}
                  className={`${entry.customer_id === selectedId ? "active" : ""} ${entry.cold_start ? "cold" : ""}`}
                  aria-pressed={entry.customer_id === selectedId}
                  onClick={() => setSelectedId(entry.customer_id)}
                >
                  <span className="rc-id">Shopper {entry.customer_id}</span>
                  <strong>{entry.persona}</strong>
                  <small>{entry.history_note}</small>
                  <span className="rc-chip-row">
                    {entry.cold_start ? (
                      <span className="rc-chip warn">
                        <Ban size={11} aria-hidden="true" /> cannot be personalized
                      </span>
                    ) : (
                      <span className="rc-chip info">
                        <Sparkles size={11} aria-hidden="true" />{" "}
                        {entry.discovery_hits_out_of_10} of 10 on discovery
                      </span>
                    )}
                    {entry.is_discussion_case ? (
                      <span className="rc-chip risk">
                        <AlertTriangle size={11} aria-hidden="true" /> discussion case
                      </span>
                    ) : null}
                    {!entry.cold_start && entry.reorder_hits_out_of_10_standard !== null ? (
                      <span className="rc-chip">
                        <Repeat size={11} aria-hidden="true" />{" "}
                        {entry.reorder_hits_out_of_10_standard} of 10 reorder
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <div className="rc-stack">
            <section className="rc-panel">
              <header>
                <span>
                  <span className="rc-kicker">Protocol switch</span>
                  <strong>What counts as a correct answer?</strong>
                  <small>
                    Same shopper, same model, same day. Only the question changes - and the ten
                    products change with it.
                  </small>
                </span>
                <div className="rc-protocol-switch">
                  <button
                    type="button"
                    className={protocol === "discovery" ? "active" : ""}
                    aria-pressed={protocol === "discovery"}
                    onClick={() => setProtocol("discovery")}
                  >
                    <Sparkles size={15} aria-hidden="true" /> Discovery (shipped)
                  </button>
                  <button
                    type="button"
                    className={protocol === "standard" ? "active" : ""}
                    aria-pressed={protocol === "standard"}
                    onClick={() => setProtocol("standard")}
                  >
                    <Repeat size={15} aria-hidden="true" /> Standard next-purchase
                  </button>
                </div>
              </header>
              <div className="rc-panel-body">
                {result ? (
                  <>
                    <div className="rc-history">
                      <div>
                        <strong>{integer(result.history.training_products)}</strong>
                        <span>distinct products bought before the cut</span>
                      </div>
                      <div>
                        <strong>{integer(result.history.training_baskets)}</strong>
                        <span>orders before the cut</span>
                      </div>
                      <div>
                        <strong>{integer(result.history.bought_after_the_cut)}</strong>
                        <span>products bought after the cut</span>
                      </div>
                      <div>
                        <strong>{integer(result.history.new_to_them_after_the_cut)}</strong>
                        <span>of those that were new to them</span>
                      </div>
                    </div>
                    <p style={{ margin: "0 0 10px", color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.6 }}>
                      {result.history.note}
                    </p>
                    {result.history.top_products.length > 0 ? (
                      <ul className="rc-history-products">
                        {result.history.top_products.map((product) => (
                          <li key={product.stock_code}>
                            <b>{product.description}</b> · {product.baskets} order
                            {product.baskets === 1 ? "" : "s"}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="rc-protocol-note">
                      <dl>
                        <dt>Protocol</dt>
                        <dd>{result.protocol_detail.name}</dd>
                        <dt>Asks</dt>
                        <dd>{result.protocol_detail.question}</dd>
                        <dt>Counts as right</dt>
                        <dd>{result.protocol_detail.ground_truth}</dd>
                        <dt>Can be shown</dt>
                        <dd>{result.protocol_detail.candidates}</dd>
                      </dl>
                    </div>
                  </>
                ) : (
                  <p className="rc-empty">
                    {running ? "Ranking this shopper..." : "Pick a shopper to see their history."}
                  </p>
                )}
              </div>
            </section>

            {slotError ? (
              <div className="error-banner" role="alert">
                {slotError}
              </div>
            ) : null}

            {result ? (
              <>
                {!result.matches_shipping_policy ? (
                  <div className="rc-callout warn">
                    <AlertTriangle size={16} aria-hidden="true" />
                    <div>
                      <strong>This is a measurement view, not the storefront.</strong>
                      <p>{result.policy_note}</p>
                    </div>
                  </div>
                ) : null}

                {result.is_discussion_case ? (
                  <div className="rc-callout risk">
                    <AlertTriangle size={16} aria-hidden="true" />
                    <div>
                      <strong>Discussion case, and not a bug.</strong>
                      <p>{result.discussion_note}</p>
                    </div>
                  </div>
                ) : null}

                <section className={`rc-module ${result.personalized ? "" : "fallback"}`}>
                  <header>
                    <h3>
                      {result.personalized ? (
                        <Sparkles size={16} aria-hidden="true" />
                      ) : (
                        <Ban size={16} aria-hidden="true" />
                      )}
                      {result.module_title}
                    </h3>
                    <span className="rc-chip-row" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span className={`rc-chip ${result.personalized ? "info" : "warn"}`}>
                        {result.personalized ? "personalized" : "not personalized"}
                      </span>
                      <span className="rc-chip">{result.model_used}</span>
                      <span className="rc-chip good">
                        <CheckCircle2 size={11} aria-hidden="true" /> {result.hits_out_of_10} of 10
                        bought later
                      </span>
                    </span>
                  </header>
                  {result.slots.length === 0 ? (
                    <p className="rc-empty">
                      Nothing scored above zero, so nothing is shown. A ranking built from a zero
                      score vector is a tie-break, not a recommendation.
                    </p>
                  ) : (
                    <ol className="rc-slot-list">
                      {result.slots.map((slot) => (
                        <li
                          key={slot.stock_code}
                          className={`rc-slot ${slot.already_owned ? "owned" : slot.bought_after_the_cut ? "hit" : ""}`}
                        >
                          <span className="rc-slot-head">
                            <b>Slot {slot.slot}</b>
                            <span>{slot.stock_code}</span>
                          </span>
                          <p>{slot.description}</p>
                          <small>{slot.reason}</small>
                          <span className="rc-slot-chips">
                            <span className="rc-chip">
                              score {decimal(slot.score, slot.from_fallback ? 2 : 4)}
                            </span>
                            {slot.already_owned ? (
                              <span className="rc-chip risk">
                                <Repeat size={11} aria-hidden="true" /> already owns this
                              </span>
                            ) : (
                              <span className="rc-chip info">
                                <Sparkles size={11} aria-hidden="true" /> new to them
                              </span>
                            )}
                            {slot.bought_after_the_cut ? (
                              <span className="rc-chip good">
                                <CheckCircle2 size={11} aria-hidden="true" /> bought later
                              </span>
                            ) : (
                              <span className="rc-chip">
                                <Circle size={11} aria-hidden="true" /> not bought
                              </span>
                            )}
                            {slot.from_fallback ? (
                              <span className="rc-chip warn">
                                <Ban size={11} aria-hidden="true" /> generic list
                              </span>
                            ) : null}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                  <p className="rc-note">
                    {result.reason} {result.score_basis}
                  </p>
                </section>

                <section className="rc-module reorder">
                  <header>
                    <h3>
                      <Repeat size={16} aria-hidden="true" />
                      {result.buy_it_again.title}
                    </h3>
                    <span className="rc-chip warn">
                      never counted as personalization
                    </span>
                  </header>
                  {result.buy_it_again.available ? (
                    <ol className="rc-reorder-list">
                      {result.buy_it_again.items.map((item) => (
                        <li key={item.stock_code}>
                          <b>{item.description}</b>
                          <span>
                            {item.stock_code} · {item.baskets_bought_in} past order
                            {item.baskets_bought_in === 1 ? "" : "s"}
                            {item.bought_after_the_cut ? " · bought again" : ""}
                          </span>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="rc-empty">{result.buy_it_again.note}</p>
                  )}
                  <p className="rc-note">
                    {result.buy_it_again.rule}. This strip is a separate surface with its own
                    heading. {result.buy_it_again.note} On this shopper it would have got{" "}
                    {result.buy_it_again.hits_out_of_10_standard} of 10 right - which is exactly
                    why it must never be scored as if it were a recommender.
                  </p>
                </section>

                <section className="rc-panel">
                  <header>
                    <span>
                      <span className="rc-kicker">This shopper, every model</span>
                      <strong>What each model would have shown</strong>
                      <small>
                        One shopper is an illustration, not a measurement. The two right-hand
                        columns are the frozen population results for the same models.
                      </small>
                    </span>
                  </header>
                  <div className="rc-panel-body">
                    {comparison && comparison.personalized ? (
                      <div className="rc-scroll">
                        <table className="rc-table">
                          <caption>
                            Hits are out of ten slots, for shopper {comparison.customer_id} only.
                            {" "}Under the standard protocol this shopper had{" "}
                            {integer(comparison.truth_standard)} correct answers available; under
                            discovery, {integer(comparison.truth_discovery)}.
                          </caption>
                          <thead>
                            <tr>
                              <th scope="col">Model</th>
                              <th scope="col" className="num">Standard hits</th>
                              <th scope="col" className="num">Discovery hits</th>
                              <th scope="col" className="num">Standard rank</th>
                              <th scope="col" className="num">Discovery rank</th>
                            </tr>
                          </thead>
                          <tbody>
                            {comparison.models.map((row) => (
                              <tr
                                key={row.model}
                                className={
                                  row.is_deployed ? "deployed" : row.model === REORDER ? "flagged" : ""
                                }
                              >
                                <td>
                                  <b>{row.model}</b>
                                  {row.discovery.all_scores_zero ? (
                                    <span className="rc-chip risk" style={{ marginLeft: 7 }}>
                                      <AlertTriangle size={11} aria-hidden="true" /> every score
                                      zero
                                    </span>
                                  ) : null}
                                </td>
                                <td className="num">
                                  {row.standard.hits_out_of_10} of 10
                                  {row.standard.already_owned_in_slots > 0 ? (
                                    <span
                                      style={{
                                        display: "block",
                                        color: "var(--text-muted)",
                                        fontSize: 9,
                                      }}
                                    >
                                      {row.standard.already_owned_in_slots} already owned
                                    </span>
                                  ) : null}
                                </td>
                                <td className="num">{row.discovery.hits_out_of_10} of 10</td>
                                <td className="num">
                                  <span className={`rc-rank ${row.standard_rank === 1 ? "top" : ""}`}>
                                    {row.standard_rank}
                                  </span>
                                </td>
                                <td className="num">
                                  <span className={`rc-rank ${row.discovery_rank === 7 ? "bottom" : row.discovery_rank === 1 ? "top" : ""}`}>
                                    {row.discovery_rank}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="rc-empty">
                        {comparison ? comparison.reason : "Loading the comparison..."}
                      </p>
                    )}
                    {comparison && comparison.personalized ? (
                      <p className="rc-note" style={{ borderTop: 0, paddingLeft: 0, paddingRight: 0 }}>
                        {comparison.lesson}
                      </p>
                    ) : null}
                  </div>
                </section>
              </>
            ) : !slotError && selected ? (
              <div className="loading-state">Ranking shopper {selected.customer_id}...</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {model && view === "leaderboards" ? (
        <div className="rc-stack">
          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">The inversion</span>
                <strong>One model, two tables, opposite verdicts</strong>
                <small>{model.leaderboards.rule}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <div className="rc-inversion">
                <div className="good">
                  <strong>#{inversion?.standard_rank}</strong>
                  <span>Reorder baseline, standard table</span>
                  <small>
                    {inversion ? percent(inversion.standard_hr10, 2) : "-"} hit rate. It shows the
                    shopper what they already buy, most-ordered first. Nothing is learned.
                  </small>
                </div>
                <div className="risk">
                  <strong>#{inversion?.discovery_rank}</strong>
                  <span>The same baseline, discovery table</span>
                  <small>
                    {inversion ? percent(inversion.discovery_hr10, 2) : "-"} - below ten products
                    drawn at random, which score{" "}
                    {randomDiscovery ? percent(randomDiscovery.hr_at_10, 2) : "-"}.
                  </small>
                </div>
                <div>
                  <strong>
                    {model.repeat_purchasing.repeat_share
                      ? percent(model.repeat_purchasing.repeat_share)
                      : "-"}
                  </strong>
                  <span>of correct answers are repeat buys</span>
                  <small>
                    And {percent(model.repeat_purchasing.repeat_revenue_share)} of the revenue.
                    That single fact is what puts a model that learns nothing on top of the
                    standard table.
                  </small>
                </div>
              </div>
              <div className="rc-callout risk" style={{ marginTop: 12 }}>
                <AlertTriangle size={16} aria-hidden="true" />
                <div>
                  <strong>
                    Rank {inversion?.standard_rank} on one table, rank {inversion?.discovery_rank}{" "}
                    on the other. Both numbers are real.
                  </strong>
                  <p>{model.leaderboards.reorder_zero_score_diagnosis.explanation}</p>
                </div>
              </div>
            </div>
          </section>

          <div className="rc-two-up">
            {standardProtocol ? (
              <Leaderboard
                title="Standard next-purchase"
                kicker="Protocol 1"
                rows={model.leaderboards.standard}
                question={standardProtocol.question}
                groundTruth={standardProtocol.ground_truth}
                candidates={standardProtocol.candidates}
                scored={model.split.customers_scored_standard}
              />
            ) : null}
            {discoveryProtocol ? (
              <Leaderboard
                title="Discovery"
                kicker="Protocol 2 · the one that shipped"
                rows={model.leaderboards.discovery}
                question={discoveryProtocol.question}
                groundTruth={discoveryProtocol.ground_truth}
                candidates={discoveryProtocol.candidates}
                scored={model.split.customers_scored_discovery}
              />
            ) : null}
          </div>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Coverage</span>
                <strong>An accuracy number with no coverage beside it hides this</strong>
                <small>
                  Popularity reaches a respectable{" "}
                  {popularityStandard ? percent(popularityStandard.hr_at_10) : "-"} on the standard
                  table while recommending from{" "}
                  {popularityStandard ? percent(popularityStandard.coverage, 2) : "-"} of the
                  catalog - {model.popularity_bias.what_each_model_shows[0].distinct_products_shown}{" "}
                  distinct products out of {integer(model.dataset.products_in_the_catalog)}.
                </small>
              </span>
            </header>
            <div className="rc-panel-body rc-scroll">
              <table className="rc-table">
                <caption>
                  What each model actually puts in front of shoppers, across every ten-slot list it
                  filled.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">Catalog coverage</th>
                    <th scope="col" className="num">Distinct products shown</th>
                    <th scope="col" className="num">Slots from the top 100</th>
                    <th scope="col" className="num">Median popularity rank</th>
                  </tr>
                </thead>
                <tbody>
                  {model.popularity_bias.what_each_model_shows.map((row) => (
                    <tr
                      key={row.model}
                      className={
                        row.is_deployed ? "deployed" : row.model === REORDER ? "flagged" : ""
                      }
                    >
                      <td><b>{row.model}</b></td>
                      <td className="num">
                        {percent(row.coverage, 2)}
                        <HitBar
                          value={row.coverage}
                          tone={row.is_deployed ? "deployed" : row.model === POPULARITY ? "tiny" : ""}
                        />
                      </td>
                      <td className="num">{integer(row.distinct_products_shown)}</td>
                      <td className="num">{percent(row.share_from_the_top_100)}</td>
                      <td className="num">{integer(row.median_popularity_rank)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">A third protocol nobody should ship</span>
                <strong>The incoherent middle</strong>
                <small>{incoherentProtocol?.ground_truth}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.65 }}>
                Mask the shopper&apos;s history but keep repeat purchases in the answer key, and{" "}
                {percent(model.repeat_purchasing.repeat_share)} of the correct answers become
                unreachable by construction. {incoherentProtocol?.question}. It is here so it can be
                recognized, not used.
              </p>
            </div>
          </section>
        </div>
      ) : null}

      {model && view === "evidence" ? (
        <div className="rc-stack">
          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Model card</span>
                <strong>{model.model_name}</strong>
                <small>{model.what_it_does}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <dl className="rc-facts">
                <dt>Shipped model</dt>
                <dd>
                  <b>{model.deployed_model.label}</b> — {model.deployed_model.how_it_works}
                </dd>
                <dt>Scoring</dt>
                <dd>{model.deployed_model.scoring}</dd>
                <dt>Size on disk</dt>
                <dd>
                  {model.deployed_model.stored_megabytes} MB ·{" "}
                  {integer(model.deployed_model.stored_links)} stored links ·{" "}
                  {model.deployed_model.neighbours_kept} neighbours kept per product
                </dd>
                <dt>Not the top scorer</dt>
                <dd>{model.deployed_model.why_not_the_most_accurate_model}</dd>
                <dt>Intended users</dt>
                <dd>{model.intended_users}</dd>
                <dt>Data</dt>
                <dd>
                  {model.dataset.name} ({model.dataset.license}) —{" "}
                  {model.dataset.population}. {integer(model.dataset.committed_rows)} committed
                  rows, {model.dataset.committed_grain}.
                </dd>
                <dt>Split</dt>
                <dd>
                  {model.split.type}, cut at {model.split.cut}.{" "}
                  {integer(model.split.users)} shoppers × {integer(model.split.items)} products,{" "}
                  {percent(model.split.sparsity, 3)} of the grid empty. {model.split.why_not_random}
                </dd>
                <dt>Version</dt>
                <dd>
                  {model.model_version} · seed {model.environment.seed} · Python{" "}
                  {model.environment.python}
                </dd>
              </dl>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Both protocols, in plain words</span>
                <strong>What &quot;correct&quot; means, twice</strong>
                <small>
                  Neither table is optional, and a leaderboard with no protocol printed on it is not
                  a result.
                </small>
              </span>
            </header>
            <div className="rc-panel-body rc-two-up">
              {[standardProtocol, discoveryProtocol].map((entry) =>
                entry ? (
                  <div
                    key={entry.id}
                    className="rc-callout info"
                    style={{ gridTemplateColumns: "minmax(0, 1fr)" }}
                  >
                    <div>
                      <strong>{entry.name}</strong>
                      <p>
                        <b>Asks:</b> {entry.question}
                      </p>
                      <p>
                        <b>Counts as right:</b> {entry.ground_truth}.
                      </p>
                      <p>
                        <b>Can be shown:</b> {entry.candidates}.
                      </p>
                      <p>
                        {entry.id === "discovery"
                          ? "This is the one the storefront ships. The module exists to put something new in front of a shopper; a slot filled with a product they already own is a slot wasted."
                          : "This is the one most tutorials use by default. It rewards a model for predicting a repeat purchase, which is why a reorder list wins it."}
                      </p>
                    </div>
                  </div>
                ) : null,
              )}
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Limitation 1</span>
                <strong>The honest revenue ceiling</strong>
                <small>{model.incremental_revenue.boundary}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <div className="rc-gap">
                {model.incremental_revenue.by_model
                  .slice()
                  .sort(
                    (left, right) =>
                      right.share_of_available_new_product_revenue -
                      left.share_of_available_new_product_revenue,
                  )
                  .map((row) => (
                    <div className="rc-gap-row" key={row.model}>
                      <span>{row.model}</span>
                      <span className="rc-gap-track">
                        <i
                          className={
                            row.is_deployed
                              ? "deployed"
                              : row.model === "Fallback: recent revenue 28d"
                                ? "none"
                                : ""
                          }
                          style={{
                            width: `${Math.max(
                              1,
                              (row.share_of_available_new_product_revenue / 0.04) * 100,
                            )}%`,
                          }}
                        />
                      </span>
                      <b>{percent(row.share_of_available_new_product_revenue, 2)}</b>
                    </div>
                  ))}
              </div>
              <div className="rc-callout warn" style={{ marginTop: 14 }}>
                <AlertTriangle size={16} aria-hidden="true" />
                <div>
                  <strong>
                    {percent(model.incremental_revenue.deployed_share, 2)} against{" "}
                    {percent(model.incremental_revenue.no_personalization_share, 2)} — a{" "}
                    {model.incremental_revenue.gain_percentage_points} point gain, and an upper
                    bound.
                  </strong>
                  <p>{model.incremental_revenue.upper_bound_note}</p>
                  <p>
                    The whole pool this is measured against is{" "}
                    {money(model.incremental_revenue.available_new_product_revenue)} of revenue on
                    products new to the shopper, across{" "}
                    {integer(model.incremental_revenue.customers)} shoppers.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Limitation 2</span>
                <strong>
                  {percent(model.cold_start.unservable_share)} of shoppers cannot be served at all
                </strong>
                <small>
                  {integer(model.cold_start.unservable_customers)} of{" "}
                  {integer(model.cold_start.registered_customers_active_in_test)} registered
                  shoppers active in the test window. They get the fallback list, labeled
                  &quot;{model.policy.fallback.label}&quot; and never
                  &quot;{model.policy.fallback.never_label_it}&quot;.
                </small>
              </span>
            </header>
            <div className="rc-panel-body">
              <div className="rc-inversion">
                <div className="risk">
                  <strong>{integer(model.cold_start.cold_registered_customers)}</strong>
                  <span>bought nothing before the cut</span>
                  <small>
                    {percent(model.cold_start.cold_registered_share)} of active shoppers, carrying{" "}
                    {percent(model.cold_start.cold_registered_revenue_share)} of the revenue.
                  </small>
                </div>
                <div className="risk">
                  <strong>{integer(model.cold_start.thin_history_customers)}</strong>
                  <span>bought too little to learn from</span>
                  <small>
                    Fewer than {model.split.min_training_products_per_customer} distinct products,
                    so no row in the matrix.
                  </small>
                </div>
                <div>
                  <strong>{percent(model.cold_start.fallback_hr10)}</strong>
                  <span>hit rate for the fallback list</span>
                  <small>
                    Measured on the {integer(model.policy.fallback.sweep[0].cold_customers_scored)}{" "}
                    cold shoppers. It is a generic list and it says so on the label.
                  </small>
                </div>
                <div>
                  <strong>{integer(model.cold_start.guest_baskets_in_test)}</strong>
                  <span>guest orders with no shopper id at all</span>
                  <small>
                    {percent(model.cold_start.guest_revenue_share)} of test revenue. A different
                    population from cold registered shoppers.
                  </small>
                </div>
              </div>
              <div className="rc-callout warn" style={{ marginTop: 12 }}>
                <AlertTriangle size={16} aria-hidden="true" />
                <div>
                  <strong>Two shares that must never be added together.</strong>
                  <p>{model.cold_start.warning}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Limitation 3</span>
                <strong>Popularity feeds itself</strong>
                <small>{model.popularity_bias.exposure_loop.assumption_note}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <div className="rc-callout warn">
                <RefreshCcw size={16} aria-hidden="true" />
                <div>
                  <strong>
                    The top ten products go from{" "}
                    {percent(model.popularity_bias.exposure_loop.start_top_10_share, 2)} of all
                    purchases to{" "}
                    {percent(model.popularity_bias.exposure_loop.end_top_10_share, 2)} in{" "}
                    {model.popularity_bias.exposure_loop.rounds} simulated rounds.
                  </strong>
                  <p>
                    Show the same ten products to everyone, some of them sell, that makes them more
                    popular, so they are shown again. This is a simulation with an assumed{" "}
                    {percent(model.popularity_bias.exposure_loop.assumed_conversion, 0)} conversion
                    rate. It is a classroom assumption, not a measurement from this data.
                  </p>
                </div>
              </div>
              <div className="rc-scroll" style={{ marginTop: 12 }}>
                <table className="rc-table">
                  <caption>
                    Simulated rounds. Round 0 is the real starting point measured from the
                    training data; every round after it is the assumption playing out.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Round</th>
                      <th scope="col" className="num">Top-10 share of purchases</th>
                      <th scope="col" className="num">Top-100 share</th>
                      <th scope="col" className="num">Concentration (Gini)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {model.popularity_bias.exposure_loop.history.map((row) => (
                      <tr key={row.round} className={row.round === 0 ? "" : "muted"}>
                        <td>{row.round === 0 ? "0 (measured)" : row.round}</td>
                        <td className="num">
                          {percent(row.top_10_share, 2)}
                          <HitBar value={row.top_10_share * 8} tone="tiny" />
                        </td>
                        <td className="num">{percent(row.top_100_share, 2)}</td>
                        <td className="num">{decimal(row.gini, 5)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">How the split was chosen</span>
                <strong>What leave-one-out would have added</strong>
                <small>{model.leave_one_out.plain_words}</small>
              </span>
            </header>
            <div className="rc-panel-body rc-scroll">
              <table className="rc-table">
                <caption>{model.leave_one_out.design}</caption>
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">A — honest split</th>
                    <th scope="col" className="num">B — leave-one-out</th>
                    <th scope="col" className="num">Inflation</th>
                  </tr>
                </thead>
                <tbody>
                  {model.leave_one_out.by_model.map((row) => (
                    <tr key={row.model}>
                      <td><b>{row.model}</b></td>
                      <td className="num">{percent(row.honest_hr10, 2)}</td>
                      <td className="num">{percent(row.leave_one_out_hr10, 2)}</td>
                      <td className="num">
                        <span className="rc-chip risk">
                          <ArrowUp size={11} aria-hidden="true" /> +{percent(row.inflation, 1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Engineering</span>
                <strong>The small artifact is also the accurate one</strong>
                <small>
                  Keeping only each product&apos;s closest neighbours shrinks the model and raises
                  discovery hit rate at the same time. That is unusual, and it is measured.
                </small>
              </span>
            </header>
            <div className="rc-panel-body rc-scroll">
              <table className="rc-table">
                <thead>
                  <tr>
                    <th scope="col">Neighbours kept</th>
                    <th scope="col" className="num">Discovery hit rate</th>
                    <th scope="col" className="num">Catalog coverage</th>
                    <th scope="col" className="num">Megabytes</th>
                  </tr>
                </thead>
                <tbody>
                  {model.engineering.truncation_trade.map((row) => (
                    <tr key={row.neighbours_kept} className={row.is_deployed ? "deployed" : ""}>
                      <td>
                        <b>{row.neighbours_kept}</b>
                        {row.is_deployed ? (
                          <span className="rc-chip good" style={{ marginLeft: 7 }}>
                            <BadgeCheck size={11} aria-hidden="true" /> shipped
                          </span>
                        ) : null}
                      </td>
                      <td className="num">{percent(row.discovery_hr10, 2)}</td>
                      <td className="num">{percent(row.coverage, 2)}</td>
                      <td className="num">{row.stored_megabytes.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="rc-note" style={{ paddingLeft: 0, paddingRight: 0 }}>
                <Minus size={12} aria-hidden="true" /> {model.engineering.damping_note}
              </p>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Operating policy</span>
                <strong>The rules the service runs, written down</strong>
                <small>{model.policy.human_authority}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <pre className="rc-policy-statement">{model.policy.statement}</pre>
              <h3 style={{ margin: "14px 0 8px" }}>What the service must do</h3>
              <ul className="rc-list">
                {model.policy.service_must.map((rule) => (
                  <li key={rule}>{rule}</li>
                ))}
              </ul>
              <h3 style={{ margin: "14px 0 8px" }}>
                The fallback list: &quot;{model.policy.fallback.label}&quot;
              </h3>
              <p style={{ margin: "0 0 10px", color: "var(--text-secondary)", fontSize: 12, lineHeight: 1.6 }}>
                {model.policy.fallback.rule}, refreshed {model.policy.fallback.refresh}. Everyone
                who cannot be personalized sees these ten, in this order, and the heading says so.
              </p>
              <ul className="rc-history-products">
                {model.policy.fallback.items.map((item) => (
                  <li key={item.stock_code}>
                    <b>{item.description}</b> · {money(item.revenue_in_window)}
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="rc-panel">
            <header>
              <span>
                <span className="rc-kicker">Known limits</span>
                <strong>What this system will not do</strong>
                <small>{model.boundary}</small>
              </span>
            </header>
            <div className="rc-panel-body">
              <h3 style={{ margin: "0 0 8px" }}>It does not</h3>
              <ul className="rc-list">
                {model.what_it_does_not_do.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <h3 style={{ margin: "14px 0 8px" }}>Measured limits</h3>
              <ul className="rc-list">
                {model.known_limits.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <h3 style={{ margin: "14px 0 8px" }}>Claims nobody may make from this</h3>
              <ul className="rc-list">
                {model.prohibited_claims.map((line) => (
                  <li key={line}>
                    <ArrowDown size={11} aria-hidden="true" /> {line}
                  </li>
                ))}
              </ul>
              <p className="rc-note" style={{ paddingLeft: 0, paddingRight: 0 }}>
                <UserRound size={12} aria-hidden="true" /> {model.dataset.citation}
              </p>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
