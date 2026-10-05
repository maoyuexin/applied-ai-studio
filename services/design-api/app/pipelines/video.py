"""Video pipeline: brief -> shot list (gate) -> keyframes (gate) -> takes (gate) -> voiceover -> assemble -> provenance."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..media import cover_resize_png
from ..providers.base import ProviderError
from .base import ActionError, Pipeline, StepSpec, Template, c2pa_check, check, clean_text, rules_sentence

if TYPE_CHECKING:
    from ..engine import RunContext

SHOTLIST_SYSTEM = """You are a commercial director planning a short video for a text-to-video model \
(Sora 2 on Microsoft Foundry). Write a shot list as JSON.

Rules that come from how the model behaves:
- Each shot is generated separately and the model remembers nothing between shots. Describe the subject fully \
and consistently in every shot prompt (same colors, shape, clothing, setting details).
- Ask for visible action: specific movement verbs, camera movement (dolly, drone follow, handheld) and what \
changes from the first second to the last. Static descriptions produce clips that look like still slides.
- Shots that show people must be "t2v" (text to video): the service rejects input images that contain faces.
- Shots of the product or a place without people may be "i2v" when reference images are available: they start \
from a keyframe image. For those, also write "keyframe_prompt": an instruction for an image editor to place the \
exact product from reference image 1 into the opening frame of the shot.
- No real brand names, logos, celebrities or readable license plates unless the brief owns them.
- One short sound cue per shot (ambience, effects, music mood; no lyrics).

Return only JSON: {"shots": [{"title": "3-6 words", "subject": "product|people|scene", "mode": "i2v|t2v", \
"keyframe_prompt": "...", "prompt": "60-110 words", "sound": "...", "on_screen_text": ""}], \
"notes": "one sentence on the story arc"}"""

PRODUCT_ID_SUFFIX = "Keep the product identical to image 1: same shape, paint, lights and proportions."


class Reference(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["subject", "style", "scene"] = "subject"
    name: str = Field("", max_length=120)


class VideoBrief(BaseModel):
    brief: str = Field(min_length=20, max_length=4000)
    shots: int = Field(4, ge=1, le=8)
    seconds: Literal[4, 8, 12] = 8
    takes_per_shot: int = Field(3, ge=1, le=4)
    size: Literal["1280x720", "720x1280"] = "1280x720"
    must_not_include: str = Field("", max_length=600)
    visible_label: str = Field("Made with AI", max_length=80)
    end_title: str = Field("", max_length=60)
    end_tagline: str = Field("", max_length=90)
    voiceover: str = Field("", max_length=800)
    voice: str = Field("", max_length=120)
    references: list[Reference] = Field(default_factory=list, max_length=5)


class Shot(BaseModel):
    id: str
    title: str = Field(max_length=80)
    subject: Literal["product", "people", "scene"] = "scene"
    mode: Literal["i2v", "t2v"] = "t2v"
    keyframe_prompt: str = Field("", max_length=1500)
    prompt: str = Field(min_length=10, max_length=2000)
    sound: str = Field("", max_length=300)
    on_screen_text: str = Field("", max_length=120)


def frame_size(size: str) -> tuple[int, int]:
    width, height = (int(part) for part in size.split("x"))
    return width, height


def keyframe_size(size: str) -> tuple[int, int]:
    return (1536, 864) if size == "1280x720" else (864, 1536)


def motion_check(value: float | None) -> dict[str, str]:
    basis = "mean frame-to-frame luminance change (0-255)"
    if value is None:
        return check("motion", "Motion: not measured", "info", basis)
    if value < 0.6:
        return check("motion", f"Motion {value:.2f} (low: may look like a still)", "warn", basis)
    if value < 1.5:
        return check("motion", f"Motion {value:.2f} (moderate)", "ok", basis)
    return check("motion", f"Motion {value:.2f} (strong)", "ok", basis)


def audio_check(has_audio: bool, loudness: dict[str, Any]) -> dict[str, str]:
    basis = "ffmpeg volumedetect + silencedetect (measured, not listened to)"
    if not has_audio:
        return check("audio", "No audio track", "warn", basis)
    mean = loudness.get("mean_db")
    if mean is None or mean < -50:
        return check("audio", "Audio track is silent", "warn", basis)
    gaps = loudness.get("silent_gaps") or 0
    if gaps:
        return check("audio", f"Sound present, {gaps} silent gap(s) over 0.8 s", "warn", basis)
    return check("audio", f"Sound present ({mean:.1f} dB mean), no silent gaps", "ok", basis)


class VideoPipeline(Pipeline):
    key = "video"
    title = "Video"
    summary = "Brief to shot list, keyframes for product shots, several takes per shot, your keep / regenerate " \
              "calls, then the assembled, labeled cut."
    roles = ("text-draft", "image", "video", "voice")
    steps = (
        StepSpec("shotlist", "Brief → shot list", gate=True, role="text-draft",
                 description="The text model turns the brief into shots. You edit or redraft, then approve."),
        StepSpec("keyframes", "Keyframes for product shots", gate=True, role="image",
                 description="Opening frames edited from your reference images. Shots with people skip this."),
        StepSpec("takes", "Takes", gate=True, role="video",
                 description="Several takes per shot. Keep one per shot; regenerate or remix the rest."),
        StepSpec("voiceover", "Voiceover", optional=True, role="voice",
                 description="Optional narration over the cut."),
        StepSpec("assemble", "Assemble", description="Kept takes, crossfades, label overlay and end card."),
        StepSpec("provenance", "Label + provenance", description="Content Credentials check and a provenance report."),
    )
    templates = (
        Template("product-ad-30", "30-second product ad", "4 shots × 8 s, 3 takes each",
                 {"shots": 4, "seconds": 8, "takes_per_shot": 3, "size": "1280x720"}),
        Template("social-15", "15-second social promo", "4 shots × 4 s, vertical, 2 takes each",
                 {"shots": 4, "seconds": 4, "takes_per_shot": 2, "size": "720x1280"}),
        Template("previz", "Storyboard previz", "6 shots × 4 s, 1 take each",
                 {"shots": 6, "seconds": 4, "takes_per_shot": 1, "size": "1280x720"}),
        Template("blank", "Blank", "Choose everything yourself",
                 {"shots": 3, "seconds": 4, "takes_per_shot": 2, "size": "1280x720"}),
    )

    def __init__(self, poll_seconds: float = 8.0, timeout_seconds: float = 1200) -> None:
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.slot_wait = max(poll_seconds * 3.75, 0.01)

    # Definition

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            return VideoBrief.model_validate(brief).model_dump()
        except ValidationError as error:
            raise ActionError(_first_error(error)) from error

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        shots, takes, seconds = brief["shots"], brief["takes_per_shot"], brief["seconds"]
        per_take = 55 if seconds == 4 else (97 if seconds == 8 else 140)
        waves = -(-shots * takes // 2)
        return {
            "video_generations": shots * takes,
            "video_seconds": shots * takes * seconds,
            "keyframes": shots if brief.get("references") else 0,
            "text_calls": 1,
            "minutes": round(waves * per_take / 60, 1),
            "basis": f"2 takes at a time, about {per_take} s per {seconds}-second take (measured on Sora 2, Oct 2026)",
        }

    def default_title(self, brief: dict[str, Any]) -> str:
        return super().default_title(brief)

    # Shot list

    def should_skip(self, ctx: RunContext, step: dict[str, Any]) -> bool:
        if step["key"] == "keyframes":
            return not any(shot["mode"] == "i2v" for shot in self.shots(ctx))
        if step["key"] == "voiceover":
            return not ctx.brief.get("voiceover", "").strip()
        return False

    def shots(self, ctx: RunContext) -> list[dict[str, Any]]:
        return ctx.step_data("shotlist").get("shots", [])

    async def _draft_shots(self, ctx: RunContext, feedback: str = "") -> None:
        brief = ctx.brief
        has_refs = bool(brief["references"])
        request: dict[str, Any] = {
            "brief": brief["brief"], "shots": brief["shots"], "seconds_per_shot": brief["seconds"],
            "aspect": "16:9 landscape" if brief["size"] == "1280x720" else "9:16 vertical",
            "reference_images": [{"role": ref["role"], "name": ref["name"]} for ref in brief["references"]],
            "keyframes_available": has_refs, "must_not_include": brief["must_not_include"],
        }
        if feedback:
            request["previous_shot_list"] = self.shots(ctx)
            request["editor_feedback"] = feedback
        payload, result = await ctx.text_json(
            "text-draft", SHOTLIST_SYSTEM, json.dumps(request, ensure_ascii=False), purpose="video.shotlist",
            context={"shots": brief["shots"], "seconds": brief["seconds"], "has_reference": has_refs})
        shots = self._clean_shots(payload.get("shots") if isinstance(payload, dict) else None, has_refs,
                                  brief["shots"])
        drafts = ctx.step_data("shotlist").get("drafts", 0) + 1
        ctx.set_step_data("shotlist", shots=shots, notes=clean_text(payload.get("notes"), 400), drafts=drafts,
                          model=result.deployment, seconds=result.seconds, feedback=feedback or None)
        verb = "Redrafted" if feedback else "Drafted"
        ctx.event("info", f"{verb} {len(shots)} shots with {result.deployment} in {result.seconds:.1f} s.",
                  code="drafted")

    @staticmethod
    def _clean_shots(raw: Any, has_refs: bool, limit: int) -> list[dict[str, Any]]:
        if not isinstance(raw, list) or not raw:
            raise ProviderError("The text model returned no shots.", code="bad_output")
        shots = []
        for index, item in enumerate(raw[:limit]):
            if not isinstance(item, dict):
                continue
            subject = item.get("subject") if item.get("subject") in ("product", "people", "scene") else "scene"
            mode = "i2v" if item.get("mode") == "i2v" and has_refs and subject != "people" else "t2v"
            keyframe = clean_text(item.get("keyframe_prompt"), 1500) if mode == "i2v" else ""
            if mode == "i2v" and not keyframe:
                keyframe = "Place the exact product from image 1 into the opening frame of this shot."
            try:
                shots.append(Shot(
                    id=f"s{index + 1}", title=clean_text(item.get("title"), 80) or f"Shot {index + 1}",
                    subject=subject, mode=mode, keyframe_prompt=keyframe,
                    prompt=clean_text(item.get("prompt"), 2000), sound=clean_text(item.get("sound"), 300),
                    on_screen_text=clean_text(item.get("on_screen_text"), 120)).model_dump())
            except ValidationError:
                continue
        if not shots:
            raise ProviderError("The text model's shots were unusable (empty prompts).", code="bad_output")
        return shots

    def _validate_edited_shots(self, ctx: RunContext, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list) or not raw:
            raise ActionError("The shot list needs at least one shot.")
        has_refs = bool(ctx.brief["references"])
        shots = []
        for index, item in enumerate(raw[:8]):
            try:
                shot = Shot.model_validate({**item, "id": f"s{index + 1}"})
            except ValidationError as error:
                raise ActionError(f"Shot {index + 1}: {_first_error(error)}") from error
            if shot.mode == "i2v" and (not has_refs or shot.subject == "people"):
                shot.mode = "t2v"
            if shot.mode == "i2v" and not shot.keyframe_prompt.strip():
                raise ActionError(f"Shot {index + 1} starts from a keyframe, so it needs a keyframe prompt.")
            shots.append(shot.model_dump())
        return shots

    # Execution

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        key = step["key"]
        if key == "shotlist":
            if not self.shots(ctx):
                await self._draft_shots(ctx)
        elif key == "keyframes":
            existing = {a["grp"] for a in ctx.artifacts(step_key="keyframes", kind="keyframe")}
            for shot in self.shots(ctx):
                if shot["mode"] == "i2v" and shot["id"] not in existing:
                    self._add_keyframe(ctx, shot)
        elif key == "takes":
            existing = {a["grp"] for a in ctx.artifacts(step_key="takes", kind="take")}
            for shot in self.shots(ctx):
                if shot["id"] in existing:
                    continue
                for _ in range(ctx.brief["takes_per_shot"]):
                    self._add_take(ctx, shot)
        elif key == "voiceover":
            if not ctx.artifacts(step_key="voiceover"):
                ctx.require("voice")
                ctx.add_artifact("voiceover", "voiceover", label="voiceover", role="voice",
                                 prompt=ctx.brief["voiceover"], params={"voice": ctx.brief["voice"]})
        elif key == "assemble":
            kept = self._kept_takes(ctx)
            ctx.add_artifact("assemble", "final", label="final cut", role="tool",
                             inputs=[take["media_sha"] for take in kept],
                             params={"edit_list": [take["id"] for take in kept],
                                     "edit_labels": [take["label"] for take in kept]})
        elif key == "provenance":
            ctx.add_artifact("provenance", "report", label="provenance", role="tool")

    def _add_keyframe(self, ctx: RunContext, shot: dict[str, Any], *, prompt: str | None = None,
                      parent_id: str | None = None) -> dict[str, Any]:
        ctx.require("image")
        refs = sorted(ctx.brief["references"], key=lambda ref: ("subject", "scene", "style").index(ref["role"]))
        text = prompt or " ".join(part for part in (shot["keyframe_prompt"], PRODUCT_ID_SUFFIX,
                                                    rules_sentence(ctx.brief["must_not_include"])) if part)
        width, height = keyframe_size(ctx.brief["size"])
        return ctx.add_artifact(
            "keyframes", "keyframe", grp=shot["id"], label=ctx.next_label(f"{shot['id']}_k", "keyframes", shot["id"]),
            role="image", prompt=text, inputs=[ref["sha"] for ref in refs], parent_id=parent_id,
            params={"width": width, "height": height, "operation": "edits" if refs else "generations"})

    def _add_take(self, ctx: RunContext, shot: dict[str, Any], *, prompt: str | None = None,
                  parent: dict[str, Any] | None = None, remix_note: str | None = None) -> dict[str, Any]:
        ctx.require("video")
        params: dict[str, Any] = {"seconds": ctx.brief["seconds"], "size": ctx.brief["size"], "mode": shot["mode"]}
        inputs: list[str] = []
        if remix_note and parent is not None:
            params.update(mode="remix", remix_of=parent["vendor_job_id"], remix_of_label=parent["label"])
            text = remix_note
        else:
            text = prompt or " ".join(part for part in (
                shot["prompt"], f"Sound: {shot['sound']}." if shot["sound"] else "",
                rules_sentence(ctx.brief["must_not_include"])) if part)
            if shot["mode"] == "i2v":
                keyframe = self._kept_keyframe(ctx, shot["id"])
                if keyframe is None:
                    raise ActionError(f"Shot {shot['id']} needs a kept keyframe first.")
                inputs = [keyframe["media_sha"]]
                params["keyframe_id"] = keyframe["id"]
        return ctx.add_artifact(
            "takes", "take", grp=shot["id"], label=ctx.next_label(f"{shot['id']}_t", "takes", shot["id"]),
            role="video", prompt=text, inputs=inputs, params=params, parent_id=parent["id"] if parent else None)

    def _kept_keyframe(self, ctx: RunContext, shot_id: str) -> dict[str, Any] | None:
        for artifact in reversed(ctx.artifacts(step_key="keyframes", grp=shot_id)):
            if artifact["status"] == "ready" and artifact["verdict"] == "keep":
                return artifact
        return None

    def _kept_takes(self, ctx: RunContext) -> list[dict[str, Any]]:
        kept = []
        for shot in self.shots(ctx):
            take = next((a for a in ctx.artifacts(step_key="takes", grp=shot["id"])
                         if a["status"] == "ready" and a["verdict"] == "keep"), None)
            if take is None:
                raise ActionError(f"Shot {shot['id']} has no kept take.")
            kept.append(take)
        return kept

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        kind = artifact["kind"]
        if kind == "keyframe":
            await self._run_keyframe(ctx, artifact)
        elif kind == "take":
            await self._run_take(ctx, artifact)
        elif kind == "voiceover":
            await self._run_voiceover(ctx, artifact)
        elif kind == "final":
            await self._run_assemble(ctx, artifact)
        elif kind == "report":
            await self._run_provenance(ctx, artifact)

    async def _run_keyframe(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        ctx.require("image")
        ctx.reserve("image")
        params = artifact["params"]
        started = time.perf_counter()
        images = [ctx.media.read(sha) for sha in artifact["inputs"]]
        try:
            data = await ctx.providers.image.edit(artifact["prompt"], images, params["width"], params["height"])
        except ProviderError:
            ctx.store.release("image", 1)
            raise
        info, thumb = ctx.save_image(data)
        c2pa = await ctx.tools.c2pa(ctx.media_path(info.sha))
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type=info.media_type,
                            thumb_sha=thumb.sha, gen_seconds=round(time.perf_counter() - started, 1),
                            metrics={"width": info.meta["width"], "height": info.meta["height"], "c2pa": c2pa},
                            checks=[c2pa_check(c2pa)])
        self._auto_keep(ctx, ctx.artifact(artifact["id"]))
        ctx.event("success", f"{artifact['label']} keyframe ready · {time.perf_counter() - started:.0f} s",
                  code="image_done")

    def _auto_keep(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        siblings = [a for a in ctx.artifacts(step_key=artifact["step_key"], grp=artifact["grp"]) if a["id"] != artifact["id"]]
        kept = [a for a in siblings if a["verdict"] == "keep"]
        if not kept or any(a["id"] == artifact["parent_id"] for a in kept):
            for sibling in kept:
                ctx.update_artifact(sibling["id"], verdict=None, quiet=True)
            ctx.update_artifact(artifact["id"], verdict="keep")

    async def _create_take(self, ctx: RunContext, artifact: dict[str, Any]) -> dict[str, Any]:
        video = ctx.providers.video
        params = artifact["params"]
        announced = False
        for _ in range(60):
            try:
                if params.get("mode") == "remix":
                    if not params.get("remix_of"):
                        raise ProviderError("The source take has no vendor job id to remix.", code="bad_request")
                    return await video.remix(params["remix_of"], artifact["prompt"])
                frame = None
                if params.get("mode") == "i2v" and artifact["inputs"]:
                    width, height = frame_size(params["size"])
                    frame = cover_resize_png(ctx.media.read(artifact["inputs"][0]), width, height)
                return await video.create(artifact["prompt"], seconds=params["seconds"], size=params["size"],
                                          input_reference=frame)
            except ProviderError as error:
                if error.code != "too_many_tasks":
                    raise
                if not announced:
                    ctx.event("warn", f"{artifact['label']}: Sora says too many running tasks · waiting for a slot.",
                              code="slot_wait")
                    announced = True
                await asyncio.sleep(self.slot_wait)
        raise ProviderError("Sora stayed busy for too long; retry this take.", code="too_many_tasks")

    async def _run_take(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        ctx.require("video")
        video = ctx.providers.video
        label = artifact["label"]
        job_id = artifact["vendor_job_id"]
        if not job_id:
            ctx.reserve("video")
            try:
                job = await self._create_take(ctx, artifact)
            except ProviderError:
                ctx.store.release("video", 1)
                raise
            job_id = job["id"]
            ctx.update_artifact(artifact["id"], vendor_job_id=job_id, progress=0,
                                data={**artifact["data"], "vendor_created_at": job.get("created_at")})
            how = {"remix": f"remix of {artifact['params'].get('remix_of_label')}", "i2v": "keyframe → video",
                   "t2v": "text → video"}.get(artifact["params"].get("mode"), "")
            ctx.event("info", f"{label} started ({how}).", code="job_started", data={"vendor_job_id": job_id})
        started = time.monotonic()
        last_progress = -1
        transient = 0
        while True:
            try:
                job = await video.get(job_id)
                transient = 0
            except ProviderError as error:
                if error.code == "not_found":
                    raise ProviderError("The Sora job is gone (Sora keeps jobs and outputs for 24 hours).",
                                        code="expired") from error
                transient += 1
                if not error.retryable or transient > 10:
                    raise
                await asyncio.sleep(self.poll_seconds)
                continue
            status = job.get("status")
            if status == "completed":
                break
            if status in ("failed", "cancelled", "canceled"):
                error_info = job.get("error") or {}
                text = json.dumps(error_info).lower()
                code = "content_filter" if any(term in text for term in ("moderation", "safety", "content")) else "upstream"
                message = error_info.get("message") or error_info.get("code") or status
                raise ProviderError(f"Sora could not make this take: {message}", code=code, detail=error_info)
            progress = int(job.get("progress") or 0)
            if progress != last_progress:
                last_progress = progress
                ctx.update_artifact(artifact["id"], progress=progress)
            if time.monotonic() - started > self.timeout_seconds:
                raise ProviderError("Sora took too long; the job may still finish. Retry later.", code="timeout")
            await asyncio.sleep(self.poll_seconds)
        data = await video.download(job_id)
        info = ctx.save_media(data, "video/mp4")
        path = ctx.media_path(info.sha)
        probe = await ctx.tools.probe(path)
        poster = await ctx.tools.video_poster(path, (probe["duration"] or 4) * 0.4)
        thumb = ctx.save_media(poster, "image/jpeg", {"thumb_of": info.sha})
        motion = await ctx.tools.motion_score(path)
        loudness = await ctx.tools.loudness(path) if probe["has_audio"] else {}
        c2pa = await ctx.tools.c2pa(path)
        created, completed = job.get("created_at"), job.get("completed_at")
        gen_seconds = float(completed - created) if isinstance(created, int | float) and isinstance(completed, int | float) else None
        ctx.update_artifact(
            artifact["id"], status="ready", progress=100, media_sha=info.sha, media_type="video/mp4",
            thumb_sha=thumb.sha, gen_seconds=gen_seconds,
            metrics={"motion": motion, **loudness, "duration": probe["duration"], "width": probe["width"],
                     "height": probe["height"], "has_audio": probe["has_audio"], "c2pa": c2pa},
            checks=[motion_check(motion), audio_check(probe["has_audio"], loudness), c2pa_check(c2pa)])
        took = f" · {gen_seconds:.0f} s" if gen_seconds else ""
        ctx.event("success", f"{label} completed{took}.", code="job_done")

    async def _run_voiceover(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        ctx.require("voice")
        voice = artifact["params"].get("voice") or ""
        if not voice:
            voices = await ctx.providers.speech.voices()
            match = next((v for v in voices if v["locale"] == ctx.settings.voice_locale), voices[0] if voices else None)
            if match is None:
                raise ProviderError("No voices are available for the configured voice model.", code="not_configured")
            voice = match["name"]
        ctx.reserve("voice")
        started = time.perf_counter()
        data = await ctx.providers.speech.synthesize(artifact["prompt"], voice, locale=voice[:5])
        info = ctx.save_media(data, "audio/mpeg")
        duration = await ctx.tools.audio_duration(ctx.media_path(info.sha))
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="audio/mpeg",
                            gen_seconds=round(time.perf_counter() - started, 1),
                            params={**artifact["params"], "voice": voice}, metrics={"duration": duration})

    async def _run_assemble(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        brief = ctx.brief
        takes = [ctx.artifact(take_id) for take_id in artifact["params"]["edit_list"]]
        clips = [ctx.media_path(take["media_sha"]) for take in takes]
        voiceover = next((a for a in ctx.artifacts(step_key="voiceover") if a["status"] == "ready"), None)
        with tempfile.TemporaryDirectory(dir=ctx.media.tmp) as folder:
            out = Path(folder) / "final.mp4"
            result = await ctx.tools.assemble_video(
                clips, out, clip_seconds=[float(take["params"].get("seconds") or 4) for take in takes],
                label_text=brief["visible_label"],
                end_card=(brief["end_title"], brief["end_tagline"], brief["visible_label"]) if brief["end_title"] else None,
                voiceover=ctx.media_path(voiceover["media_sha"]) if voiceover else None,
                size=frame_size(brief["size"]))
            info = ctx.media.put_file(out, "video/mp4", {"duration": result["duration"]})
        path = ctx.media_path(info.sha)
        poster = await ctx.tools.video_poster(path, result["duration"] * 0.35)
        thumb = ctx.save_media(poster, "image/jpeg", {"thumb_of": info.sha})
        loudness = await ctx.tools.loudness(path)
        checks = [check("label", f"Label burned in: “{brief['visible_label']}”", "ok" if brief["visible_label"] else "warn",
                        "overlay on every frame")]
        if brief["end_title"]:
            checks.append(check("endcard", f"End card: {brief['end_title']}", "ok", "last 3 seconds"))
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="video/mp4",
                            thumb_sha=thumb.sha, metrics={**result, **loudness}, checks=checks)
        ctx.event("success", f"Assembled {result['clips']} takes into a {result['duration']:.1f} s cut.",
                  code="assembled")

    async def _run_provenance(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        final = next((a for a in ctx.artifacts(step_key="assemble", kind="final") if a["status"] == "ready"), None)
        if final is None:
            raise ActionError("There is no assembled cut to check.")
        final_c2pa = await ctx.tools.c2pa(ctx.media_path(final["media_sha"]))
        takes = [ctx.artifact(take_id) for take_id in final["params"]["edit_list"]]
        report = {
            "final": {"label": final["label"], "c2pa": final_c2pa},
            "takes": [{"label": take["label"], "c2pa": take["metrics"].get("c2pa"), "deployment": take["deployment"],
                       "model_version": take["model_version"]} for take in takes],
            "visible_label": ctx.brief["visible_label"],
            "models": sorted({a["deployment"] for a in ctx.artifacts() if a["deployment"] and a["status"] == "ready"}),
            "note": "Re-encoding removes the vendor's Content Credentials; the burned-in label and this report "
                    "are the disclosure for the final cut.",
        }
        checks = [c2pa_check(final_c2pa)]
        present = sum(1 for take in report["takes"] if (take["c2pa"] or {}).get("present"))
        checks.append(check("c2pa-takes", f"Raw takes with Content Credentials: {present} of {len(takes)}",
                            "ok" if present == len(takes) else "info", "c2patool on each kept take"))
        ctx.update_artifact(artifact["id"], status="ready", data=report, checks=checks)
        ctx.set_step_data("provenance", report=report)

    # Gates and actions

    def gate_status(self, ctx: RunContext, step: dict[str, Any]) -> tuple[bool, str]:
        key = step["key"]
        if key == "shotlist":
            return (True, "") if self.shots(ctx) else (False, "There is no shot list yet.")
        if key == "keyframes":
            for shot in self.shots(ctx):
                if shot["mode"] == "i2v" and self._kept_keyframe(ctx, shot["id"]) is None:
                    return False, f"Keep a keyframe for shot {shot['id'][1:]} ({shot['title']})."
            return True, ""
        if key == "takes":
            for shot in self.shots(ctx):
                kept = [a for a in ctx.artifacts(step_key="takes", grp=shot["id"])
                        if a["status"] == "ready" and a["verdict"] == "keep"]
                if not kept:
                    return False, f"Keep one take for shot {shot['id'][1:]} ({shot['title']})."
            return True, ""
        return True, ""

    async def approve(self, ctx: RunContext, step: dict[str, Any], payload: dict[str, Any]) -> None:
        if step["key"] == "shotlist" and "shots" in payload:
            ctx.set_step_data("shotlist", shots=self._validate_edited_shots(ctx, payload["shots"]), edited=True)

    def on_decision(self, ctx: RunContext, artifact: dict[str, Any], verdict: str | None) -> None:
        if verdict != "keep":
            return
        for sibling in ctx.artifacts(step_key=artifact["step_key"], grp=artifact["grp"]):
            if sibling["id"] != artifact["id"] and sibling["verdict"] == "keep":
                ctx.update_artifact(sibling["id"], verdict=None, quiet=True)

    def _require_step(self, ctx: RunContext, key: str) -> None:
        step = ctx.step(key)
        if step["status"] not in ("running", "waiting"):
            raise ActionError(f"'{step['title']}' is not open. Reopen it first.")

    def _shot(self, ctx: RunContext, shot_id: str) -> dict[str, Any]:
        shot = next((shot for shot in self.shots(ctx) if shot["id"] == shot_id), None)
        if shot is None:
            raise ActionError(f"Unknown shot: {shot_id}")
        return shot

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if name == "update_shots":
            self._require_step(ctx, "shotlist")
            ctx.set_step_data("shotlist", shots=self._validate_edited_shots(ctx, payload.get("shots")), edited=True)
            ctx.event("info", "You edited the shot list.", code="edited")
        elif name == "redraft_shots":
            self._require_step(ctx, "shotlist")
            note = clean_text(payload.get("note"), 1000)
            if not note:
                raise ActionError("Say what should change in the shot list.")
            await self._draft_shots(ctx, note)
        elif name == "regenerate_keyframe":
            self._require_step(ctx, "keyframes")
            shot = self._shot(ctx, str(payload.get("shot_id")))
            latest = ctx.artifacts(step_key="keyframes", grp=shot["id"])
            parent = latest[-1] if latest else None
            prompt = clean_text(payload.get("prompt"), 2000) or None
            note = clean_text(payload.get("note"), 600)
            if note and not prompt:
                prompt = f"{(parent or {}).get('prompt') or shot['keyframe_prompt']} Change: {note}"
            self._add_keyframe(ctx, shot, prompt=prompt, parent_id=parent["id"] if parent else None)
        elif name == "regenerate_take":
            self._require_step(ctx, "takes")
            shot = self._shot(ctx, str(payload.get("shot_id")))
            self._add_take(ctx, shot, prompt=clean_text(payload.get("prompt"), 2000) or None)
        elif name == "remix_take":
            self._require_step(ctx, "takes")
            parent = ctx.artifact(str(payload.get("artifact_id")))
            note = clean_text(payload.get("note"), 1000)
            if parent["kind"] != "take" or parent["status"] != "ready" or not parent["vendor_job_id"]:
                raise ActionError("Only finished takes can be remixed.")
            if not note:
                raise ActionError("Describe the change for the remix.")
            self._add_take(ctx, self._shot(ctx, parent["grp"]), parent=parent, remix_note=note)
        else:
            return await super().action(ctx, name, payload)
        return None

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        takes = [a for a in artifacts if a["kind"] == "take" and a["status"] not in ("superseded",)]
        ready = [a for a in takes if a["status"] == "ready"]
        passed = [a for a in ready if a["verdict"] in ("keep", "usable")]
        final = next((a for a in reversed(artifacts) if a["kind"] == "final" and a["status"] == "ready"), None)
        thumb = (final or {}).get("thumb_sha") or next((a["thumb_sha"] for a in ready if a["verdict"] == "keep"
                                                       and a["thumb_sha"]), None) \
            or next((a["thumb_sha"] for a in artifacts if a["thumb_sha"]), None)
        motions = sorted(a["metrics"]["motion"] for a in ready if isinstance(a["metrics"].get("motion"), int | float))
        median = None
        if motions:
            middle = len(motions) // 2
            median = motions[middle] if len(motions) % 2 else round((motions[middle - 1] + motions[middle]) / 2, 2)
        outputs = []
        if final:
            outputs.append(f"{final['metrics'].get('duration', 0):.1f} s cut")
        outputs.append(f"{len(takes)} takes")
        if ready:
            outputs.append(f"{len(passed)} passed")
        return {
            "outputs": " · ".join(outputs), "thumb_sha": thumb, "takes": len(takes), "ready": len(ready),
            "kept": sum(1 for a in ready if a["verdict"] == "keep"), "passed": len(passed),
            "video_seconds": sum(int(a["params"].get("seconds") or 0) for a in ready),
            "images": sum(1 for a in artifacts if a["kind"] == "keyframe" and a["status"] == "ready"),
            "median_motion": median, "final_duration": (final or {}).get("metrics", {}).get("duration"),
            "models": sorted({a["deployment"] for a in artifacts if a["deployment"] and a["status"] == "ready"}),
        }


def _first_error(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(part) for part in first.get("loc", ()))
    return f"{where}: {first.get('msg')}" if where else str(first.get("msg"))
