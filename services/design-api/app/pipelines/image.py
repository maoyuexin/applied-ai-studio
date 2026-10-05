"""Image pipeline: brief -> prompt (gate) -> candidates (gate) -> iterate on a version tree (gate) -> finish."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..media import title_overlay_image
from ..providers.base import ProviderError
from .base import ActionError, Pipeline, StepSpec, Template, c2pa_check, check, clean_text, rules_sentence
from .video import Reference, _first_error

if TYPE_CHECKING:
    from ..engine import RunContext

SIZES = {"1536x864": (1536, 864), "1024x1024": (1024, 1024), "864x1536": (864, 1536)}

USE_CASES: dict[str, dict[str, Any]] = {
    "hero": {"title": "Product hero / key art", "size": "1536x864",
             "guide": "a clean, premium product hero image with room for a headline",
             "checklist": ["Same product as the reference?", "No real brand, logo, plate or face?",
                           "Room for a headline?"]},
    "poster": {"title": "Campaign poster with title", "size": "864x1536",
               "guide": "a vertical campaign poster; leave the lower third calm because the title is added afterwards",
               "checklist": ["Title spelled right (added by the app, not the model)?", "No real brand or logo?",
                             "Reads at a glance?"]},
    "social": {"title": "Social post", "size": "1024x1024",
               "guide": "a square social post that reads at thumbnail size",
               "checklist": ["Reads at thumbnail size?", "No real brand, logo or face?", "On-brief mood?"]},
    "keyframe": {"title": "Storyboard frame / video keyframe", "size": "1536x864",
                 "guide": "the opening frame of a video shot, cinematic, with room for motion",
                 "checklist": ["Matches the design sheet?", "Room for motion in the shot?",
                               "No faces (video tools reject them)?"]},
    "person": {"title": "Character or person study", "size": "864x1536",
               "guide": "a character study; natural hands and faces",
               "checklist": ["Consent for any real person in the references?", "Hands and faces look natural?",
                             "Not a likeness of a real public figure?"]},
    "blank": {"title": "Blank", "size": "1536x864", "guide": "an image that matches the brief",
              "checklist": ["Matches the brief?", "No real brand, logo or face?"]},
}

PROMPT_SYSTEM = """You write prompts for an image model (Microsoft MAI-Image). Turn the creative brief into one \
vivid, concrete prompt of 60-120 words: subject, setting, composition and camera, lighting, palette, mood, \
materials. Describe only what should be visible. Do not mention brands, logos or real people. Do not add text \
or lettering to the image. If reference images are listed, refer to them as "image 1", "image 2" in their order \
and respect their roles. Return only JSON: {"prompt": "..."}"""

REVISE_SYSTEM = """You revise prompts for an image editing model (Microsoft MAI-Image). You get the prompt that \
made the current image and an editor's note. Write the new prompt (60-120 words) that keeps everything the note \
does not change and makes the requested change clearly. Image 1 is the current image unless told otherwise. \
Do not mention brands, logos or real people. Return only JSON: {"prompt": "..."}"""

ROLE_TEXT = {
    "base": "is the current image: keep it unless the instructions change it",
    "subject": "is the subject: keep it exactly as shown (shape, color, details)",
    "scene": "is the scene: place the subject in this setting",
    "style": "is the style reference: borrow its lighting, palette and mood",
}


class ImageBrief(BaseModel):
    use_case: Literal["hero", "poster", "social", "keyframe", "person", "blank"] = "hero"
    brief: str = Field(min_length=10, max_length=4000)
    references: list[Reference] = Field(default_factory=list, max_length=5)
    must_not_include: str = Field("", max_length=600)
    size: Literal["1536x864", "1024x1024", "864x1536"] = "1536x864"
    candidates: int = Field(4, ge=1, le=6)
    prompt_helper: bool = True
    title: str = Field("", max_length=60)
    visible_label: str = Field("Made with AI", max_length=80)


def ordered_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(refs, key=lambda ref: ("base", "subject", "scene", "style").index(ref["role"]))


def role_preamble(refs: list[dict[str, Any]]) -> str:
    return " ".join(f"Image {index + 1} {ROLE_TEXT[ref['role']]}." for index, ref in enumerate(refs))


def compose(core: str, refs: list[dict[str, Any]], must_not_include: str) -> str:
    return " ".join(part for part in (role_preamble(refs), core.strip(), rules_sentence(must_not_include)) if part)


class ImagePipeline(Pipeline):
    key = "image"
    title = "Image"
    summary = "Generate candidates, pick one, then edit in passes with reference images. Every version stays " \
              "on a tree, so you can branch from any of them."
    roles = ("text-draft", "image")
    steps = (
        StepSpec("prompt", "Brief → prompt", gate=True, role="text-draft",
                 description="The text model writes the full prompt from your brief and rules. You can edit it."),
        StepSpec("candidates", "Candidates", gate=True, role="image",
                 description="Several images from the prompt. Keep one or more to iterate on."),
        StepSpec("iterate", "Iterate", gate=True, role="image",
                 description="Revise any version with a note and references. Each pass is a new version."),
        StepSpec("finish", "Finish", description="Title overlay, visible label and Content Credentials check."),
    )
    templates = tuple(Template(key, value["title"], value["guide"], {"use_case": key, "size": value["size"]})
                      for key, value in USE_CASES.items())

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            return ImageBrief.model_validate(brief).model_dump()
        except ValidationError as error:
            raise ActionError(_first_error(error)) from error

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        return {"image_calls": brief["candidates"], "text_calls": 1 if brief["prompt_helper"] else 0,
                "minutes": round(max(brief["candidates"] / 6, 0.5), 1),
                "basis": "MAI-Image-2.6 allows 6 images per minute on this deployment"}

    def checklist(self, brief: dict[str, Any]) -> list[str]:
        return USE_CASES[brief["use_case"]]["checklist"]

    def describe(self) -> dict[str, Any]:
        info = super().describe()
        info["use_cases"] = {key: {k: v for k, v in value.items() if k != "guide"} for key, value in USE_CASES.items()}
        return info

    # Execution

    async def _draft_prompt(self, ctx: RunContext) -> None:
        brief = ctx.brief
        refs = ordered_refs(brief["references"])
        if not brief["prompt_helper"]:
            ctx.set_step_data("prompt", prompt=brief["brief"].strip(), model=None)
            ctx.event("info", "Prompt helper is off: your brief is the prompt.", code="drafted")
            return
        request = {
            "use_case": USE_CASES[brief["use_case"]]["guide"], "brief": brief["brief"],
            "reference_images": [{"image": index + 1, "role": ref["role"], "name": ref["name"]}
                                 for index, ref in enumerate(refs)],
            "must_not_include": brief["must_not_include"], "aspect": brief["size"],
        }
        payload, result = await ctx.text_json("text-draft", PROMPT_SYSTEM, json.dumps(request, ensure_ascii=False),
                                              purpose="image.prompt", context={"brief": brief["brief"]})
        prompt = clean_text(payload.get("prompt") if isinstance(payload, dict) else "", 3000)
        if not prompt:
            raise ProviderError("The text model returned an empty prompt.", code="bad_output")
        ctx.set_step_data("prompt", prompt=prompt, model=result.deployment, seconds=result.seconds)
        ctx.event("info", f"Prompt written by {result.deployment} in {result.seconds:.1f} s.", code="drafted")

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        key = step["key"]
        if key == "prompt":
            if not ctx.step_data("prompt").get("prompt"):
                await self._draft_prompt(ctx)
        elif key == "candidates":
            if not ctx.artifacts(step_key="candidates"):
                self._add_candidates(ctx, ctx.brief["candidates"])
        elif key == "finish":
            data = ctx.step_data("iterate")
            source = ctx.artifact(data["final_id"])
            ctx.add_artifact("finish", "final", label="final", role="tool", inputs=[source["media_sha"]],
                             parent_id=source["id"],
                             params={"title": data.get("title", ""), "label": data.get("label", "")})

    def _add_candidates(self, ctx: RunContext, count: int) -> None:
        ctx.require("image")
        brief = ctx.brief
        refs = ordered_refs(brief["references"])
        width, height = SIZES[brief["size"]]
        core = ctx.step_data("prompt")["prompt"]
        prompt = compose(core, refs, brief["must_not_include"])
        for _ in range(count):
            ctx.add_artifact("candidates", "image", grp="candidates", label=ctx.next_label("c", "candidates"),
                             role="image", prompt=prompt, inputs=[ref["sha"] for ref in refs],
                             params={"width": width, "height": height, "core": core,
                                     "operation": "edits" if refs else "generations",
                                     "roles": [ref["role"] for ref in refs]})

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        if artifact["kind"] == "image":
            await self._run_image(ctx, artifact)
        elif artifact["kind"] == "final":
            await self._run_finish(ctx, artifact)

    async def _run_image(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        ctx.require("image")
        ctx.reserve("image")
        params = artifact["params"]
        started = time.perf_counter()
        images = [ctx.media.read(sha) for sha in artifact["inputs"]]
        try:
            if images:
                data = await ctx.providers.image.edit(artifact["prompt"], images, params["width"], params["height"])
            else:
                data = await ctx.providers.image.generate(artifact["prompt"], params["width"], params["height"])
        except ProviderError:
            ctx.store.release("image", 1)
            raise
        info, thumb = ctx.save_image(data)
        c2pa = await ctx.tools.c2pa(ctx.media_path(info.sha))
        seconds = round(time.perf_counter() - started, 1)
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type=info.media_type,
                            thumb_sha=thumb.sha, gen_seconds=seconds,
                            metrics={"width": info.meta["width"], "height": info.meta["height"], "c2pa": c2pa},
                            checks=[c2pa_check(c2pa)])
        ctx.event("success", f"{artifact['label']} ready · {seconds:.0f} s.", code="image_done")

    async def _run_finish(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        source = ctx.artifact(artifact["parent_id"])
        title, label = artifact["params"].get("title", ""), artifact["params"].get("label", "")
        original = ctx.media.read(source["media_sha"])
        source_c2pa = source["metrics"].get("c2pa") or await ctx.tools.c2pa(ctx.media_path(source["media_sha"]))
        if title or label:
            info, thumb = ctx.save_image(title_overlay_image(original, title, label))
            out_c2pa = await ctx.tools.c2pa(ctx.media_path(info.sha))
        else:
            info, thumb = ctx.save_image(original)
            out_c2pa = source_c2pa
        checks = [check("label", f"Visible label: “{label}”" if label else "No visible label", "ok" if label else "warn",
                        "drawn by the app")]
        if title:
            checks.append(check("title", f"Title set by the app: “{title}”", "ok", "spelling is exact; not generated"))
        checks.append(c2pa_check(source_c2pa) | {"key": "c2pa-source", "label": "Original: " + c2pa_check(source_c2pa)["label"]})
        if title or label:
            checks.append(c2pa_check(out_c2pa) | {"key": "c2pa-final", "label": "Labeled copy: " + c2pa_check(out_c2pa)["label"]})
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type=info.media_type,
                            thumb_sha=thumb.sha, checks=checks,
                            metrics={"source_c2pa": source_c2pa, "final_c2pa": out_c2pa, **info.meta},
                            data={"source_label": source["label"]})
        ctx.event("success", f"Finished from {source['label']}.", code="finished")

    # Gates and actions

    def kept_images(self, ctx: RunContext) -> list[dict[str, Any]]:
        return [a for a in ctx.artifacts(kind="image") if a["status"] == "ready" and a["verdict"] == "keep"]

    def gate_status(self, ctx: RunContext, step: dict[str, Any]) -> tuple[bool, str]:
        key = step["key"]
        if key == "prompt":
            return (True, "") if ctx.step_data("prompt").get("prompt") else (False, "The prompt is empty.")
        if key == "candidates":
            kept = [a for a in ctx.artifacts(step_key="candidates") if a["status"] == "ready" and a["verdict"] == "keep"]
            return (True, "") if kept else (False, "Keep at least one candidate to iterate on.")
        if key == "iterate":
            return (True, "") if self.kept_images(ctx) else (False, "Keep at least one version to finish.")
        return True, ""

    async def approve(self, ctx: RunContext, step: dict[str, Any], payload: dict[str, Any]) -> None:
        if step["key"] == "prompt" and isinstance(payload.get("prompt"), str):
            prompt = clean_text(payload["prompt"], 3000)
            if not prompt:
                raise ActionError("The prompt is empty.")
            ctx.set_step_data("prompt", prompt=prompt, edited=prompt != ctx.step_data("prompt").get("prompt"))
        if step["key"] == "iterate":
            kept = self.kept_images(ctx)
            if not kept:
                raise ActionError("Keep at least one version to finish.")
            final_id = str(payload.get("final_id") or kept[-1]["id"])
            if final_id not in {a["id"] for a in kept}:
                raise ActionError("Pick one of the kept versions as the final image.")
            title = clean_text(payload.get("title", ctx.brief["title"]), 60)
            label = clean_text(payload.get("label", ctx.brief["visible_label"]), 80)
            ctx.set_step_data("iterate", final_id=final_id, title=title, label=label)

    def _require_open(self, ctx: RunContext, *keys: str) -> str:
        for key in keys:
            if ctx.step(key)["status"] in ("running", "waiting"):
                return key
        raise ActionError("That is not available at this step.")

    def _revision_refs(self, ctx: RunContext, base: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        if payload.get("mode", "edit") == "edit":
            refs.append({"sha": base["media_sha"], "role": "base", "name": base["label"]})
        for item in payload.get("references") or []:
            try:
                ref = Reference.model_validate(item).model_dump()
            except ValidationError as error:
                raise ActionError(_first_error(error)) from error
            if not ctx.media.exists(ref["sha"]):
                raise ActionError("A reference image is missing; upload it again.")
            if ref["sha"] != base["media_sha"]:
                refs.append(ref)
        if len(refs) > 5:
            raise ActionError("Use at most 5 images in one pass (the current version counts as one).")
        return ordered_refs(refs)

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if name == "update_prompt":
            self._require_open(ctx, "prompt")
            prompt = clean_text(payload.get("prompt"), 3000)
            if not prompt:
                raise ActionError("The prompt is empty.")
            ctx.set_step_data("prompt", prompt=prompt, edited=True)
            ctx.event("info", "You edited the prompt.", code="edited")
            return None
        if name == "more_candidates":
            self._require_open(ctx, "candidates")
            count = max(1, min(int(payload.get("count") or 2), 6))
            self._add_candidates(ctx, count)
            ctx.event("info", f"Asked for {count} more candidate(s).", code="more")
            return None
        if name in ("draft_revision", "revise"):
            self._require_open(ctx, "iterate")
            base = ctx.artifact(str(payload.get("artifact_id")))
            if base["kind"] != "image" or base["status"] != "ready":
                raise ActionError("Pick a finished image to revise.")
            note = clean_text(payload.get("note"), 1500)
            refs = self._revision_refs(ctx, base, payload)
            if name == "draft_revision":
                core = await self._rewrite(ctx, base, note, refs)
                return {"prompt": core, "preview": compose(core, refs, ctx.brief["must_not_include"])}
            core = clean_text(payload.get("prompt"), 3000)
            if not core:
                if not note:
                    raise ActionError("Say what should change.")
                core = f"{self._core(base)} Change: {note}"
            prompt = compose(core, refs, ctx.brief["must_not_include"])
            width, height = SIZES[ctx.brief["size"]]
            count = max(1, min(int(payload.get("count") or 1), 3))
            mode = "edit" if payload.get("mode", "edit") == "edit" else "regenerate"
            created = []
            for _ in range(count):
                created.append(ctx.add_artifact(
                    "iterate", "image", grp="versions", label=ctx.next_label("v", grp="versions"), role="image",
                    prompt=prompt, inputs=[ref["sha"] for ref in refs], parent_id=base["id"],
                    params={"width": width, "height": height, "operation": "edits" if refs else "generations",
                            "roles": [ref["role"] for ref in refs], "mode": mode, "note": note, "core": core}))
            labels = ", ".join(a["label"] for a in created)
            ctx.event("info", f"Revising {base['label']} → {labels}" + (f": “{note}”" if note else "."),
                      code="revise")
            return {"created": [a["id"] for a in created]}
        return await super().action(ctx, name, payload)

    @staticmethod
    def _core(base: dict[str, Any]) -> str:
        return base["params"].get("core") or base["prompt"] or ""

    async def _rewrite(self, ctx: RunContext, base: dict[str, Any], note: str, refs: list[dict[str, Any]]) -> str:
        if not note:
            raise ActionError("Say what should change.")
        if not ctx.brief["prompt_helper"]:
            return f"{self._core(base)} Change: {note}"
        request = {
            "current_prompt": self._core(base), "editor_note": note,
            "images": [{"image": index + 1, "role": ref["role"]} for index, ref in enumerate(refs)],
            "must_not_include": ctx.brief["must_not_include"],
        }
        payload, result = await ctx.text_json("text-draft", REVISE_SYSTEM, json.dumps(request, ensure_ascii=False),
                                              purpose="image.revise", context={"note": note})
        core = clean_text(payload.get("prompt") if isinstance(payload, dict) else "", 3000)
        if not core:
            raise ProviderError("The text model returned an empty prompt.", code="bad_output")
        ctx.event("info", f"{result.deployment} rewrote your note into a prompt ({result.seconds:.1f} s).",
                  code="drafted")
        return core

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        images = [a for a in artifacts if a["kind"] == "image" and a["status"] != "superseded"]
        ready = [a for a in images if a["status"] == "ready"]
        kept = [a for a in ready if a["verdict"] == "keep"]
        versions = [a for a in ready if a["grp"] == "versions"]
        final = next((a for a in reversed(artifacts) if a["kind"] == "final" and a["status"] == "ready"), None)
        thumb = (final or {}).get("thumb_sha") or (kept[-1]["thumb_sha"] if kept else None) \
            or next((a["thumb_sha"] for a in ready if a["thumb_sha"]), None)
        outputs = [f"{len(kept)} kept"]
        if versions:
            outputs.append(f"{len(versions)} edit pass{'es' if len(versions) != 1 else ''}")
        blocked = sum(1 for a in images if a["status"] == "blocked")
        if blocked:
            outputs.append(f"{blocked} blocked")
        return {"outputs": " · ".join(outputs), "thumb_sha": thumb, "images": len(ready), "kept": len(kept),
                "versions": len(versions), "blocked": blocked,
                "models": sorted({a["deployment"] for a in artifacts if a["deployment"] and a["status"] == "ready"})}
