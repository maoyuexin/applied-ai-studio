# Module 8: AI Media Content & Creative

Studio route: `/promo-studio`

## Case 3: Promo Studio for SOLENNE GT

Promo Studio is a classroom page for the Friday Oct. 9, 2026 ITAI 2372 Module 8
case on image and video generation for a luxury car advertisement. The vehicle
and brand are fictional:

- Brand: **SOLENNE GT**
- Tagline: **Drive the quiet.**
- Required visible label: **Fictional vehicle. Made with AI.**

The route is designed for projection from the instructor laptop. It uses large
dark-theme panels, a five-tab review flow, mobile-safe layouts, and a JSON export
for the student review record.

## Media is local and ignored

The real media manifest is produced outside git under the course module folder:

```sh
PROMO_STUDIO_MODULE="/Users/yuexinmao/Documents/Microsoft Scout/Scratchpad/HCC_2372/modules/Module_08_AI_Media_Content_Creative" \
  npm run sync:promo-media
```

The sync script copies `artifacts/case3/manifest.json` and every referenced file
from `artifacts/captures/` into `apps/web/public/media/m8/`. That target is
gitignored because the files are large and the guardrail brand-test clip is for
in-class use only.

If the real manifest is not present yet, `scripts/sync-promo-studio-media.mjs`
writes a fallback manifest from `manifest.schema.example.json` plus the real
design image and smoke-test clips that already exist. When the real manifest
appears, the same command copies it as-is and fails if any referenced capture is
missing.

Use this check before packaging a release:

```sh
PROMO_STUDIO_MODULE="/path/to/Module_08_AI_Media_Content_Creative" \
  npm run sync:promo-media -- --check
```

For any public build or recording, exclude the in-class-only real-brand guardrail
clip while preserving the prompt/result framing in the manifest:

```sh
PROMO_STUDIO_MODULE="/path/to/Module_08_AI_Media_Content_Creative" \
  npm run sync:promo-media -- --exclude-brand-test
```

## Local run

Recorded mode does not require Azure credentials:

```sh
npm run dev -w @applied-ai-studio/web
open http://127.0.0.1:5173/promo-studio
```

Optional live mode is served only by `services/media-api`; the browser never
calls Azure directly. The media API is off by default even when it is running:

```sh
npm run setup:media
npm run dev:media
```

Set these only for an instructor-owned environment:

```sh
MEDIA_LIVE_IMAGES=1
MEDIA_LIVE_VIDEO=1
MEDIA_DAILY_IMAGE_CAP=40
MEDIA_DAILY_VIDEO_CAP=4
MEDIA_IMAGE_RETRY_ATTEMPTS=3
MEDIA_IMAGE_RETRY_BACKOFF_SECONDS=1
```

The service builds prompts from the fixed SOLENNE GT description and allowed
classroom options, appends at most 160 characters of free text, and authenticates
with `azure-identity` `DefaultAzureCredential`. Do not put Foundry secrets in the
repo. MAI-Image-2.6 rate limits are retried with backoff, and benign vendor
content-filter blocks are surfaced as a teachable classroom message instead of a
page crash.

## Home-server release notes

This worktree intentionally does not modify deployment files. The checked-out
baseline does not contain `deploy/homeserver/README.md`, compose files, or nginx
files, so active home-server wiring should be done in the private deployment
configuration after review.

For the owner-only home-server release behind Cloudflare Access:

1. Sync the media on the server or copy a prepared media directory to a host path
   such as `/srv/applied-ai-studio/m8-media`.
2. Mount that directory read-only into the web container at the static path that
   serves `/media/m8/` (equivalent to `apps/web/public/media/m8/` in local Vite).
3. Keep containers read-only; the sync happens outside the running web container.
4. If live generation is needed, add a separate `media-api` Python service using
   the same Python service pattern as the other FastAPI apps, expose it only to
   the internal compose network, and route nginx `/api/media/` to it after the
   existing Cloudflare Access and nginx auth subrequest checks.
5. Give the service principal only **Cognitive Services User** on the two Foundry
   resources:
   - `aifoundry-image-studio-ymao` for MAI-Image-2.6 image generation/editing.
   - `kestrel-ai` for Sora 2 video generation.
6. Store the service principal environment in the server secrets directory and
   mount that secret only into `media-api`. Do not mount Azure credentials into
   the web container or other services.
7. Enable `MEDIA_LIVE_IMAGES=1` and/or `MEDIA_LIVE_VIDEO=1` only after the secret
   is mounted and the daily caps are set.

Recorded mode remains the default and is sufficient for class if live credentials
or quota are unavailable.
