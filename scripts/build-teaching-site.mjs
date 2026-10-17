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
      `<li><a class="item studio-link" data-route="${escape(link.route)}" data-title="${escape(link.title)}" data-lesson="${escape(lesson.id)}" href="#studio">` +
      `<span class="kind studio">Studio</span><span class="name">${escape(link.title)}</span><span class="meta">${escape(link.route.split("?")[0])}</span></a></li>`).join("");
    const cases = (lesson.cases ?? []).map((c) => `<span class="case">${escape(c)}</span>`).join("");
    return `<section class="lesson" id="${escape(lesson.id)}" aria-labelledby="${escape(lesson.id)}-title">
  <header><span class="number">${String(index + 1).padStart(2, "0")}</span><div>
    <h2 id="${escape(lesson.id)}-title">${escape(lesson.title)}</h2>
    <p>${escape(lesson.summary)}</p><div class="cases">${cases}</div></div></header>
  <div class="columns">
    <div><h3>Slides and readings</h3><ul>${read}</ul></div>
    <div><h3>Open in the browser</h3>${open ? `<ul>${open}</ul>` : `<p class="empty">Discussion-led lesson; use the Studio links.</p>`}</div>
    <div><h3>In the Studio app</h3><p class="col-hint">Runs in your own Codespace. <a href="#studio">How to start it</a></p>${studio ? `<ul>${studio}</ul>` : `<p class="empty">No Studio route.</p>`}</div>
  </div>
  <p class="lesson-foot"><a href="${repoUrl}/tree/main/lessons/${escape(lesson.id)}">Lesson guide on GitHub</a></p>
</section>`;
  }).join("\n");
  const nav = catalog.lessons.map((lesson, index) => `<a href="#${escape(lesson.id)}">${String(index + 1).padStart(2, "0")} ${escape(lesson.title.split(":")[0])}</a>`).join("");
  const countOf = (group) => catalog.lessons.reduce((total, lesson) => total + lesson.materials.filter((m) => TYPES[m.type].group === group).length, 0);
  const codespaceButtons = `<a class="button primary" href="https://codespaces.new/${escape(catalog.repository)}?quickstart=1" target="_blank" rel="noopener">Open in Codespaces</a>` +
    `<a class="button" href="${repoUrl}/blob/main/docs/student-quickstart.md" target="_blank" rel="noopener">Step-by-step guide</a>`;
  const steps = `<ol class="steps"><li>Sign in to GitHub. A free account is enough.</li>` +
    `<li>Open in Codespaces and create (or resume) your codespace. The first start takes about 3 minutes; wait for <strong>Applied AI Studio setup is ready</strong>.</li>` +
    `<li>The app opens in a new tab on port 5173. Paste that tab's address here once, and every Studio link opens your copy.</li></ol>`;
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
.paths{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:18px;margin:8px 0}
.path{padding:22px;border:1px solid var(--border);border-radius:10px;background:var(--surface);display:flex;flex-direction:column;gap:12px}
.path h2{margin:0;font-size:22px}.path p{margin:0;color:var(--muted)}.path .actions{margin-top:auto}
.tag{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.tag.browser{color:var(--green)}.tag.app{color:var(--violet)}
.steps{margin:0;padding-left:22px;display:grid;gap:6px;color:var(--text)}.steps li{display:list-item}
.counts{display:grid;gap:8px}.counts li{display:block;color:var(--muted)}.counts strong{font-size:22px;color:var(--text);margin-right:6px}
.connect{border-top:1px solid var(--border);padding-top:12px;display:grid;gap:10px}
.connect summary{cursor:pointer;font-weight:600;min-height:44px;display:flex;align-items:center}
.connect .hint,.dialog-body .hint{font-size:14px;color:var(--muted);margin:0}
#studio-status{font-size:14px;color:var(--muted)}.studio-connected #studio-status{color:var(--green)}.error{color:#f08a7e;font-size:14px;margin:0}.error:empty{display:none}
.studio-row{display:flex;gap:10px;flex-wrap:wrap}.studio-row input{flex:1 1 260px;min-width:0;min-height:44px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font:inherit}
.studio-row button,.text-button{min-height:44px;padding:8px 16px;border-radius:6px;border:1px solid var(--teal);background:transparent;color:var(--text);font:inherit;font-weight:600;cursor:pointer}
.col-hint{font-size:13px;color:var(--muted);margin:-4px 0 10px}.studio-connected .col-hint{display:none}
dialog{padding:0;border:1px solid var(--border);border-radius:12px;background:var(--surface);color:var(--text);width:min(600px,calc(100vw - 24px));max-height:calc(100vh - 24px)}
dialog::backdrop{background:rgba(0,0,0,.65)}.dialog-body{padding:24px;display:grid;gap:14px;position:relative}
.dialog-body h2{margin:0;padding-right:48px;font-size:21px;line-height:1.3}.dialog-body h3{margin:6px 0 0}.dialog-body p{margin:0;color:var(--muted)}
#dialog-close{position:absolute;top:12px;right:12px;width:44px;height:44px;border-radius:6px;border:1px solid var(--border);background:var(--raised);color:var(--text);font-size:22px;cursor:pointer}
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
@media(max-width:900px){.columns,.paths{grid-template-columns:1fr}.hero h1{font-size:31px}}
@media(max-width:520px){.shell{padding:24px 16px 48px}.lesson{padding:18px}.lesson header{grid-template-columns:1fr;gap:4px}}
</style></head>
<body><div class="shell">
<header class="hero"><div class="eyebrow">Applied AI Studio</div><h1>${escape(catalog.title)}</h1><p>${escape(catalog.tagline)}</p></header>
<section class="paths" aria-label="Two ways to explore">
<div class="path"><div class="tag browser">In your browser &middot; no setup</div><h2>Read and try</h2>
<p>Slides, readings, notebook reports and interactive demos open right here. No account, no installation, nothing sent anywhere.</p>
<ul class="counts"><li><strong>${catalog.lessons.length}</strong> lessons</li><li><strong>${countOf("read")}</strong> slide decks and readings</li><li><strong>${countOf("open")}</strong> notebook reports and demos</li></ul>
<div class="actions"><a class="button" href="#lessons">Browse the lessons</a><a class="button" href="${repoUrl}">Source on GitHub</a></div></div>
<div class="path" id="studio"><div class="tag app">Full Studio app &middot; free GitHub Codespace</div><h2>Run the Studio</h2>
<p>Workflows, model labs and review queues are a full application. It runs in your own private Codespace, free within GitHub's monthly allowance.</p>
${steps}
<div class="actions">${codespaceButtons}</div>
<div class="connect"><div id="studio-status" role="status">Not connected yet. Studio links will show these steps.</div>
<details><summary>Already running? Connect it to this page</summary>
<div class="studio-row"><input id="studio-base" type="url" inputmode="url" autocomplete="off" spellcheck="false" aria-label="Studio address" placeholder="https://your-codespace-5173.app.github.dev"><button type="button" id="studio-save">Connect</button></div>
<p class="error" id="studio-error" role="alert"></p>
<p class="hint">Paste the address of the tab that opened on port 5173. Saved in this browser only. Running it on this computer instead? <button type="button" class="text-button" id="studio-local">Use ${DEFAULT_STUDIO.replace("http://", "")}</button></p>
</details><div><button type="button" class="text-button" id="studio-disconnect" hidden>Disconnect</button></div></div></div>
</section>
<nav class="toc" aria-label="Lessons">${nav}</nav>
<main id="lessons">${lessons}</main>
<footer><p>Everything here is educational. Datasets are public teaching data; each lab's README lists its source and license. Merchant product photographs are not redistributed, so public copies show placeholders. Models, cutoffs and results describe classroom evidence, not production systems.</p>
<p>Notebook reports are read-only exports; to rerun code, open the notebook source in a Codespace.</p></footer>
</div>
<dialog id="studio-dialog" aria-labelledby="dialog-title"><div class="dialog-body">
<button type="button" id="dialog-close" aria-label="Close">&times;</button>
<h2 id="dialog-title">&ldquo;<span id="dialog-target"></span>&rdquo; runs in the Studio app</h2>
<p>The Studio is a full application, so it runs in your own GitHub Codespace (free) or on your computer, not on this page.</p>
${steps}
<div class="actions">${codespaceButtons}</div>
<h3>Already running?</h3>
<div class="studio-row"><input id="dialog-base" type="url" inputmode="url" autocomplete="off" spellcheck="false" aria-label="Studio address" placeholder="https://your-codespace-5173.app.github.dev"><button type="button" id="dialog-connect">Connect and open</button></div>
<p class="error" id="dialog-error" role="alert"></p>
<p class="hint">Running it on this computer? <button type="button" class="text-button" id="dialog-local">Use ${DEFAULT_STUDIO.replace("http://", "")}</button></p>
<p class="hint">Just exploring? This lesson's slides, notebook reports and demos open without any setup. <a id="dialog-lesson" href="#lessons">Back to the lesson</a></p>
</div></dialog>
<script>
(()=>{const KEY="applied-ai-studio-base",LOCAL=${JSON.stringify(DEFAULT_STUDIO)};
const $=(id)=>document.getElementById(id),dialog=$("studio-dialog"),links=[...document.querySelectorAll("a[data-route]")];
const toOrigin=(value)=>{try{const url=new URL(String(value).trim());return url.protocol==="http:"||url.protocol==="https:"?url.origin:null}catch{return null}};
let base=null,pending=null;try{base=toOrigin(localStorage.getItem(KEY)||"")}catch{}
const render=()=>{for(const link of links){if(base){link.href=base+link.dataset.route;link.target="_blank";link.rel="noopener"}else{link.href="#studio";link.removeAttribute("target")}}
document.body.classList.toggle("studio-connected",Boolean(base));$("studio-disconnect").hidden=!base;
$("studio-status").textContent=base?"Connected to "+base+". Studio links open your running app.":"Not connected yet. Studio links will show these steps."};
const connect=(value,error)=>{const next=toOrigin(value);if(!next){error.textContent="Paste the full address, for example https://your-codespace-5173.app.github.dev";return false}
error.textContent="";base=next;try{localStorage.setItem(KEY,base)}catch{}$("studio-base").value=base;render();return true};
const openPending=()=>{dialog.close();if(pending)window.open(base+pending,"_blank","noopener")};
$("studio-save").addEventListener("click",()=>connect($("studio-base").value,$("studio-error")));
$("studio-local").addEventListener("click",()=>connect(LOCAL,$("studio-error")));
$("studio-disconnect").addEventListener("click",()=>{base=null;try{localStorage.removeItem(KEY)}catch{}$("studio-base").value="";render()});
$("dialog-connect").addEventListener("click",()=>{if(connect($("dialog-base").value,$("dialog-error")))openPending()});
$("dialog-local").addEventListener("click",()=>{connect(LOCAL,$("dialog-error"));openPending()});
for(const [input,button] of [["studio-base","studio-save"],["dialog-base","dialog-connect"]])$(input).addEventListener("keydown",(event)=>{if(event.key==="Enter"){event.preventDefault();$(button).click()}});
for(const link of links)link.addEventListener("click",(event)=>{if(base)return;event.preventDefault();pending=link.dataset.route;
$("dialog-target").textContent=link.dataset.title;$("dialog-lesson").href="#"+link.dataset.lesson;$("dialog-error").textContent="";dialog.showModal()});
$("dialog-close").addEventListener("click",()=>dialog.close());$("dialog-lesson").addEventListener("click",()=>dialog.close());
dialog.addEventListener("click",(event)=>{if(event.target===dialog)dialog.close()});
if(base)$("studio-base").value=base;render();})();
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
