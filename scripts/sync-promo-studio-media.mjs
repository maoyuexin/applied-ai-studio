// Copies the Module 8 Case 3 Promo Studio manifest and referenced media into
// apps/web/public/media/m8/, which is intentionally gitignored.
//
//   PROMO_STUDIO_MODULE=/path/to/Module_08_AI_Media_Content_Creative \
//     node scripts/sync-promo-studio-media.mjs
//   PROMO_STUDIO_MODULE=/path/to/Module_08_AI_Media_Content_Creative \
//     node scripts/sync-promo-studio-media.mjs --check
//   PROMO_STUDIO_MODULE=/path/to/Module_08_AI_Media_Content_Creative \
//     node scripts/sync-promo-studio-media.mjs --exclude-brand-test
//
// When artifacts/case3/manifest.json is not available yet, the script writes a
// small fallback manifest from the documented schema plus the real smoke/design
// files that already exist. Once the real manifest is produced, it is copied
// as-is and every referenced capture file must exist.
import { access, copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const targetRoot = path.join(root, "apps/web/public/media/m8");
const targetCaptures = path.join(targetRoot, "captures");
const sourceModule = process.env.PROMO_STUDIO_MODULE ?? process.env.MODULE;
const check = process.argv.includes("--check");
const includeBrandTest = process.env.PROMO_STUDIO_INCLUDE_BRAND_TEST !== "0"
  && !process.argv.includes("--exclude-brand-test");
const mediaPath = /^(?!https?:|data:|\/).+\.(?:png|jpe?g|webp|mp4)$/i;

if (!sourceModule) {
  throw new Error("Set PROMO_STUDIO_MODULE to the Module_08_AI_Media_Content_Creative folder.");
}

const sourceRoot = path.resolve(sourceModule);
const capturesRoot = path.join(sourceRoot, "artifacts/captures");
const realManifestPath = path.join(sourceRoot, "artifacts/case3/manifest.json");
const exampleManifestPath = path.join(sourceRoot, "artifacts/case3/manifest.schema.example.json");

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

function assertInsideCaptures(relativePath) {
  const resolved = path.resolve(capturesRoot, relativePath);
  if (!resolved.startsWith(`${path.resolve(capturesRoot)}${path.sep}`)) {
    throw new Error(`Refusing to copy a path outside artifacts/captures: ${relativePath}`);
  }
  return resolved;
}

function collectMediaPaths(value, result = new Set()) {
  if (typeof value === "string") {
    if (mediaPath.test(value) && value.includes("/")) result.add(value);
  } else if (Array.isArray(value)) {
    for (const item of value) collectMediaPaths(item, result);
  } else if (value && typeof value === "object") {
    for (const item of Object.values(value)) collectMediaPaths(item, result);
  }
  return result;
}

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

async function readBrandFact() {
  const factsPath = path.join(capturesRoot, "smoke/car_tests_facts.json");
  if (!(await exists(factsPath))) return null;
  const facts = await readJson(factsPath);
  return Array.isArray(facts) ? facts.find((item) => item.tag === "car_brand") ?? null : null;
}

async function firstExisting(...relativePaths) {
  for (const relativePath of relativePaths) {
    if (await exists(path.join(capturesRoot, relativePath))) return relativePath;
  }
  return undefined;
}

async function fallbackTake(shot, take) {
  const base = `case3/takes/${shot.id}_t${take}`;
  const file = await firstExisting(`${base}.mp4`);
  const poster = await firstExisting(`${base}.jpg`, `${base}_contact.png`);
  return {
    id: `${shot.id}_t${take}`,
    file,
    poster,
    generation_seconds: file ? 53 : undefined,
    seconds: "4",
    prompt: `${shot.title}: ${shot.picture}`,
    qc: {
      verdict: file ? (take === 1 || (shot.id === "s3" && take === 4) ? "keep" : "regenerate") : "pending",
      issues: file && take === 2 ? ["Design drift"] : [],
      note: file
        ? "Generated development manifest; instructor verdicts can be replaced by the real manifest."
        : "Take is still rendering or missing from the source captures.",
    },
  };
}

async function fallbackManifest() {
  const example = await readJson(exampleManifestPath);
  const brandFact = await readBrandFact();
  const shotSpecs = [
    {
      id: "s1",
      title: "Studio reveal",
      picture: "Dark studio; a thin light sweeps across the hood and silent badge.",
      sound: "Low synth swell.",
      keyframe: "case3/frames/s1_keyframe_v1_1280.png",
    },
    {
      id: "s2",
      title: "Coastal glide",
      picture: "The grand tourer moves along a wet coastal highway at blue hour.",
      sound: "Soft tire hiss and a deep electric tone.",
      keyframe: "case3/frames/s2_keyframe_v2_1280.png",
    },
    {
      id: "s3",
      title: "Interior craft",
      picture: "Close detail on stitched leather, glass dashboard and ambient light.",
      sound: "Quiet tactile clicks.",
      keyframe: "case3/frames/s3_keyframe_v1_1280.png",
    },
    {
      id: "s4",
      title: "Arrival pause",
      picture: "The car stops under a hotel canopy; reflections hold on the body line.",
      sound: "City room tone, no engine roar.",
      keyframe: "case3/frames/s4_keyframe_v2_1280.png",
    },
    {
      id: "s5",
      title: "End card",
      picture: "Logo lockup with the car in profile and the visible AI label.",
      sound: "Synth resolves, one clean chime.",
      keyframe: "case3/frames/s5_keyframe_v2_1280.png",
    },
  ];
  const shots = await Promise.all(shotSpecs.map(async (shot) => ({
    id: shot.id,
    title: shot.title,
    picture: shot.picture,
    sound: shot.sound,
    keyframe: await firstExisting(shot.keyframe),
    keyframe_prompt: `${shot.title} keyframe based on the SOLENNE GT design reference.`,
    video_prompt: `${shot.title}. ${shot.picture} ${shot.sound}`,
    takes: await Promise.all([1, 2, 3, 4].map((take) => fallbackTake(shot, take))),
  })));

  return {
    _note: "Fallback manifest generated by scripts/sync-promo-studio-media.mjs because artifacts/case3/manifest.json was not present.",
    brand: example.brand,
    tagline: example.tagline,
    disclaimer: example.disclaimer,
    models: example.models,
    design: {
      hero: "case3/design/design_hero_v1.png",
      car_description:
        "A fictional two-door electric grand tourer with a long hood, low roofline, champagne-silver paint, slim horizon headlamps, flush glass, a quiet luxury interior, and no real-world badge or trade dress.",
      qc_notes: example.design.qc_notes,
    },
    qc_checklist: example.qc_checklist,
    shots,
    recorded_images: [
      {
        id: "design-base",
        label: "Recorded generate: studio design reference",
        action: "generate",
        file: "case3/design/design_hero_v1.png",
        prompt: "Generate the hero design reference for SOLENNE GT.",
        generation_seconds: 8,
      },
      {
        id: "design-keyframe",
        label: "Recorded edit: 16:9 keyframe crop",
        action: "edit",
        file: "case3/frames/design_hero_v1_1280.png",
        prompt: "Edit into a clean studio keyframe suitable for image-to-video.",
        generation_seconds: 6,
      },
    ],
    comparisons: {
      text_only: {
        file: "case3/takes/s2_text_only.mp4",
        poster: "case3/takes/s2_text_only.jpg",
        prompt: "Photorealistic luxury car commercial from text only.",
        note: "Without a keyframe, the design can drift between shots.",
      },
      keyframe_guided: {
        file: "case3/takes/s2_t1.mp4",
        poster: "case3/takes/s2_t1.jpg",
        prompt: "Use the SOLENNE GT reference frame to guide the coastal glide.",
        note: "The keyframe keeps the body language closer to the design reference.",
      },
      remix: {
        from: "s3_t2",
        file: "case3/takes/s3_t2.mp4",
        poster: "case3/takes/s3_t2.jpg",
        prompt: "Remix the chosen take with quieter lighting and steadier camera motion.",
        note: "A remix is still a new generation that needs the same QC pass.",
      },
    },
    guardrail: {
      brand_test: {
        file: includeBrandTest ? "smoke/smoke_car_brand.mp4" : undefined,
        poster: includeBrandTest ? "smoke/contact_car_brand.png" : undefined,
        prompt: brandFact?.prompt ?? example.guardrail.brand_test.prompt,
        result: brandFact?.observation?.startsWith("NOT refused") ? "Not refused" : example.guardrail.brand_test.result,
        in_class_only: true,
        public_build_note: includeBrandTest ? undefined : "Brand-test media excluded by sync option.",
      },
    },
    final: {
      file: "smoke/smoke_car_photoreal.mp4",
      poster: "smoke/contact_car_photoreal.png",
      edit_list: ["s1_t1", "s2_t1", "s3_t4", "s4_t1", "s5_t1"],
      c2pa: { raw_take: true, after_reencode: false, visible_label: example.disclaimer },
    },
    stats: { takes_total: 20, takes_usable: 0, usable_rate: 0, video_seconds_generated: 80, mean_generation_seconds: 52, cost_usd_estimate: null },
  };
}

function applyBrandTestPolicy(manifest) {
  if (includeBrandTest || !manifest?.guardrail?.brand_test) return manifest;
  delete manifest.guardrail.brand_test.file;
  delete manifest.guardrail.brand_test.poster;
  manifest.guardrail.brand_test.public_build_note = "Brand-test media excluded by sync option.";
  return manifest;
}

async function writeOrCheck(file, bytes) {
  if (check) {
    const current = await readFile(file).catch(() => null);
    if (!current || !current.equals(bytes)) {
      throw new Error(`${path.relative(root, file)} is out of date. Run node scripts/sync-promo-studio-media.mjs`);
    }
    console.log(`up to date  ${path.relative(root, file)}`);
    return;
  }
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, bytes);
  console.log(`wrote       ${path.relative(root, file)} (${(bytes.length / 1024).toFixed(1)} KB)`);
}

async function copyOrCheck(from, to) {
  if (check) {
    const source = await readFile(from);
    const current = await readFile(to).catch(() => null);
    if (!current || !current.equals(source)) {
      throw new Error(`${path.relative(root, to)} is out of date. Run node scripts/sync-promo-studio-media.mjs`);
    }
    console.log(`up to date  ${path.relative(root, to)}`);
    return;
  }
  await mkdir(path.dirname(to), { recursive: true });
  await copyFile(from, to);
  console.log(`copied      ${path.relative(capturesRoot, from)} -> ${path.relative(root, to)}`);
}

const usingRealManifest = await exists(realManifestPath);
const manifest = applyBrandTestPolicy(
  usingRealManifest ? await readJson(realManifestPath) : await fallbackManifest(),
);
const manifestBytes = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`);
const paths = [...collectMediaPaths(manifest)].sort();

for (const relativePath of paths) {
  const source = assertInsideCaptures(relativePath);
  if (!(await exists(source))) {
    throw new Error(`Referenced media is missing: artifacts/captures/${relativePath}`);
  }
}

await writeOrCheck(path.join(targetRoot, "manifest.json"), manifestBytes);
for (const relativePath of paths) {
  await copyOrCheck(assertInsideCaptures(relativePath), path.join(targetCaptures, relativePath));
}

console.log(
  `${check ? "Checked" : "Synced"} Promo Studio ${usingRealManifest ? "manifest" : "fallback manifest"} with ${paths.length} media file(s).`,
);
