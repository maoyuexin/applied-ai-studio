import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { inflateSync } from "node:zlib";
import test from "node:test";
import { buildSite, loadCatalog, renderIndex, validateCatalog } from "./build-teaching-site.mjs";

const root = join(import.meta.dirname, "..");

function pdfLinks(file) {
  const bytes = readFileSync(file);
  const chunks = [bytes.toString("latin1")];
  for (const match of chunks[0].matchAll(/stream\r?\n/g)) {
    const start = match.index + match[0].length;
    const end = chunks[0].indexOf("endstream", start);
    try { chunks.push(inflateSync(bytes.subarray(start, end)).toString("latin1")); } catch { /* not a Flate stream */ }
  }
  return new Set(chunks.flatMap((text) => [...text.matchAll(/\/URI\s*\(([^)]*)\)/g)].map((m) => m[1])));
}

function markdownFiles() {
  const files = [join(root, "README.md")];
  for (const base of ["lessons", "courses"]) {
    const walk = (dir) => readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith(".md")) files.push(full);
    });
    if (existsSync(join(root, base))) walk(join(root, base));
  }
  return files;
}

test("catalog references existing files and every lesson PDF", () => {
  const catalog = validateCatalog(loadCatalog());
  const listed = new Set(catalog.lessons.flatMap((lesson) => lesson.materials.map((m) => m.path)));
  for (const lesson of catalog.lessons) {
    for (const material of lesson.materials.filter((m) => m.type === "slides" || m.type === "reading")) {
      assert.equal(dirname(material.path), `lessons/${lesson.id}`, `${material.path} belongs in its lesson folder`);
    }
    for (const name of readdirSync(join(root, "lessons", lesson.id)).filter((n) => n.endsWith(".pdf"))) {
      assert.ok(listed.has(`lessons/${lesson.id}/${name}`), `${lesson.id}/${name} is not in lessons.json`);
    }
  }
});

test("relative links inside slide PDFs resolve to files published beside them", () => {
  const catalog = loadCatalog();
  for (const lesson of catalog.lessons) {
    const published = new Set(lesson.materials.map((m) => m.publishAs ?? basename(m.path)));
    for (const material of lesson.materials.filter((m) => m.path.endsWith(".pdf"))) {
      for (const link of pdfLinks(join(root, material.path))) {
        if (/^[a-z]+:/i.test(link)) continue;
        assert.ok(published.has(link), `${material.path} links to ${link}, which is not published in ${lesson.id}`);
      }
    }
  }
});

test("relative Markdown links resolve", () => {
  for (const file of markdownFiles()) {
    const text = readFileSync(file, "utf8").replace(/```[\s\S]*?```/g, "");
    for (const [, target] of text.matchAll(/\]\(([^)\s]+)\)/g)) {
      if (/^(?:[a-z]+:|#)/i.test(target)) continue;
      const path = decodeURIComponent(target.split("#")[0]);
      assert.ok(existsSync(join(dirname(file), path)), `${file.slice(root.length + 1)} -> ${target}`);
    }
  }
});

test("site build copies every material under its published name", () => {
  const out = mkdtempSync(join(tmpdir(), "teaching-site-"));
  try {
    const { catalog } = buildSite({ out });
    const html = readFileSync(join(out, "index.html"), "utf8");
    assert.ok(existsSync(join(out, ".nojekyll")));
    for (const lesson of catalog.lessons) {
      assert.ok(html.includes(`id="${lesson.id}"`));
      for (const material of lesson.materials) {
        const name = material.publishAs ?? basename(material.path);
        const copy = join(out, "lessons", lesson.id, name);
        assert.equal(statSync(copy).size, statSync(join(root, material.path)).size, copy);
        assert.ok(html.includes(`href="lessons/${lesson.id}/${name}"`), name);
      }
      for (const link of lesson.studio ?? []) assert.ok(html.includes(`data-route="${link.route.replaceAll("&", "&amp;")}"`));
    }
    assert.ok(!/<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i.test(html), "index loads no remote resources");
    assert.ok(!html.includes('href="http://127.0.0.1'), "Studio links default to setup steps, not a local address");
    assert.ok(html.includes('id="studio"') && html.includes('<dialog id="studio-dialog"'));
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("validation rejects unsafe entries and rendering escapes text", () => {
  const catalog = () => structuredClone(loadCatalog());
  const bad = catalog();
  bad.lessons[0].materials[0].path = "../outside.pdf";
  assert.throws(() => validateCatalog(bad), /relative inside/);
  const duplicate = catalog();
  duplicate.lessons[0].materials.push({ ...duplicate.lessons[0].materials[0] });
  assert.throws(() => validateCatalog(duplicate), /duplicate published name/);
  const route = catalog();
  route.lessons[0].studio[0].route = "//example.com";
  assert.throws(() => validateCatalog(route), /single \//);
  const hostile = catalog();
  hostile.lessons[0].title = "<script>alert(1)</script>";
  assert.ok(renderIndex(hostile).includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  assert.throws(() => buildSite({ out: root }), /refusing/);
});
