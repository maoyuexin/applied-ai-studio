"""Voice pipeline: brief -> script (gate) -> synthesize each line + listen-back (gate) -> mix and label."""

from __future__ import annotations

import difflib
import json
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..providers.base import ProviderError
from .base import ActionError, Pipeline, StepSpec, Template, check, clean_text
from .video import _first_error

if TYPE_CHECKING:
    from ..engine import RunContext

SCRIPT_SYSTEM = """You write short audio scripts for synthetic voices (Microsoft MAI-Voice). Write natural spoken \
language: short sentences, contractions, no stage directions, no sound effects, no emojis, no markdown. Each line \
is one speaker turn of one to three sentences. Use only the speakers given, by name. A speaker's "style" may be \
one value from that speaker's style list, or empty. Write at most target_words words in total and count them: these voices read at about \
150 words per minute, plus a pause between lines. Write in the language of the locale. {disclosure}Return only JSON: \
{{"lines": [{{"speaker": "...", "text": "...", "style": ""}}]}}"""

DISCLOSURE_RULE = "The last line, spoken by the first speaker, says in one short sentence that the voices are \
AI-generated. "

FORMATS = {
    "two-hosts": "a friendly two-host conversation",
    "narration": "a single-narrator explainer",
    "ad-read": "a radio-style ad read",
    "interview": "a short interview (host asks, guest answers)",
}

NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
                "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
                "eighteen": "18", "nineteen": "19", "twenty": "20"}


class Speaker(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    voice: str = Field(min_length=3, max_length=120)
    style: str = Field("", max_length=40)


class VoiceBrief(BaseModel):
    format: Literal["two-hosts", "narration", "ad-read", "interview"] = "two-hosts"
    brief: str = Field(min_length=20, max_length=4000)
    target_seconds: int = Field(45, ge=10, le=300)
    locale: str = Field("en-US", pattern=r"^[a-z]{2,3}-[A-Z]{2}$")
    speakers: list[Speaker] = Field(min_length=1, max_length=4)
    pause_ms: int = Field(350, ge=100, le=2000)
    disclosure: bool = True


class Line(BaseModel):
    id: str
    speaker: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=600)
    style: str = Field("", max_length=40)


ORDINALS = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "5th": "fifth"}


def words(text: str) -> list[str]:
    """Lowercase words with apostrophes unified and numbers in one spelling, so '8'/'eight' and 'we’re'/'we're' match."""
    normalized = text.lower().replace("\u2019", "'").replace("\u2018", "'").replace("-", " ")
    tokens = re.findall(r"[\w']+", normalized)
    return [NUMBER_WORDS.get(ORDINALS.get(token, token), ORDINALS.get(token, token)) for token in tokens]


def listen_back(expected: str, heard: str) -> dict[str, Any]:
    """Compare script words with the transcript; returns word errors and the spans that differ."""
    want, got = words(expected), words(heard)
    matcher = difflib.SequenceMatcher(a=want, b=got, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    diffs = [{"script": " ".join(want[i1:i2]), "heard": " ".join(got[j1:j2])}
             for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    return {"word_errors": max(len(want) - matched, len(got) - matched), "words": len(want), "diffs": diffs[:8]}


class VoicePipeline(Pipeline):
    key = "voice"
    title = "Voice"
    summary = "An LLM writes the script, you cast the voices, MAI-Voice reads each line, and a listen-back " \
              "check flags lines that don't say what the script says."
    roles = ("text-draft", "voice", "listen-back")
    steps = (
        StepSpec("script", "Brief → script", gate=True, role="text-draft",
                 description="Speakers, lines and delivery styles. Edit any line before recording."),
        StepSpec("lines", "Synthesize + listen-back", gate=True, role="voice",
                 description="One call per line, so a bad line can be redone alone. Transcripts are compared "
                             "with the script."),
        StepSpec("mix", "Mix + label", description="Lines joined with pauses, loudness normalized, transcript kept."),
    )
    templates = (
        Template("two-hosts", "Two-host intro", "A short friendly conversation",
                 {"format": "two-hosts", "target_seconds": 45}),
        Template("narration", "Narrated explainer", "One voice explains a topic",
                 {"format": "narration", "target_seconds": 60}),
        Template("ad-read", "Radio ad read", "A 30-second ad",
                 {"format": "ad-read", "target_seconds": 30}),
        Template("interview", "Interview", "Host asks, guest answers",
                 {"format": "interview", "target_seconds": 60}),
    )

    def normalize_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = VoiceBrief.model_validate(brief).model_dump()
        except ValidationError as error:
            raise ActionError(_first_error(error)) from error
        names = [speaker["name"] for speaker in normalized["speakers"]]
        if len(set(names)) != len(names):
            raise ActionError("Speaker names must be different.")
        return normalized

    def estimate(self, brief: dict[str, Any]) -> dict[str, Any]:
        lines = max(2, round(brief["target_seconds"] / 7))
        return {"voice_calls": lines, "listen_back_calls": lines, "text_calls": 1,
                "minutes": round(max(lines * 4 / 60, 0.5), 1),
                "basis": "about one line per 7 seconds of audio; each line is one synthesis call"}

    def lines(self, ctx: RunContext) -> list[dict[str, Any]]:
        return ctx.step_data("script").get("lines", [])

    async def _voice_styles(self, ctx: RunContext) -> dict[str, list[str]]:
        try:
            voices = await ctx.providers.speech.voices() if ctx.providers.speech else []
        except ProviderError:
            voices = []
        return {voice["name"]: voice.get("styles") or [] for voice in voices}

    async def _draft_script(self, ctx: RunContext, feedback: str = "") -> None:
        brief = ctx.brief
        styles = await self._voice_styles(ctx)
        speakers = [{"name": s["name"], "styles": styles.get(s["voice"], [])} for s in brief["speakers"]]
        request: dict[str, Any] = {
            "format": FORMATS[brief["format"]], "brief": brief["brief"], "target_seconds": brief["target_seconds"],
            "target_words": round(brief["target_seconds"] * 2.2), "locale": brief["locale"],
            "speakers": speakers,
        }
        if feedback:
            request["previous_script"] = [{k: line[k] for k in ("speaker", "text", "style")} for line in self.lines(ctx)]
            request["editor_feedback"] = feedback
        system = SCRIPT_SYSTEM.format(disclosure=DISCLOSURE_RULE if brief["disclosure"] else "")
        payload, result = await ctx.text_json(
            "text-draft", system, json.dumps(request, ensure_ascii=False), purpose="voice.script",
            context={"speakers": speakers, "lines": max(2, round(brief["target_seconds"] / 7))})
        lines = self._clean_lines(ctx, payload.get("lines") if isinstance(payload, dict) else None, styles)
        ctx.set_step_data("script", lines=lines, model=result.deployment, seconds=result.seconds,
                          drafts=ctx.step_data("script").get("drafts", 0) + 1, feedback=feedback or None)
        words_total = sum(len(line["text"].split()) for line in lines)
        ctx.event("info", f"{'Redrafted' if feedback else 'Drafted'} {len(lines)} lines ({words_total} words, about "
                          f"{words_total * 60 / 150:.0f} s) with {result.deployment}.", code="drafted")

    def _clean_lines(self, ctx: RunContext, raw: Any, styles: dict[str, list[str]]) -> list[dict[str, Any]]:
        if not isinstance(raw, list) or not raw:
            raise ProviderError("The text model returned no script lines.", code="bad_output")
        speakers = {speaker["name"]: speaker for speaker in ctx.brief["speakers"]}
        first = ctx.brief["speakers"][0]["name"]
        lines = []
        for item in raw[:60]:
            if not isinstance(item, dict):
                continue
            text = clean_text(item.get("text"), 600)
            if not text:
                continue
            speaker = item.get("speaker") if item.get("speaker") in speakers else first
            allowed = styles.get(speakers[speaker]["voice"], [])
            style = item.get("style") if item.get("style") in allowed else ""
            lines.append({"id": f"l{len(lines) + 1}", "speaker": speaker, "text": text, "style": style})
        if not lines:
            raise ProviderError("The script had no usable lines.", code="bad_output")
        return lines

    def _validate_lines(self, ctx: RunContext, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list) or not raw:
            raise ActionError("The script needs at least one line.")
        names = {speaker["name"] for speaker in ctx.brief["speakers"]}
        lines = []
        for index, item in enumerate(raw[:60]):
            try:
                line = Line.model_validate({**item, "id": item.get("id") or f"l{index + 1}"})
            except ValidationError as error:
                raise ActionError(f"Line {index + 1}: {_first_error(error)}") from error
            if line.speaker not in names:
                raise ActionError(f"Line {index + 1}: unknown speaker '{line.speaker}'.")
            lines.append(line.model_dump())
        ids = [line["id"] for line in lines]
        if len(set(ids)) != len(ids):
            raise ActionError("Line ids must be unique.")
        return lines

    # Execution

    async def start_step(self, ctx: RunContext, step: dict[str, Any]) -> None:
        key = step["key"]
        if key == "script":
            if not self.lines(ctx):
                await self._draft_script(ctx)
        elif key == "lines":
            existing = {a["grp"] for a in ctx.artifacts(step_key="lines")}
            for line in self.lines(ctx):
                if line["id"] not in existing:
                    self._add_line(ctx, line)
        elif key == "mix":
            kept = self._kept_lines(ctx)
            ctx.add_artifact("mix", "final", label="mix", role="tool", inputs=[a["media_sha"] for a in kept],
                             params={"line_ids": [a["id"] for a in kept], "pause_ms": ctx.brief["pause_ms"]})

    def _add_line(self, ctx: RunContext, line: dict[str, Any], *, parent_id: str | None = None,
                  voice: str | None = None) -> dict[str, Any]:
        ctx.require("voice")
        speaker = next(s for s in ctx.brief["speakers"] if s["name"] == line["speaker"])
        number = line["id"][1:]
        return ctx.add_artifact(
            "lines", "line", grp=line["id"], label=ctx.next_label(f"line {number}.", "lines", line["id"]),
            role="voice", prompt=line["text"], parent_id=parent_id,
            params={"voice": voice or speaker["voice"], "style": line.get("style") or speaker.get("style") or "",
                    "speaker": line["speaker"], "locale": ctx.brief["locale"]})

    def _kept_lines(self, ctx: RunContext) -> list[dict[str, Any]]:
        kept = []
        for line in self.lines(ctx):
            take = next((a for a in reversed(ctx.artifacts(step_key="lines", grp=line["id"]))
                         if a["status"] == "ready" and a["verdict"] == "keep"), None)
            if take is None:
                raise ActionError(f"Line {line['id'][1:]} has no kept recording.")
            kept.append(take)
        return kept

    async def run_artifact(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        if artifact["kind"] == "line":
            await self._run_line(ctx, artifact)
        elif artifact["kind"] == "final":
            await self._run_mix(ctx, artifact)

    async def _run_line(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        ctx.require("voice")
        params = artifact["params"]
        ctx.reserve("voice")
        started = time.perf_counter()
        try:
            audio = await ctx.providers.speech.synthesize(artifact["prompt"], params["voice"], locale=params["locale"],
                                                          style=params.get("style") or None)
        except ProviderError:
            ctx.store.release("voice", 1)
            raise
        seconds = round(time.perf_counter() - started, 1)
        info = ctx.save_media(audio, "audio/mpeg")
        path = ctx.media_path(info.sha)
        duration = await ctx.tools.audio_duration(path)
        loudness = await ctx.tools.loudness(path)
        metrics: dict[str, Any] = {"duration": duration, **loudness}
        checks = []
        if ctx.providers.ready("listen-back"):
            try:
                ctx.reserve("listen-back")
                with tempfile.TemporaryDirectory(dir=ctx.media.tmp) as folder:
                    wav = Path(folder) / "line.wav"
                    await ctx.tools.to_wav16k(path, wav)
                    heard = await ctx.providers.speech.transcribe(wav.read_bytes(), locale=params["locale"],
                                                                  expected=artifact["prompt"])
                result = listen_back(artifact["prompt"], heard.get("text") or "")
                metrics.update(transcript=heard.get("text"), confidence=heard.get("confidence"), **result)
                errors = result["word_errors"]
                checks.append(check("listen-back", "Listen-back: matches the script" if errors == 0 else
                                    f"Listen-back: {errors} word difference{'s' if errors != 1 else ''}",
                                    "ok" if errors == 0 else ("warn" if errors <= 2 else "bad"),
                                    "speech-to-text transcript compared with the script, word by word"))
            except ProviderError as error:
                checks.append(check("listen-back", "Listen-back: not run", "info", str(error)))
        else:
            checks.append(check("listen-back", "Listen-back: not configured", "info", "no speech-to-text role"))
        if (loudness.get("silent_gaps") or 0) > 0:
            checks.append(check("silence", f"{loudness['silent_gaps']} silent gap(s) over 0.8 s", "warn",
                                "ffmpeg silencedetect"))
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="audio/mpeg",
                            gen_seconds=seconds, metrics=metrics, checks=checks)
        self._auto_keep(ctx, ctx.artifact(artifact["id"]))

    def _auto_keep(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        siblings = [a for a in ctx.artifacts(step_key="lines", grp=artifact["grp"]) if a["id"] != artifact["id"]]
        kept = [a for a in siblings if a["verdict"] == "keep"]
        if not kept or any(a["id"] == artifact["parent_id"] for a in kept):
            for sibling in kept:
                ctx.update_artifact(sibling["id"], verdict=None, quiet=True)
            ctx.update_artifact(artifact["id"], verdict="keep")

    async def _run_mix(self, ctx: RunContext, artifact: dict[str, Any]) -> None:
        lines = [ctx.artifact(line_id) for line_id in artifact["params"]["line_ids"]]
        with tempfile.TemporaryDirectory(dir=ctx.media.tmp) as folder:
            out = Path(folder) / "mix.mp3"
            result = await ctx.tools.concat_audio([ctx.media_path(line["media_sha"]) for line in lines], out,
                                                  pause_ms=artifact["params"]["pause_ms"])
            info = ctx.media.put_file(out, "audio/mpeg", {"duration": result["duration"]})
        transcript = [{"speaker": line["params"]["speaker"], "text": line["prompt"]} for line in lines]
        errors = sum(int(line["metrics"].get("word_errors") or 0) for line in lines)
        checked = sum(1 for line in lines if "word_errors" in line["metrics"])
        disclosure = bool(re.search(r"\b(ai|artificial|generad|synthetic|IA)\b", lines[-1]["prompt"], re.I))
        checks = [
            check("loudness", "Loudness normalized to -16 LUFS", "ok", "ffmpeg loudnorm"),
            check("listen-back", f"Listen-back: {errors} word difference(s) across {checked} checked lines"
                  if checked else "Listen-back: not run", "ok" if checked and errors == 0 else "info",
                  "per-line transcripts"),
            check("disclosure", "Spoken AI disclosure in the last line" if disclosure else
                  "No spoken AI disclosure found in the last line", "ok" if disclosure else "warn",
                  "keyword check on the script"),
        ]
        ctx.update_artifact(artifact["id"], status="ready", media_sha=info.sha, media_type="audio/mpeg",
                            metrics={**result, "word_errors": errors}, checks=checks,
                            data={"transcript": transcript, "voices": sorted({line["params"]["voice"] for line in lines})})
        ctx.event("success", f"Mixed {len(lines)} lines into {result['duration']:.0f} s of audio.", code="mixed")

    # Gates and actions

    def gate_status(self, ctx: RunContext, step: dict[str, Any]) -> tuple[bool, str]:
        if step["key"] == "script":
            return (True, "") if self.lines(ctx) else (False, "There is no script yet.")
        if step["key"] == "lines":
            for line in self.lines(ctx):
                if not any(a["status"] == "ready" and a["verdict"] == "keep"
                           for a in ctx.artifacts(step_key="lines", grp=line["id"])):
                    return False, f"Line {line['id'][1:]} needs a kept recording."
        return True, ""

    async def approve(self, ctx: RunContext, step: dict[str, Any], payload: dict[str, Any]) -> None:
        if step["key"] == "script" and "lines" in payload:
            ctx.set_step_data("script", lines=self._validate_lines(ctx, payload["lines"]), edited=True)

    def on_decision(self, ctx: RunContext, artifact: dict[str, Any], verdict: str | None) -> None:
        if verdict != "keep":
            return
        for sibling in ctx.artifacts(step_key=artifact["step_key"], grp=artifact["grp"]):
            if sibling["id"] != artifact["id"] and sibling["verdict"] == "keep":
                ctx.update_artifact(sibling["id"], verdict=None, quiet=True)

    async def action(self, ctx: RunContext, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if name == "update_script":
            if ctx.step("script")["status"] not in ("running", "waiting"):
                raise ActionError("The script is approved. Reopen it to edit.")
            ctx.set_step_data("script", lines=self._validate_lines(ctx, payload.get("lines")), edited=True)
            ctx.event("info", "You edited the script.", code="edited")
        elif name == "redraft_script":
            if ctx.step("script")["status"] not in ("running", "waiting"):
                raise ActionError("The script is approved. Reopen it to redraft.")
            note = clean_text(payload.get("note"), 1000)
            if not note:
                raise ActionError("Say what should change in the script.")
            await self._draft_script(ctx, note)
        elif name == "regenerate_line":
            if ctx.step("lines")["status"] not in ("running", "waiting"):
                raise ActionError("Recording is not open.")
            line_id = str(payload.get("line_id"))
            lines = self.lines(ctx)
            line = next((item for item in lines if item["id"] == line_id), None)
            if line is None:
                raise ActionError("Unknown line.")
            text = clean_text(payload.get("text"), 600) or line["text"]
            style = payload.get("style", line.get("style", ""))
            updated = {**line, "text": text, "style": clean_text(style, 40)}
            if updated != line:
                ctx.set_step_data("script", lines=[updated if item["id"] == line_id else item for item in lines])
            previous = ctx.artifacts(step_key="lines", grp=line_id)
            self._add_line(ctx, updated, parent_id=previous[-1]["id"] if previous else None,
                           voice=clean_text(payload.get("voice"), 120) or None)
            ctx.event("info", f"Re-recording line {line_id[1:]}.", code="retry")
        else:
            return await super().action(ctx, name, payload)
        return None

    def summarize(self, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        lines = [a for a in artifacts if a["kind"] == "line" and a["status"] == "ready"]
        final = next((a for a in reversed(artifacts) if a["kind"] == "final" and a["status"] == "ready"), None)
        outputs = []
        if final:
            outputs.append(f"{final['metrics'].get('duration', 0):.0f} s MP3")
            outputs.append(f"{final['metrics'].get('word_errors', 0)} word errors")
        else:
            outputs.append(f"{len(lines)} lines recorded")
        return {"outputs": " · ".join(outputs), "thumb_sha": None, "lines": len(lines),
                "audio_seconds": round(sum(a["metrics"].get("duration") or 0 for a in lines), 1),
                "final_duration": (final or {}).get("metrics", {}).get("duration"),
                "models": sorted({a["deployment"] for a in artifacts if a["deployment"] and a["status"] == "ready"})}
