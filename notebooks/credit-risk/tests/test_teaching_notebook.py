from __future__ import annotations

import ast
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT))

from validate_teaching_notebook import SECTION_FOUR_HEADINGS, validate_lesson


def generated_cells() -> list[dict]:
    tree = ast.parse((PROJECT / "scripts/build_notebook.py").read_text())
    return [
        {"cell_type": "markdown" if node.value.func.id == "md" else "code",
         "source": node.value.args[0].value.strip("\n")}
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id in {"md", "code"}
    ]


def test_generator_keeps_approved_lesson_and_recent_simplifications():
    cells = generated_cells()
    validate_lesson({"cells": cells})
    assert any('leaderboard.drop(columns=["Validation PR-AUC"])' in cell["source"] for cell in cells)
    assert any("20% across and 60% up" in cell["source"] for cell in cells)
    assert not any("**Term - PR-AUC" in cell["source"] for cell in cells)


def test_every_generated_code_cell_compiles():
    for index, cell in enumerate(generated_cells()):
        if cell["cell_type"] == "code":
            compile(cell["source"], f"notebook-cell-{index}", "exec")


def test_three_real_account_examples_keep_scores_and_cutoff(capsys):
    import joblib
    import numpy as np
    import pandas as pd
    from creditlab import config, data, explain, features, metrics

    pipeline = joblib.load(PROJECT / "artifacts/model.joblib")
    test_frame = data.split_accounts(pd.read_parquet(PROJECT / "data/accounts.parquet"))["test"]
    probabilities = pipeline.predict_proba(test_frame)[:, 1]
    exposure = metrics.exposure(test_frame)
    flags = metrics.policy_flags(probabilities, exposure, config.REVIEW_COST_NT)
    namespace = {
        "np": np, "pd": pd, "config": config, "explain": explain, "features": features,
        "pipeline": pipeline, "test_df": test_frame, "p_test": probabilities,
        "expo_test": exposure, "test_flags": flags, "review_cutoff": config.REVIEW_COST_NT,
    }
    cells = generated_cells()
    for banner in ("# 5.1 SELECT THREE", "# 5.2 WALK EACH ACCOUNT"):
        source = next(cell["source"] for cell in cells if banner in cell["source"])
        exec(compile(source, banner, "exec"), namespace)
    positions = list(namespace["picks"].values())
    assert int(flags.sum()) == 761
    assert test_frame.iloc[positions]["ID"].tolist() == [20993, 2403, 386]
    losses = probabilities[positions] * exposure[positions] * config.LOSS_GIVEN_DEFAULT
    assert np.rint(losses).astype(int).tolist() == [126031, 14443, 10695]
    assert test_frame.iloc[positions][config.TARGET].tolist() == [1, 0, 0]
    output = capsys.readouterr().out
    assert output.count("classroom cutoff? Yes -> analyst queue") == 3
    assert output.count("1. Chance of missing payment:") == 3
    assert output.count("2. Loss if default happens:") == 3
    assert output.count("3. Estimated loss:") == 3
    assert "review cost" not in output.lower()
    assert "borderline" not in output.lower()


def test_old_heading_is_rejected():
    cells = generated_cells()
    cell = next(cell for cell in cells if cell["source"].startswith(SECTION_FOUR_HEADINGS[0]))
    cell["source"] = "## 4.1 Do the probabilities mean what they say?"
    with pytest.raises(ValueError, match="approved plain-language"):
        validate_lesson({"cells": cells})


def test_classroom_cutoff_is_not_a_review_price(capsys):
    cells = generated_cells()
    prose = next(cell["source"] for cell in cells if cell["source"].startswith(SECTION_FOUR_HEADINGS[2]))
    assert "The cutoff is not the price of a review" in prose
    assert "how much loss the resulting action can prevent" in prose
    source = next(cell["source"] for cell in cells if "# 4.3 APPLY THE CLASSROOM RULE" in cell["source"])
    namespace = {
        "config": SimpleNamespace(REVIEW_COST_NT=10_000),
        "example_probability": 0.30,
        "example_loss_if_default": 50_000,
    }
    exec(compile(source, "classroom-cutoff", "exec"), namespace)
    assert namespace["example_expected_loss"] == 15_000
    assert namespace["example_needs_review"] is True
    output = capsys.readouterr().out
    assert "Classroom cutoff: NT$10,000" in output
    assert "review cost" not in output.lower()
    namespace["config"].REVIEW_COST_NT = 20_000
    exec(compile(source, "classroom-cutoff", "exec"), namespace)
    assert namespace["example_needs_review"] is False


def test_review_price_framing_is_rejected():
    cells = generated_cells()
    cell = next(cell for cell in cells if cell["source"].startswith(SECTION_FOUR_HEADINGS[2]))
    cell["source"] = cell["source"].replace(
        "The cutoff is not the price of a review", "One review costs NT$10,000")
    with pytest.raises(ValueError, match="not a review price"):
        validate_lesson({"cells": cells})


def test_old_chart_and_missing_outputs_are_rejected():
    cells = generated_cells()
    with pytest.raises(ValueError, match="Run the four"):
        validate_lesson({"cells": cells}, require_outputs=True)
    changed = deepcopy(cells)
    cell = next(cell for cell in changed if "# 4.1 A MADE-UP" in cell["source"])
    cell["source"] += "\ncharts.reliability_curve(calibration_table).show()"
    with pytest.raises(ValueError, match="diagnostic charts"):
        validate_lesson({"cells": changed})


def test_saved_notebook_matches_generator():
    notebook = json.loads((PROJECT / "01_credit_build.ipynb").read_text())
    validate_lesson(notebook, require_outputs=True)
    cells = generated_cells()
    saved = [(cell["cell_type"], "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]) for cell in notebook["cells"]]
    assert saved == [(cell["cell_type"], cell["source"]) for cell in cells]