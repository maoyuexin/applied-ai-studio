"""Design Studio API: pipelines with human gates, run history, live updates and run bundles."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .bundles import export_run, import_run
from .config import Settings
from .engine import Engine
from .events import Broker
from .media import MediaStore, MediaTools, MediaToolError, normalize_upload, thumbnail_jpeg
from .pipelines import build_pipelines
from .pipelines.base import ActionError
from .providers.base import ProviderError
from .providers.registry import ROLE_LABELS, Providers
from .store import Store, now

log = logging.getLogger("design-api")
PREFIX = "/api/design"


class CreateRunRequest(BaseModel):
    pipeline: str = Field(max_length=40)
    brief: dict[str, Any]
    title: str | None = Field(None, max_length=120)
    template: str | None = Field(None, max_length=60)
    parent_run_id: str | None = Field(None, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=12)


class EstimateRequest(BaseModel):
    pipeline: str = Field(max_length=40)
    brief: dict[str, Any]


class UpdateRunRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=120)
    tags: list[str] | None = Field(None, max_length=12)
    restricted: bool | None = None


def _display_path(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def create_app(
    settings: Settings | None = None,
    *,
    providers: Providers | None = None,
    tools: MediaTools | None = None,
) -> FastAPI:
    current = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        data_dir = current.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir / "design.db")
        media = MediaStore(data_dir / "media", store)
        broker = Broker()
        engine = Engine(current, store, media, tools or MediaTools(current.ffmpeg, current.ffprobe, current.c2patool),
                        providers or Providers(current), broker, build_pipelines(current))
        app.state.store, app.state.media, app.state.broker, app.state.engine = store, media, broker, engine
        app.state.tests = {}
        await engine.start()
        cleanup = asyncio.create_task(_cleanup_loop(media))
        try:
            yield
        finally:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
            await engine.stop()
            store.close()

    app = FastAPI(title="Design Studio API", version="0.1.0", lifespan=lifespan)
    app.state.settings = current
    app.add_middleware(
        CORSMiddleware, allow_origins=current.origin_list, allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ActionError)
    async def action_error(_: Request, error: ActionError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(ProviderError)
    async def provider_error(_: Request, error: ProviderError) -> JSONResponse:
        status = 429 if error.code in ("cap_reached", "rate_limit") else 502
        return JSONResponse(status_code=status, content={"detail": str(error), "code": error.code})

    @app.exception_handler(MediaToolError)
    async def media_error(_: Request, error: MediaToolError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    def engine_of(request: Request) -> Engine:
        return request.app.state.engine

    def get_run_or_404(request: Request, run_id: str) -> dict[str, Any]:
        run = request.app.state.store.get_run(run_id)
        if run is None or (current.hide_restricted and run["restricted"]):
            raise HTTPException(status_code=404, detail="Run not found.")
        return run

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "design-api"}

    # Status and settings

    @app.get(f"{PREFIX}/status")
    async def status(request: Request) -> dict[str, Any]:
        engine = engine_of(request)
        store: Store = request.app.state.store
        usage = store.usage()
        caps = {
            "video": {"label": "Video takes", "used": usage.get("video", 0), "cap": current.cap_video_takes,
                      "detail": f"{current.video_concurrency} at a time"},
            "image": {"label": "Images", "used": usage.get("image", 0), "cap": current.cap_images,
                      "detail": f"{current.image_per_minute} per minute"},
            "voice": {"label": "Voice lines", "used": usage.get("voice", 0), "cap": current.cap_voice_lines,
                      "detail": "synthesis + listen-back"},
            "text": {"label": "Text calls", "used": usage.get("text", 0), "cap": current.cap_text_calls, "detail": ""},
        }
        roles = []
        for role in engine.providers.roles():
            item = role.as_dict()
            item["last_test"] = request.app.state.tests.get(role.role)
            roles.append(item)
        pipelines = []
        for pipeline in engine.pipelines.values():
            missing = [role for role in pipeline.roles if role != "listen-back" and not engine.providers.ready(role)]
            pipelines.append({"key": pipeline.key, "title": pipeline.title, "ready": not missing, "missing": missing})
        retires = None
        if current.video_retires_on:
            with contextlib.suppress(ValueError):
                days = (date.fromisoformat(current.video_retires_on) - date.today()).days
                retires = {"on": current.video_retires_on, "days_left": days}
        return {
            "install": current.install_name, "auth": engine.providers.auth_mode, "provider_mode": current.provider_mode,
            "data_dir": _display_path(current.data_dir), "storage_bytes": store.media_total_bytes(),
            "tools": engine.tools.available(), "roles": roles, "caps": caps, "pipelines": pipelines,
            "video_retirement": retires, "hide_restricted": current.hide_restricted,
        }

    @app.post(f"{PREFIX}/status/test/{{role}}")
    async def test_role(request: Request, role: str) -> dict[str, Any]:
        engine = engine_of(request)
        if role not in ROLE_LABELS:
            raise HTTPException(status_code=404, detail="Unknown role.")
        if not engine.providers.ready(role):
            raise ActionError("This role is not configured on this install.")
        started = time.perf_counter()
        providers = engine.providers
        try:
            if role in ("text-draft", "text-judge"):
                if not request.app.state.store.try_reserve("text", 1, current.cap_text_calls):
                    raise ProviderError("Daily cap reached for text calls.", code="cap_reached")
                result = await providers.text.complete(providers.deployment(role), "Reply with JSON only.",
                                                       'Return {"ok": true}.', max_tokens=200, purpose="test")
                detail = f"{result.deployment} answered."
            elif role == "image":
                detail = (await providers.image.probe())["detail"]
            elif role == "video":
                info = await providers.video.ping()
                detail = f"Reachable; {info['jobs_visible']} recent job(s) visible."
            else:
                voices = await providers.speech.voices()
                detail = f"Reachable; {len(voices)} {current.voice_model} voices." if role == "voice" else \
                    "Speech resource reachable (speech to text uses the same resource)."
            outcome = {"ok": True, "seconds": round(time.perf_counter() - started, 2), "detail": detail, "at": now()}
        except ProviderError as error:
            outcome = {"ok": False, "seconds": round(time.perf_counter() - started, 2), "detail": str(error),
                       "code": error.code, "at": now()}
        request.app.state.tests[role] = outcome
        return outcome

    @app.get(f"{PREFIX}/pipelines")
    async def pipelines(request: Request) -> list[dict[str, Any]]:
        return [pipeline.describe() for pipeline in engine_of(request).pipelines.values()]

    @app.post(f"{PREFIX}/estimate")
    async def estimate(request: Request, body: EstimateRequest) -> dict[str, Any]:
        engine = engine_of(request)
        pipeline = engine.pipelines.get(body.pipeline)
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Unknown pipeline.")
        return {"estimate": pipeline.estimate(pipeline.normalize_brief(body.brief)),
                "usage": request.app.state.store.usage()}

    @app.get(f"{PREFIX}/voices")
    async def voices(request: Request, locale: str | None = Query(None, max_length=12)) -> list[dict[str, Any]]:
        providers = engine_of(request).providers
        if not providers.ready("voice"):
            return []
        items = await providers.speech.voices()
        return [voice for voice in items if not locale or voice["locale"] == locale]

    # Uploads and media

    @app.post(f"{PREFIX}/uploads")
    async def upload(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        limit = current.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"Images must be under {current.max_upload_mb} MB.")
        png, media_type, meta = normalize_upload(data)
        media: MediaStore = request.app.state.media
        info = media.put_bytes(png, media_type, {**meta, "name": (file.filename or "upload")[:120]})
        thumb = media.put_bytes(thumbnail_jpeg(png), "image/jpeg", {"thumb_of": info.sha})
        return {"sha": info.sha, "thumb_sha": thumb.sha, "media_type": media_type, "name": file.filename or "upload",
                **meta}

    @app.get(PREFIX + "/media/{sha}")
    async def media_file(request: Request, sha: str, download: str | None = Query(None, max_length=160)) -> FileResponse:
        media: MediaStore = request.app.state.media
        info = request.app.state.store.get_media(sha) if len(sha) == 64 else None
        if info is None or not media.exists(sha):
            raise HTTPException(status_code=404, detail="Media not found.")
        headers = {"Cache-Control": "private, max-age=31536000, immutable"}
        filename = None
        if download:
            safe = "".join(ch for ch in download if ch.isalnum() or ch in "._- ")[:120] or "download"
            filename = safe
        return FileResponse(media.path(sha), media_type=info["media_type"], headers=headers, filename=filename)

    # Runs

    @app.post(f"{PREFIX}/runs", status_code=201)
    async def create_run(request: Request, body: CreateRunRequest) -> dict[str, Any]:
        engine = engine_of(request)
        pipeline = engine.pipelines.get(body.pipeline)
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Unknown pipeline.")
        missing = [role for role in pipeline.roles if role != "listen-back" and not engine.providers.ready(role)]
        if missing:
            raise ActionError(f"This install has no model for: {', '.join(missing)}. Open Settings to connect one.")
        if body.parent_run_id and request.app.state.store.get_run(body.parent_run_id) is None:
            raise ActionError("The run you forked from no longer exists.")
        if body.pipeline == "voice" and engine.providers.ready("voice"):
            known = {voice["name"] for voice in await engine.providers.speech.voices()}
            for speaker in body.brief.get("speakers") or []:
                if speaker.get("voice") not in known:
                    raise ActionError(f"Unknown voice for {speaker.get('name')}: {speaker.get('voice')}")
        tags = sorted({tag.strip()[:40] for tag in body.tags if tag.strip()})
        run = engine.create_run(body.pipeline, body.brief, title=body.title, template=body.template,
                                parent_run_id=body.parent_run_id, tags=tags)
        return engine.detail(run["id"])

    @app.get(f"{PREFIX}/runs")
    async def list_runs(
        request: Request,
        pipeline: str | None = Query(None, max_length=40),
        status_filter: str | None = Query(None, alias="status", max_length=20),
        q: str | None = Query(None, max_length=120),
        tag: str | None = Query(None, max_length=40),
        days: int | None = Query(None, ge=1, le=3650),
        limit: int = Query(200, ge=1, le=1000),
    ) -> dict[str, Any]:
        store: Store = request.app.state.store
        engine = engine_of(request)
        since = (datetime.now().astimezone() - timedelta(days=days)).isoformat(timespec="seconds") if days else None
        runs = store.list_runs(pipeline=pipeline, status=status_filter, query=q, tag=tag, since=since,
                               include_restricted=not current.hide_restricted, limit=limit)
        items = []
        for run in runs:
            steps = store.get_steps(run["id"])
            current_step = next((s for s in steps if s["key"] == run["current_step"]), None)
            pipeline_obj = engine.pipelines.get(run["pipeline"])
            items.append({
                **{key: run[key] for key in ("id", "pipeline", "title", "status", "created_at", "updated_at",
                                             "restricted", "source", "parent_run_id", "tags", "counters", "error")},
                "brief_excerpt": str(run["brief"].get("brief", ""))[:160],
                "pipeline_title": pipeline_obj.title if pipeline_obj else run["pipeline"],
                "step": {"key": current_step["key"], "title": current_step["title"], "index": current_step["idx"] + 1,
                         "total": len(steps), "status": current_step["status"]} if current_step else None,
                "steps_done": sum(1 for s in steps if s["status"] in ("done", "skipped")), "steps_total": len(steps),
            })
        return {"runs": items, "tags": store.all_tags(), "storage_bytes": store.media_total_bytes(),
                "data_dir": _display_path(current.data_dir)}

    @app.get(PREFIX + "/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> dict[str, Any]:
        get_run_or_404(request, run_id)
        return engine_of(request).detail(run_id)

    @app.patch(PREFIX + "/runs/{run_id}")
    async def update_run(request: Request, run_id: str, body: UpdateRunRequest) -> dict[str, Any]:
        get_run_or_404(request, run_id)
        engine = engine_of(request)
        fields: dict[str, Any] = {}
        if body.title is not None:
            fields["title"] = body.title.strip()
        if body.tags is not None:
            fields["tags"] = sorted({tag.strip()[:40] for tag in body.tags if tag.strip()})
        if body.restricted is not None:
            fields["restricted"] = body.restricted
        if fields:
            request.app.state.store.update_run(run_id, **fields)
            if "restricted" in fields:
                engine.ctx(run_id).event("info", "Marked restricted: visible here, never exported." if body.restricted
                                         else "No longer restricted.", code="restricted")
            engine.changed(run_id)
        return engine.detail(run_id)

    @app.delete(PREFIX + "/runs/{run_id}", status_code=204)
    async def delete_run(request: Request, run_id: str) -> None:
        get_run_or_404(request, run_id)
        engine = engine_of(request)
        run = request.app.state.store.get_run(run_id)
        store: Store = request.app.state.store
        if run and store.active_artifacts(run_id):
            engine.cancel(run_id)
        shas = {sha for a in store.list_artifacts(run_id) for sha in (a["media_sha"], a["thumb_sha"]) if sha}
        store.delete_run(run_id)
        request.app.state.media.delete_shas(shas & set(store.unreferenced_media()))
        request.app.state.broker.publish(run_id, {"type": "deleted"})

    @app.post(PREFIX + "/runs/{run_id}/actions/{action}")
    async def run_action(request: Request, run_id: str, action: str) -> dict[str, Any]:
        get_run_or_404(request, run_id)
        try:
            payload = await request.json() if (await request.body()) else {}
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="Body must be JSON.") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        engine = engine_of(request)
        result = await engine.act(run_id, action[:40], payload)
        return {"result": result, "detail": engine.detail(run_id)}

    @app.get(PREFIX + "/runs/{run_id}/stream")
    async def stream(request: Request, run_id: str) -> StreamingResponse:
        run = get_run_or_404(request, run_id)
        broker: Broker = request.app.state.broker
        queue = broker.subscribe(run_id)

        async def events() -> AsyncIterator[str]:
            try:
                yield f"event: hello\ndata: {json.dumps({'rev': run['rev']})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    batch = [message]
                    while not queue.empty():
                        batch.append(queue.get_nowait())
                    changed = [m for m in batch if m["type"] == "changed"]
                    for item in [m for m in batch if m["type"] != "changed"] + changed[-1:]:
                        yield f"event: {item['type']}\ndata: {json.dumps(item, default=str)}\n\n"
                    if any(m["type"] == "deleted" for m in batch):
                        break
            finally:
                broker.unsubscribe(run_id, queue)

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Bundles

    @app.get(PREFIX + "/runs/{run_id}/export")
    async def export(request: Request, run_id: str) -> FileResponse:
        run = get_run_or_404(request, run_id)
        folder = Path(tempfile.mkdtemp(dir=request.app.state.media.tmp))
        out = folder / f"{run_id}.zip"
        await asyncio.to_thread(export_run, request.app.state.store, request.app.state.media, run_id, out)
        return FileResponse(out, media_type="application/zip", filename=f"{run_id}.zip",
                            background=BackgroundTask(shutil.rmtree, folder, True))

    @app.post(f"{PREFIX}/runs/import", status_code=201)
    async def import_bundle(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        limit = current.max_import_mb * 1024 * 1024
        folder = Path(tempfile.mkdtemp(dir=request.app.state.media.tmp))
        try:
            target = folder / "bundle.zip"
            size = 0
            with target.open("wb") as handle:
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(status_code=413, detail="The bundle is larger than this install accepts.")
                    handle.write(chunk)
            run_id = await asyncio.to_thread(import_run, request.app.state.store, request.app.state.media, target,
                                             max_bytes=limit * 2)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        engine_of(request).changed(run_id)
        return engine_of(request).detail(run_id)

    return app


async def _cleanup_loop(media: MediaStore) -> None:
    """Hourly: remove uploads that never became part of a run (older than a day)."""
    while True:
        await asyncio.sleep(3600)
        try:
            cutoff = (datetime.now().astimezone() - timedelta(days=1)).isoformat(timespec="seconds")
            removed = await asyncio.to_thread(media.delete_unreferenced, cutoff)
            if removed:
                log.info("Removed %s unreferenced media files", removed)
        except Exception:  # noqa: BLE001
            log.exception("Media cleanup failed")


app = create_app()
