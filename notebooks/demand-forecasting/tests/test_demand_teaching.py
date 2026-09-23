from __future__ import annotations

import re
import sys
from pathlib import Path

import nbformat
import numpy as np
import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from fclab import teaching  # noqa: E402

NOTEBOOK = PROJECT_DIR / "01_forecast_build.ipynb"
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
    assert len(notebook.cells) <= 35
    assert words < 1_500
    assert source.count(".show()") == 6
    assert "handoff" not in source.lower()
    assert "joblib" not in source.lower()
    assert max(sum(bool(line.strip()) for line in cell.source.splitlines())
               for cell in code) <= 15
    for cell in code:
        compile(cell.source, f"{NOTEBOOK}:{cell.id}", "exec")


def test_regression_refit_preserves_teaching_contract() -> None:
    """Fresh fits may differ across platforms; saved browser fixtures stay exact."""
    lesson = teaching.load_lesson()
    selection = teaching.model_selection_table(lesson.design).set_index("Candidate")
    structure = teaching.training_structure(lesson.design).set_index("Training fact")
    validation = teaching.validation_comparison(lesson.design).set_index("Model")
    model = teaching.fit_final_model(lesson.design)
    predictions = teaching.prediction_frame(lesson.design, model)
    final = teaching.test_comparison(predictions).set_index("Model")
    example = teaching.worked_prediction_example(lesson, model)

    assert lesson.panel.shape == (4_871, 102)
    assert len(lesson.cohort) == 469
    assert len(predictions) == 12_194
    assert list(teaching.feature_dictionary()["Columns"]) == [
        "lag1, lag2, lag3, lag4, lag8", "ma4, ma8", "std4",
        "lag52, woy, woy_sin, woy_cos",
    ]
    assert selection.loc[teaching.MODEL_LABEL, "Selected"]
    assert selection["Validation MAE"].idxmin() == teaching.MODEL_LABEL
    assert selection.loc[teaching.RIDGE_LABEL, "Validation MAE"] == pytest.approx(52.9616, abs=0.01)
    assert selection.loc[teaching.SQUARED_LABEL, "Validation MAE"] > selection.loc[teaching.MODEL_LABEL, "Validation MAE"]
    for name, value in teaching.MODEL_PARAMS.items():
        assert model.get_params()[name] == value
    assert model.n_features_in_ == 12
    assert 0 < model.n_iter_ <= teaching.MODEL_PARAMS["max_iter"]
    assert structure.loc["Models trained", "Value"] == "1 shared regression model"
    assert structure.loc["Model-selection fit", "Value"] == "24,388 rows = 469 products x 52 target weeks"
    assert structure.loc["Validation", "Value"] == "7,504 rows = 469 products x 16 target weeks"
    assert structure.loc["Final refit", "Value"] == "31,892 rows = 469 products x 68 target weeks"
    assert structure.loc["Product identifier feature", "Value"].startswith("No")
    assert validation.loc[teaching.MODEL_LABEL, "MAE"] < validation.loc[teaching.BASELINE_LABEL, "MAE"]
    assert validation.loc[teaching.BASELINE_LABEL, "MAE"] == pytest.approx(51.3663, abs=0.01)
    assert final.loc[teaching.MODEL_LABEL, "MAE"] < final.loc[teaching.BASELINE_LABEL, "MAE"]
    assert final.loc[teaching.BASELINE_LABEL, "MAE"] == pytest.approx(52.3061, abs=0.01)
    assert final.loc[teaching.MODEL_LABEL, "RMSE"] > final.loc[teaching.BASELINE_LABEL, "RMSE"]
    assert final.loc[teaching.BASELINE_LABEL, "RMSE"] == pytest.approx(129.7526, abs=0.02)
    assert np.isfinite(predictions[["actual", "8-week average", "regression"]]).all().all()
    np.testing.assert_allclose(
        predictions["regression"],
        np.maximum(model.predict(lesson.design["x_test"]), 0.0), rtol=0, atol=0)
    assert example.attrs["week"].isoformat() == "2011-11-21"
    selected = predictions.loc[
        (predictions["StockCode"] == "85099B")
        & (predictions["week"].dt.date == example.attrs["week"]), "regression"]
    assert len(selected) == 1
    assert example.loc[example["Quantity"] == teaching.MODEL_LABEL, "Value"].iloc[0] == pytest.approx(selected.iloc[0])
    assert example.loc[example["Quantity"] == "Actual units", "Value"].iloc[0] == 753