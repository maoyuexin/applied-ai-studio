"""Import Module 8 Case 3 work (made before Design Studio existed) into run history.

    python -m app.importer --module8 "<Module_08 folder>/artifacts" [--replace]

Creates: round 1 and round 2 SOLENNE GT video runs (round 2 is a fork of round 1), the SOLENNE design
sheet image run, and the brand-name guardrail test as a Restricted run. Media files are copied into the
Design Studio data folder; nothing in the Module 8 folder is changed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .media import MediaStore, thumbnail_jpeg
from .pipelines.base import c2pa_check, check
from .pipelines.video import audio_check, motion_check
from .store import Store, new_artifact_id

ROUND1_ID = "run_2026-10-05_m8-round1"
ROUND2_ID = "run_2026-10-05_m8-round2"
DESIGN_ID = "run_2026-10-04_m8-design-sheet"
BRAND_ID = "run_2026-10-04_m8-brand-test"


def mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


class Builder:
    def __init__(self, store: Store, media: MediaStore, root: Path) -> None:
        self.store, self.media, self.root = store, media, root
        self.captures = root / "captures"
        self.artifacts: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.seq = 0

    def file(self, relative: str) -> Path:
        path = self.captures / relative
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def put(self, path: Path, media_type: str) -> str:
        return self.media.put_file(path, media_type).sha

    def thumb(self, path: Path) -> str:
        return self.media.put_bytes(thumbnail_jpeg(path.read_bytes()), "image/jpeg", {"thumb_of": path.name}).sha

    def artifact(self, run_id: str, at: str, **fields: Any) -> dict[str, Any]:
        self.seq += 1
        record = {"id": new_artifact_id(), "run_id": run_id, "seq": self.seq, "created_at": at, "updated_at": at,
                  "status": "ready", "inputs": [], "params": {}, "metrics": {}, "checks": [], "checklist": {},
                  "data": {"imported_from": "Module 8 Case 3"}, **fields}
        self.artifacts.append(record)
        return record

    def event(self, at: str, level: str, message: str, code: str = "imported") -> None:
        self.events.append({"at": at, "level": level, "code": code, "message": message, "data": {}})

    def decide(self, artifact: dict[str, Any], at: str) -> None:
        if artifact.get("verdict"):
            self.decisions.append({"artifact_id": artifact["id"], "step_key": artifact["step_key"], "action": "decide",
                                   "verdict": artifact["verdict"], "note": artifact.get("note"), "at": at})

    def save(self, run: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        self.store.import_rows(run, steps, self.artifacts, self.decisions, self.events)


def steps_for(keys: list[tuple[str, str, bool]], statuses: dict[str, str], data: dict[str, dict[str, Any]],
              at: str) -> list[dict[str, Any]]:
    return [{"idx": index, "key": key, "title": title, "gate": gate, "status": statuses.get(key, "done"),
             "data": data.get(key, {}), "started_at": at, "finished_at": at}
            for index, (key, title, gate) in enumerate(keys)]


VIDEO_STEPS = [("shotlist", "Brief → shot list", True), ("keyframes", "Keyframes for product shots", True),
               ("takes", "Takes", True), ("voiceover", "Voiceover", False), ("assemble", "Assemble", False),
               ("provenance", "Label + provenance", False)]


def import_video_round(store: Store, media: MediaStore, root: Path, manifest: dict[str, Any], *, run_id: str,
                       title: str, final: dict[str, Any], seconds: int, parent: str | None, brief_text: str,
                       note: str) -> None:
    b = Builder(store, media, root)
    first_take = b.file(manifest["shots"][0]["takes"][0]["file"])
    final_path = b.file(final["file"])
    created, finished = mtime(first_take), mtime(final_path)
    hero = b.file("case3/design/design_hero_v1.png")
    hero_sha = b.put(hero, "image/png")
    b.artifact(run_id, created, step_key="shotlist", kind="reference", grp="references", label="design_hero_v1.png",
               media_sha=hero_sha, media_type="image/png", thumb_sha=b.thumb(hero),
               data={"role": "subject", "position": 1, "imported_from": "Module 8 Case 3"})
    shots = []
    takes_total = 0
    for index, shot in enumerate(manifest["shots"]):
        shot_id = f"s{index + 1}"
        mode = shot.get("mode") or ("i2v" if shot.get("keyframe") else "t2v")
        people = mode == "t2v"
        shots.append({"id": shot_id, "title": shot["title"], "subject": "people" if people else "product", "mode": mode,
                      "keyframe_prompt": shot.get("keyframe_prompt") or "" if mode == "i2v" else "",
                      "prompt": shot["video_prompt"], "sound": shot.get("sound", ""), "on_screen_text": ""})
        keyframe = None
        if mode == "i2v" and shot.get("keyframe"):
            frame = b.file(shot["keyframe"])
            keyframe = b.artifact(run_id, created, step_key="keyframes", kind="keyframe", grp=shot_id,
                                  label=f"{shot_id}_k1", role="image", provider="image", deployment="mai-image-2-6",
                                  model_version="MAI-Image-2.6", prompt=shot.get("keyframe_prompt"),
                                  inputs=[hero_sha], media_sha=b.put(frame, "image/png"), media_type="image/png",
                                  thumb_sha=b.thumb(frame), verdict="keep",
                                  checks=[check("c2pa", "Content Credentials: removed by the resize to 1280×720",
                                                "info", "Module 8 provenance test")])
        for take in shot["takes"]:
            takes_total += 1
            path = b.file(take["file"])
            qc = take.get("qc") or {}
            metrics = dict(qc.get("metrics") or {})
            metrics.setdefault("duration", float(take.get("seconds") or seconds))
            issues = "; ".join(qc.get("issues") or [])
            note_text = " ".join(part for part in (qc.get("note"), f"Issues: {issues}" if issues else "") if part) or None
            poster = b.file(take["poster"]) if take.get("poster") else None
            verdict = qc.get("verdict") if qc.get("verdict") in ("keep", "usable", "regenerate") else None
            artifact = b.artifact(
                run_id, mtime(path), step_key="takes", kind="take", grp=shot_id,
                label=take["id"].replace("v", "s", 1) if take["id"].startswith("v") else take["id"],
                role="video", provider="video", deployment="sora-2", model_version="2025-12-08",
                prompt=shot["video_prompt"], inputs=[keyframe["media_sha"]] if keyframe else [],
                params={"seconds": int(take.get("seconds") or seconds), "size": "1280x720", "mode": mode},
                vendor_job_id=take.get("video_id"), media_sha=b.put(path, "video/mp4"), media_type="video/mp4",
                thumb_sha=b.thumb(poster) if poster else None, gen_seconds=take.get("generation_seconds"),
                metrics=metrics, verdict=verdict, note=note_text,
                checks=[motion_check(metrics.get("motion")),
                        audio_check(True, {"mean_db": metrics.get("mean_db"), "silent_gaps": metrics.get("silent_gaps", 0)}),
                        c2pa_check({"checked": True, "present": True, "valid": False,
                                    "detail": "fails check: signingCredential.expired"})])
    edit_list = final.get("edit_list", [])
    kept = [a for a in b.artifacts if a["kind"] == "take" and a["label"] in
            [label.replace("v", "s", 1) if label.startswith("v") else label for label in edit_list]]
    for take in b.artifacts:
        if take["kind"] == "take":
            take["verdict"] = "keep" if take in kept else ("usable" if take["verdict"] == "keep" else take["verdict"])
            b.decide(take, finished)
    poster = final_path.with_suffix(".jpg")
    final_art = b.artifact(run_id, finished, step_key="assemble", kind="final", label="final cut", role="tool",
                           provider="local tools", inputs=[t["media_sha"] for t in kept],
                           params={"edit_list": [t["id"] for t in kept], "edit_labels": [t["label"] for t in kept]},
                           media_sha=b.put(final_path, "video/mp4"), media_type="video/mp4",
                           thumb_sha=b.thumb(poster) if poster.exists() else None,
                           metrics={"duration": final.get("duration_seconds"), "clips": len(kept), "end_card": True},
                           checks=[check("label", "Label burned in: “Made with AI” (top right, whole ad) + end card",
                                         "ok", "overlay on every frame")])
    b.artifact(run_id, finished, step_key="provenance", kind="report", label="provenance", role="tool",
               provider="local tools",
               checks=[check("c2pa", "Final cut: Content Credentials: none found (re-encoding removes them)", "warn",
                             "c2patool 0.27.22"),
                       check("c2pa-takes", "Raw Sora takes: present, fail validation (signingCredential.expired)",
                             "warn", "c2patool on the raw takes")],
               data={"note": "Re-encoding removes the vendor's Content Credentials; the burned-in label and this "
                             "report are the disclosure for the final cut.", "imported_from": "Module 8 Case 3"})
    passed = sum(1 for a in b.artifacts if a["kind"] == "take" and a["verdict"] in ("keep", "usable"))
    b.event(created, "info", f"Imported from Module 8 Case 3 ({note}).")
    b.event(finished, "success", f"{takes_total} takes, {passed} passed review; final cut "
                                 f"{final.get('duration_seconds')} s from {', '.join(t['label'] for t in kept)}.",
            code="completed")
    motions = sorted(a["metrics"]["motion"] for a in b.artifacts if a["kind"] == "take" and
                     isinstance(a["metrics"].get("motion"), int | float))
    median = None
    if motions:
        middle = len(motions) // 2
        median = motions[middle] if len(motions) % 2 else round((motions[middle - 1] + motions[middle]) / 2, 2)
    run = {
        "id": run_id, "pipeline": "video", "title": title, "template": "product-ad-30", "status": "completed",
        "brief": {"brief": brief_text, "shots": len(shots), "seconds": seconds,
                  "takes_per_shot": max(len(s["takes"]) for s in manifest["shots"]), "size": "1280x720",
                  "must_not_include": "real car brands or logos, readable license plates",
                  "visible_label": "Made with AI", "end_title": "SOLENNE GT", "end_tagline": "Drive the quiet.",
                  "voiceover": "", "voice": "",
                  "references": [{"sha": hero_sha, "role": "subject", "name": "design_hero_v1.png"}]},
        "settings": {}, "parent_run_id": parent, "tags": ["Module 8", "imported"], "restricted": False,
        "source": "imported", "current_step": None, "error": None, "rev": 1, "created_at": created,
        "updated_at": finished,
        "counters": {"outputs": f"{final.get('duration_seconds')} s cut · {takes_total} takes · {passed} passed",
                     "thumb_sha": final_art["thumb_sha"], "takes": takes_total, "ready": takes_total, "kept": len(kept),
                     "passed": passed, "video_seconds": takes_total * seconds,
                     "images": sum(1 for a in b.artifacts if a["kind"] == "keyframe"), "median_motion": median,
                     "final_duration": final.get("duration_seconds"), "models": ["mai-image-2-6", "sora-2"]},
    }
    statuses = {"voiceover": "skipped"}
    if not any(s["mode"] == "i2v" for s in shots):
        statuses["keyframes"] = "skipped"
    b.save(run, steps_for(VIDEO_STEPS, statuses, {"shotlist": {"shots": shots, "edited": True}}, finished))


def import_design_sheet(store: Store, media: MediaStore, root: Path) -> None:
    b = Builder(store, media, root)
    hero = b.file("case3/design/design_hero_v1.png")
    created = mtime(hero)
    hero_sha = b.put(hero, "image/png")
    candidate = b.artifact(DESIGN_ID, created, step_key="candidates", kind="image", grp="candidates", label="c1",
                           role="image", provider="image", deployment="mai-image-2-6", model_version="MAI-Image-2.6",
                           prompt="Design sheet for SOLENNE GT, a fictional luxury electric grand tourer (see brief).",
                           media_sha=hero_sha, media_type="image/png", thumb_sha=b.thumb(hero), verdict="keep",
                           params={"width": 1536, "height": 864, "operation": "generations"},
                           checks=[c2pa_check({"checked": True, "present": True, "valid": True,
                                               "issuer": "Microsoft Corporation"})])
    b.decide(candidate, created)
    passes = [("s2_keyframe_v2.png", "Night waterfront road", "blocked by BingBlockList, reworded, then ok"),
              ("s4_keyframe_v2.png", "Seaside highway at sunrise, drone view", ""),
              ("s5_keyframe_v2.png", "Glass house at dusk", "")]
    last = created
    for index, (name, title, extra) in enumerate(passes):
        path = b.file(f"case3/frames/{name}")
        last = mtime(path)
        version = b.artifact(DESIGN_ID, last, step_key="iterate", kind="image", grp="versions", label=f"v{index + 1}",
                             parent_id=candidate["id"], role="image", provider="image", deployment="mai-image-2-6",
                             model_version="MAI-Image-2.6", inputs=[hero_sha], prompt=f"Edit of c1: {title}.",
                             params={"width": 1536, "height": 864, "operation": "edits", "note": title,
                                     "roles": ["base"]},
                             media_sha=b.put(path, "image/png"), media_type="image/png", thumb_sha=b.thumb(path),
                             verdict="keep", note=extra or None,
                             checks=[c2pa_check({"checked": True, "present": True, "valid": True,
                                                 "issuer": "Microsoft Corporation"})])
        b.decide(version, last)
    b.artifact(DESIGN_ID, last, step_key="finish", kind="final", label="final", role="tool", provider="local tools",
               parent_id=candidate["id"], inputs=[hero_sha], media_sha=hero_sha, media_type="image/png",
               thumb_sha=candidate["thumb_sha"], data={"source_label": "c1", "imported_from": "Module 8 Case 3"},
               checks=[check("label", "No visible label (internal design sheet)", "warn", "drawn by the app"),
                       c2pa_check({"checked": True, "present": True, "valid": True, "issuer": "Microsoft Corporation"})])
    b.event(created, "info", "Imported from Module 8 Case 3 (the design sheet every shot had to match).")
    b.event(last, "warn", "MAI-Image blocked 4 harmless keyframe requests (BingBlockList); rewording got them through.",
            code="content_filter")
    run = {
        "id": DESIGN_ID, "pipeline": "image", "title": "SOLENNE GT · design sheet", "template": "hero",
        "status": "completed",
        "brief": {"use_case": "hero", "brief": "Design sheet for SOLENNE GT, an original fictional luxury electric grand "
                  "tourer: long-hood two-door fastback, liquid-silver paint, thin full-width light bars, no badges. "
                  "Then edit passes that place the exact car in the ad's scenes.",
                  "references": [], "must_not_include": "real car brands or logos", "size": "1536x864",
                  "candidates": 1, "prompt_helper": False, "title": "", "visible_label": ""},
        "settings": {}, "parent_run_id": None, "tags": ["Module 8", "imported"], "restricted": False,
        "source": "imported", "current_step": None, "error": None, "rev": 1, "created_at": created, "updated_at": last,
        "counters": {"outputs": "4 kept · 3 edit passes", "thumb_sha": candidate["thumb_sha"], "images": 4,
                     "kept": 4, "versions": 3, "blocked": 0, "models": ["mai-image-2-6"]},
    }
    keys = [("prompt", "Brief → prompt", True), ("candidates", "Candidates", True), ("iterate", "Iterate", True),
            ("finish", "Finish", False)]
    b.save(run, steps_for(keys, {}, {"prompt": {"prompt": run["brief"]["brief"]}, "iterate": {"final_id": candidate["id"]}}, last))


def import_brand_test(store: Store, media: MediaStore, root: Path, guardrail: dict[str, Any]) -> None:
    b = Builder(store, media, root)
    test = guardrail["brand_test"]
    path = b.file(test["file"])
    at = mtime(path)
    contact = b.captures / "smoke" / "contact_car_brand.png"
    take = b.artifact(BRAND_ID, at, step_key="takes", kind="take", grp="s1", label="s1_t1", role="video",
                      provider="video", deployment="sora-2", model_version="2025-12-08", prompt=test["prompt"],
                      params={"seconds": 4, "size": "1280x720", "mode": "t2v"}, media_sha=b.put(path, "video/mp4"),
                      media_type="video/mp4", thumb_sha=b.thumb(contact) if contact.exists() else None,
                      gen_seconds=test.get("generation_seconds"), metrics={"duration": 4}, verdict="reject",
                      note=test["note"],
                      checks=[check("guardrail", "Vendor filter: not refused", "bad",
                                    "a real brand was requested on purpose; the brand review is a human job")])
    b.decide(take, at)
    b.event(at, "warn", "Guardrail test: Sora 2 did not refuse a real brand and badge. Restricted: in class only, "
                        "never exported.", code="restricted")
    shots = [{"id": "s1", "title": "Brand-name test", "subject": "product", "mode": "t2v", "keyframe_prompt": "",
              "prompt": test["prompt"], "sound": "", "on_screen_text": ""}]
    run = {
        "id": BRAND_ID, "pipeline": "video", "title": "Brand-name test (guardrail missed)", "template": "blank",
        "status": "completed",
        "brief": {"brief": "Guardrail test: ask for a real brand and badge on purpose, to see whether the vendor "
                  "filter stops it.", "shots": 1, "seconds": 4, "takes_per_shot": 1, "size": "1280x720",
                  "must_not_include": "", "visible_label": "", "end_title": "", "end_tagline": "", "voiceover": "",
                  "voice": "", "references": []},
        "settings": {}, "parent_run_id": None, "tags": ["Module 8", "imported", "in class only"], "restricted": True,
        "source": "imported", "current_step": None, "error": None, "rev": 1, "created_at": at, "updated_at": at,
        "counters": {"outputs": "1 take · not refused", "thumb_sha": take["thumb_sha"], "takes": 1, "ready": 1,
                     "kept": 0, "passed": 0, "video_seconds": 4, "models": ["sora-2"]},
    }
    statuses = {"keyframes": "skipped", "voiceover": "skipped", "assemble": "skipped", "provenance": "skipped"}
    b.save(run, steps_for(VIDEO_STEPS, statuses, {"shotlist": {"shots": shots}}, at))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module8", required=True, type=Path, help="Module_08 .../artifacts folder")
    parser.add_argument("--replace", action="store_true", help="delete and re-import runs that already exist")
    args = parser.parse_args(argv)
    root: Path = args.module8
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.data_dir / "design.db")
    media = MediaStore(settings.data_dir / "media", store)
    manifest = json.loads((root / "case3" / "manifest.json").read_text())
    manifest_v1 = json.loads((root / "case3" / "manifest_v1.json").read_text())
    jobs = [
        (ROUND1_ID, lambda: import_video_round(
            store, media, root, manifest_v1, run_id=ROUND1_ID, title="SOLENNE GT · round 1",
            final=manifest["first_attempt"]["final"], seconds=4, parent=None,
            brief_text="A 20-second ad for SOLENNE GT, a fictional luxury electric grand tourer: studio reveal, "
                       "coastal road, city at night, home at dusk. Product shots start from keyframes edited from the "
                       "design sheet.", note="round 1: 5 shots × 4 s; judged 'looked like slides'")),
        (ROUND2_ID, lambda: import_video_round(
            store, media, root, manifest, run_id=ROUND2_ID, title="SOLENNE GT · family drive",
            final=manifest["final"], seconds=8, parent=ROUND1_ID,
            brief_text="A 30-second ad for SOLENNE GT, a fictional luxury electric grand tourer in liquid silver. A "
                       "family drive: the car on a coastal highway at sunrise, dad at the wheel, two kids laughing in "
                       "the back, arriving home at dusk. Warm, cinematic, quiet confidence.",
            note="round 2: 4 shots × 8 s with specific actions and people")),
        (DESIGN_ID, lambda: import_design_sheet(store, media, root)),
        (BRAND_ID, lambda: import_brand_test(store, media, root, manifest["guardrail"])),
    ]
    for run_id, job in jobs:
        if store.get_run(run_id):
            if not args.replace:
                print(f"skip {run_id} (already imported)")
                continue
            store.delete_run(run_id)
        job()
        print(f"imported {run_id}: {store.get_run(run_id)['title']}")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
