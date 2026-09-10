from __future__ import annotations

import sys
import base64
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaintlab import charts, metrics, text_prep


@pytest.mark.parametrize("identifier", [10158370, "10158370"])
def test_word_clouds_use_actual_counts_and_training_weights(identifier):
    narrative = ("my credit card airline flight points statement payment disputed refund XXXX " * 35).strip()
    train = pd.DataFrame([
        {"complaint_id": identifier, "team": "Credit cards", "narrative": narrative},
        {"complaint_id": 2, "team": "Credit cards", "narrative": "credit card airline flight points refund payment statement"},
        {"complaint_id": 3, "team": "Bank accounts", "narrative": "bank balance statement disputed payment"},
    ])
    words = text_prep.word_cloud_weights(train)
    assert words.attrs["complaint_id"] == text_prep.WORD_CLOUD_COMPLAINT_ID
    assert words.attrs["team"] == "Credit cards"
    assert words.attrs["training_complaints"] == 3
    assert len(words) >= 8
    assert not any(token in ENGLISH_STOP_WORDS or set(token) == {"x"}
                   for term in words["term"] for token in term.split())
    vectorizer = text_prep.build_vectorizer()
    matrix = vectorizer.fit_transform(train["narrative"])
    for row in words.to_dict("records"):
        assert row["weight"] == pytest.approx(matrix[0, vectorizer.vocabulary_[row["term"]]])
    assert words.set_index("term").loc["refund", "count"] == 35
    with pytest.raises(ValueError, match="Expected one training complaint"):
        text_prep.word_cloud_weights(train.iloc[1:])
    with pytest.raises(ValueError, match="Expected one training complaint"):
        text_prep.word_cloud_weights(pd.concat([train, train.iloc[:1]]))
    figure = charts.tfidf_word_clouds(train)
    repeat = charts.tfidf_word_clouds(train)
    assert len(figure.data) == 2
    for trace, duplicate in zip(figure.data, repeat.data):
        assert trace.source == duplicate.source
        pixels = np.asarray(Image.open(BytesIO(base64.b64decode(trace.source.split(",", 1)[1]))).convert("RGB"))
        assert pixels.shape == (450, 1000, 3)
        assert (pixels < 220).any(axis=2).mean() > 0.05
    assert figure.data[0].source != figure.data[1].source
    assert figure.layout.meta["terms"] == words.to_dict("records")


def test_coverage_and_recall_count_different_groups():
    sample = charts.coverage_example_data()
    scores = metrics.policy_eval(sample["team"], sample["prediction"], sample["confidence"])
    assert scores["auto_routed"] == 16
    assert scores["triage_rows"] == 4
    assert scores["coverage"] == pytest.approx(0.8)
    recall = metrics.per_team_table(sample["team"], sample["prediction"])
    assert recall.loc[recall["Team"] == "Mortgages", "Recall"].iloc[0] == pytest.approx(0.6)
    all_auto = metrics.policy_eval(sample["team"], sample["prediction"], sample["confidence"], threshold=0)
    assert all_auto["coverage"] == 1.0
    figure = charts.coverage_recall_example()
    assert list(figure.data[0].text).count("A") == 16
    assert list(figure.data[0].text).count("H") == 4
    assert list(figure.data[1].text) == ["M", "M", "M", "C", "C"]
    assert figure.to_json()