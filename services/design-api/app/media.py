"""Content-addressed media files plus the image, video and audio helpers the pipelines need.

Files live at <data_dir>/media/<sha[:2]>/<sha>; the SQLite `media` table records type and size.
Heavy work (ffmpeg, c2patool) runs as subprocesses so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .store import Store

SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)


class MediaToolError(RuntimeError):
    pass


@dataclass
class MediaInfo:
    sha: str
    media_type: str
    size: int
    meta: dict[str, Any]


class MediaStore:
    def __init__(self, root: Path, store: Store) -> None:
        self.root = root
        self.store = store
        self.root.mkdir(parents=True, exist_ok=True)
        self.tmp = root.parent / "tmp"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def path(self, sha: str) -> Path:
        if not SHA_PATTERN.match(sha):
            raise ValueError("Invalid media id.")
        return self.root / sha[:2] / sha

    def exists(self, sha: str) -> bool:
        return SHA_PATTERN.match(sha) is not None and self.path(sha).is_file()

    def put_bytes(self, data: bytes, media_type: str, meta: dict[str, Any] | None = None) -> MediaInfo:
        sha = hashlib.sha256(data).hexdigest()
        target = self.path(sha)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.tmp, delete=False) as handle:
                handle.write(data)
                temp_name = handle.name
            os.replace(temp_name, target)
        info_meta = meta or {}
        self.store.put_media(sha, media_type, len(data), info_meta)
        return MediaInfo(sha, media_type, len(data), info_meta)

    def put_file(self, source: Path, media_type: str, meta: dict[str, Any] | None = None) -> MediaInfo:
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        sha = digest.hexdigest()
        target = self.path(sha)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = self.tmp / f"{sha}.part"
            shutil.copyfile(source, temp)
            os.replace(temp, target)
        size = target.stat().st_size
        info_meta = meta or {}
        self.store.put_media(sha, media_type, size, info_meta)
        return MediaInfo(sha, media_type, size, info_meta)

    def read(self, sha: str) -> bytes:
        return self.path(sha).read_bytes()

    def delete_unreferenced(self, older_than: str | None = None) -> int:
        return self.delete_shas(set(self.store.unreferenced_media(older_than)))

    def delete_shas(self, shas: set[str]) -> int:
        for sha in shas:
            try:
                self.path(sha).unlink(missing_ok=True)
            except ValueError:
                continue
        self.store.delete_media_rows(shas)
        return len(shas)

    def temp_dir(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=self.tmp)


# Image helpers (Pillow)


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def normalize_upload(data: bytes, max_side: int = 2048) -> tuple[bytes, str, dict[str, Any]]:
    """Validate an uploaded image, apply EXIF rotation, cap its size and return PNG bytes."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue(), "image/png", {"width": image.width, "height": image.height}
    except Exception as error:  # noqa: BLE001 - Pillow raises many types for bad input
        raise MediaToolError("That file is not an image Design Studio can read (PNG, JPEG or WebP).") from error


def thumbnail_jpeg(data: bytes, width: int = 480) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        ratio = width / image.width
        image = image.resize((width, max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        return buffer.getvalue()


def cover_resize_png(data: bytes, width: int, height: int) -> bytes:
    """Scale and center-crop to exactly width x height (used for video input frames)."""
    with Image.open(io.BytesIO(data)) as image:
        fitted = ImageOps.fit(image.convert("RGB"), (width, height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        fitted.save(buffer, format="PNG")
        return buffer.getvalue()


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def label_overlay_png(text: str, width: int = 1280, height: int = 720) -> bytes:
    """Transparent full-frame PNG with a small label badge in the top-right corner."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(max(14, height // 40))
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    pad_x, pad_y, margin = 12, 7, 18
    box = (width - margin - (right - left) - 2 * pad_x, margin, width - margin, margin + (bottom - top) + 2 * pad_y)
    draw.rounded_rectangle(box, radius=8, fill=(10, 12, 16, 170))
    draw.text((box[0] + pad_x - left, box[1] + pad_y - top), text, font=font, fill=(245, 243, 240, 255))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: float) -> Any:
    font = load_font(size)
    while size > 12:
        left, _, right, _ = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width:
            break
        size -= 2
        font = load_font(size)
    return font


def end_card_png(title: str, tagline: str, footnote: str, width: int = 1280, height: int = 720) -> bytes:
    canvas = Image.new("RGBA", (width, height), (8, 9, 12, 255))
    draw = ImageDraw.Draw(canvas)
    base = min(width, height * 16 / 9)

    def centered(text: str, size: int, y: int, fill: tuple[int, int, int, int]) -> None:
        font = _fit_font(draw, text, size, width * 0.88)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (right - left)) / 2 - left, y - top), text, font=font, fill=fill)

    centered(title, int(base / 16), int(height * 0.40), (245, 243, 240, 255))
    if tagline:
        centered(tagline, int(base / 46), int(height * 0.53), (232, 145, 60, 255))
    if footnote:
        centered(footnote, int(base / 80), int(height * 0.88), (150, 154, 168, 255))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def title_overlay_image(data: bytes, title: str, label: str) -> bytes:
    """Poster-style title at the bottom plus a small disclosure label, on a copy of the image."""
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert("RGBA")
    width, height = image.size
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    for row in range(height // 3):
        alpha = int(190 * (row / (height / 3)))
        shade_draw.line([(0, height - height // 3 + row), (width, height - height // 3 + row)], fill=(0, 0, 0, alpha))
    image = Image.alpha_composite(image, shade)
    draw = ImageDraw.Draw(image)
    if title:
        font = _fit_font(draw, title, max(24, min(width // 12, height // 9)), width * 0.9)
        left, top, right, bottom = draw.textbbox((0, 0), title, font=font)
        draw.text(((width - (right - left)) / 2 - left, height - height // 7 - (bottom - top) - top), title,
                  font=font, fill=(245, 243, 240, 255))
    if label:
        image = Image.alpha_composite(image, Image.open(io.BytesIO(label_overlay_png(label, width, height))))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


# Subprocess helpers


async def run_tool(*args: str, timeout: float = 600) -> tuple[int, bytes, bytes]:
    try:
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError as error:
        raise MediaToolError(f"{args[0]} is not installed on this machine.") from error
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as error:
        process.kill()
        raise MediaToolError(f"{Path(args[0]).name} timed out.") from error
    return process.returncode or 0, stdout, stderr


class MediaTools:
    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", c2patool: str = "c2patool") -> None:
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.c2patool = c2patool

    def available(self) -> dict[str, bool]:
        return {name: shutil.which(tool) is not None for name, tool in
                (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe), ("c2patool", self.c2patool))}

    async def _ffmpeg(self, *args: str, timeout: float = 600) -> bytes:
        code, _, stderr = await run_tool(self.ffmpeg, "-hide_banner", "-nostdin", "-y", *args, timeout=timeout)
        if code != 0:
            raise MediaToolError(f"ffmpeg failed: {stderr.decode(errors='replace')[-600:]}")
        return stderr

    async def probe(self, path: Path) -> dict[str, Any]:
        code, stdout, stderr = await run_tool(
            self.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path), timeout=60
        )
        if code != 0:
            raise MediaToolError(f"ffprobe failed: {stderr.decode(errors='replace')[-300:]}")
        payload = json.loads(stdout or b"{}")
        streams = payload.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        duration = float(payload.get("format", {}).get("duration") or 0)
        return {
            "duration": round(duration, 2),
            "width": int(video["width"]) if video else None,
            "height": int(video["height"]) if video else None,
            "has_audio": audio is not None,
        }

    async def video_poster(self, path: Path, at: float, width: int = 480) -> bytes:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "poster.jpg"
            await self._ffmpeg("-v", "error", "-ss", f"{max(at, 0):.2f}", "-i", str(path), "-frames:v", "1",
                               "-vf", f"scale={width}:-2", "-q:v", "4", str(out), timeout=60)
            return out.read_bytes()

    async def motion_score(self, path: Path) -> float | None:
        code, stdout, stderr = await run_tool(
            self.ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path), "-an", "-vf",
            "scale=320:180,format=gray,tblend=all_mode=difference,signalstats,"
            "metadata=print:key=lavfi.signalstats.YAVG:file=-",
            "-f", "null", "-", timeout=300,
        )
        if code != 0:
            raise MediaToolError(f"ffmpeg motion check failed: {stderr.decode(errors='replace')[-300:]}")
        values = [float(match) for match in re.findall(rb"lavfi\.signalstats\.YAVG=([0-9.]+)", stdout)]
        # tblend's first output frame compares frame 0 with itself; drop it.
        values = values[1:] if len(values) > 1 else values
        return round(sum(values) / len(values), 2) if values else None

    async def loudness(self, path: Path) -> dict[str, Any]:
        stderr = await self._ffmpeg(
            "-v", "info", "-i", str(path), "-vn", "-af", "volumedetect,silencedetect=noise=-50dB:d=0.8",
            "-f", "null", "-", timeout=300,
        )
        text = stderr.decode(errors="replace")
        mean = re.search(r"mean_volume: (-?[0-9.]+) dB", text)
        peak = re.search(r"max_volume: (-?[0-9.]+) dB", text)
        return {
            "mean_db": float(mean.group(1)) if mean else None,
            "peak_db": float(peak.group(1)) if peak else None,
            "silent_gaps": len(re.findall(r"silence_start", text)),
        }

    async def c2pa(self, path: Path) -> dict[str, Any]:
        """Read Content Credentials with c2patool. Reports what was found; never guesses."""
        if shutil.which(self.c2patool) is None:
            return {"checked": False, "present": None, "valid": None, "detail": "c2patool is not installed"}
        code, stdout, stderr = await run_tool(self.c2patool, str(path), timeout=60)
        text = (stdout + stderr).decode(errors="replace")
        if code != 0 or "No claim found" in text or not stdout.strip():
            return {"checked": True, "present": False, "valid": None, "detail": "No Content Credentials found"}
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError:
            return {"checked": True, "present": True, "valid": None, "detail": "Unreadable c2patool output"}
        active = report.get("active_manifest")
        manifest = report.get("manifests", {}).get(active, {}) if active else {}
        issuer = (manifest.get("signature_info") or {}).get("issuer")
        generator = manifest.get("claim_generator") or ""
        status = report.get("validation_status") or []
        failures = [item.get("code") for item in status if "fail" in str(item.get("code", "")).lower()
                    or "expired" in str(item.get("code", "")).lower() or "mismatch" in str(item.get("code", ""))]
        state = report.get("validation_state")
        valid = (state in ("Valid", "Trusted")) if state else not failures
        detail = "valid" if valid else ("fails check: " + ", ".join(str(code) for code in failures[:3]) if failures
                                        else f"state: {state}")
        return {"checked": True, "present": True, "valid": valid, "issuer": issuer, "generator": generator,
                "detail": detail}

    async def assemble_video(
        self,
        clips: list[Path],
        out: Path,
        *,
        clip_seconds: list[float],
        label_text: str,
        end_card: tuple[str, str, str] | None = None,
        size: tuple[int, int] = (1280, 720),
        crossfade: float = 0.5,
        voiceover: Path | None = None,
    ) -> dict[str, Any]:
        if not clips:
            raise MediaToolError("Nothing to assemble: no kept takes.")
        with tempfile.TemporaryDirectory() as folder:
            label = Path(folder) / "label.png"
            width, height = size
            label.write_bytes(label_overlay_png(label_text, width, height) if label_text else blank_png(width, height))
            inputs: list[str] = []
            parts: list[str] = []
            count = len(clips)
            for index, clip in enumerate(clips):
                info = await self.probe(clip)
                inputs += ["-i", str(clip)]
                seconds = min(clip_seconds[index], info["duration"] or clip_seconds[index])
                clip_seconds[index] = seconds
                parts.append(f"[{index}:v]trim=0:{seconds:.3f},setpts=PTS-STARTPTS,fps=30,scale={width}:{height}:"
                             f"force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,format=yuv420p[v{index}]")
                if info["has_audio"]:
                    parts.append(f"[{index}:a]atrim=0:{seconds:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                                 f"aformat=channel_layouts=stereo[a{index}]")
                else:
                    parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{seconds:.3f}[a{index}]")
            total = sum(clip_seconds) - crossfade * (count - 1)
            inputs += ["-loop", "1", "-i", str(label)]
            vprev, aprev, offset = "v0", "a0", clip_seconds[0] - crossfade
            for index in range(1, count):
                parts.append(f"[{vprev}][v{index}]xfade=transition=fade:duration={crossfade}:offset={offset:.3f}[vx{index}]")
                parts.append(f"[{aprev}][a{index}]acrossfade=d={crossfade}[ax{index}]")
                vprev, aprev = f"vx{index}", f"ax{index}"
                offset += clip_seconds[index] - crossfade
            parts.append(f"[{count}:v]format=rgba[lab]")
            parts.append(f"[{vprev}][lab]overlay=0:0:shortest=1[vl]")
            next_input = count + 1
            if end_card is not None:
                card = Path(folder) / "card.png"
                card.write_bytes(end_card_png(*end_card, width=width, height=height))
                card_seconds, card_fade = 3.0, 0.6
                inputs += ["-loop", "1", "-t", f"{card_seconds}", "-i", str(card)]
                parts.append(f"[{next_input}:v]fps=30,scale={width}:{height},setsar=1,format=yuv420p[card]")
                parts.append(f"[vl][card]xfade=transition=fade:duration={card_fade}:offset={total - card_fade:.3f}[vout]")
                parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{card_seconds - card_fade:.3f}[pad]")
                parts.append(f"[{aprev}][pad]concat=n=2:v=0:a=1[amain]")
                final_seconds = total + card_seconds - card_fade
                next_input += 1
            else:
                parts.append("[vl]null[vout]")
                parts.append(f"[{aprev}]anull[amain]")
                final_seconds = total
            if voiceover is not None:
                inputs += ["-i", str(voiceover)]
                parts.append(f"[{next_input}:a]aresample=48000,aformat=channel_layouts=stereo,adelay=600|600[vo]")
                parts.append("[amain]volume=0.45[bed]")
                parts.append("[bed][vo]amix=inputs=2:duration=first:normalize=0[amix]")
                parts.append(f"[amix]afade=t=out:st={max(final_seconds - 1.2, 0):.3f}:d=1.2[aout]")
            else:
                parts.append(f"[amain]afade=t=out:st={max(final_seconds - 1.2, 0):.3f}:d=1.2[aout]")
            await self._ffmpeg(
                "-v", "error", *inputs, "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
                "-t", f"{final_seconds:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt",
                "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out), timeout=900,
            )
        return {"duration": round(final_seconds, 2), "crossfade": crossfade, "clips": count,
                "end_card": end_card is not None}

    async def to_wav16k(self, source: Path, out: Path) -> None:
        await self._ffmpeg("-v", "error", "-i", str(source), "-ac", "1", "-ar", "16000", "-f", "wav", str(out),
                           timeout=120)

    async def audio_duration(self, path: Path) -> float:
        return (await self.probe(path))["duration"]

    async def concat_audio(self, lines: list[Path], out: Path, *, pause_ms: int = 350) -> dict[str, Any]:
        if not lines:
            raise MediaToolError("No audio lines to mix.")
        inputs: list[str] = []
        parts: list[str] = []
        labels: list[str] = []
        for index, line in enumerate(lines):
            inputs += ["-i", str(line)]
            parts.append(f"[{index}:a]aresample=48000,aformat=channel_layouts=mono[l{index}]")
            labels.append(f"[l{index}]")
            if index < len(lines) - 1:
                parts.append(f"anullsrc=r=48000:cl=mono,atrim=0:{pause_ms / 1000:.3f}[p{index}]")
                labels.append(f"[p{index}]")
        parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[cat]")
        parts.append("[cat]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
        await self._ffmpeg("-v", "error", *inputs, "-filter_complex", ";".join(parts), "-map", "[aout]",
                           "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "160k", str(out), timeout=600)
        return {"duration": await self.audio_duration(out), "lines": len(lines), "pause_ms": pause_ms}


def blank_png(width: int = 1280, height: int = 720) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()
