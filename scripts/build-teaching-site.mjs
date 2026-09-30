// Builds the static teaching-library site (GitHub Pages) from lessons/lessons.json.
// Usage: node scripts/build-teaching-site.mjs [--out _site] [--check]
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = {
  slides: { label: "Slides", ext: ".pdf", group: "read" },
  reading: { label: "Reading", ext: ".pdf", group: "read" },
  report: { label: "Notebook", ext: ".html", group: "open" },
  demo: { label: "Demo", ext: ".html", group: "open" },
};
const SAFE_ID = /^[a-z0-9][a-z0-9-]*$/;
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const DEFAULT_STUDIO = "http://127.0.0.1:5173";

export function loadCatalog(root = ROOT) {
  return JSON.parse(readFileSync(join(root, "lessons/lessons.json"), "utf8"));
}

function repoFile(root, path, label) {
  if (typeof path !== "string" || !path || path.startsWith("/") || normalize(path).split(sep).includes("..")) {
    throw new Error(`${label}: path must be relative inside the repository (${path})`);
  }
  const full = join(root, path);
  if (!existsSync(full) || !statSync(full).isFile()) throw new Error(`${label}: missing file ${path}`);
  return full;
}

export function validateCatalog(catalog, root = ROOT) {
  if (!/^[\w.-]+\/[\w.-]+$/.test(catalog.repository ?? "")) throw new Error("repository must be owner/name");
  const ids = new Set();
  for (const lesson of catalog.lessons ?? []) {
    if (!SAFE_ID.test(lesson.id ?? "") || ids.has(lesson.id)) throw new Error(`invalid or duplicate lesson id ${lesson.id}`);
    ids.add(lesson.id);
    if (!lesson.title || !lesson.summary) throw new Error(`${lesson.id}: title and summary are required`);
    const names = new Set();
    for (const material of lesson.materials ?? []) {
      const kind = TYPES[material.type];
      const label = `${lesson.id}/${material.title}`;
      if (!kind) throw new Error(`${label}: unknown type ${material.type}`);
      repoFile(root, material.path, label);
      if (extname(material.path) !== kind.ext) throw new Error(`${label}: ${material.type} must be ${kind.ext}`);
      const name = material.publishAs ?? basename(material.path);
      if (!SAFE_NAME.test(name) || extname(name) !== kind.ext || names.has(name)) {
        throw new Error(`${label}: invalid or duplicate published name ${name}`);
      }
      names.add(name);
      if (material.notebook !== undefined) repoFile(root, material.notebook, `${label} notebook`);
    }
    for (const link of lesson.studio ?? []) {
      if (typeof link.route !== "string" || !link.route.startsWith("/") || link.route.startsWith("//")) {
        throw new Error(`${lesson.id}/${link.title}: route must start with a single /`);
      }
    }
  }
  if (!ids.size) throw new Error("catalog has no lessons");
  return catalog;
}

const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const publishedName = (material) => material.publishAs ?? basename(material.path);

function materialItem(lesson, material, repoUrl) {
  const kind = TYPES[material.type];
  const href = `lessons/${lesson.id}/${publishedName(material)}`;
  const size = material.bytes ? ` · ${(material.bytes / 1e6).toFixed(1)} MB` : "";
  const source = material.notebook
    ? ` <a class="source" href="${repoUrl}/blob/main/${escape(material.notebook)}">notebook source</a>`
    : "";
  const note = material.note ? `<span class="note">${escape(material.note)}</span>` : "";
  return `<li><a class="item" href="${escape(href)}"><span class="kind ${material.type}">${kind.label}</span>` +
    `<span class="name">${escape(material.title)}</span><span class="meta">${kind.ext.slice(1).toUpperCase()}${size}</span></a>${source}${note}</li>`;
}

export function renderIndex(catalog) {
  const repoUrl = `https://github.com/${catalog.repository}`;
  const lessons = catalog.lessons.map((lesson, index) => {
    const read = lesson.materials.filter((m) => TYPES[m.type].group === "read").map((m) => materialItem(lesson, m, repoUrl)).join("");
    const open = lesson.materials.filter((m) => TYPES[m.type].group === "open").map((m) => materialItem(lesson, m, repoUrl)).join("");
    const studio = (lesson.studio ?? []).map((link) =>
      `<li><a class="item studio-link" data-route="${escape(link.route)}" href="${escape(DEFAULT_STUDIO + link.route)}" target="_blank" rel="noopener">` +
      `<span class="kind studio">Studio</span><span class="name">${escape(link.title)}</span><span class="meta">${escape(link.route.split("?")[0])}</span></a></li>`).join("");
    const cases = (lesson.cases ?? []).map((c) => `<span class="case">${escape(c)}</span>`).join("");
    return `<section class="lesson" id="${escape(lesson.id)}" aria-labelledby="${escape(lesson.id)}-title">
  <header><span class="number">${String(index + 1).padStart(2, "0")}</span><div>
    <h2 id="${escape(lesson.id)}-title">${escape(lesson.title)}</h2>
    <p>${escape(lesson.summary)}</p><div class="cases">${cases}</div></div></header>
  <div class="columns">
    <div><h3>Slides and readings</h3><ul>${read}</ul></div>
    <div><h3>Open in the browser</h3>${open ? `<ul>${open}</ul>` : `<p class="empty">Discussion-led lesson; use the Studio links.</p>`}</div>
    <div><h3>Live in the Studio app</h3>${studio ? `<ul>${studio}</ul>` : `<p class="empty">No Studio route.</p>`}</div>
  </div>
  <p class="lesson-foot"><a href="${repoUrl}/tree/main/lessons/${escape(lesson.id)}">Lesson guide on GitHub</a></p>
</section>`;
  }).join("\n");
  const nav = catalog.lessons.map((lesson, index) => `<a href="#${escape(lesson.id)}">${String(index + 1).padStart(2, "0")} ${escape(lesson.title.split(":")[0])}</a>`).join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>${escape(catalog.title)}</title><meta name="description" content="${escape(catalog.tagline)}">
<style>
:root{--bg:#111318;--surface:#181a20;--raised:#222530;--border:#2e323d;--text:#f5f3f0;--muted:#a9adb8;--orange:#e8913c;--teal:#7eaeb8;--green:#7fbf8e;--violet:#a99be0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--teal)}a:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
.shell{max-width:1180px;margin:0 auto;padding:40px 28px 64px}
.hero h1{font-size:40px;line-height:1.15;margin:6px 0 12px}.eyebrow{color:var(--orange);font-size:13px;letter-spacing:.12em;text-transform:uppercase;font-weight:600}
.hero p{color:var(--muted);font-size:18px;max-width:70ch;margin:0 0 22px}
.actions{display:flex;flex-wrap:wrap;gap:12px}.button{display:inline-flex;align-items:center;min-height:44px;padding:10px 18px;border-radius:6px;border:1px solid var(--border);background:var(--raised);color:var(--text);text-decoration:none;font-weight:600}
.button.primary{background:var(--orange);border-color:var(--orange);color:#1b1206}
.studio-bar{margin:28px 0 8px;padding:16px 18px;border:1px solid var(--border);border-radius:8px;background:var(--surface);display:grid;gap:10px}
.studio-bar label{font-weight:600}.studio-bar p{margin:0;color:var(--muted);font-size:14px}
.studio-row{display:flex;gap:10px;flex-wrap:wrap}.studio-row input{flex:1 1 320px;min-height:44px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit}
.studio-row button{min-height:44px;padding:8px 16px;border-radius:6px;border:1px solid var(--teal);background:transparent;color:var(--text);font:inherit;font-weight:600;cursor:pointer}
#studio-status{font-size:14px;color:var(--muted)}#studio-status.error{color:#f08a7e}
nav.toc{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0 8px}nav.toc a{font-size:14px;padding:6px 10px;border:1px solid var(--border);border-radius:999px;text-decoration:none;color:var(--text)}
.lesson{margin-top:28px;padding:24px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.lesson header{display:grid;grid-template-columns:56px 1fr;gap:16px}.number{font-size:30px;font-weight:700;color:var(--orange)}
.lesson h2{margin:0 0 6px;font-size:24px;line-height:1.25}.lesson header p{margin:0;color:var(--muted);max-width:85ch}
.cases{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.case{font-size:13px;padding:3px 10px;border-radius:999px;background:var(--raised);color:var(--text)}
.columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px;margin-top:20px}
h3{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
ul{list-style:none;margin:0;padding:0;display:grid;gap:8px}li{display:grid;gap:4px}
.item{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;align-items:center;min-height:44px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--raised);color:var(--text);text-decoration:none}
.item:hover{border-color:var(--teal)}.item .name{font-weight:600}.item .meta{grid-column:2;font-size:12px;color:var(--muted)}
.kind{grid-row:span 2;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:3px 7px;border-radius:4px;color:#111318}
.kind.slides{background:var(--orange)}.kind.reading{background:#e3c77b}.kind.report{background:var(--teal)}.kind.demo{background:var(--green)}.kind.studio{background:var(--violet)}
.source{font-size:13px;margin-left:12px}.note{font-size:12px;color:var(--muted);margin-left:12px}.empty{color:var(--muted);font-size:14px;margin:0}
.lesson-foot{margin:18px 0 0;font-size:14px}
footer{margin-top:40px;color:var(--muted);font-size:14px;border-top:1px solid var(--border);padding-top:20px}footer p{max-width:90ch}
@media(max-width:900px){.columns{grid-template-columns:1fr}.hero h1{font-size:31px}}
@media(max-width:520px){.shell{padding:24px 16px 48px}.lesson{padding:18px}.lesson header{grid-template-columns:1fr;gap:4px}}
</style></head>
<body><div class="shell">
<header class="hero"><div class="eyebrow">Applied AI Studio</div><h1>${escape(catalog.title)}</h1><p>${escape(catalog.tagline)}</p>
<div class="actions"><a class="button primary" href="https://codespaces.new/${escape(catalog.repository)}?quickstart=1">Open the Studio in Codespaces</a><a class="button" href="${repoUrl}">Source on GitHub</a><a class="button" href="${repoUrl}/blob/main/docs/student-quickstart.md">Student quickstart</a></div></header>
<section class="studio-bar" aria-labelledby="studio-label"><label id="studio-label" for="studio-base">Where is your Studio running?</label>
<p>Notebook reports and demos on this page run entirely in your browser. <strong>Studio</strong> links open the full app, which runs in GitHub Codespaces or on your computer. Paste the address of your running Studio (port 5173) once; it is saved in this browser only.</p>
<div class="studio-row"><input id="studio-base" type="url" inputmode="url" autocomplete="off" spellcheck="false" placeholder="${DEFAULT_STUDIO}"><button type="button" id="studio-save">Use this address</button><button type="button" id="studio-reset">Reset to local</button></div>
<div id="studio-status" role="status">Studio links open ${DEFAULT_STUDIO}</div></section>
<nav class="toc" aria-label="Lessons">${nav}</nav>
<main>${lessons}</main>
<footer><p>Everything here is educational. Datasets are public teaching data; each lab's README lists its source and license. Merchant product photographs are not redistributed, so public copies show placeholders. Models, cutoffs and results describe classroom evidence, not production systems.</p>
<p>Notebook reports are read-only exports; to rerun code, open the notebook source in a Codespace.</p></footer>
</div>
<script>
(()=>{const KEY="applied-ai-studio-base",FALLBACK=${JSON.stringify(DEFAULT_STUDIO)};
const input=document.getElementById("studio-base"),status=document.getElementById("studio-status");
const origin=(value)=>{try{const url=new URL(value.trim());return url.protocol==="http:"||url.protocol==="https:"?url.origin:null}catch{return null}};
const apply=(base)=>{for(const link of document.querySelectorAll("a[data-route]"))link.href=base+link.dataset.route;status.className="";status.textContent="Studio links open "+base;};
let saved=null;try{saved=origin(localStorage.getItem(KEY)||"")}catch{}
if(saved){input.value=saved;apply(saved)}
document.getElementById("studio-save").addEventListener("click",()=>{const base=origin(input.value);if(!base){status.className="error";status.textContent="Enter a full http:// or https:// address, for example https://your-codespace-5173.app.github.dev";return}input.value=base;try{localStorage.setItem(KEY,base)}catch{}apply(base)});
input.addEventListener("keydown",(event)=>{if(event.key==="Enter")document.getElementById("studio-save").click()});
document.getElementById("studio-reset").addEventListener("click",()=>{try{localStorage.removeItem(KEY)}catch{}input.value="";apply(FALLBACK)});})();
</script></body></html>
`;
}

export function buildSite({ root = ROOT, out = join(ROOT, "_site"), check = false } = {}) {
  const catalog = validateCatalog(loadCatalog(root), root);
  for (const lesson of catalog.lessons) {
    for (const material of lesson.materials) material.bytes = statSync(join(root, material.path)).size;
  }
  const html = renderIndex(catalog);
  if (check) return { catalog, html };
  if (out === root || root.startsWith(out + sep)) throw new Error(`refusing to replace ${out}`);
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  for (const lesson of catalog.lessons) {
    const folder = join(out, "lessons", lesson.id);
    mkdirSync(folder, { recursive: true });
    for (const material of lesson.materials) copyFileSync(join(root, material.path), join(folder, publishedName(material)));
  }
  writeFileSync(join(out, "index.html"), html);
  writeFileSync(join(out, ".nojekyll"), "");
  return { catalog, html };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const outIndex = args.indexOf("--out");
  const out = outIndex >= 0 ? resolve(args[outIndex + 1]) : join(ROOT, "_site");
  const { catalog } = buildSite({ out, check: args.includes("--check") });
  const files = catalog.lessons.reduce((total, lesson) => total + lesson.materials.length, 0);
  console.log(`${args.includes("--check") ? "Checked" : `Built ${out} with`} ${catalog.lessons.length} lessons and ${files} files`);
}
