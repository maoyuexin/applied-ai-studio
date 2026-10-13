"""Record the curated replay set. Usage: python scripts/record_all.py [scenario ...]"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = [
    ("card-alert", "caught-fraud-2", []),
    ("card-alert", "reviewed-normal-1", ["--reject"]),
    ("card-alert", "missed-fraud-1", []),
    ("trial-finder", "P01", []),
    ("work-order", "W-1104", []),
    ("work-order", "W-0708", []),
    ("work-order", "W-0215", []),
    ("coding-team", "ship-142", ["--tag", "1"]),
    ("coding-team", "ship-142", ["--tag", "2"]),
    ("coding-team", "ship-142", ["--tag", "3"]),
    ("holiday-promo", "homepage-week-48", ["--tag", "1"]),
    ("holiday-promo", "homepage-week-48", ["--tag", "2"]),
    ("holiday-promo", "homepage-week-48", ["--tag", "3"]),
]


def main() -> int:
    only = set(sys.argv[1:])
    failures = 0
    for scenario, task, extra in PLAN:
        if only and scenario not in only:
            continue
        print(f"=== {scenario} {task} {' '.join(extra)}", flush=True)
        result = subprocess.run([sys.executable, str(HERE / "record.py"), scenario, task, *extra])
        failures += result.returncode != 0
    print(f"done, {failures} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
