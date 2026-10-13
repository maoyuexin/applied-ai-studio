"""Record runs for replay: python scripts/record.py card-alert caught-fraud-2 [--reject] [--tag a]."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import RECORDINGS_DIR, load_settings  # noqa: E402
from app.runner import run_scenario  # noqa: E402
from app.scenarios import get_scenario  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("task")
    parser.add_argument("--reject", action="store_true", help="answer approval requests with reject")
    parser.add_argument("--tag", default="1", help="suffix that keeps several takes apart")
    parser.add_argument("--out", type=Path, default=RECORDINGS_DIR)
    args = parser.parse_args()

    settings = load_settings()
    if not settings.live_ready:
        print("Set foundry_project_endpoint and foundry_model in settings.local.json", file=sys.stderr)
        return 2
    scenario = get_scenario(args.scenario)

    async def decide(request: dict) -> bool:
        print(f"  approval asked: {request['tool']} -> {'reject' if args.reject else 'approve'}")
        return not args.reject

    def show(event: dict) -> None:
        kind = event["type"]
        if kind in ("model_call",):
            return
        who = event.get("agent") or event.get("source") or ""
        detail = event.get("tool") or event.get("target") or (event.get("text") or "")[:70].replace("\n", " ")
        print(f"  {event['t']:7.2f}s {kind:16s} {who:18s} {detail}")

    run = await run_scenario(
        scenario, args.task, settings, mode="recorded", decide=decide, emit=show
    )
    folder = args.out / scenario.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{args.task}--{args.tag}.json"
    path.write_text(json.dumps(run, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    s = run["stats"]
    print(
        f"{run['status']} in {run['seconds']} s · model calls {s['model_calls']} · tools {s['tool_calls']}"
        f" · tokens {s['input_tokens'] + s['output_tokens']} -> {path}"
    )
    return 0 if run["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
