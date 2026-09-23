from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path

import nbformat
import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from reclab import teaching  # noqa: E402

NOTEBOOK = PROJECT_DIR / "01_recommendation_build.ipynb"
STAGES = [
    "# 1 - Data Ingestion",
    "# 2 - Feature Engineering",
    "# 3 - Model Training",
    "# 4 - Model Validation",
    "# 5 - Model Prediction",
]


def test_classroom_notebook_contract() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    markdown = [cell for cell in notebook.cells if cell.cell_type == "markdown"]
    headings = [line for cell in markdown for line in cell.source.splitlines()
                if line in STAGES]
    source = "\n".join(cell.source for cell in code)
    words = sum(len(re.findall(r"\b[\w'-]+\b", cell.source)) for cell in markdown)

    assert headings == STAGES
    assert len(notebook.cells) <= 38
    assert words < 2_000
    assert source.count(".show()") == 7
    assert 'source_product = "85099B"' in source
    assert "buyer_overlap_figure" in source
    assert "neighbor_retention_figure" in source
    assert "similarity to the named product" not in "\n".join(cell.source for cell in markdown)
    assert "handoff" not in source.lower()
    assert "joblib" not in source.lower()
    assert max(sum(bool(line.strip()) for line in cell.source.splitlines())
               for cell in code) <= 15
    for cell in code:
        compile(cell.source, f"{NOTEBOOK}:{cell.id}", "exec")


def test_generator_preserves_saved_cells(tmp_path: Path) -> None:
    namespace = runpy.run_path(str(PROJECT_DIR / "scripts/build_notebook.py"))
    generated = namespace["build_notebook"]()
    nbformat.validate(generated)
    assert len(generated.cells) == 37
    assert len({cell.id for cell in generated.cells}) == 37
    original_ids = [f"recommendation-classroom-{index:03d}" for index in range(1, 31)]
    assert all(cell_id in {cell.id for cell in generated.cells} for cell_id in original_ids)
    for cell in generated.cells:
        assert cell.metadata.id == cell.id
        assert cell.metadata.language == ("python" if cell.cell_type == "code" else "markdown")
        if cell.cell_type == "code":
            compile(cell.source, "generated classroom cell", "exec")
    saved = nbformat.read(NOTEBOOK, as_version=4)
    destination = tmp_path / NOTEBOOK.name
    nbformat.write(saved, destination)
    namespace["main"].__globals__["OUTPUT"] = destination
    namespace["main"]()
    updated = nbformat.read(destination, as_version=4)
    expected = {cell.id: cell for cell in generated.cells}
    retained = {cell.id: cell for cell in updated.cells}
    for cell in saved.cells:
        if cell.id in expected and cell.source == expected[cell.id].source:
            assert retained[cell.id] == cell
    first_bytes = destination.read_bytes()
    namespace["main"]()
    assert destination.read_bytes() == first_bytes


def test_next_best_product_result_and_fallback() -> None:
    lesson = teaching.load_lesson()
    fitted = teaching.fit_models(lesson.split)
    selection = teaching.model_selection_table(lesson.split, fitted).set_index("Model")
    result = teaching.comparison_table(lesson.split, fitted).set_index("Model")
    example = teaching.example_recommendations(lesson, fitted[teaching.MODEL_LABEL])
    neighbors = teaching.similar_product_table(lesson, fitted[teaching.MODEL_LABEL])
    explanations = teaching.recommendation_explanations(
        lesson, fitted[teaching.MODEL_LABEL], example)
    cold = teaching.cold_start_summary(lesson)

    assert lesson.split.R.shape == (4_962, 4_443)
    assert result.loc[teaching.BASELINE_LABEL, "HR@10"] == pytest.approx(0.2947, abs=0.0001)
    assert result.loc[teaching.MODEL_LABEL, "HR@10"] == pytest.approx(0.4156, abs=0.0001)
    assert result.loc[teaching.BASELINE_LABEL, "Coverage"] == pytest.approx(0.0180, abs=0.0001)
    assert result.loc[teaching.MODEL_LABEL, "Coverage"] == pytest.approx(0.2577, abs=0.0001)
    assert selection.loc[teaching.FULL_MODEL_LABEL, "HR@10"] == pytest.approx(0.3644, abs=0.0001)
    assert selection.loc[teaching.MODEL_LABEL, "Selected"]
    assert len(example) == 10
    assert bool(example["Bought later"].any())
    assert neighbors.iloc[0]["Similar product"] == "JUMBO BAG PINK POLKADOT"
    assert neighbors.iloc[0]["Cosine similarity"] == pytest.approx(0.611196, abs=0.000001)
    figure = teaching.similar_products_figure(lesson, fitted[teaching.MODEL_LABEL])
    assert "85099B" in figure.layout.title.text
    assert "JUMBO BAG RED RETROSPOT" in figure.layout.title.text.replace("<br>", " ")
    assert "0.611" in figure.data[0].text
    assert "0.606" in figure.data[0].text
    assert all(len(line) <= 14 for label in figure.data[0].y for line in label.split("<br>"))
    assert figure.layout.xaxis.range[1] > max(figure.data[0].x) * 1.2
    pair = teaching.product_pair_summary(lesson).iloc[0]
    source = lesson.split.item_index["85099B"]
    other = lesson.split.item_index["22386"]
    assert pair["Source product"] == "JUMBO BAG RED RETROSPOT"
    assert pair["Other product"] == "JUMBO BAG PINK POLKADOT"
    assert pair["Cosine similarity"] == pytest.approx(
        fitted[teaching.FULL_MODEL_LABEL].payload[source, other], abs=0.000001)
    assert pair["Cosine similarity"] == pytest.approx(0.611196, abs=0.000001)
    overlap = teaching.buyer_overlap_figure(lesson)
    groups = list(overlap.data[0].y)
    assert groups[0] + groups[1] == pair["Source buyers"]
    assert groups[1] + groups[2] == pair["Other buyers"]
    assert groups[1] == pair["Shared buyers"]
    retained = teaching.neighbor_retention_figure(
        lesson, fitted[teaching.FULL_MODEL_LABEL], fitted[teaching.MODEL_LABEL])
    assert len(retained.data[0].x) == 15
    assert len(retained.data[1].x) == 5
    assert all(rank <= 15 for rank in retained.data[0].x)
    assert all(rank > 15 for rank in retained.data[1].x)
    assert all(str(code) != "85099B" for trace in retained.data for code, _ in trace.customdata)
    for trace in retained.data:
        for details, value in zip(trace.customdata, trace.y):
            target = lesson.split.item_index[str(details[0])]
            assert value == fitted[teaching.FULL_MODEL_LABEL].payload[source, target]
            assert bool(fitted[teaching.MODEL_LABEL].payload[source, target]) == (
                trace.name == "Saved link")
    assert explanations.iloc[3]["Recommended product"] == "DOORMAT FAIRY CAKE"
    assert bool(explanations.iloc[3]["Bought later"])
    assert int(cold.loc[cold["Population"].str.startswith("No usable"), "Count"].iloc[0]) == 648