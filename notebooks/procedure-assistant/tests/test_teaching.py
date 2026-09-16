import asyncio
import ast
import importlib.util
import json
import sys
from pathlib import Path

import nbformat
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from raglab import teaching


def test_sources_preserve_the_three_verified_citations():
    sources = teaching.load_sources()
    chunks = teaching.prepare_chunks(sources)
    assert chunks["citation"].tolist() == teaching.SOURCE_CITATIONS
    assert len(chunks) == 3
    assert "at least 1 year" in chunks.iloc[0]["text"]


def test_quote_and_citation_must_belong_together():
    prompt = teaching.make_prompt("A question", [{"citation": "Source A", "text": "At least 1 year."}])
    valid = {"answerable": True, "answer": "At least 1 year.", "citation": "Source A", "quote": "1 year"}
    assert teaching.validate_response(json.dumps(valid), prompt) == valid
    for changed in [{**valid, "citation": "Source B"}, {**valid, "quote": "3 years"},
                    {**valid, "answerable": "true"}, {**valid, "answerable": False}]:
        with pytest.raises(ValueError):
            teaching.validate_response(json.dumps(changed), prompt)


def test_unanswered_question_has_no_claimed_evidence():
    result = {"answerable": False, "answer": "Not in these excerpts.", "citation": "", "quote": ""}
    assert teaching.validate_response(json.dumps(result), teaching.make_prompt("Unknown", [])) == result


def test_replay_rejects_changed_question_or_instruction(tmp_path):
    prompt = teaching.make_prompt("Question", [{"citation": "A", "text": "A fact"}])
    response = {"answerable": True, "answer": "A fact", "citation": "A", "quote": "A fact"}
    capture = {"model": teaching.MODEL, "captured_at": "test",
               "system_sha256": teaching.fingerprint(teaching.SYSTEM_PROMPT),
               "sources_sha256": teaching.fingerprint(teaching.load_sources().to_json(orient="records")),
               "records": [{"prompt": prompt, "prompt_sha256": teaching.fingerprint(prompt),
                            "response": response, "raw_response": json.dumps(response)}]}
    output = tmp_path / "capture.json"
    output.write_text(json.dumps(capture))
    assert asyncio.run(teaching.answer(prompt, capture_path=output))["response"] == response
    with pytest.raises(ValueError):
        asyncio.run(teaching.answer(prompt + " ", capture_path=output))
    capture["system_sha256"] = "changed"
    output.write_text(json.dumps(capture))
    with pytest.raises(ValueError):
        asyncio.run(teaching.answer(prompt, capture_path=output))


@pytest.mark.parametrize("folder,filename", [
    ("predictive-maintenance", "01_pdm_build.ipynb"),
    ("procedure-assistant", "01_procedure_build.ipynb"),
])
def test_classroom_build_is_valid_short_and_preserves_outputs(tmp_path, folder, filename):
    lab = Path(__file__).resolve().parents[2] / folder
    spec = importlib.util.spec_from_file_location("classroom_builder", lab / "scripts" / "build_notebook.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    executed = nbformat.read(lab / filename, as_version=4)
    assert builder.build().cells == executed.cells
    builder.OUTPUT = tmp_path / filename
    fresh = builder.build()
    assert [(cell.cell_type, cell.source) for cell in fresh.cells] == [
        (cell.cell_type, cell.source) for cell in executed.cells]
    assert len(fresh.cells) <= (70 if folder == "predictive-maintenance" else 35)
    assert len({cell.metadata.id for cell in fresh.cells}) == len(fresh.cells)
    for cell in fresh.cells:
        assert cell.metadata.language == ("markdown" if cell.cell_type == "markdown" else "python")
        if cell.cell_type == "code":
            compile(cell.source, "cell", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    word_limit = 4500 if folder == "predictive-maintenance" else 2000
    assert sum(len(cell.source.split()) for cell in fresh.cells if cell.cell_type == "markdown") < word_limit
    for cell in executed.cells:
        if cell.cell_type == "code":
            assert cell.execution_count is not None
            assert not any(output.output_type == "error" for output in cell.outputs)
    code_source = "\n".join(cell.source for cell in fresh.cells if cell.cell_type == "code")
    assert "handoff.export" not in code_source
    if folder == "predictive-maintenance":
        assert code_source.count(".show()") == 7
        assert max(len(cell.source.splitlines()) for cell in fresh.cells if cell.cell_type == "code") <= 15
        narrative = "\n".join(cell.source for cell in fresh.cells if cell.cell_type == "markdown")
        headings = [line for line in narrative.splitlines() if line.startswith("# ")][1:]
        assert headings == ["# 1 - Data Ingestion", "# 2 - EDA and Feature Engineering",
                            "# 3 - Model Training", "# 4 - Model Validation", "# 5 - Model Prediction"]
        assert "Anomaly does not mean confirmed failure" in narrative
        assert "agreement with reports, not diagnostic accuracy" in narrative
        assert "existing app still uses its earlier" in narrative
        assert "forest.fit(training)" in code_source
        assert "contamination=\"auto\"" in code_source
        assert "forest.predict(" not in code_source
        assert "teaching.score_cutoff_plot" in code_source
        assert "teaching.score_distribution" not in code_source
        assert "score < cutoff" in narrative and "score >= cutoff" in narrative
        final_cutoff = 'cutoff = float(comparison.loc'
        assert code_source.index("teaching.compare_models") < code_source.index(final_cutoff)
        assert code_source.index(final_cutoff) < code_source.index("teaching.score_cutoff_plot")
        assert code_source.index("teaching.score_cutoff_plot") < code_source.index("test_scores =")
        assert code_source.index("test_result =") < code_source.index("later_scores =")
        assert code_source.index("test_result =") < code_source.index("teaching.prediction_timeline")
        assert "not a standard-deviation threshold" in narrative
        assert "## 4.4 Does the alert help a person?" in narrative
        assert "## 4.2 Check the final rule on later data" in narrative
        assert "Score the test period only after those choices are fixed" not in narrative
        assert "## 4.5" not in narrative and "## 4.6" not in narrative
        assert "teaching.alert_map(" not in code_source
        assert "teaching.event_timeline(" not in code_source
        assert "teaching.drift_plot(" not in code_source
        assert "working minutes / recorded minutes x 100" in narrative
        assert "30 working minutes out of 60 = 50%" in narrative
        assert '"Compressor working (%)"' in code_source
        assert "Choosing which source columns to transform is part of **feature engineering**" in narrative
        assert "teaching.compare_feature_sets" not in code_source
        assert "teaching.feature_comparison" in code_source
        assert "teaching.feature_context" not in code_source
        assert "What looked different in this flagged hour?" in narrative
        assert "IQR units" not in narrative
        assert "assert usable_incomplete.empty" in code_source
        assert "np.testing.assert_allclose" in code_source
    else:
        assert "LIVE_GENERATION = False" in code_source
        assert "await teaching.answer" in code_source
        assert "answers.build_pack" not in code_source


def test_recorded_llm_responses_replay_and_are_not_written_answer_pack():
    capture = json.loads(teaching.CAPTURE.read_text())
    assert len(capture["records"]) == len(teaching.CASES) == 5
    for case, record in zip(teaching.CASES, capture["records"]):
        prompt = json.loads(record["prompt"])
        assert prompt["question"] == case["question"]
        assert set(prompt) == {"question", "passages"}
        assert record["usage"]["reported_model"]
        replay = asyncio.run(teaching.answer(record["prompt"]))
        response = replay["response"]
        if case["citation"]:
            assert response["answerable"] and response["citation"] == case["citation"]
            assert any(term in response["answer"].lower() for term in case["terms"])
        else:
            assert not response["answerable"]