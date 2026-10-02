// Copies the transportation lesson files from the folder they are built in into the Studio, byte for byte:
// three browser labs, three executed notebooks with their offline reports, and the JSON files the notebooks read.
//   TRANSPORT_LABS_SOURCE=/path/to/source node scripts/sync-transportation-labs.mjs           copy
//   TRANSPORT_LABS_SOURCE=/path/to/source node scripts/sync-transportation-labs.mjs --check   fail if a copy is out of date
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const targetDir = path.join(root, "notebooks/transportation-rl");

const labs = [
  { file: "M7_Robot_Training_Lab.html", target: "backup/warehouse-robot.html", steps: 8 },
  { file: "M7_Traffic_Signal_Lab.html", target: "backup/traffic-signal.html", steps: 7 },
  { file: "M7_Ride_Hail_Lab.html", target: "backup/ride-hail.html", steps: 7 },
];
const notebooks = [
  { file: "M7_Notebook_Warehouse_Robot", target: "01_warehouse_robot" },
  { file: "M7_Notebook_Traffic_Signal", target: "02_traffic_signal" },
  { file: "M7_Notebook_Ride_Hail_Dispatch", target: "03_ride_hail_dispatch" },
];
const artifacts = ["robot_lab_facts.json", "signal_lab_facts.json", "dispatch_lab_facts.json", "nyc_borough_summary.json"];

const remote = /<(script|link|img)[^>]+(src|href)=["']https?:/i;

function checkPage(name, html) {
  if (!/^<!doctype html>/i.test(html) || !/<\/html>\s*$/i.test(html)) throw new Error(`${name} is not a complete HTML page`);
  if (remote.test(html)) throw new Error(`${name} loads a remote resource`);
}

function checkNotebook(name, text) {
  const cells = JSON.parse(text).cells.filter((cell) => cell.cell_type === "code");
  if (!cells.length || cells.some((cell) => !cell.execution_count)) throw new Error(`${name} is not fully executed`);
  if (cells.some((cell) => (cell.outputs ?? []).some((out) => out.output_type === "error"))) throw new Error(`${name} has an error output`);
}

function plan(sourceDir) {
  return [
    ...labs.map(({ file, target, steps }) => ({
      from: path.join(sourceDir, file), to: target,
      check: (html) => {
        checkPage(file, html);
        for (let step = 1; step <= steps; step += 1) {
          if (!html.includes(`id: 'step-${step}'`)) throw new Error(`${file} is missing step-${step}`);
        }
      },
    })),
    ...notebooks.flatMap(({ file, target }) => [
      { from: path.join(sourceDir, `${file}.ipynb`), to: `${target}.ipynb`, check: (text) => checkNotebook(file, text) },
      { from: path.join(sourceDir, `${file}.html`), to: `backup/${target}.html`, check: (html) => checkPage(`${file}.html`, html) },
    ]),
    ...artifacts.map((name) => ({ from: path.join(sourceDir, "artifacts", name), to: `artifacts/${name}`, check: (text) => JSON.parse(text) })),
  ];
}

const sourceDir = process.env.TRANSPORT_LABS_SOURCE;
if (!sourceDir) throw new Error("Set TRANSPORT_LABS_SOURCE to the folder that holds the M7_* lesson files.");
const check = process.argv.includes("--check");
for (const { from, to, check: validate } of plan(sourceDir)) {
  const bytes = await readFile(from);
  validate(bytes.toString("utf8"));
  const target = path.join(targetDir, to);
  if (check) {
    const current = await readFile(target).catch(() => null);
    if (!current || !current.equals(bytes)) throw new Error(`${to} is out of date. Run node scripts/sync-transportation-labs.mjs`);
    console.log(`up to date  ${to}`);
  } else {
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, bytes);
    console.log(`copied      ${path.basename(from)} -> ${to} (${(bytes.length / 1024).toFixed(1)} KB)`);
  }
}
