# ADR-0004: Design Studio as a stateful pipeline service

- Status: accepted
- Date: 2026-10-05

## Context

Module 8 needs more than single model calls. Making a usable ad, poster, voice track or article takes
several steps with a person deciding between them, and the class needs to reopen earlier runs. The
Foundry playgrounds already cover one-off calls. The existing `media-api` (Promo Studio) was stateless:
it proxied MAI-Image and Sora and kept a daily counter in memory.

## Decision

Add `services/design-api`, a FastAPI service that owns pipeline state:

- **Pipelines are declared steps** (Python classes). A step can be a human gate. Each generation is an
  *artifact* whose parameters are enough to run it again.
- **State lives in SQLite** (runs, steps, artifacts, decisions, events, usage) with media stored by
  SHA-256 beside it. The data folder is configurable and is the only writable state.
- **Models are roles** (`text-draft`, `text-judge`, `image`, `video`, `voice`, `listen-back`) mapped to
  deployments by environment variables, so swapping a retired model is configuration only.
- **Auth is Entra ID** through `DefaultAzureCredential`; keys are never stored. Speech uses the
  `aad#<resource-id>#<token>` bearer form, which also covers speech-to-text for the listen-back check.
- **Live updates use server-sent events** with polling as the fallback.
- **Long jobs resume**: vendor job ids are saved before polling, so a restart resumes instead of paying
  for the generation again.
- **Bundles** (`run.json` plus media) move runs between installs; restricted runs never leave.

`media-api` stays for the Promo Studio case-study page and can be removed once that page reads from
Design Studio history.

## Consequences

- One more Python service, and the first with a writable volume and outbound network access on the
  home server. It needs a scoped service principal there, plus nginx settings that don't buffer SSE.
- Students can run everything with their own resource, or offline with `DESIGN_PROVIDER_MODE=fake`.
- The engine runs jobs in-process (asyncio). That fits one instructor or one student per install; a shared
  multi-user deployment would need a real job queue and per-user auth.
