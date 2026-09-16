from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaintlab import config, data, explain, presentation


def test_excerpt_keeps_exact_text_and_escapes_untrusted_markup():
    narrative = '<script>alert("not an instruction")</script> & a refund\nSecond line.'
    row = pd.Series({"complaint_id": '42"', "date_received": "2023-01-01", "narrative": narrative})
    output = presentation.complaint_excerpt(row, 1, "A < B", limit=30)
    document = BeautifulSoup(output.data, "html.parser")
    assert document.select_one(".complaint-text").get_text() == narrative[:30]
    assert document.select_one("details blockquote").get_text() == narrative
    assert document.select_one("h3").get_text() == "A < B"
    assert document.select_one("section")["data-complaint-id"] == '42"'
    assert not document.select("script, img, iframe, link")
    assert "Excerpt: first 30" in document.get_text()


def test_short_excerpt_does_not_need_an_expander():
    row = pd.Series({"complaint_id": "7", "date_received": "2023-01-01", "narrative": "Please return my money."})
    document = BeautifulSoup(presentation.complaint_excerpt(row, 2, "Needs human routing").data, "html.parser")
    assert document.select_one(".complaint-text").get_text() == row["narrative"]
    assert not document.select("details")


@pytest.fixture(scope="module")
def real_examples():
    root = Path(__file__).resolve().parents[1]
    pipeline = joblib.load(root / "artifacts/model.joblib")
    test = data.load_splits()["test"]
    identifiers = [config.WALKTHROUGH_IDS[0], config.WALKTHROUGH_IDS[1], config.MISROUTE_EXAMPLE_ID]
    return pipeline, [test.loc[test["complaint_id"] == identifier].iloc[0] for identifier in identifiers]


def test_visual_decisions_preserve_all_three_predictions_and_facts(real_examples):
    pipeline, examples = real_examples
    routes = []
    for row in examples:
        facts = explain.route_card(pipeline, row).set_index("Field")["Value"]
        probabilities = explain.team_probabilities(pipeline, row[config.TEXT_COLUMN])
        document = BeautifulSoup(presentation.routing_decision(pipeline, row).data, "html.parser")
        decision = document.select_one(".decision")
        routes.append(decision["data-route"])
        assert decision["data-route"] == facts["Route"]
        assert float(decision["data-confidence"]) == probabilities.iloc[0]["Probability"]
        assert float(decision["data-threshold"]) == 0.55
        assert document.select_one(".team-name").get_text() == facts["Model's team"]
        assert document.select_one(".result strong").get_text() == row[config.TARGET]
        assert facts["What happens next"] in document.get_text()
        for field in ("Complaint ID", "Received", "CFPB issue field (not shown to the model)", "Characters in the narrative"):
            assert str(facts[field]) in document.get_text()
        assert bool(document.select(".result.mismatch")) == (facts["Model's team"] != row[config.TARGET])
    assert routes == ["auto_route", "human_triage", "auto_route"]


def test_probability_bars_preserve_all_eight_exact_values(real_examples):
    pipeline, examples = real_examples
    for row in examples:
        expected = explain.team_probabilities(pipeline, row[config.TEXT_COLUMN])
        document = BeautifulSoup(presentation.probability_bars(pipeline, row[config.TEXT_COLUMN]).data, "html.parser")
        bars = document.select(".bar-row")
        assert [bar["data-team"] for bar in bars] == expected["Team"].tolist()
        np.testing.assert_array_equal([float(bar["data-probability"]) for bar in bars], expected["Probability"])
        assert len(bars) == 8
        assert sum(float(bar["data-probability"]) for bar in bars) == pytest.approx(1)


def test_word_bars_preserve_terms_and_contributions(real_examples):
    pipeline, examples = real_examples
    for row in examples:
        team = explain.team_probabilities(pipeline, row[config.TEXT_COLUMN]).iloc[0]["Team"]
        expected = explain.routing_words(pipeline, row[config.TEXT_COLUMN], team)
        document = BeautifulSoup(presentation.routing_word_bars(pipeline, row[config.TEXT_COLUMN], team).data, "html.parser")
        bars = document.select(".bar-row")
        assert [bar["data-word"] for bar in bars] == expected["Word or phrase"].tolist()
        np.testing.assert_array_equal([float(bar["data-push"]) for bar in bars], expected["Push toward this team"])
        assert "not percentages" in document.get_text()


def test_source_details_cannot_inject_html(real_examples):
    pipeline, examples = real_examples
    row = examples[0].copy()
    row["issue"] = '<img src="https://invalid.test/tracker" onerror="alert(1)">'
    document = BeautifulSoup(presentation.routing_decision(pipeline, row).data, "html.parser")
    assert row["issue"] in document.get_text()
    assert not document.select("script, img, iframe, link")


def test_export_hides_only_walkthrough_code_and_preserves_contents():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("complaint_html_export", root / "scripts/make_backup.py")
    assert spec is not None and spec.loader is not None
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    document = BeautifulSoup(
        '<html><head></head><body><div class="jp-CodeCell"><div class="jp-InputArea">example()</div>'
        '<section class="complaint-view">Visible example</section></div>'
        '<div class="jp-CodeCell"><div class="jp-InputArea">other_code()</div></div></body></html>',
        "html.parser",
    )
    assert exporter.collapse_walkthrough_code(document) == 1
    disclosure = document.select_one("details.walkthrough-code")
    assert not disclosure.has_attr("open")
    assert disclosure.select_one("summary").get_text() == "Python code"
    assert disclosure.select_one(".jp-InputArea").get_text() == "example()"
    assert document.select_one(".complaint-view").find_parent("details") is None
    assert document.select(".jp-InputArea")[1].find_parent("details") is None
    assert exporter.collapse_walkthrough_code(document) == 0