import { useEffect, useState } from "react";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { navigate } from "../router";
import explorerUrl from "../../../../notebooks/ai-blockchain/backup/blockchain-explorer.html?url";
import walletUrl from "../../../../notebooks/ai-blockchain/backup/agent-wallet.html?url";
import recallUrl from "../../../../notebooks/ai-blockchain/backup/recall-desk.html?url";

// Ledger Watch is built from the Elliptic Data Set (CC BY-NC-ND 4.0), so it is a git-ignored local teaching copy:
// present on the instructor's machine after scripts/sync-blockchain-labs.mjs, absent from the public repository.
const localCopies = import.meta.glob("../../../../notebooks/ai-blockchain/local/ledger-watch.html", { query: "?url", import: "default", eager: true }) as Record<string, string>;
const ledgerUrl = Object.values(localCopies)[0] ?? null;

export type BlockchainLab = "blockchain-explorer" | "ledger-watch" | "agent-wallet" | "recall-desk";

const labs: Record<BlockchainLab, {
  url: string | null; title: string; eyebrow: string; summary: string; steps: string[]; evidence: string[];
}> = {
  "blockchain-explorer": {
    url: explorerUrl, steps: ["job", "hash", "block", "chain", "merkle", "work", "agree", "proves"],
    title: "Blockchain Explorer", eyebrow: "AI & Blockchain · Opening",
    summary: "What a blockchain actually does, on real bitcoin blocks: fingerprints, a real block header, the chain link, a Merkle tree, mining and agreement. Every hash is computed in your browser.",
    evidence: [
      "Real blocks fetched from public explorers (blocks 0, 170, 840,000 and a block from Oct 13, 2026) and two Ethereum blocks from the 2022 switch to proof of stake.",
      "The build checks the page's own SHA-256, Merkle and mining code against Node's crypto library and every real block hash.",
    ],
  },
  "ledger-watch": {
    url: ledgerUrl, steps: ["job", "graph", "labels", "model", "test", "shift", "desk", "assist", "decide"],
    title: "Ledger Watch", eyebrow: "AI & Blockchain · Case 1 · AI reads the ledger",
    summary: "A random forest flags illicit bitcoin transactions on a public ledger, then fails after a dark market shuts down. An agent drafts the analyst's case note; the analyst decides.",
    evidence: [
      "Elliptic Data Set (Weber et al., 2019): 203,769 real bitcoin transactions. Licensed CC BY-NC-ND 4.0, so this page is a local teaching copy and is not published in this repository.",
      "Seven recorded agent runs (Microsoft Agent Framework, gpt-5.6-sol); case notes were auto-approved for recording and say so.",
    ],
  },
  "agent-wallet": {
    url: walletUrl, steps: ["job", "pay", "ledger", "rules", "budget", "break", "ask", "who", "decide"],
    title: "Agent Wallet", eyebrow: "AI & Blockchain · Case 2 · AI acts on the ledger",
    summary: "During Hurricane Harvey, a dispatch agent buys real river-gauge readings through HTTP 402, paying from a wallet contract whose limits it cannot change. A note in the data asks it to pay $25.",
    evidence: [
      "Real USGS 15-minute gage heights for four Brays Bayou gauges (public domain). The data desk, prices and test dollars are our demo.",
      "18 recorded runs on a local Ethereum development chain (one machine, no consensus). Payments follow x402's messages but settle through our own spending contract, not x402's facilitator.",
      "Approvals in recordings were automatic and are marked. The live version runs from the module folder (src/agent-wallet).",
    ],
  },
  "recall-desk": {
    url: recallUrl, steps: ["job", "tamper", "ai", "truth", "follow", "proves"],
    title: "Recall Desk", eyebrow: "AI & Blockchain · Case 3 · The ledger checks AI",
    summary: "A salad outbreak and a signed, anchored supply chain: edit one record and the proof breaks; an AI reads a smudged paper log; a wrong record is preserved perfectly, and the fix is a new record.",
    evidence: [
      "Every company, lot and case is fictional, shaped like the FDA Food Traceability Rule (FSMA 204). Signatures and Merkle roots are real, anchored on a local development chain.",
      "Three recorded vision runs (gpt-5.6-sol) read the paper log; the wrong-record story is a labeled what-if.",
    ],
  },
};

const currentHash = (steps: string[]) => {
  const hash = window.location.hash.slice(1);
  return hash === "lab" || steps.includes(hash) ? hash : steps[0];
};

const styles = `
.chain-lab { width: 100%; min-width: 0; }
.chain-lab .page-back-button { min-height: 44px; }
.chain-lab-header { margin: 18px 0; }
.chain-lab-header h1 { margin: 4px 0 8px; font-size: 27px; line-height: 1.25; }
.chain-lab-header p { margin: 0; max-width: 75ch; color: var(--text-secondary); font-size: 14px; line-height: 1.6; }
.chain-lab-evidence { border-block: 1px solid var(--border); margin-bottom: 18px; }
.chain-lab-evidence summary { min-height: 44px; padding: 12px 0; cursor: pointer; color: var(--text-secondary); font-size: 13px; }
.chain-lab-evidence p { max-width: 95ch; margin: 10px 0; font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
.chain-lab-evidence a { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; color: var(--teal); }
.chain-lab-frame { display: block; width: 100%; height: max(900px, calc(100dvh - 140px)); border: 1px solid var(--border); border-radius: 5px; background: var(--surface); }
.chain-lab-missing { padding: 24px; border: 1px dashed var(--border); border-radius: 5px; color: var(--text-secondary); font-size: 14px; line-height: 1.6; max-width: 75ch; }
.chain-lab-missing code { color: var(--text-primary); }
@media (max-width: 760px) {
  .chain-lab-header h1 { font-size: 23px; }
  .chain-lab-frame { height: 100dvh; min-height: 660px; }
}
`;

export default function BlockchainLabPage({ lab }: { lab: BlockchainLab }) {
  const info = labs[lab];
  const [hash, setHash] = useState(() => currentHash(info.steps));
  useEffect(() => {
    const update = () => setHash(currentHash(info.steps));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, [info.steps]);

  return (
    <div className="page chain-lab">
      <style>{styles}</style>
      <button className="page-back-button" type="button" onClick={() => navigate("/showcase?industry=ai-blockchain")}>
        <ArrowLeft size={15} aria-hidden="true" /> Industry workflows
      </button>
      <header className="chain-lab-header">
        <span className="eyebrow">{info.eyebrow}</span>
        <h1>{info.title}</h1>
        <p>{info.summary}</p>
      </header>
      <details className="chain-lab-evidence">
        <summary>Data, assumptions and evidence boundaries</summary>
        {info.evidence.map((line) => <p key={line}>{line}</p>)}
        <p>One standalone offline page running in the browser. No model service is required.</p>
        {info.url ? <a href={`${info.url}#${hash}`} target="_blank" rel="noreferrer">Open the lesson full screen <ExternalLink size={14} aria-hidden="true" /></a> : null}
      </details>
      {info.url
        ? <iframe key={lab} className="chain-lab-frame" title={`${info.title} lesson`} src={`${info.url}#${hash}`} allow="fullscreen" />
        : (
          <div className="chain-lab-missing" role="note">
            <p><strong>Local teaching copy only.</strong> This lesson is built from licensed data that this public repository does not publish.</p>
            <p>On the instructor's machine, run <code>BLOCKCHAIN_LABS_SOURCE=/path/to/Module_13_AI_Blockchain_Integration node scripts/sync-blockchain-labs.mjs</code>, then reload.</p>
          </div>
        )}
    </div>
  );
}
