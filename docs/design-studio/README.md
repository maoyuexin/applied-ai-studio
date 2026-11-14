# Design Studio

Design Studio is the Applied AI Studio workspace for generative pipelines that a person reviews
step by step. It runs on **your own Microsoft Foundry deployments** and keeps every run in a
history you can reopen, fork, compare, export and import.

| Pipeline | Steps (✋ = waits for you) | Models (roles) | Checks that flag |
|---|---|---|---|
| **Article** | brief + sources → outline ✋ → draft → fact check → revise ✋ (repeat) → approve + label | text-draft, text-judge | claims vs sources (supported / partly / unsupported), length, must-not-include |
| **Voice** | brief → script ✋ → synthesize each line + listen-back ✋ → mix + label | text-draft, voice, listen-back | transcript vs script word differences, silence, spoken AI disclosure |
| **Image** | brief + references → prompt ✋ → candidates ✋ → iterate on a version tree ✋ → finish | text-draft, image | content-filter outcome, Content Credentials (C2PA) on originals and labeled copies |
| **Video** | brief → shot list ✋ → keyframes ✋ → takes ✋ → voiceover → assemble → provenance | text-draft, image, video, voice | motion, audio and silent gaps, Content Credentials, burned-in label |
| **Inspect** | images + questions + your labels ✋ → ask the models (1–3 tries) → check against the labels → review disagreements ✋ → rules for asking ✋ → report | up to 4 text models that read images | right, wrong, overconfident (a firm answer where the label is “cannot tell”), unsure, declined vs did not decline, flag terms in open answers |
| **Alerts** | facts per moment + languages ✋ → draft (alert + answer, every language) → check (back-translation, length, AI disclosure, numbers, watch terms) → sign-off desk ✋ → report | text-draft (you pick up to 4), text-judge | numbers not in the facts, missing disclosure, over length, watch terms the facts never mention, the second model's issues |

Video can also run **prompt only**: with *Shot prompts* set to Off, each line of the brief is one shot sent to Sora as written (no text model, no keyframes).

Inspect starts from images you upload, or from a **kit**: a `.zip` with `kit.json` (format
`design-studio-inspect-kit`, version 1: title, tags and a brief whose images name a `file` in the zip) and the
images. Labels are fixed in the review step with the old label kept; once every model has answered, **Ask live**
sends one free question about one image to one model. Vision calls count toward the daily text cap.

Checks never decide. Every keep, regenerate, remix, revision and approval is stored with the run.

Planning documents: [DEV_PLAN.md](DEV_PLAN.md) and the clickable [ux-mockup.html](ux-mockup.html).
Manual end-to-end test script (two cases per pipeline, plus two prompt-only video cases): [TEST_CASES.md](TEST_CASES.md).
How the video pipeline works, for teaching: [VIDEO_GUIDE.md](VIDEO_GUIDE.md).
Architecture decision: [ADR-0004](../adr/0004-design-studio-service.md).

## Run it locally

```sh
npm run setup:design                          # once: Python deps into .venv
cp services/design-api/.env.example services/design-api/.env
# edit .env: your endpoints and deployment names (no keys)
az login                                      # Entra ID; needs "Cognitive Services User" on the resources
npm run dev                                   # web + all APIs, including design-api on :4430
open http://127.0.0.1:5173/design-studio
```

`npm run dev:design` starts only the Design Studio API. Open **Settings** in the app and press
**Test** on each role before class.

No Azure? `DESIGN_PROVIDER_MODE=fake` runs every pipeline end to end with placeholder media,
which is enough to learn the flow and to run the tests.

### Data

Runs live in a SQLite database plus content-addressed media files:

- macOS: `~/Library/Application Support/AppliedAIStudio/design`
- Linux: `~/.local/share/applied-ai-studio/design`
- Override: `DESIGN_DATA_DIR`

Back up that folder, or export runs as bundles (one `.zip` per run) from **Run history** and
import them on another install. Restricted runs are never exported.

### Import the Module 8 runs

```sh
cd services/design-api
../../.venv/bin/python -m app.importer --module8 "<Module_08_AI_Media_Content_Creative>/artifacts"
```

This adds SOLENNE GT round 1 and round 2 (round 2 is a fork of round 1), the design sheet image run
and the brand-name guardrail test (Restricted). It copies media; the Module 8 folder is not changed.
`--replace` re-imports.

## Students

Students bring their own Foundry resource, the same way the AI Fit Analyzer needs their Copilot:

1. Deploy the models they want (for example `gpt-5.4-mini`; `MAI-Image-2.6`; MAI-Voice through the
   Speech service on the same AI Services resource).
2. Give their account the **Cognitive Services User** role on the resource.
3. Copy `.env.example` to `.env`, fill in their endpoints, `az login`, `npm run dev`.

Pipelines whose roles are not configured show what is missing instead of failing.

## Operations

| Topic | What to know |
|---|---|
| Auth | `DefaultAzureCredential`: `az login` on a laptop; `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` for a server's service principal. Keys are never used or stored. |
| Text models | Each run picks its writing model (and, for articles, its fact-check model) on the New run page from `DESIGN_TEXT_MODELS` plus the two defaults (`DESIGN_TEXT_DRAFT_DEPLOYMENT`, `DESIGN_TEXT_JUDGE_DEPLOYMENT`). The choice is stored with the run. This install: gpt-6-astra writes, gpt-6.1-sol checks. |
| Caps | `DESIGN_CAP_VIDEO_TAKES`, `DESIGN_CAP_IMAGES`, `DESIGN_CAP_VOICE_LINES`, `DESIGN_CAP_TEXT_CALLS` per day. Blocked or failed calls give their unit back. |
| Concurrency | Sora: `DESIGN_VIDEO_CONCURRENCY` (default 2; Sora rejects more with "too many running tasks", which the app waits out). MAI-Image: `DESIGN_IMAGE_PER_MINUTE` (default 6). |
| Restarts | Work survives a restart: queued jobs re-run, and Sora jobs resume polling by the job id saved before polling. Sora keeps outputs 24 hours, so takes are downloaded as soon as they finish. |
| Video model lifecycle | Sora 2 (2025-12-08) inference retires **2026-10-15**. Finished takes stay in history; point `DESIGN_VIDEO_DEPLOYMENT` at a successor when one is deployed. |
| Tools | `ffmpeg`/`ffprobe` (assembly, checks) and optionally `c2patool` (Content Credentials). Settings shows which are present. |
| Live updates | Server-sent events at `/api/design/runs/{id}/stream`; proxies must not buffer (`X-Accel-Buffering: no`). The page falls back to polling. |

## Tests

```sh
npm run test:design      # pytest on offline fake providers, including resume-after-restart and bundles
```

Browser end-to-end (all four pipelines clicked through the real UI against the fake API):
see the header of [`services/design-api/e2e/browser_e2e.py`](../../services/design-api/e2e/browser_e2e.py).

## Home server

The home server runs Design Studio as its own `design` container (release notes and rollback in the
deploy README on the server). It authenticates with a service principal that has only
*Cognitive Services User* on the two Foundry resources. Copy runs to it with **Export bundle** on the
Mac and **Import bundle** in its Run history.
