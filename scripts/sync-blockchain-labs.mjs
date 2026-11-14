// Copies the Module 13 (AI and blockchain) lesson pages from the folder they are built in into the Studio, byte for byte.
//   BLOCKCHAIN_LABS_SOURCE=/path/to/Module_13_AI_Blockchain_Integration node scripts/sync-blockchain-labs.mjs           copy
//   BLOCKCHAIN_LABS_SOURCE=/path/to/Module_13_AI_Blockchain_Integration node scripts/sync-blockchain-labs.mjs --check   fail if a copy is out of date
//
// Public pages go to notebooks/ai-blockchain/backup/ (committed). Ledger Watch and the deck are built from the Elliptic
// Data Set, licensed CC BY-NC-ND 4.0 (no derivatives), so they go to notebooks/ai-blockchain/local/, which is
// git-ignored: local teaching copies only, never part of this public repository or the lesson site.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const targetDir = path.join(root, "notebooks/ai-blockchain");

const pages = [
  { file: "M13_Blockchain_Explorer.html", target: "backup/blockchain-explorer.html", steps: ["job", "hash", "block", "chain", "merkle", "work", "agree", "proves"] },
  { file: "M13_Agent_Wallet.html", target: "backup/agent-wallet.html", steps: ["job", "pay", "ledger", "rules", "budget", "break", "ask", "who", "decide"] },
  { file: "M13_Recall_Desk.html", target: "backup/recall-desk.html", steps: ["job", "tamper", "ai", "truth", "follow", "proves"] },
  { file: "M13_Ledger_Watch.html", target: "local/ledger-watch.html", steps: ["job", "graph", "labels", "model", "test", "shift", "desk", "assist", "decide"], local: true },
];
const files = [{ file: "M13_Deck_AI_Blockchain.pdf", target: "local/M13_Deck_AI_Blockchain.pdf", local: true }];

const remote = /<(script|link|img)[^>]+(src|href)=["']https?:/i;
// Test-network keys live outside the course folder; make sure none ever lands in a copied page.
const walletEnv = path.join(os.homedir(), ".config/itai2372/m13-wallet.env");
const secrets = existsSync(walletEnv)
  ? readFileSync(walletEnv, "utf8").split("\n").filter((l) => /_KEY=0x/.test(l)).map((l) => l.split("=")[1].trim().toLowerCase())
  : [];

function checkPage({ file, steps, local }, html) {
  if (!/^<!doctype html>/i.test(html) || !/<\/html>\s*$/i.test(html)) throw new Error(`${file} is not a complete HTML page`);
  if (remote.test(html)) throw new Error(`${file} loads a remote resource`);
  const chapters = [...html.matchAll(/\{id: '([a-z]+)', label:/g)].map((m) => m[1]);
  for (const id of steps) if (!chapters.includes(id)) throw new Error(`${file} is missing step "${id}"`);
  if (!local && /elliptic/i.test(html)) throw new Error(`${file} mentions Elliptic: licensed content must stay in local/`);
  const lower = html.toLowerCase();
  for (const key of secrets) if (lower.includes(key.slice(2))) throw new Error(`${file} contains a wallet private key`);
}

const sourceDir = process.env.BLOCKCHAIN_LABS_SOURCE;
if (!sourceDir) throw new Error("Set BLOCKCHAIN_LABS_SOURCE to the Module_13_AI_Blockchain_Integration folder.");
const check = process.argv.includes("--check");
for (const item of [...pages, ...files]) {
  const from = path.join(sourceDir, item.file);
  if (item.local && !existsSync(from)) { console.log(`skipped     ${item.file} (local copy, not in the source folder)`); continue; }
  const bytes = await readFile(from);
  if (item.steps) checkPage(item, bytes.toString("utf8"));
  const target = path.join(targetDir, item.target);
  if (check) {
    if (item.local && !existsSync(target)) { console.log(`not copied  ${item.target} (local only)`); continue; }
    const current = await readFile(target).catch(() => null);
    if (!current || !current.equals(bytes)) throw new Error(`${item.target} is out of date. Run node scripts/sync-blockchain-labs.mjs`);
    console.log(`up to date  ${item.target}`);
  } else {
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, bytes);
    console.log(`copied      ${item.file} -> ${item.target} (${(bytes.length / 1024).toFixed(1)} KB)${item.local ? "  [local only, git-ignored]" : ""}`);
  }
}
