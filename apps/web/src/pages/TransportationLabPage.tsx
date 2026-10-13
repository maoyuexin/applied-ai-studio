import { useEffect, useState } from "react";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { navigate } from "../router";
import robotUrl from "../../../../notebooks/transportation-rl/backup/warehouse-robot.html?url";
import signalUrl from "../../../../notebooks/transportation-rl/backup/traffic-signal.html?url";
import rideHailUrl from "../../../../notebooks/transportation-rl/backup/ride-hail.html?url";

export type TransportationLab = "warehouse-robot" | "traffic-signal" | "ride-hail";

const labs: Record<TransportationLab, {
  url: string; title: string; eyebrow: string; summary: string; steps: number; evidence: string[];
}> = {
  "warehouse-robot": {
    url: robotUrl, steps: 8,
    title: "Train a Warehouse Robot", eyebrow: "Transportation \u00b7 Learning by reward",
    summary: "A robot learns a route to the packing station from points alone: try a move, get points, update one score. Eight guided steps, then a free training lab.",
    evidence: [
      "The floor and the points are invented for teaching; nothing here is a real warehouse.",
      "Real fleets compute routes from a map. The lesson compares the learned route with that map search: both take 4 moves.",
    ],
  },
  "traffic-signal": {
    url: signalUrl, steps: 7,
    title: "Train a Traffic Light", eyebrow: "Transportation \u00b7 Learning by reward",
    summary: "A signal learns when to keep green or switch, inside timing rules it cannot break, and is tested against a fixed timer and a simple rule on the same cars.",
    evidence: [
      "Traffic is simulated (about 4.8 cars a minute on Main St, 1.8 on Side St), not counts from a real intersection.",
      "Five fixed test hours: best fixed timer 20.7 s, serve-the-longer-line rule 13.8 s, learned light 12.6 s average wait.",
      "Yellow, all-red, minimum and maximum green are rules outside the learner.",
    ],
  },
  "ride-hail": {
    url: rideHailUrl, steps: 7,
    title: "Train a Ride-Hail Driver", eyebrow: "Transportation \u00b7 Learning by reward",
    summary: "On real New York trip data, a driver learns where to wait or drive empty. Then we ask who a driver-earnings reward leaves behind.",
    evidence: [
      "Trip counts, pay and trip times summarize 19,663,930 NYC TLC high-volume for-hire trips, January 2024. No trip rows are included.",
      "The chance of a request while waiting and the cost of driving empty are named assumptions.",
      "One driver, replayed demand: not a forecast of how real riders and drivers would respond.",
    ],
  },
};

const currentHash = (steps: number) => {
  const hash = window.location.hash.slice(1);
  const step = /^step-(\d+)$/.exec(hash);
  return hash === "lab" || (step && Number(step[1]) >= 1 && Number(step[1]) <= steps) ? hash : "step-1";
};

const styles = `
.transport-lab { width: 100%; min-width: 0; }
.transport-lab .page-back-button { min-height: 44px; }
.transport-lab-header { margin: 18px 0; }
.transport-lab-header h1 { margin: 4px 0 8px; font-size: 27px; line-height: 1.25; }
.transport-lab-header p { margin: 0; max-width: 75ch; color: var(--text-secondary); font-size: 14px; line-height: 1.6; }
.transport-lab-evidence { border-block: 1px solid var(--border); margin-bottom: 18px; }
.transport-lab-evidence summary { min-height: 44px; padding: 12px 0; cursor: pointer; color: var(--text-secondary); font-size: 13px; }
.transport-lab-evidence p { max-width: 95ch; margin: 10px 0; font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
.transport-lab-evidence a { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; color: var(--teal); }
.transport-lab-frame { display: block; width: 100%; height: max(820px, calc(100dvh - 260px)); border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
@media (max-width: 760px) {
  .transport-lab-header h1 { font-size: 23px; }
  .transport-lab-frame { height: 100dvh; min-height: 660px; }
}
`;

export default function TransportationLabPage({ lab }: { lab: TransportationLab }) {
  const info = labs[lab];
  const [hash, setHash] = useState(() => currentHash(info.steps));
  useEffect(() => {
    const update = () => setHash(currentHash(info.steps));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, [info.steps]);

  return (
    <div className="page transport-lab">
      <style>{styles}</style>
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=transportation")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>
      <header className="transport-lab-header">
        <span className="eyebrow">{info.eyebrow}</span>
        <h1>{info.title}</h1>
        <p>{info.summary}</p>
      </header>
      <details className="transport-lab-evidence">
        <summary>Data, assumptions and evidence boundaries</summary>
        {info.evidence.map((line) => <p key={line}>{line}</p>)}
        <p>One standalone offline page running in the browser. No model service is required.</p>
        <a href={`${info.url}#${hash}`} target="_blank" rel="noreferrer">Open the lesson full screen <ExternalLink size={14} aria-hidden="true" /></a>
      </details>
      <iframe key={lab} className="transport-lab-frame" title={`${info.title} lesson`} src={`${info.url}#${hash}`} allow="fullscreen" />
    </div>
  );
}
