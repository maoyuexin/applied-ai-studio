"""Explicit live capture: 32 Copilot requests on public redacted test narratives."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaintlab import data, llm_comparison


async def main() -> None:
    sample = llm_comparison.select_sample(data.load_splits()["test"])
    result = await llm_comparison.run_comparison(
        sample, live=True,
        progress=lambda index, total, outcome: print(f"{index}/{total}: {outcome}", flush=True),
    )
    if not any(row["status"] == "ok" for row in result["rows"]):
        raise RuntimeError("No valid LLM answers; no capture was saved.")
    llm_comparison.CAPTURE_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    llm_comparison.load_capture(sample)
    print(llm_comparison.summary_table(result).to_string(index=False))
    print(llm_comparison.conclusion(result))
    print(f"Saved {llm_comparison.CAPTURE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())