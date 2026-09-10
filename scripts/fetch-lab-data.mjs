#!/usr/bin/env node
// Restore the large lab datasets if a checkout is missing any of them.
//
// These files are committed, so a normal clone already has them and this script
// prints "present" four times and exits. It earns its place when that is not
// true: a shallow or partial clone, a file deleted by accident, or a Codespace
// that lost one. The same files are published as Release assets, so they can be
// restored without re-cloning 200 MB.
//
// Git LFS was considered for hosting them and rejected on purpose: its free tier
// meters 1 GB per MONTH of bandwidth, which roughly six student clones would
// exhaust, and after that clones FAIL rather than slow down. Release assets are
// not metered that way.
//
// This runs once, during Codespace creation, and is a no-op in the normal case.
// Class time needs no network.
//
//   node scripts/fetch-lab-data.mjs            # fetch anything missing
//   node scripts/fetch-lab-data.mjs --force    # re-fetch everything
//   node scripts/fetch-lab-data.mjs --check    # report only, download nothing

import { createWriteStream } from "node:fs";
import { mkdir, stat, readFile, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const manifest = JSON.parse(await readFile(resolve(here, "lab-data-manifest.json"), "utf8"));

const args = new Set(process.argv.slice(2));
const force = args.has("--force");
const checkOnly = args.has("--check");

// Owner/repo is read from the git remote so a fork works without editing anything.
async function repoSlug() {
  if (process.env.LAB_DATA_REPO) return process.env.LAB_DATA_REPO;
  const { execSync } = await import("node:child_process");
  try {
    const url = execSync("git remote get-url origin", { cwd: root, encoding: "utf8" }).trim();
    const m = url.match(/github\.com[:/]([^/]+\/[^/.]+)(\.git)?$/);
    if (m) return m[1];
  } catch { /* not a git checkout, fall through */ }
  return null;
}

async function sizeOf(path) {
  try { return (await stat(path)).size; } catch { return null; }
}

const slug = await repoSlug();
let missing = 0, ok = 0, failed = 0;

console.log(`Lab datasets: ${manifest.files.length} files, release "${manifest.release_tag}"`);

for (const file of manifest.files) {
  const target = resolve(root, file.path);
  const have = await sizeOf(target);

  if (have !== null && !force) {
    // A truncated download is worse than a missing one: the notebook fails deep
    // inside a cell instead of at setup. Size-check what is already here.
    if (have === file.bytes) { console.log(`  present  ${file.asset}`); ok += 1; continue; }
    console.log(`  WRONG SIZE  ${file.asset} - have ${have}, expect ${file.bytes}; re-fetching`);
  } else if (have === null) {
    missing += 1;
  }

  if (checkOnly) { console.log(`  MISSING  ${file.asset} (${(file.bytes / 1048576).toFixed(1)} MB)`); continue; }
  if (!slug) {
    console.error(`  cannot fetch ${file.asset}: no GitHub remote found. Set LAB_DATA_REPO=owner/repo.`);
    failed += 1; continue;
  }

  const url = `https://github.com/${slug}/releases/download/${manifest.release_tag}/${file.asset}`;
  process.stdout.write(`  fetching ${file.asset} (${(file.bytes / 1048576).toFixed(1)} MB) ... `);
  try {
    const response = await fetch(url, { redirect: "follow" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await mkdir(dirname(target), { recursive: true });
    // Write to a temp name and rename, so an interrupted download never leaves a
    // half file that looks real to the notebook.
    const tmp = `${target}.partial`;
    await pipeline(Readable.fromWeb(response.body), createWriteStream(tmp));
    const got = await sizeOf(tmp);
    if (got !== file.bytes) { await rm(tmp, { force: true }); throw new Error(`size ${got}, expected ${file.bytes}`); }
    const { rename } = await import("node:fs/promises");
    await rename(tmp, target);
    console.log("done");
    ok += 1;
  } catch (error) {
    console.log(`FAILED (${error.message})`);
    console.log(`     rebuild instead: ${file.rebuild}`);
    failed += 1;
  }
}

console.log(`\n  ${ok} ready, ${failed} failed${checkOnly && missing ? `, ${missing} missing` : ""}`);
if (failed) {
  console.log(`\n  Some lab data is missing. Everything else still works: the notebooks are`);
  console.log(`  committed with their outputs, and every lab has an offline HTML copy you`);
  console.log(`  can read without running anything. Only re-running those labs is blocked.`);
  process.exit(checkOnly ? 0 : 1);
}
