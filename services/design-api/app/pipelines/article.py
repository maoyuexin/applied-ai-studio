"""Article pipeline: brief + sources -> outline (gate) -> drafts with a fact check, revised with notes (gate) -> label."""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..providers.base import ProviderError
from .base import ActionError, Pipeline, StepSpec, Template, check, clean_text
from .video import _first_error

if TYPE_CHECKING:
    from ..engine import RunContext

FORMATS = {
    "news-summary": "a short newsroom summary of a release",
    "report": "a structured report with short sections",
    "explainer": "a plain-language explainer",
    "blog": "a blog post",
    "press-release": "a press release",
}

OUTLINE_SYSTEM = """You are an editor planning {format}. From the brief and the numbered sources, write a \
headline and 3 to 7 outline points in the order the piece should follow. Each point cites the source ids it \
relies on. Use only facts stated in the sources. Return only JSON: \
{{"headline": "...", "points": [{{"text": "...", "sources": [1]}}]}}"""

DRAFT_SYSTEM = """You write {format} for {audience}. Write the body from the approved outline using only facts \
stated in the sources. Keep names, numbers and dates exactly as the sources state them; when a source says \
"this year" or "next month", resolve it from that source's publication date or leave it relative. Do not add \
background the sources don't give. About {words} words, short paragraphs, markdown allowed (no headline in the \
body). Tone: {tone}. {rules}Return only JSON: {{"headline": "...", "body": "..."}}"""

REVISE_SYSTEM = """You revise {format} for {audience}. Apply the editor's note and fix every claim the fact \
check marked unsupported or partly supported, using only facts in the sources. Keep everything else as close \
to the previous version as possible. About {words} words. Tone: {tone}. {rules}Return only JSON: \
{{"headline": "...", "body": "..."}}"""

CRITIQUE_SYSTEM = """You are a fact checker. Split the draft (headline and body) into its factual claims, each a \
short sentence. For each claim decide whether the numbered sources support it: "supported" (stated or directly \
implied), "partly" (some detail missing from or different in the sources), or "unsupported" (not in the \
sources, or contradicted). Quote the shortest source evidence, or leave it empty. Judge dates against each \
source's publication date. Return only JSON: {"claims": [{"claim": "...", "verdict": \
"supported|partly|unsupported", "evidence": "...", "source": 1, "note": "short reason"}]}"""


class Source(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=40, max_length=30_000)
    url: str = Field("", max_length=500)
    published: str = Field("", max_length=40)


class ArticleBrief(BaseModel):
    format: Literal["news-summary", "report", "explainer", "blog", "press-release"] = "news-summary"
    brief: str = Field(min_length=10, max_length=4000)
    audience: str = Field("general readers", max_length=200)
    tone: str = Field("clear, neutral, specific", max_length=200)
    target_words: int = Field(250, ge=50, le=1500)
    sources: list[Source] = Field(min_length=1, max_length=8)
    must_not_include: str = Field("", max_length=600)
    fact_check: bool = True
    visible_label: str = Field("AI-assisted draft, reviewed by an editor.", max_length=120)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text))


def sources_block(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": index + 1, "title": source["title"], "published": source["published"], "url": source["url"],
             "text": source["text"]} for index, source in enumerate(sources)]


class ArticlePipeline(Pipeline):
    key = "article"
    title = "Article"
    summary = "Brief and sources to an outline you approve, then drafts that a second model fact-checks against " \
              "the sources. Revise with notes until it's right; every version is kept."
    roles = ("text-draft", "text-judge")
    steps = (
        StepSpec("outline", "Brief + sources → outline", gate=True, role="text-draft",
                 description="Headline and points, each tied to a source. Edit or redraft before any writing."),
        StepSpec("draft", "Draft → check → revise", gate=True, role="text-draft",
                 description="Each version is fact-checked by a second model. Revise with a note or edit it yourself."),
        StepSpec("finish", "Approve + label", description="The approved version with its disclosure label and claim report."),
    )
    templates = (
        Template("news-summary", "Newsroom summary", "A short summary of a release for readers", {"format": "news-summary", "target_words": 150}),
        Template("report", "Report", "Structured report with short sections", {"format": "report", "target_words": 600}),
        Template("explainer", "Explainer", "Plain-language explainer", {"format": "explainer", "target_words": 400}),
        Template("blog", "Blog post", "A blog post", {"format": "blog", "target_words": 500}),
        Template("press-release", "Press release", "A press release", {"format": "press-release", "target_words": 350}),
    )

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = ArticleBrief.model_validate(brief).model_dump()
        except ValidationError as error:
            raise ActionError(_first_error(error)) from error
        if sum(len(source["text"]) for source in normalized["sources"]) > 60_000:
            raise ActionError("Sources are too long together (60,000 characters at most).")
        return normalized

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        return {"text_calls": 2 + (1 if brief["fact_check"] else 0), "minutes": 1,
                "basis": "one outline call, one draft call and one fact-check call per version"}

    def default_title(self, brief: dict[str, Any]) -> str:
        return brief["sources"][0]["title"][:80] if brief.get("sources") else super().default_title(brief)

    def _ctx_text(self, ctx: RunContext) -> dict[str, str]:
        brief = ctx.brief
        rules = f"Never include: {brief['must_not_include']}. " if brief["must_not_include"].strip() else ""
        return {"format": FORMATS[brief["format"]], "audience": brief["audience"], "tone": brief["tone"],
                "words": str(brief["target_words"]), "rules": rules}

    # Outline

    async def _draft_outline(self, ctx: RunContext, feedback: str = "") -> None:
        brief = ctx.brief
        request: dict[str, Any] = {"brief": brief["brief"], "audience": brief["audience"],
                                   "target_words": brief["target_words"], "sources": sources_block(brief["sources"])}
        if feedback:
            current = ctx.step_data("outline")
            request["previous_outline"] = {"headline": current.get("headline"), "points": current.get("points")}
            request["editor_feedback"] = feedback
        payload, result = await ctx.text_json(
            "text-draft", OUTLINE_SYSTEM.format(format=FORMATS[brief["format"]]),
            json.dumps(request, ensure_ascii=False), purpose="article.outline", context={"sources": len(brief["sources"])})
        headline, points = self._clean_outline(payload, len(brief["sources"]))
        data = ctx.step_data("outline")
        ctx.set_step_data("outline", headline=headline, points=points, model=result.deployment, seconds=result.seconds,
                          drafts=data.get("drafts", 0) + 1, feedback=feedback or None)
        ctx.event("info", f"{'Redrafted' if feedback else 'Drafted'} the outline ({len(points)} points) with "
                          f"{result.deployment} in {result.seconds:.1f} s.", code="drafted")

    @staticmethod
    def _clean_outline(payload: Any, source_count: int) -> tuple[str, list[dict[str, Any]]]:
        if not isinstance(payload, dict):
            raise ProviderError("The text model returned no outline.", code="bad_output")
        headline = clean_text(payload.get("headline"), 200)
        points = []
        for item in payload.get("points") or []:
            if isinstance(item, dict) and clean_text(item.get("text"), 600):
                ids = [int(i) for i in item.get("sources") or [] if str(i).isdigit() and 1 <= int(i) <= source_count]
                points.append({"text": clean_text(item.get("text"), 600), "sources": sorted(set(ids))})
        if not headline or not points:
            raise ProviderError("The outline was empty.", code="bad_output")
        return headline, points[:10]

    # Execution

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        key = step["key"]
        if key == "outline":
            if not ctx.step_data("outline").get("points"):
                await self._draft_outline(ctx)
        elif key == "draft":
            if not ctx.artifacts(step_key="draft"):
                ctx.require("text-draft")
                ctx.add_artifact("draft", "version", grp="versions", label="v1", role="text-draft",
                                 params={"mode": "draft"})
        elif key == "finish":
            version = ctx.artifact(ctx.step_data("draft")["final_id"])
            ctx.add_artifact("finish", "final", label="final", role="tool", parent_id=version["id"],
                             params={"label": ctx.brief["visible_label"]})

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        if artifact["kind"] == "version":
            await self._run_version(ctx, artifact)
        elif artifact["kind"] == "final":
            await self._run_finish(ctx, artifact)

    async def _run_version(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        brief = ctx.brief
        params = artifact["params"]
        data = dict(artifact["data"])
        started = time.perf_counter()
        if params.get("mode") in ("draft", "revise") and not data.get("body"):
            outline = ctx.step_data("outline")
            words = self._ctx_text(ctx)
            request: dict[str, Any] = {"brief": brief["brief"], "headline": outline["headline"],
                                       "outline": outline["points"], "sources": sources_block(brief["sources"])}
            system = DRAFT_SYSTEM.format(**words)
            purpose = "article.draft"
            if params.get("mode") == "revise":
                base = ctx.artifact(artifact["parent_id"])
                request.update(previous_headline=base["data"].get("headline"), previous_body=base["data"].get("body"),
                               editor_note=params.get("note") or "",
                               fact_check=[c for c in base["data"].get("claims", []) if c.get("verdict") != "supported"])
                system = REVISE_SYSTEM.format(**words)
                purpose = "article.revise"
            payload, result = await ctx.text_json("text-draft", system, json.dumps(request, ensure_ascii=False),
                                                  purpose=purpose, context={"note": params.get("note")})
            headline = clean_text(payload.get("headline") if isinstance(payload, dict) else "", 200)
            body = str(payload.get("body") or "").strip() if isinstance(payload, dict) else ""
            if not body:
                raise ProviderError("The text model returned an empty draft.", code="bad_output")
            data.update(headline=headline or outline["headline"], body=body[:20_000], author=result.deployment,
                        write_seconds=result.seconds)
            ctx.update_artifact(artifact["id"], data=data, prompt=system, quiet=True)
        checks = self._static_checks(ctx, data)
        claims: list[dict[str, Any]] = []
        if brief["fact_check"]:
            claims = await self._critique(ctx, data)
            data["claims"] = claims
            data["judge"] = ctx.deployment("text-judge")
            counts = {verdict: sum(1 for c in claims if c["verdict"] == verdict)
                      for verdict in ("supported", "partly", "unsupported")}
            state = "bad" if counts["unsupported"] else ("warn" if counts["partly"] else "ok")
            checks.insert(0, check("claims", f"Claims: {counts['supported']} supported · {counts['partly']} partly · "
                                             f"{counts['unsupported']} unsupported", state,
                                   f"{data['judge']} compared each claim with the sources; it flags, you decide"))
        metrics = {"words": word_count(data.get("body", "")),
                   "unsupported": sum(1 for c in claims if c["verdict"] == "unsupported"),
                   "partly": sum(1 for c in claims if c["verdict"] == "partly"), "claims": len(claims)}
        ctx.update_artifact(artifact["id"], status="ready", data=data, checks=checks, metrics=metrics,
                            gen_seconds=round(time.perf_counter() - started, 1))
        ctx.event("success", f"{artifact['label']} ready · {metrics['words']} words"
                             + (f" · {metrics['unsupported']} unsupported claim(s)" if claims else ""), code="text_done")

    def _static_checks(self, ctx: RunContext, data: dict[str, Any]) -> list[dict[str, str]]:
        brief = ctx.brief
        words = word_count(data.get("body", ""))
        target = brief["target_words"]
        checks = [check("length", f"{words} words (target {target})",
                        "ok" if abs(words - target) <= target * 0.25 else "warn", "word count")]
        banned = [item.strip() for item in re.split(r"[,;·]", brief["must_not_include"]) if item.strip()]
        text = f"{data.get('headline', '')} {data.get('body', '')}".lower()
        hits = [item for item in banned if item.lower() in text]
        if banned:
            checks.append(check("rules", "Must-not-include: none found" if not hits else f"Must-not-include found: {', '.join(hits)}",
                                "ok" if not hits else "bad", "exact phrase search"))
        return checks

    async def _critique(self, ctx: RunContext, data: dict[str, Any]) -> list[dict[str, Any]]:
        request = {"sources": sources_block(ctx.brief["sources"]),
                   "draft": {"headline": data.get("headline"), "body": data.get("body")}}
        payload, result = await ctx.text_json("text-judge", CRITIQUE_SYSTEM, json.dumps(request, ensure_ascii=False),
                                              purpose="article.critique", context={"body": data.get("body")})
        claims = []
        for item in (payload.get("claims") if isinstance(payload, dict) else None) or []:
            if not isinstance(item, dict) or not clean_text(item.get("claim"), 400):
                continue
            verdict = item.get("verdict") if item.get("verdict") in ("supported", "partly", "unsupported") else "partly"
            source = item.get("source")
            claims.append({"claim": clean_text(item.get("claim"), 400), "verdict": verdict,
                           "evidence": clean_text(item.get("evidence"), 400), "note": clean_text(item.get("note"), 300),
                           "source": int(source) if str(source).isdigit() else None})
        data["judge_seconds"] = result.seconds
        return claims[:40]

    async def _run_finish(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        version = ctx.artifact(artifact["parent_id"])
        label = artifact["params"].get("label", "")
        body = version["data"].get("body", "")
        headline = version["data"].get("headline", "")
        markdown = f"# {headline}\n\n{body}\n\n---\n*{label}*\n" if label else f"# {headline}\n\n{body}\n"
        sources = "\n".join(f"{i + 1}. {s['title']}{' — ' + s['url'] if s['url'] else ''}"
                            for i, s in enumerate(ctx.brief["sources"]))
        markdown += f"\nSources:\n{sources}\n"
        info = ctx.save_media(markdown.encode(), "text/markdown; charset=utf-8")
        unsupported = version["metrics"].get("unsupported", 0)
        checks = [check("label", f"Label: “{label}”" if label else "No disclosure label", "ok" if label else "warn",
                        "appended to the text"),
                  check("approved", f"Approved by you: {version['label']}", "ok", "human sign-off is recorded"),
                  *[c for c in version["checks"] if c["key"] in ("claims", "rules", "length")]]
        if unsupported:
            checks.append(check("signoff", f"Approved with {unsupported} unsupported claim(s) still flagged", "warn",
                                "your decision is on record"))
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="text/markdown",
                            data={"headline": headline, "body": body, "label": label, "markdown": markdown,
                                  "source_label": version["label"]},
                            metrics=version["metrics"], checks=checks)
        ctx.event("success", f"Approved {version['label']} with its label.", code="finished")

    # Gates and actions

    def gate_status(self, ctx: RunContext, step: dict[str, Any]) -> tuple[bool, str]:
        if step["key"] == "outline":
            return (True, "") if ctx.step_data("outline").get("points") else (False, "There is no outline yet.")
        if step["key"] == "draft":
            ready = [a for a in ctx.artifacts(step_key="draft") if a["status"] == "ready"]
            return (True, "") if ready else (False, "Wait for a finished version.")
        return True, ""

    async def approve(self, ctx: RunContext, step: dict[str, Any], payload: dict[str, Any]) -> None:
        if step["key"] == "outline" and ("points" in payload or "headline" in payload):
            self._save_outline(ctx, payload)
        if step["key"] == "draft":
            ready = [a for a in ctx.artifacts(step_key="draft") if a["status"] == "ready"]
            if not ready:
                raise ActionError("Wait for a finished version.")
            chosen = str(payload.get("version_id") or ready[-1]["id"])
            if chosen not in {a["id"] for a in ready}:
                raise ActionError("Pick a finished version to approve.")
            ctx.set_step_data("draft", final_id=chosen)
            ctx.store.update_artifact(chosen, verdict="keep")

    def _save_outline(self, ctx: RunContext, payload: dict[str, Any]) -> None:
        headline = clean_text(payload.get("headline", ctx.step_data("outline").get("headline")), 200)
        points = []
        for item in payload.get("points") or ctx.step_data("outline").get("points", []):
            text = clean_text(item.get("text") if isinstance(item, dict) else item, 600)
            if text:
                points.append({"text": text, "sources": [int(i) for i in (item.get("sources") if isinstance(item, dict) else []) or []
                                                         if str(i).isdigit()]})
        if not headline or not points:
            raise ActionError("The outline needs a headline and at least one point.")
        ctx.set_step_data("outline", headline=headline, points=points[:12], edited=True)

    def _open(self, ctx: RunContext, key: str) -> None:
        if ctx.step(key)["status"] not in ("running", "waiting"):
            raise ActionError(f"'{ctx.step(key)['title']}' is not open. Reopen it first.")

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if name == "update_outline":
            self._open(ctx, "outline")
            self._save_outline(ctx, payload)
            ctx.event("info", "You edited the outline.", code="edited")
        elif name == "redraft_outline":
            self._open(ctx, "outline")
            note = clean_text(payload.get("note"), 1000)
            if not note:
                raise ActionError("Say what should change in the outline.")
            await self._draft_outline(ctx, note)
        elif name in ("revise", "save_edit"):
            self._open(ctx, "draft")
            versions = ctx.artifacts(step_key="draft")
            base_id = str(payload.get("base_id") or (versions[-1]["id"] if versions else ""))
            base = ctx.artifact(base_id)
            if base["status"] != "ready":
                raise ActionError("Pick a finished version to start from.")
            label = ctx.next_label("v", "draft", "versions")
            if name == "revise":
                note = clean_text(payload.get("note"), 1500)
                if not note and not base["metrics"].get("unsupported") and not base["metrics"].get("partly"):
                    raise ActionError("Say what should change (or wait for the fact check to flag something).")
                ctx.require("text-draft")
                created = ctx.add_artifact("draft", "version", grp="versions", label=label, role="text-draft",
                                           parent_id=base["id"], params={"mode": "revise", "note": note})
                ctx.event("info", f"Revising {base['label']} → {label}" + (f": “{note}”" if note else " (fix flagged claims)."),
                          code="revise")
            else:
                body = str(payload.get("body") or "").strip()
                headline = clean_text(payload.get("headline", base["data"].get("headline")), 200)
                if not body:
                    raise ActionError("The text is empty.")
                created = ctx.add_artifact("draft", "version", grp="versions", label=label, role="text-judge",
                                           parent_id=base["id"], params={"mode": "manual", "note": "edited by you"},
                                           data={"headline": headline, "body": body[:20_000], "author": "you"})
                ctx.event("info", f"You edited {base['label']} → {label}; checking it now.", code="edited")
            return {"created": created["id"]}
        else:
            return await super().action(ctx, name, payload)
        return None

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        versions = [a for a in artifacts if a["kind"] == "version" and a["status"] == "ready"]
        final = next((a for a in reversed(artifacts) if a["kind"] == "final" and a["status"] == "ready"), None)
        outputs = [f"{len(versions)} version{'s' if len(versions) != 1 else ''}"]
        if versions:
            first, last = versions[0]["metrics"], (final or versions[-1])["metrics"]
            outputs.append(f"{last.get('words', 0)} words")
            if first.get("claims") is not None and last.get("claims"):
                fixed = max(first.get("unsupported", 0) - last.get("unsupported", 0), 0)
                outputs.append(f"{last.get('unsupported', 0)} unsupported" + (f" ({fixed} fixed)" if fixed else ""))
        return {"outputs": " · ".join(outputs), "thumb_sha": None, "versions": len(versions),
                "models": sorted({a["deployment"] for a in artifacts if a["deployment"] and a["status"] == "ready"}
                                 | {a["data"]["judge"] for a in versions if a["data"].get("judge")})}
