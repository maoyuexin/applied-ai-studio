"""Reject outdated Section 4 content before replacing the classroom HTML."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SECTION_FOUR_HEADINGS = [
    "## 4.1 What does the model's score tell us?",
    "## 4.2 How much money could be lost?",
    "## 4.3 Should this account go to an analyst?",
    "## 4.4 What happens when we apply the rule?",
    "## 4.5 Remove the demographic columns, retrain, compare",
    "## 4.6 Final check on 6,000 unseen accounts",
]


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def validate_lesson(notebook: dict, *, require_outputs: bool = False) -> None:
    cells = notebook["cells"]
    sources = [source_text(cell) for cell in cells]
    headings = [source.splitlines()[0] for source in sources if source.startswith("## 4.")]
    if headings != SECTION_FOUR_HEADINGS:
        raise ValueError("Section 4 is not the approved plain-language lesson. Restore the current generator before exporting.")
    start = sources.index(next(source for source in sources if source.startswith(SECTION_FOUR_HEADINGS[0])))
    end = sources.index(next(source for source in sources if source.startswith(SECTION_FOUR_HEADINGS[4])))
    lesson = cells[start:end]
    code = [cell for cell in lesson if cell["cell_type"] == "code"]
    if len(code) != 4:
        raise ValueError("Sections 4.1-4.4 must contain one short code cell per question.")
    blocked = ("charts.reliability_curve", "charts.risk_exposure_plane", "charts.policy_sweep_chart")
    if any(name in source_text(cell) for cell in lesson for name in blocked):
        raise ValueError("The old Section 4 diagnostic charts have returned to the main lesson.")
    decision = next(source for source in sources if source.startswith(SECTION_FOUR_HEADINGS[2]))
    if "The cutoff is not the price of a review" not in decision:
        raise ValueError("Explain that the classroom cutoff is not a review price before exporting.")
    examples = next((cell for cell in cells if "# 5.2 WALK EACH ACCOUNT" in source_text(cell)), None)
    if examples is None or "classroom cutoff?" not in source_text(examples):
        raise ValueError("Rebuild all three account examples using the classroom cutoff.")
    if require_outputs:
        if any(not cell.get("outputs") for cell in code):
            raise ValueError("Run the four Section 4 example cells before exporting.")
        if not examples.get("outputs"):
            raise ValueError("Run the three real account examples before exporting.")
        if any(output.get("output_type") == "error" for cell in cells for output in cell.get("outputs", [])):
            raise ValueError("The notebook contains an error output.")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "01_credit_build.ipynb"
    validate_lesson(json.loads(target.read_text(encoding="utf-8")), require_outputs=True)
    print("Verified the approved plain-language Section 4 before HTML export.")