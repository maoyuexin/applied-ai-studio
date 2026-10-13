"""Run bundles: one .zip per run (run.json + media/<sha>) to copy runs between installs."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .media import MediaStore
from .pipelines.base import ActionError
from .store import Store, now

FORMAT = "design-studio-run"
VERSION = 1
MEDIA_NAME = re.compile(r"^media/([0-9a-f]{64})$")


def export_run(store: Store, media: MediaStore, run_id: str, out_path: Path) -> Path:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    if run["restricted"]:
        raise ActionError("Restricted runs are never exported.")
    artifacts = store.list_artifacts(run_id)
    shas = sorted({sha for a in artifacts for sha in (a["media_sha"], a["thumb_sha"]) if sha and media.exists(sha)})
    manifest = {
        "format": FORMAT, "version": VERSION, "exported_at": now(), "run": run, "steps": store.get_steps(run_id),
        "artifacts": artifacts, "decisions": store.list_decisions(run_id), "events": store.list_events(run_id, 100_000),
        "media": [store.get_media(sha) for sha in shas],
    }
    with zipfile.ZipFile(out_path, "w") as archive:
        archive.writestr("run.json", json.dumps(manifest, ensure_ascii=False, indent=1),
                         compress_type=zipfile.ZIP_DEFLATED)
        for sha in shas:
            archive.write(media.path(sha), f"media/{sha}", compress_type=zipfile.ZIP_STORED)
    return out_path


def import_run(store: Store, media: MediaStore, zip_path: Path, *, max_bytes: int) -> str:
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as error:
        raise ActionError("That file is not a Design Studio run bundle (.zip).") from error
    with archive:
        infos = archive.infolist()
        names = {info.filename for info in infos}
        if "run.json" not in names:
            raise ActionError("The bundle has no run.json.")
        for info in infos:
            if info.filename != "run.json" and not MEDIA_NAME.match(info.filename):
                raise ActionError(f"Unexpected file in bundle: {info.filename[:80]}")
        if sum(info.file_size for info in infos) > max_bytes:
            raise ActionError("The bundle is larger than this install accepts.")
        manifest: dict[str, Any] = json.loads(archive.read("run.json"))
        if manifest.get("format") != FORMAT or int(manifest.get("version", 0)) > VERSION:
            raise ActionError("Unsupported bundle format or version.")
        run = manifest["run"]
        if store.get_run(run["id"]) is not None:
            raise ActionError("This run is already in your history.")
        if run.get("restricted"):
            raise ActionError("Restricted runs cannot be imported.")
        for entry in manifest.get("media", []):
            if not entry:
                continue
            sha = entry["sha"]
            data = archive.read(f"media/{sha}")
            if hashlib.sha256(data).hexdigest() != sha:
                raise ActionError("A media file in the bundle is damaged (checksum mismatch).")
            media.put_bytes(data, entry["media_type"], entry.get("meta") or {})
    artifacts = manifest["artifacts"]
    for artifact in artifacts:
        if artifact["status"] in ("queued", "running"):
            artifact.update(status="canceled", error="Interrupted: the run was exported while this was running.")
    steps = manifest["steps"]
    for step in steps:
        if step["status"] == "running":
            step.update(status="failed", error="Interrupted by export; retry this step.")
    store.import_rows(run, steps, artifacts, manifest.get("decisions", []), manifest.get("events", []))
    store.add_event(run["id"], "info", f"Imported from a bundle exported {manifest.get('exported_at', '')}.",
                    code="imported")
    return str(run["id"])
