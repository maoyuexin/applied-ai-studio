"""HTTP API for the Agent Workflows tab: scenarios, saved runs, and live runs streamed over SSE."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .config import LIVE_RUNS_DIR, RECORDINGS_DIR, load_settings
from .runner import framework_version, run_scenario
from .scenarios import SCENARIOS, get_scenario

PREFIX = "/api/agent-workflows"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.json$")
SAFE_ID = re.compile(r"^[a-z0-9-]{1,40}$")
APPROVAL_TIMEOUT_SECONDS = 900
KEEP_RUNS = 12

app = FastAPI(title="Agent Workflows API", version="0.1.0")
settings = load_settings()


class LiveRun:
    def __init__(self, scenario_id: str, task_id: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.scenario = scenario_id
        self.task = task_id
        self.events: list[dict] = []
        self.changed = asyncio.Event()
        self.approvals: dict[str, asyncio.Future[bool]] = {}
        self.result: dict | None = None
        self.job: asyncio.Task | None = None

    def push(self, event: dict) -> None:
        self.events.append(event)
        self.changed.set()

    async def decide(self, request: dict) -> bool:
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.approvals[request["request_id"]] = future
        try:
            return await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return False

    @property
    def done(self) -> bool:
        return self.result is not None


RUNS: dict[str, LiveRun] = {}


def active_run() -> LiveRun | None:
    return next((run for run in RUNS.values() if not run.done), None)


async def service_status() -> dict[str, bool]:
    async def probe(client: httpx.AsyncClient, url: str) -> bool:
        try:
            response = await client.get(f"{url.rstrip('/')}/health")
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    async with httpx.AsyncClient(timeout=1.5) as client:
        names = list(settings.services)
        results = await asyncio.gather(*(probe(client, settings.services[n]) for n in names))
    return dict(zip(names, results))


@app.get("/health")
@app.get(f"{PREFIX}/health")
async def health() -> dict:
    return {
        "status": "ok",
        "live_ready": settings.live_ready,
        "model": settings.model,
        "framework": framework_version(),
        "services": await service_status(),
        "busy": active_run() is not None,
    }


@app.get(f"{PREFIX}/scenarios")
async def scenarios() -> list[dict]:
    services = await service_status()
    items = []
    for scenario in SCENARIOS.values():
        missing = [name for name in scenario.requires if not services.get(name)]
        data = scenario.to_dict()
        data["live"] = {
            "available": settings.live_ready and scenario.builder is not None and not missing,
            "reason": (
                "Live runs need a Foundry project and model in settings."
                if not settings.live_ready
                else f"Start these services first: {', '.join(missing)}" if missing else ""
            ),
        }
        items.append(data)
    return items


def _run_summary(path: Path, folder: str) -> dict | None:
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "scenario": run.get("scenario"),
        "name": path.name,
        "folder": folder,
        "task": (run.get("task") or {}).get("label"),
        "status": run.get("status"),
        "mode": run.get("mode"),
        "seconds": run.get("seconds"),
        "started_at": run.get("started_at"),
        "stats": {k: v for k, v in (run.get("stats") or {}).items() if k != "per_agent"},
    }


@app.get(f"{PREFIX}/recordings")
async def recordings() -> list[dict]:
    items: list[dict] = []
    for folder, root in (("recordings", RECORDINGS_DIR), ("live-runs", LIVE_RUNS_DIR)):
        if root.exists():
            for path in sorted(root.glob("*/*.json")):
                summary = _run_summary(path, folder)
                if summary:
                    items.append(summary)
    return items


@app.get(f"{PREFIX}/recordings/{{folder}}/{{scenario_id}}/{{name}}")
async def recording(folder: str, scenario_id: str, name: str) -> dict:
    root = {"recordings": RECORDINGS_DIR, "live-runs": LIVE_RUNS_DIR}.get(folder)
    if root is None or not SAFE_ID.match(scenario_id) or not SAFE_NAME.match(name):
        raise HTTPException(status_code=404, detail="Not found")
    path = (root / scenario_id / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return json.loads(path.read_text(encoding="utf-8"))


class StartRun(BaseModel):
    scenario: str = Field(min_length=1, max_length=40)
    task: str = Field(min_length=1, max_length=60)


@app.post(f"{PREFIX}/runs", status_code=201)
async def start_run(body: StartRun) -> dict:
    if not settings.live_ready:
        raise HTTPException(status_code=503, detail="Live runs need a Foundry project and model in settings.")
    try:
        scenario = get_scenario(body.scenario)
        scenario.task(body.task)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if scenario.builder is None:
        raise HTTPException(status_code=400, detail="This scenario is replay-only.")
    if active_run() is not None:
        raise HTTPException(status_code=409, detail="Another live run is in progress.")

    live = LiveRun(scenario.id, body.task)
    RUNS[live.id] = live
    for old in list(RUNS)[:-KEEP_RUNS]:
        RUNS.pop(old, None)

    async def job() -> None:
        try:
            run = await run_scenario(
                scenario, body.task, settings, mode="live", decide=live.decide, emit=live.push, run_id=live.id
            )
        except Exception as exc:  # reported to the page, the server keeps running
            run = {"id": live.id, "status": "error", "error": f"{type(exc).__name__}: {exc}"[:400], "events": live.events}
        live.result = run
        live.changed.set()
        if run.get("events"):
            folder = LIVE_RUNS_DIR / scenario.id
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            (folder / f"{stamp}--{body.task}.json").write_text(
                json.dumps(run, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    live.job = asyncio.create_task(job())
    return {"id": live.id}


def _live(run_id: str) -> LiveRun:
    live = RUNS.get(run_id)
    if live is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    return live


@app.get(f"{PREFIX}/runs/{{run_id}}/events")
async def run_events(run_id: str) -> EventSourceResponse:
    live = _live(run_id)

    async def stream():  # type: ignore[no-untyped-def]
        sent = 0
        while True:
            while sent < len(live.events):
                yield {"event": "event", "data": json.dumps(live.events[sent], ensure_ascii=False)}
                sent += 1
            if live.done and sent >= len(live.events):
                result = {k: v for k, v in (live.result or {}).items() if k != "events"}
                yield {"event": "done", "data": json.dumps(result, ensure_ascii=False)}
                return
            live.changed.clear()
            try:
                await asyncio.wait_for(live.changed.wait(), timeout=15)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(stream())


class Decision(BaseModel):
    approved: bool


@app.post(f"{PREFIX}/runs/{{run_id}}/approvals/{{request_id}}")
async def decide(run_id: str, request_id: str, body: Decision) -> dict[str, Any]:
    live = _live(run_id)
    future = live.approvals.get(request_id)
    if future is None or future.done():
        raise HTTPException(status_code=404, detail="No pending approval with that id")
    future.set_result(body.approved)
    return {"ok": True}


@app.post(f"{PREFIX}/runs/{{run_id}}/stop")
async def stop(run_id: str) -> dict[str, Any]:
    live = _live(run_id)
    if live.job and not live.job.done():
        live.job.cancel()
    return {"ok": True}
