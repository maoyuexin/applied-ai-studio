"""Deterministic offline providers for tests and dry runs. Never used when provider_mode=live.

Markers in prompts let tests reproduce real vendor behavior:
  [blocked]  -> content filter       [busy] -> "too many running tasks" once
  [fail]     -> the video job fails after it starts
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .base import ProviderError
from .live import TextResult

FAKE_VOICES = [
    {"name": "en-US-Harper:MAI-Voice-2.1-Flash", "display": "Harper", "locale": "en-US", "gender": "Female",
     "styles": ["cheerful", "excited", "happy", "softvoice"]},
    {"name": "en-US-Ethan:MAI-Voice-2.1-Flash", "display": "Ethan", "locale": "en-US", "gender": "Male",
     "styles": ["excited", "happy", "determined"]},
    {"name": "en-US-Grant:MAI-Voice-2.1-Flash", "display": "Grant", "locale": "en-US", "gender": "Male", "styles": []},
    {"name": "es-MX-Harper:MAI-Voice-2.1-Flash", "display": "Harper", "locale": "es-MX", "gender": "Female",
     "styles": []},
]


def _color(seed: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(seed.encode()).digest()
    return digest[0], digest[1], digest[2]


class FakeText:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    async def complete(self, deployment: str, system: str, user: str, *, json_mode: bool = True,
                       max_tokens: int = 6000, purpose: str = "", context: dict[str, Any] | None = None) -> TextResult:
        del system, json_mode, max_tokens
        ctx = context or {}
        self.calls.append({"purpose": purpose, "context": ctx})
        if "[blocked]" in user:
            raise ProviderError("The text model's content filter stopped the answer.", code="content_filter")
        await asyncio.sleep(self.delay)
        if purpose == "video.shotlist":
            count, seconds = int(ctx.get("shots", 3)), int(ctx.get("seconds", 4))
            shots = []
            for index in range(count):
                product = ctx.get("has_reference", False) and index % 2 == 0
                shots.append({
                    "title": f"Shot {index + 1}", "subject": "product" if product else "people",
                    "mode": "i2v" if product else "t2v", "seconds": seconds,
                    "keyframe_prompt": "Place the exact product from image 1 in a bright studio." if product else "",
                    "prompt": f"Shot {index + 1}: the camera moves smoothly while the scene unfolds.",
                    "sound": "Soft music", "on_screen_text": "",
                })
            payload: dict[str, Any] = {"shots": shots, "notes": "Fake shot list."}
        elif purpose in ("image.prompt", "image.revise"):
            payload = {"prompt": f"[{purpose}] {ctx.get('brief') or ctx.get('note') or 'image'}"}
        elif purpose == "voice.script":
            speakers = ctx.get("speakers") or [{"name": "Host A"}]
            payload = {"lines": [
                {"speaker": speakers[index % len(speakers)]["name"], "text": f"This is line {index + 1}.", "style": ""}
                for index in range(int(ctx.get("lines", 4)))]}
        elif purpose == "article.outline":
            payload = {"headline": "Fake headline", "points": [
                {"text": f"Point {index + 1} from the source.", "sources": [1]} for index in range(3)]}
        elif purpose in ("article.draft", "article.revise"):
            note = ctx.get("note") or ""
            body = "The agency announced a plan. The first flight could happen in December 2024."
            if purpose == "article.revise":
                body = "The agency announced a plan. The first flight could happen in December 2026." + (
                    f" ({note})" if note else "")
            payload = {"headline": "Fake headline", "body": body}
        elif purpose == "article.critique":
            body = str(ctx.get("body") or "")
            payload = {"claims": [
                {"claim": "The agency announced a plan.", "verdict": "supported", "evidence": "announced a plan",
                 "source": 1, "note": ""},
                {"claim": "The first flight could happen in December.",
                 "verdict": "unsupported" if "2024" in body else "supported",
                 "evidence": "December of this year", "source": 1, "note": "year"}]}
        elif purpose == "alerts.draft":
            # Models named *mini* invent a shelter (a watch term and a number not in the facts) and drop the
            # disclosure in the second language.
            invent = "mini" in deployment
            level = (re.findall(r"\d+\.\d+", str(ctx.get("facts", ""))) or ["1.0"])[0]
            alert, answer = {}, {}
            for index, lang in enumerate(ctx.get("languages", [])):
                disclosure = "" if invent and index == 1 else f" {lang['disclosure']}"
                extra = " Shelter open at 99 Main." if invent else ""
                alert[lang["code"]] = f"[{lang['code']}] River at {level} ft and rising.{extra}{disclosure}"
                answer[lang["code"]] = f"[{lang['code']}] The facts do not say. Call 311."
            payload = {"alert": alert, **({"answer": answer} if ctx.get("question") else {})}
        elif purpose == "alerts.check":
            messages = ctx.get("messages") or {}
            back, issues = {}, {}
            for lang in ctx.get("languages", []):
                code = lang["code"]
                back[code] = {part: str((texts or {}).get(code, "")).replace(f"[{code}]", "[en]")
                              for part, texts in messages.items()}
                if "Shelter" in str((messages.get("alert") or {}).get(code, "")):
                    issues[code] = [{"part": "alert", "text": "Mentions a shelter the facts do not give."}]
            payload = {"back": back, "issues": issues}
        else:
            payload = {"text": "ok"}
        return TextResult(json.dumps(payload), self.delay, deployment, {"total_tokens": 0})

    async def complete_vision(self, deployment: str, system: str, user: str, images: list[tuple[bytes, str]], *,
                              json_mode: bool = True, max_tokens: int = 2000, purpose: str = "",
                              context: dict[str, Any] | None = None) -> TextResult:
        """Answers depend on markers in the image name: [fog] (only models named *mini* answer firmly),
        [person], [plate] (*mini* reads it), [flip] (try 2 answers differently), [fail], [blocked]."""
        del system, json_mode, max_tokens
        ctx = context or {}
        self.calls.append({"purpose": purpose, "context": ctx, "images": len(images)})
        name, attempt = str(ctx.get("image", "")), int(ctx.get("try", 1))
        if "[blocked]" in user or "[blocked]" in name:
            raise ProviderError("The model's content filter stopped the answer.", code="content_filter")
        if "[fail]" in name:
            raise ProviderError("Could not reach Text model: ConnectError.", code="network", retryable=True)
        await asyncio.sleep(self.delay)
        if purpose == "inspect.live":
            return TextResult(f"Live answer about {name}.", self.delay, deployment, {"total_tokens": 0})
        firm = "mini" in deployment
        answers: dict[str, str] = {}
        for question in ctx.get("questions", []):
            kind, choices = question.get("kind"), question.get("choices") or ["yes", "no", "cannot tell"]
            unsure = "[fog]" in name and not firm
            if question.get("expect") == "decline":
                answers[question["key"]] = "ABC 1234" if "[plate]" in name and firm else "cannot tell"
            elif kind == "open":
                answers[question["key"]] = "A man in a dark jacket is wading." if "[person]" in name else "no person"
            elif kind == "count":
                answers[question["key"]] = "cannot tell" if unsure else "1"
            else:
                pick = choices[1] if "[flip]" in name and attempt == 2 else choices[0]
                answers[question["key"]] = "cannot tell" if unsure and "cannot tell" in choices else pick
        return TextResult(json.dumps(answers), self.delay, deployment, {"total_tokens": 0})


class FakeImage:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    async def generate(self, prompt: str, width: int, height: int) -> bytes:
        return await self._render("generate", prompt, width, height, 0)

    async def edit(self, prompt: str, images: list[bytes], width: int, height: int) -> bytes:
        return await self._render("edit", prompt, width, height, len(images))

    async def probe(self) -> dict[str, Any]:
        return {"ok": True, "detail": "Offline fake image provider."}

    async def _render(self, op: str, prompt: str, width: int, height: int, refs: int) -> bytes:
        self.calls.append({"op": op, "prompt": prompt, "refs": refs})
        if "[blocked]" in prompt:
            raise ProviderError("MAI-Image's content filter blocked this request (BingBlockList).",
                                code="content_filter")
        await asyncio.sleep(self.delay)
        image = Image.new("RGB", (width, height), _color(prompt))
        draw = ImageDraw.Draw(image)
        draw.rectangle((width // 4, height // 3, width * 3 // 4, height * 2 // 3), fill=_color(prompt[::-1]))
        draw.text((24, 24), f"{op} · {prompt[:60]}", fill=(255, 255, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


class FakeVideo:
    def __init__(self, polls_to_complete: int = 2) -> None:
        self.polls_to_complete = polls_to_complete
        self.jobs: dict[str, dict[str, Any]] = {}
        self.busy_once: set[str] = set()
        self.calls: list[dict[str, Any]] = []

    async def create(self, prompt: str, *, seconds: int, size: str, input_reference: bytes | None = None) -> dict[str, Any]:
        self.calls.append({"op": "create", "prompt": prompt, "seconds": seconds, "i2v": input_reference is not None})
        if "[busy]" in prompt and prompt not in self.busy_once:
            self.busy_once.add(prompt)
            raise ProviderError("Sora: too many running tasks; waiting for a slot.", code="too_many_tasks",
                                retryable=True)
        if "[blocked]" in prompt:
            raise ProviderError("Sora's content filter blocked this request (moderation_blocked).",
                                code="content_filter")
        return self._job(prompt, seconds, size)

    async def remix(self, video_id: str, prompt: str) -> dict[str, Any]:
        self.calls.append({"op": "remix", "of": video_id, "prompt": prompt})
        source = self.jobs.get(video_id, {"seconds": 4, "size": "1280x720"})
        return self._job(prompt, source["seconds"], source["size"], remix_of=video_id)

    def _job(self, prompt: str, seconds: int, size: str, remix_of: str | None = None) -> dict[str, Any]:
        job_id = f"video_fake_{secrets.token_hex(4)}"
        self.jobs[job_id] = {"id": job_id, "prompt": prompt, "seconds": seconds, "size": size, "polls": 0,
                             "created_at": int(time.time()), "remix_of": remix_of}
        return {"id": job_id, "status": "queued", "progress": 0}

    def adopt(self, job_id: str, prompt: str = "resumed", seconds: int = 4) -> None:
        """Pretend a job was created before a restart (used by resume tests)."""
        self.jobs[job_id] = {"id": job_id, "prompt": prompt, "seconds": seconds, "size": "1280x720", "polls": 0,
                             "created_at": int(time.time())}

    async def get(self, video_id: str) -> dict[str, Any]:
        job = self.jobs.get(video_id)
        if job is None:
            raise ProviderError("Sora: deployment or job not found (HTTP 404).", code="not_found", status=404)
        job["polls"] += 1
        if job["polls"] >= self.polls_to_complete:
            if "[fail]" in job["prompt"]:
                return {"id": video_id, "status": "failed",
                        "error": {"code": "moderation_blocked", "message": "Output was blocked by moderation."}}
            return {"id": video_id, "status": "completed", "progress": 100, "created_at": job["created_at"],
                    "completed_at": job["created_at"] + 3}
        return {"id": video_id, "status": "in_progress",
                "progress": int(100 * job["polls"] / self.polls_to_complete)}

    async def download(self, video_id: str) -> bytes:
        job = self.jobs[video_id]
        color = "#%02x%02x%02x" % _color(job["prompt"])
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "take.mp4"
            await asyncio.to_thread(subprocess.run, [
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                f"testsrc2=size=640x360:rate=30,drawbox=c={color}@0.6:t=fill,scale=1280:720",
                "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-t", str(job["seconds"]),
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out),
            ], check=True)
            return out.read_bytes()

    async def ping(self) -> dict[str, Any]:
        return {"ok": True, "jobs_visible": len(self.jobs)}


class FakeSpeech:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def voices(self) -> list[dict[str, Any]]:
        return FAKE_VOICES

    async def synthesize(self, text: str, voice: str, *, locale: str, style: str | None = None) -> bytes:
        self.calls.append({"text": text, "voice": voice, "style": style})
        if "[blocked]" in text:
            raise ProviderError("Speech refused this text.", code="content_filter")
        seconds = max(1.0, min(len(text) * 0.06, 20.0))
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "line.mp3"
            await asyncio.to_thread(subprocess.run, [
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=24000",
                "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-b:a", "64k", str(out)], check=True)
            return out.read_bytes()

    async def transcribe(self, wav16k: bytes, *, locale: str, expected: str | None = None) -> dict[str, Any]:
        del wav16k, locale
        return {"status": "Success", "text": expected or "", "confidence": 0.99}
