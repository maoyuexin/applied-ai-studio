"""Pipeline engine: run state machine, human gates, the job worker, caps and resume-after-restart.

Lifecycle of a run
  steps:     pending -> running -> (gate? waiting -> done) | done | skipped | failed
  run:       running | waiting (at a gate) | completed | failed (a step failed; retry it) | canceled
  artifacts: queued -> running -> ready | failed | blocked (content filter) | canceled | superseded

Every generation is an artifact whose `params` hold everything needed to run it again, so a restart
re-queues queued work and resumes vendor jobs (e.g. Sora) by the job id saved before polling.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .events import Broker
from .media import MediaInfo, MediaStore, MediaTools, MediaToolError, image_size, thumbnail_jpeg
from .pipelines.base import ActionError, Pipeline
from .providers.base import ProviderError
from .providers.live import TextResult
from .providers.registry import Providers
from .store import Store, new_run_id, now

log = logging.getLogger("design-api")

ACTIVE = ("queued", "running")
CAP_KEYS = {"text-draft": "text", "text-judge": "text", "image": "image", "video": "video", "voice": "voice",
            "listen-back": "voice"}
CONCURRENCY = {"text-draft": 4, "text-judge": 4, "image": 2, "voice": 3, "listen-back": 3, "tool": 1}


class RunContext:
    """What a pipeline sees while it works on one run."""

    def __init__(self, engine: Engine, run_id: str) -> None:
        self.engine = engine
        self.run_id = run_id

    # Shortcuts
    @property
    def store(self) -> Store:
        return self.engine.store

    @property
    def media(self) -> MediaStore:
        return self.engine.media

    @property
    def tools(self) -> MediaTools:
        return self.engine.tools

    @property
    def providers(self) -> Providers:
        return self.engine.providers

    @property
    def settings(self) -> Settings:
        return self.engine.settings

    @property
    def run(self) -> dict[str, Any]:
        run = self.store.get_run(self.run_id)
        if run is None:
            raise ActionError("This run no longer exists.")
        return run

    @property
    def brief(self) -> dict[str, Any]:
        return self.run["brief"]

    def deployment(self, role: str) -> str:
        """The deployment this run uses for a role: the run's own choice, else the install default."""
        chosen = (self.run.get("settings") or {}).get("models", {}).get(role)
        return chosen or self.providers.deployment(role)

    # Steps
    def step(self, key: str) -> dict[str, Any]:
        step = self.store.get_step(self.run_id, key)
        if step is None:
            raise ActionError(f"Unknown step: {key}")
        return step

    def step_data(self, key: str) -> dict[str, Any]:
        return self.step(key)["data"]

    def set_step_data(self, key: str, **values: Any) -> dict[str, Any]:
        data = {**self.step_data(key), **values}
        self.store.update_step(self.run_id, key, data=data)
        self.changed()
        return data

    # Artifacts
    def artifacts(self, **filters: Any) -> list[dict[str, Any]]:
        return self.store.list_artifacts(self.run_id, **filters)

    def artifact(self, artifact_id: str) -> dict[str, Any]:
        artifact = self.store.get_artifact(artifact_id)
        if artifact is None or artifact["run_id"] != self.run_id:
            raise ActionError("That item is not part of this run.")
        return artifact

    def add_artifact(
        self, step_key: str, kind: str, *, grp: str | None = None, label: str | None = None, role: str | None = None,
        prompt: str | None = None, params: dict[str, Any] | None = None, inputs: list[str] | None = None,
        parent_id: str | None = None, status: str = "queued", data: dict[str, Any] | None = None,
        enqueue: bool = True,
    ) -> dict[str, Any]:
        provider = deployment = version = None
        if role == "tool":
            provider = "local tools"
        elif role:
            provider = {"text-draft": "text", "text-judge": "text"}.get(role, role)
            deployment = self.deployment(role)
            if role == "video":
                version = self.settings.video_model_version or None
            elif role == "image":
                version = self.settings.image_model_label
            elif role == "voice":
                version = self.settings.voice_model
        artifact = self.store.insert_artifact({
            "run_id": self.run_id, "step_key": step_key, "kind": kind, "grp": grp, "label": label,
            "parent_id": parent_id, "status": status, "role": role, "provider": provider, "deployment": deployment,
            "model_version": version, "prompt": prompt, "params": params or {}, "inputs": inputs or [],
            "data": data or {},
        })
        self.changed()
        if enqueue and status == "queued":
            self.engine.enqueue(artifact["id"])
        return artifact

    def update_artifact(self, artifact_id: str, *, quiet: bool = False, **fields: Any) -> None:
        self.store.update_artifact(artifact_id, **fields)
        if not quiet:
            self.changed()

    def next_label(self, prefix: str, step_key: str | None = None, grp: str | None = None) -> str:
        existing = {a["label"] for a in self.artifacts(step_key=step_key, grp=grp)}
        number = 1
        while f"{prefix}{number}" in existing:
            number += 1
        return f"{prefix}{number}"

    # Events and live updates
    def event(self, level: str, message: str, *, code: str | None = None, data: dict[str, Any] | None = None) -> None:
        record = self.store.add_event(self.run_id, level, message, code=code, data=data)
        self.engine.broker.publish(self.run_id, {"type": "event", "event": record})
        self.changed()

    def changed(self) -> None:
        self.engine.changed(self.run_id)

    # Provider helpers
    def reserve(self, role: str, units: float = 1) -> None:
        key = CAP_KEYS.get(role)
        if key is None:
            return
        cap = {"text": self.settings.cap_text_calls, "image": self.settings.cap_images,
               "video": self.settings.cap_video_takes, "voice": self.settings.cap_voice_lines}[key]
        if not self.store.try_reserve(key, units, cap):
            raise ProviderError(f"Daily cap reached for {key} ({cap:g} per day). Raise it in the server settings "
                                "or continue tomorrow.", code="cap_reached")

    def require(self, role: str) -> None:
        if not self.providers.ready(role):
            raise ProviderError(f"No model is configured for the '{role}' role on this install. See Settings.",
                                code="not_configured")

    async def text_json(self, role: str, system: str, user: str, *, purpose: str,
                        context: dict[str, Any] | None = None, max_tokens: int = 6000) -> tuple[Any, TextResult]:
        self.require(role)
        self.reserve(role)
        result: TextResult = await self.providers.text.complete(
            self.deployment(role), system, user, json_mode=True, max_tokens=max_tokens, purpose=purpose,
            context=context)
        return result.json(), result

    # Media helpers
    def save_media(self, data: bytes, media_type: str, meta: dict[str, Any] | None = None) -> MediaInfo:
        return self.media.put_bytes(data, media_type, meta)

    def save_image(self, data: bytes) -> tuple[MediaInfo, MediaInfo]:
        width, height = image_size(data)
        media_type = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
        info = self.media.put_bytes(data, media_type, {"width": width, "height": height})
        thumb = self.media.put_bytes(thumbnail_jpeg(data), "image/jpeg", {"thumb_of": info.sha})
        return info, thumb

    def media_path(self, sha: str) -> Path:
        return self.media.path(sha)


class Engine:
    def __init__(self, settings: Settings, store: Store, media: MediaStore, tools: MediaTools,
                 providers: Providers, broker: Broker, pipelines: dict[str, Pipeline]) -> None:
        self.settings = settings
        self.store = store
        self.media = media
        self.tools = tools
        self.providers = providers
        self.broker = broker
        self.pipelines = pipelines
        self.artifact_tasks: dict[str, asyncio.Task[None]] = {}
        self.step_tasks: dict[str, asyncio.Task[None]] = {}
        self.semaphores = {role: asyncio.Semaphore(limit) for role, limit in CONCURRENCY.items()}
        self.semaphores["video"] = asyncio.Semaphore(settings.video_concurrency)
        self._stopping = False

    def ctx(self, run_id: str) -> RunContext:
        return RunContext(self, run_id)

    def pipeline_for(self, run: dict[str, Any]) -> Pipeline:
        pipeline = self.pipelines.get(run["pipeline"])
        if pipeline is None:
            raise ActionError(f"This install has no '{run['pipeline']}' pipeline.")
        return pipeline

    def changed(self, run_id: str) -> None:
        rev = self.store.bump(run_id)
        self.broker.publish(run_id, {"type": "changed", "rev": rev})

    # Lifecycle

    async def start(self) -> None:
        """Resume work interrupted by a restart: re-queue artifacts and continue steps."""
        for run in self.store.list_runs(limit=10_000):
            if run["status"] not in ("running", "waiting"):
                continue
            run_id = run["id"]
            active = self.store.active_artifacts(run_id)
            if active:
                self.ctx(run_id).event("warn", f"Resumed after a restart: {len(active)} job(s) continue.",
                                       code="resumed")
            for artifact in active:
                self.enqueue(artifact["id"])
            for step in self.store.get_steps(run_id):
                if step["status"] != "running":
                    continue
                if step["data"].get("_started"):
                    self._maybe_finish_step(run_id, step["key"])
                else:
                    self._schedule_step(run_id, step["key"])
            self._advance(run_id)

    async def stop(self) -> None:
        self._stopping = True
        tasks = [*self.artifact_tasks.values(), *self.step_tasks.values()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def idle(self, timeout: float = 30) -> None:
        """Wait until no work is running (tests and the importer use this)."""
        deadline = time.monotonic() + timeout
        while self.artifact_tasks or self.step_tasks:
            if time.monotonic() > deadline:
                raise TimeoutError("Engine still busy.")
            await asyncio.sleep(0.02)

    # Runs

    def create_run(self, pipeline_key: str, brief: dict[str, Any], *, title: str | None = None,
                   template: str | None = None, parent_run_id: str | None = None,
                   tags: list[str] | None = None, source: str = "studio",
                   models: dict[str, str] | None = None) -> dict[str, Any]:
        pipeline = self.pipelines.get(pipeline_key)
        if pipeline is None:
            raise ActionError(f"Unknown pipeline: {pipeline_key}")
        normalized = pipeline.normalize_brief(brief)
        stamp = now()
        run = {
            "id": new_run_id(), "pipeline": pipeline_key, "title": (title or pipeline.default_title(normalized))[:120],
            "template": template, "status": "running", "brief": normalized,
            "settings": {"models": self._check_models(models or {})},
            "parent_run_id": parent_run_id, "tags": sorted(set(tags or [])), "restricted": False, "source": source,
            "current_step": pipeline.steps[0].key, "counters": {}, "created_at": stamp, "updated_at": stamp,
        }
        steps = [{"idx": index, **plan, "status": "pending", "data": {}}
                 for index, plan in enumerate(pipeline.plan_steps(normalized))]
        for index, ref in enumerate(normalized.get("references") or []):
            if self.store.get_media(ref["sha"]) is None or not self.media.exists(ref["sha"]):
                raise ActionError(f"Reference image {index + 1} is missing; upload it again.")
        created = self.store.insert_run(run, steps)
        self._add_references(created["id"], pipeline.steps[0].key, normalized.get("references") or [])
        ctx = self.ctx(created["id"])
        parent = f" (fork of {parent_run_id})" if parent_run_id else ""
        ctx.event("info", f"Run created{parent}.", code="created")
        self._advance(created["id"])
        return created

    def _check_models(self, models: dict[str, str]) -> dict[str, str]:
        allowed = self.settings.text_model_list
        checked = {}
        for role, deployment in models.items():
            if not deployment:
                continue
            if role not in ("text-draft", "text-judge"):
                raise ActionError(f"Only text models can be chosen per run (got '{role}').")
            if not self.providers.fake and deployment not in allowed:
                raise ActionError(f"'{deployment}' is not one of this install's text models: {', '.join(allowed)}.")
            checked[role] = deployment
        return checked

    def _add_references(self, run_id: str, step_key: str, references: list[dict[str, Any]]) -> None:
        """Reference images become artifacts so history shows them and bundles carry them."""
        for index, ref in enumerate(references):
            info = self.store.get_media(ref["sha"])
            if info is None or not self.media.exists(ref["sha"]):
                raise ActionError(f"Reference image {index + 1} is missing; upload it again.")
            thumb = self.media.put_bytes(thumbnail_jpeg(self.media.read(ref["sha"])), "image/jpeg",
                                         {"thumb_of": ref["sha"]})
            self.store.insert_artifact({
                "run_id": run_id, "step_key": step_key, "kind": "reference", "grp": "references",
                "label": ref.get("name") or f"reference {index + 1}", "status": "ready", "media_sha": ref["sha"],
                "media_type": info["media_type"], "thumb_sha": thumb.sha, "metrics": info["meta"],
                "data": {"role": ref.get("role", "subject"), "position": index + 1},
            })

    def detail(self, run_id: str) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        pipeline = self.pipelines.get(run["pipeline"])
        steps = self.store.get_steps(run_id)
        gate = None
        waiting = next((step for step in steps if step["status"] == "waiting"), None)
        if waiting and pipeline:
            ready, reason = pipeline.gate_status(self.ctx(run_id), waiting)
            gate = {"step": waiting["key"], "ready": ready, "reason": reason}
        for step in steps:
            step["data"] = {key: value for key, value in step["data"].items() if not key.startswith("_")}
        return {
            "run": run,
            "pipeline": pipeline.describe() if pipeline else None,
            "steps": steps,
            "artifacts": self.store.list_artifacts(run_id),
            "events": self.store.list_events(run_id, limit=250),
            "decisions": self.store.list_decisions(run_id)[-200:],
            "gate": gate,
        }

    # Actions

    async def act(self, run_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        pipeline = self.pipeline_for(run)
        ctx = self.ctx(run_id)
        if action == "approve":
            await self._approve(ctx, pipeline, str(payload.get("step") or ""), payload)
        elif action == "decide":
            self._decide(ctx, pipeline, payload)
        elif action == "retry_artifact":
            self._retry_artifact(ctx, payload)
        elif action == "retry_step":
            self._retry_step(ctx, str(payload.get("step") or ""))
        elif action == "reopen":
            self._reopen(ctx, pipeline, str(payload.get("step") or ""))
        elif action == "cancel":
            self.cancel(run_id)
        else:
            if run["status"] == "canceled":
                raise ActionError("This run was canceled. Fork it to try again.")
            result = await pipeline.action(ctx, action, payload)
            self._refresh(run_id)
            return result
        self._refresh(run_id)
        return None

    async def _approve(self, ctx: RunContext, pipeline: Pipeline, step_key: str, payload: dict[str, Any]) -> None:
        step = ctx.step(step_key)
        if step["status"] != "waiting":
            raise ActionError(f"'{step['title']}' is not waiting for review.")
        await pipeline.approve(ctx, step, payload)
        ready, reason = pipeline.gate_status(ctx, ctx.step(step_key))
        if not ready:
            raise ActionError(reason)
        self.store.update_step(ctx.run_id, step_key, status="done", finished_at=now())
        self.store.add_decision(ctx.run_id, "approve", step_key=step_key, note=payload.get("note"))
        ctx.event("success", f"You approved: {step['title']}.", code="approved")
        self._advance(ctx.run_id)

    def _decide(self, ctx: RunContext, pipeline: Pipeline, payload: dict[str, Any]) -> None:
        artifact = ctx.artifact(str(payload.get("artifact_id") or ""))
        verdict = payload.get("verdict")
        if verdict not in (None, "keep", "usable", "regenerate", "reject"):
            raise ActionError("Verdict must be keep, usable, regenerate or reject.")
        if verdict == "keep" and artifact["status"] != "ready":
            raise ActionError("Only finished items can be kept.")
        fields: dict[str, Any] = {"verdict": verdict}
        if "note" in payload:
            fields["note"] = str(payload.get("note") or "")[:2000] or None
        if isinstance(payload.get("checklist"), dict):
            fields["checklist"] = {str(k)[:80]: v for k, v in payload["checklist"].items() if v in (True, False, None)}
        self.store.update_artifact(artifact["id"], **fields)
        pipeline.on_decision(ctx, artifact, verdict)
        self.store.add_decision(ctx.run_id, "decide", artifact_id=artifact["id"], step_key=artifact["step_key"],
                                verdict=verdict, note=fields.get("note"), checklist=fields.get("checklist", {}))
        label = artifact["label"] or artifact["kind"]
        words = {"keep": "kept", "usable": "marked usable", "regenerate": "marked for regeneration",
                 "reject": "rejected", None: "cleared the verdict on"}[verdict]
        ctx.event("info", f"You {words} {label}." if verdict else f"You cleared the verdict on {label}.",
                  code="decision")

    def _retry_artifact(self, ctx: RunContext, payload: dict[str, Any]) -> None:
        artifact = ctx.artifact(str(payload.get("artifact_id") or ""))
        if artifact["status"] not in ("failed", "blocked", "canceled"):
            raise ActionError("Only failed, blocked or canceled items can be retried.")
        step = ctx.step(artifact["step_key"])
        if step["status"] in ("done", "skipped", "pending"):
            raise ActionError(f"'{step['title']}' is not active; reopen it first.")
        fields: dict[str, Any] = {"status": "queued", "error": None, "error_code": None, "vendor_job_id": None,
                                  "progress": None}
        if isinstance(payload.get("prompt"), str) and payload["prompt"].strip():
            fields["prompt"] = payload["prompt"].strip()[:6000]
        self.store.update_artifact(artifact["id"], **fields)
        if step["status"] == "failed":
            self.store.update_step(ctx.run_id, step["key"], status="running", error=None)
        reworded = " with a reworded prompt" if "prompt" in fields else ""
        ctx.event("info", f"Retrying {artifact['label'] or artifact['kind']}{reworded}.", code="retry")
        self.enqueue(artifact["id"])

    def _retry_step(self, ctx: RunContext, step_key: str) -> None:
        step = ctx.step(step_key)
        if step["status"] != "failed":
            raise ActionError(f"'{step['title']}' has not failed.")
        for artifact in ctx.artifacts(step_key=step_key):
            if artifact["status"] in ("failed", "blocked"):
                self.store.update_artifact(artifact["id"], status="superseded")
        self.store.update_step(ctx.run_id, step_key, status="pending", error=None,
                               data={k: v for k, v in step["data"].items() if k != "_started"})
        if ctx.run["status"] == "failed":
            self.store.update_run(ctx.run_id, status="running", error=None)
        ctx.event("info", f"Retrying step: {step['title']}.", code="retry")
        self._advance(ctx.run_id)

    def _reopen(self, ctx: RunContext, pipeline: Pipeline, step_key: str) -> None:
        steps = self.store.get_steps(ctx.run_id)
        target = next((step for step in steps if step["key"] == step_key), None)
        if target is None or not target["gate"]:
            raise ActionError("Only review steps can be reopened.")
        if target["status"] not in ("done",):
            raise ActionError(f"'{target['title']}' is not finished, so there is nothing to reopen.")
        for step in steps:
            if step["idx"] <= target["idx"]:
                continue
            for artifact in ctx.artifacts(step_key=step["key"]):
                if artifact["status"] in ACTIVE:
                    self._cancel_artifact(artifact["id"])
                if artifact["status"] != "superseded":
                    self.store.update_artifact(artifact["id"], status="superseded")
            self.store.update_step(ctx.run_id, step["key"], status="pending", error=None, started_at=None,
                                   finished_at=None, data={})
        self.store.update_step(ctx.run_id, step_key, status="waiting", finished_at=None)
        self.store.update_run(ctx.run_id, status="waiting", error=None)
        self.store.add_decision(ctx.run_id, "reopen", step_key=step_key)
        ctx.event("info", f"Reopened: {target['title']}. Later steps will run again after you approve.",
                  code="reopened")

    def cancel(self, run_id: str) -> None:
        ctx = self.ctx(run_id)
        for artifact in self.store.active_artifacts(run_id):
            self._cancel_artifact(artifact["id"])
            self.store.update_artifact(artifact["id"], status="canceled")
        for key, task in list(self.step_tasks.items()):
            if key.startswith(f"{run_id}:"):
                task.cancel()
        for step in self.store.get_steps(run_id):
            if step["status"] == "running":
                self.store.update_step(run_id, step["key"], status="failed", error="Canceled")
        self.store.update_run(run_id, status="canceled")
        ctx.event("warn", "Run canceled. Vendor jobs already started may still finish on their side.",
                  code="canceled")

    def _cancel_artifact(self, artifact_id: str) -> None:
        task = self.artifact_tasks.pop(artifact_id, None)
        if task is not None:
            task.cancel()

    # Step machinery

    def _schedule_step(self, run_id: str, step_key: str) -> None:
        key = f"{run_id}:{step_key}"
        if key in self.step_tasks or self._stopping:
            return
        self.step_tasks[key] = asyncio.get_running_loop().create_task(self._start_step(run_id, step_key))

    async def _start_step(self, run_id: str, step_key: str) -> None:
        ctx = self.ctx(run_id)
        run = ctx.run
        pipeline = self.pipeline_for(run)
        step = ctx.step(step_key)
        self.store.update_step(run_id, step_key, status="running", started_at=step["started_at"] or now(), error=None)
        self.store.update_run(run_id, current_step=step_key)
        self._refresh(run_id)
        try:
            await pipeline.start_step(ctx, ctx.step(step_key))
            self.store.update_step(run_id, step_key, data={**ctx.step_data(step_key), "_started": True})
        except asyncio.CancelledError:
            raise
        except (ProviderError, MediaToolError, ActionError) as error:
            self._fail_step(ctx, step, str(error), getattr(error, "code", None))
        except Exception as error:  # noqa: BLE001 - surface unexpected bugs as a failed step, not a crash
            log.exception("Step %s failed", step_key)
            self._fail_step(ctx, step, f"Unexpected error: {error}", "internal")
        finally:
            self.step_tasks.pop(f"{run_id}:{step_key}", None)
        self._maybe_finish_step(run_id, step_key)

    def _fail_step(self, ctx: RunContext, step: dict[str, Any], message: str, code: str | None) -> None:
        self.store.update_step(ctx.run_id, step["key"], status="failed", error=message)
        ctx.event("error", f"{step['title']} failed: {message}", code=code or "step_failed")
        self._refresh(ctx.run_id)

    def _maybe_finish_step(self, run_id: str, step_key: str) -> None:
        if self._stopping or f"{run_id}:{step_key}" in self.step_tasks:
            return
        step = self.store.get_step(run_id, step_key)
        if step is None or step["status"] != "running":
            self._refresh(run_id)
            return
        if any(a["step_key"] == step_key for a in self.store.active_artifacts(run_id)):
            return
        run = self.store.get_run(run_id)
        if run is None:
            return
        pipeline = self.pipeline_for(run)
        ctx = self.ctx(run_id)
        outcome = pipeline.step_settled(ctx, step)
        if outcome == "waiting":
            self.store.update_step(run_id, step_key, status="waiting")
            ctx.event("info", f"Ready for your review: {step['title']}.", code="gate")
        elif outcome == "failed":
            failed = [a for a in ctx.artifacts(step_key=step_key) if a["status"] in ("failed", "blocked")]
            reason = failed[0]["error"] if failed else "see the event log"
            self._fail_step(ctx, step, reason or "see the event log", "step_failed")
        else:
            self.store.update_step(run_id, step_key, status="done", finished_at=now())
            self._advance(run_id)
        self._refresh(run_id)

    def _advance(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if run is None or run["status"] in ("canceled",):
            return
        pipeline = self.pipeline_for(run)
        ctx = self.ctx(run_id)
        for step in self.store.get_steps(run_id):
            if step["status"] in ("done", "skipped"):
                continue
            if step["status"] == "pending":
                if pipeline.should_skip(ctx, step):
                    self.store.update_step(run_id, step["key"], status="skipped", finished_at=now())
                    ctx.event("info", f"Skipped: {step['title']} (not needed for this brief).", code="skipped")
                    continue
                self._schedule_step(run_id, step["key"])
            self._refresh(run_id)
            return
        if run["status"] != "completed":
            self.store.update_run(run_id, status="completed", current_step=None, error=None)
            ctx.event("success", "Run completed.", code="completed")
        self._refresh(run_id)

    def _refresh(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if run is None:
            return
        steps = self.store.get_steps(run_id)
        fields: dict[str, Any] = {}
        if run["status"] != "canceled":
            failed = next((step for step in steps if step["status"] == "failed"), None)
            current = next((step for step in steps if step["status"] not in ("done", "skipped")), None)
            if failed:
                fields.update(status="failed", error=failed["error"], current_step=failed["key"])
            elif current is None:
                fields.update(status="completed", error=None, current_step=None)
            else:
                fields.update(status="waiting" if current["status"] == "waiting" else "running", error=None,
                              current_step=current["key"])
        pipeline = self.pipelines.get(run["pipeline"])
        if pipeline is not None:
            counters = pipeline.summarize(run, self.store.list_artifacts(run_id))
            step_models = {step["data"].get("model") for step in steps if step["data"].get("model")}
            counters["models"] = sorted(set(counters.get("models") or []) | step_models)
            fields["counters"] = counters
        changed = {key: value for key, value in fields.items() if run.get(key) != value}
        if changed:
            self.store.update_run(run_id, **changed)
        self.changed(run_id)

    # Artifact jobs

    def enqueue(self, artifact_id: str) -> None:
        if artifact_id in self.artifact_tasks or self._stopping:
            return
        self.artifact_tasks[artifact_id] = asyncio.get_running_loop().create_task(self._run_artifact(artifact_id))

    async def _run_artifact(self, artifact_id: str) -> None:
        artifact = self.store.get_artifact(artifact_id)
        if artifact is None or artifact["status"] not in ACTIVE:
            self.artifact_tasks.pop(artifact_id, None)
            return
        run_id, step_key = artifact["run_id"], artifact["step_key"]
        ctx = self.ctx(run_id)
        label = artifact["label"] or artifact["kind"]
        semaphore = self.semaphores.get(artifact["role"] or "tool", self.semaphores["tool"])
        try:
            async with semaphore:
                artifact = self.store.get_artifact(artifact_id)
                if artifact is None or artifact["status"] not in ACTIVE:
                    return
                if artifact["status"] == "queued":
                    self.store.update_artifact(artifact_id, status="running")
                    ctx.changed()
                pipeline = self.pipeline_for(ctx.run)
                await pipeline.run_artifact(ctx, self.store.get_artifact(artifact_id))  # type: ignore[arg-type]
            current = self.store.get_artifact(artifact_id)
            if current is not None and current["status"] in ACTIVE:
                self.store.update_artifact(artifact_id, status="ready", progress=100)
        except asyncio.CancelledError:
            if self._stopping:
                raise  # leave queued/running so the next start resumes it
            return
        except ProviderError as error:
            blocked = error.code == "content_filter"
            self.store.update_artifact(artifact_id, status="blocked" if blocked else "failed", error=str(error),
                                       error_code=error.code)
            ctx.event("warn" if blocked else "error", f"{label}: {error}", code=error.code,
                      data={"artifact_id": artifact_id, "detail": str(error.detail)[:500] if error.detail else None})
        except (MediaToolError, ActionError) as error:
            self.store.update_artifact(artifact_id, status="failed", error=str(error), error_code="tool")
            ctx.event("error", f"{label}: {error}", code="tool", data={"artifact_id": artifact_id})
        except Exception as error:  # noqa: BLE001
            log.exception("Artifact %s failed", artifact_id)
            self.store.update_artifact(artifact_id, status="failed", error=f"Unexpected error: {error}",
                                       error_code="internal")
            ctx.event("error", f"{label}: unexpected error ({error.__class__.__name__}).", code="internal",
                      data={"artifact_id": artifact_id})
        finally:
            if self.artifact_tasks.get(artifact_id) is asyncio.current_task():
                self.artifact_tasks.pop(artifact_id, None)
            if not self._stopping:
                self._maybe_finish_step(run_id, step_key)
                self._refresh(run_id)
