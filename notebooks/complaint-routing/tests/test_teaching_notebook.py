from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
spec = importlib.util.spec_from_file_location("complaint_teaching_validator", PROJECT / "scripts/validate_teaching_notebook.py")
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def generated_cells() -> list[dict]:
    tree = ast.parse((PROJECT / "scripts/build_notebook.py").read_text())
    return [
        {"cell_type": "markdown" if node.value.func.id == "md" else "code",
         "source": node.value.args[0].value.strip("\n")}
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id in {"md", "code"}
    ]


def test_preparation_is_one_short_section():
    cells = generated_cells()
    validator.validate_lesson({"cells": cells})
    sources = "\n".join(cell["source"] for cell in cells)
    for call in ("data.duplicate_example_table()", "data.dedupe_summary()",
                 "charts.duplicate_share_by_team()", "data.leakage_cost()",
                 "data.label_consolidation_table(splits)"):
        assert call not in sources


def test_generated_code_cells_compile():
    for index, cell in enumerate(generated_cells()):
        if cell["cell_type"] == "code":
            compile(cell["source"], f"notebook-cell-{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


def test_worked_example_sorts_by_complaint_count_without_changing_weights():
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from complaintlab import text_prep

    frame = text_prep.worked_example()
    count_column = "In how many of the 3 complaints"
    term_column = "Word or 2-word phrase"
    assert frame[count_column].is_monotonic_decreasing
    assert frame[term_column].head(3).tolist() == ["my", "credit", "my credit"]
    assert frame[count_column].head(3).tolist() == [3, 2, 2]
    for _, group in frame.groupby(count_column):
        assert group[term_column].tolist() == sorted(group[term_column])
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(text_prep.WORKED_EXAMPLE_CORPUS)
    values = matrix[0].toarray()[0]
    present = np.flatnonzero(values)
    assert len(frame) == len(present)
    indexed = frame.set_index(term_column).loc[vectorizer.get_feature_names_out()[present]]
    np.testing.assert_array_equal(indexed[count_column], (matrix > 0).sum(axis=0).A1[present])
    np.testing.assert_array_equal(indexed["TF-IDF weight in complaint 1"], values[present].round(3))


def test_sparse_row_demonstration_is_omitted():
    sources = "\n".join(cell["source"] for cell in generated_cells())
    assert "text_prep.worked_example_shape()" not in sources
    assert "HOW WIDE THAT ROW GETS" not in sources
    assert "The row is mostly zeros" not in sources
    assert "text_prep.worked_example()" in sources


def test_word_cloud_cannot_disappear_during_simplification():
    cells = generated_cells()
    validator.validate_word_cloud({"cells": cells})
    without_cloud = [cell for cell in cells if "charts.tfidf_word_clouds(train)" not in cell["source"]]
    with pytest.raises(ValueError, match="Keep the approved word clouds"):
        validator.validate_word_cloud({"cells": without_cloud})
    with pytest.raises(ValueError, match="Execute both refund word clouds"):
        validator.validate_word_cloud({"cells": cells}, require_outputs=True)


def test_real_word_cloud_uses_the_approved_refund_complaint():
    from complaintlab import data, text_prep

    words = text_prep.word_cloud_weights(data.load_splits()["train"])
    assert words.attrs["complaint_id"] == 10158370
    assert words.attrs["team"] == "Credit cards"
    assert words.attrs["training_complaints"] == 40_729
    assert len(words) == 50
    assert "refund" in words.attrs["narrative"].lower()
    assert words.set_index("term").loc["refund", "count"] == 7
    assert words.set_index("term").loc["card", "count"] == 4
    assert "freedom" not in set(words["term"])
    assert words.sort_values("weight", ascending=False).iloc[0]["term"] == "airline"


def test_saved_worked_example_uses_count_order():
    from bs4 import BeautifulSoup
    from complaintlab import text_prep

    notebook = json.loads((PROJECT / "01_complaint_build.ipynb").read_text())
    cell = next(cell for cell in notebook["cells"] if "text_prep.worked_example()" in validator.source_text(cell))
    html = "".join(validator.source_text({"source": output.get("data", {}).get("text/html", "")})
                   for output in cell.get("outputs", []))
    table = BeautifulSoup(html, "html.parser").find("table")
    assert table is not None
    actual = [[column.get_text(strip=True) for column in row.find_all("td")]
              for row in table.select("tbody tr")]
    expected = text_prep.worked_example()
    assert [row[0] for row in actual] == expected["Word or 2-word phrase"].tolist()
    assert [int(row[1]) for row in actual] == expected["In how many of the 3 complaints"].tolist()
    assert [float(row[2]) for row in actual] == expected["TF-IDF weight in complaint 1"].tolist()


def test_generator_preserves_outputs_when_cells_move(tmp_path):
    import nbformat

    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    script = script_dir / "build_notebook.py"
    shutil.copy2(PROJECT / "scripts/build_notebook.py", script)
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
    target = tmp_path / "01_complaint_build.ipynb"
    notebook = nbformat.read(target, as_version=4)
    preserved = next(cell for cell in notebook.cells if cell.cell_type == "code")
    preserved.outputs = [nbformat.v4.new_output("stream", name="stdout", text="saved output")]
    original = deepcopy(preserved)
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell("An obsolete temporary section"))
    nbformat.write(notebook, target)
    result = subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
    rebuilt = nbformat.read(target, as_version=4)
    assert result.stdout.count("Wrote") == 1
    assert len(rebuilt.cells) == len(generated_cells())
    assert len({cell.id for cell in rebuilt.cells}) == len(rebuilt.cells)
    assert all(cell.metadata["id"] == cell.id for cell in rebuilt.cells)
    assert next(cell for cell in rebuilt.cells if cell.id == original.id) == original
    saved_bytes = target.read_bytes()
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
    assert target.read_bytes() == saved_bytes


def test_duplicate_percentage_uses_mapped_window(capsys):
    from complaintlab import config

    assert config.DEDUPE_ROWS_REMOVED + config.DEDUPE_DISTINCT_NARRATIVES == config.DEDUPE_ROWS_IN_WINDOW
    assert config.DEDUPE_ROWS_IN_WINDOW + sum(config.DROPPED_PRODUCTS.values()) == config.SOURCE_NARRATIVE_ROWS_IN_WINDOW
    source = next(cell["source"] for cell in generated_cells() if "# 2.2 EXACT REPEATS" in cell["source"])
    exec(compile(source, "duplicate-summary", "exec"), {"config": config})
    output = capsys.readouterr().out
    for expected in ("2,634,602", "1,093,131 (41.5%)", "1,541,471 (58.5%)"):
        assert expected in output


def test_committed_splits_have_no_exact_repeated_text():
    import pandas as pd
    from complaintlab import config, data

    combined = pd.concat(data.load_splits().values(), ignore_index=True)
    assert len(combined) == 58_185
    assert not combined[config.TEXT_COLUMN].duplicated().any()
    assert combined[config.TARGET].nunique() == 8


def test_old_sections_and_unexecuted_summary_are_rejected():
    cells = generated_cells()
    with pytest.raises(ValueError, match="Execute the duplicate count"):
        validator.validate_lesson({"cells": cells}, require_outputs=True)
    outdated = deepcopy(cells)
    heading = next(cell for cell in outdated if cell["source"].startswith(validator.PREPARATION_HEADING))
    heading["source"] = "## 2.2 The discovery that changed how this dataset was built"
    with pytest.raises(ValueError, match="one Section 2.2"):
        validator.validate_lesson({"cells": outdated})


@pytest.fixture(scope="module")
def routing_example_state():
    import joblib
    import numpy as np
    import pandas as pd
    from complaintlab import config, data, metrics

    splits = data.load_splits()
    pipeline = joblib.load(PROJECT / "artifacts/model.joblib")
    probabilities = pipeline.predict_proba(splits["validation"][config.TEXT_COLUMN])
    classes = pipeline.named_steps["lr"].classes_
    state = {
        "np": np, "pd": pd, "config": config, "metrics": metrics,
        "y_val": splits["validation"][config.TARGET],
        "X_test": splits["test"][config.TEXT_COLUMN],
        "y_test": splits["test"][config.TARGET],
        "tfidf": SimpleNamespace(estimator=pipeline,
                                 val_predictions=classes[np.argmax(probabilities, axis=1)],
                                 val_confidence=probabilities.max(axis=1)),
    }
    for banner in ("# 4.1 ONE SIMPLE", "# 4.2 THREE PRACTICE", "# 4.3 THE FROZEN RULE"):
        source = next(cell["source"] for cell in generated_cells() if banner in cell["source"])
        exec(compile(source, banner, "exec"), state)
    return state


def test_routing_lesson_preserves_results(routing_example_state):
    state = routing_example_state
    stored = json.loads((PROJECT / "artifacts/evaluation.json").read_text())
    for evidence_key, result in (("chosen_policy_validation", state["val_policy"]),
                                 ("test_frozen", state["test_policy"])):
        for key, value in result.items():
            assert (round(value, 4) if isinstance(value, float) else value) == stored[evidence_key][key]
    for key, value in state["test_scores"].items():
        assert round(value, 4) == stored["test_frozen"][key]
    loans = state["val_per_team"].set_index("Team").loc["Loans"]
    assert loans["Complaints in the split"] == 505
    assert loans["Recall"] == pytest.approx(325 / 505)
    summary = state["routing_summary"]
    assert summary.loc["Team chosen automatically", "Validation"] == "6,737 (77.2%)"
    assert summary.loc["Clerk chooses the team", "Test"] == "1,895 (21.7%)"
    assert summary.loc["Right team among automatic routes", "Test"] == "89.7%"


def test_practice_scores_use_the_real_boundary(routing_example_state):
    state = routing_example_state
    assert state["config"].CONFIDENCE_THRESHOLD == 0.55
    assert state["practice_confidence"].tolist() == [0.90, 0.55, 0.40]
    assert state["metrics"].routes(state["practice_confidence"]).tolist() == ["auto_route", "auto_route", "human_triage"]
    assert state["metrics"].routes([0.549999, 0.55]).tolist() == ["human_triage", "auto_route"]
    sweep = state["metrics"].threshold_sweep(state["y_val"], state["tfidf"].val_predictions, state["tfidf"].val_confidence)
    assert sweep.loc[sweep["accuracy_among_auto_routed"] >= 0.90, "threshold"].min() == 0.55
    assert state["val_policy"]["accuracy_among_auto_routed"] >= 0.90
    assert state["test_policy"]["accuracy_among_auto_routed"] < 0.90


def test_routing_guard_rejects_old_layout_and_missing_outputs():
    cells = generated_cells()
    validator.validate_routing_lesson({"cells": cells})
    with pytest.raises(ValueError, match="Execute the three simplified"):
        validator.validate_routing_lesson({"cells": cells}, require_outputs=True)
    changed = deepcopy(cells)
    heading = next(cell for cell in changed if cell["source"].startswith(validator.STAGE_FOUR_HEADINGS[0]))
    heading["source"] = "## 4.1 Reading the model team by team"
    with pytest.raises(ValueError, match="three plain-language"):
        validator.validate_routing_lesson({"cells": changed})


def test_saved_notebook_matches_generator():
    notebook = json.loads((PROJECT / "01_complaint_build.ipynb").read_text())
    validator.validate_lesson(notebook, require_outputs=True)
    saved = [(cell["cell_type"], validator.source_text(cell)) for cell in notebook["cells"]]
    assert saved == [(cell["cell_type"], cell["source"]) for cell in generated_cells()]