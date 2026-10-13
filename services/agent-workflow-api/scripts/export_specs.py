"""Write the web page's static data: scenarios.json and recordings.json (replay works without the API)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import RECORDINGS_DIR, SPECS_FILE  # noqa: E402
from app.scenarios import SCENARIOS  # noqa: E402

INDEX_FILE = SPECS_FILE.parent / "recordings.json"


def render() -> str:
    specs = []
    for scenario in SCENARIOS.values():
        scenario.validate()
        data = scenario.to_dict()
        data["has_live"] = scenario.builder is not None
        specs.append(data)
    return json.dumps(specs, indent=1, ensure_ascii=False) + "\n"


def render_index() -> str:
    order = {scenario_id: i for i, scenario_id in enumerate(SCENARIOS)}
    items = []
    for path in sorted(RECORDINGS_DIR.glob("*/*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        stats = run.get("stats") or {}
        items.append(
            {
                "file": f"{path.parent.name}/{path.name}",
                "scenario": run["scenario"],
                "task_id": run["task"]["id"],
                "task_label": run["task"]["label"],
                "status": run["status"],
                "seconds": run["seconds"],
                "model": run.get("model"),
                "started_at": run.get("started_at"),
                "headline": (run.get("result") or {}).get("headline"),
                "model_calls": stats.get("model_calls"),
                "tool_calls": stats.get("tool_calls"),
                "tokens": (stats.get("input_tokens") or 0) + (stats.get("output_tokens") or 0),
            }
        )
    items.sort(key=lambda item: (order.get(item["scenario"], 99), item["file"]))
    return json.dumps(items, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    outputs = {SPECS_FILE: render(), INDEX_FILE: render_index()}
    if "--check" in sys.argv:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"{path} is out of date; run scripts/export_specs.py", file=sys.stderr)
        return 1 if stale else 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
