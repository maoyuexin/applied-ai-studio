"""Check the simplified preparation lesson before replacing its offline HTML."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PREPARATION_HEADING = "## 2.2 Prepare the data before splitting"
STAGE_TWO_HEADINGS = [
    "## 2.1 The teams, and how unequal they are",
    PREPARATION_HEADING,
    "## 2.3 How long is a complaint?",
    "## 2.4 Turning one sentence into numbers",
]
STAGE_FOUR_HEADINGS = [
    "## 4.1 How well does it find the right team?",
    "## 4.2 When should a clerk choose the team?",
    "## 4.3 What happened on the final test?",
]


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def validate_walkthroughs(notebook: dict, *, require_outputs: bool = False) -> None:
    cells = notebook["cells"]
    start = next(index for index, cell in enumerate(cells) if "# 5 - Prediction, Routing Words and Handoff" in source_text(cell))
    end = next(index for index, cell in enumerate(cells) if source_text(cell).startswith("## 5.3 What leaves this notebook"))
    examples = cells[start:end]
    code = [cell for cell in examples if cell["cell_type"] == "code"]
    source = "\n".join(source_text(cell) for cell in code)
    for name in ("complaint_excerpt", "routing_decision", "probability_bars"):
        if source.count(f"presentation.{name}(") != 3:
            raise ValueError("Preserve all three visual complaint walkthroughs.")
    if require_outputs:
        if any(not cell.get("outputs") for cell in code):
            raise ValueError("Execute the visual walkthroughs before exporting.")
        html = "".join(source_text({"source": output.get("data", {}).get("text/html", "")})
                       for cell in code for output in cell.get("outputs", []))
        for kind in ("excerpt", "decision", "probabilities"):
            if html.count(f'data-view="{kind}"') != 3:
                raise ValueError("The saved outputs must contain all three visual walkthroughs.")


def validate_word_cloud(notebook: dict, *, require_outputs: bool = False) -> None:
    cells = notebook["cells"]
    start = next(index for index, cell in enumerate(cells) if source_text(cell).startswith(STAGE_TWO_HEADINGS[3]))
    end = next(index for index, cell in enumerate(cells) if "# 3 - Model Training" in source_text(cell))
    lesson = cells[start:end]
    if not any("charts.tfidf_word_clouds(train)" in source_text(cell) for cell in lesson):
        raise ValueError("Keep the approved word clouds in Section 2.4 when simplifying other sections.")
    display = next((cell for cell in lesson if "word_clouds.show()" in source_text(cell)), None)
    if display is None:
        raise ValueError("Display both approved word clouds in Section 2.4.")
    if require_outputs:
        outputs = json.dumps(display.get("outputs", []))
        if outputs.count("data:image/png;base64,") < 2 or "10158370" not in outputs:
            raise ValueError("Execute both refund word clouds before exporting the notebook.")


def validate_routing_lesson(notebook: dict, *, require_outputs: bool = False) -> None:
    cells = notebook["cells"]
    sources = [source_text(cell) for cell in cells]
    headings = [source.splitlines()[0] for source in sources if source.startswith("## 4.")]
    if headings != STAGE_FOUR_HEADINGS:
        raise ValueError("Keep routing in the three plain-language Section 4 questions.")
    start = next(index for index, source in enumerate(sources) if "# 4 - Validation and Operating Policy" in source)
    end = next(index for index, source in enumerate(sources) if "# 5 - Prediction, Routing Words and Handoff" in source)
    lesson = cells[start:end]
    code = [cell for cell in lesson if cell["cell_type"] == "code"]
    if len(code) != 3 or any("charts." in source_text(cell) for cell in code):
        raise ValueError("Keep Section 4 to three short examples without duplicate diagnostic charts.")
    text = "\n".join(source_text(cell) for cell in lesson)
    required = ("handles every complaint", "Three made-up scores", "called **coverage**",
                "89.7%", "below the 90% target", "not production approval")
    if any(phrase not in text for phrase in required):
        raise ValueError("Retain the human boundary, practice scores, denominators, and test shortfall.")
    if require_outputs:
        if any(not cell.get("outputs") for cell in code):
            raise ValueError("Execute the three simplified Section 4 examples before exporting.")
        final_outputs = json.dumps(code[-1]["outputs"])
        if any(value not in final_outputs for value in ("6,737", "1,991", "6,833", "1,895", "90.2%", "89.7%")):
            raise ValueError("The simplified results must show the verified validation and test counts.")


def validate_lesson(notebook: dict, *, require_outputs: bool = False) -> None:
    cells = notebook["cells"]
    sources = [source_text(cell) for cell in cells]
    headings = [source.splitlines()[0] for source in sources if source.startswith("## 2.")]
    if headings != STAGE_TWO_HEADINGS:
        raise ValueError("Keep preparation in one Section 2.2 with consecutive Stage 2 headings.")
    start = next(index for index, source in enumerate(sources) if source.startswith(PREPARATION_HEADING))
    end = next(index for index, source in enumerate(sources) if source.startswith(STAGE_TWO_HEADINGS[2]))
    lesson = cells[start:end]
    code = [cell for cell in lesson if cell["cell_type"] == "code"]
    if len(lesson) != 3 or len(code) != 1:
        raise ValueError("Keep the preparation lesson to a flow, one count output, and a short explanation.")
    text = "\n".join(source_text(cell) for cell in lesson)
    required = ("before sampling", "before** splitting", "Data leakage", "slightly reworded")
    if any(phrase.lower() not in text.lower() for phrase in required):
        raise ValueError("Explain the denominator, split order, leakage, and near-duplicate limitation.")
    if require_outputs:
        output_text = "".join(source_text({"source": output.get("text", "")}) for output in code[0].get("outputs", []))
        if any(value not in output_text for value in ("2,634,602", "1,093,131", "41.5%", "1,541,471", "58.5%")):
            raise ValueError("Execute the duplicate count cell before exporting.")
        if any(output.get("output_type") == "error" for cell in cells for output in cell.get("outputs", [])):
            raise ValueError("The notebook contains an error output.")
    validate_routing_lesson(notebook, require_outputs=require_outputs)
    validate_word_cloud(notebook, require_outputs=require_outputs)
    validate_walkthroughs(notebook, require_outputs=require_outputs)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "01_complaint_build.ipynb"
    validate_lesson(json.loads(target.read_text(encoding="utf-8")), require_outputs=True)
    print("Verified the preparation flow, routing lesson, word clouds, and visual walkthroughs.")